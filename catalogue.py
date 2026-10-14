"""
catalogue.py
============
Catalogue de matériaux enregistrés, stocké dans le fichier texte `materiaux.json` (versionné dans Git).

Module autonome (bibliothèque standard + `acv_inies_a2.py`). Il sert à :
  - LIRE le catalogue avec des contrôles clairs (messages en français) ;
  - FABRIQUER le bloc JSON d'un nouveau matériau, à coller dans `materiaux.json`.

Format du fichier (« format » : 1) :
    {
      "format": 1,
      "materiaux": [
        {
          "id": 33806,                          identifiant INIES (facultatif)
          "nom": "…",
          "lien_inies": "https://…",            adresse de la fiche (facultatif)
          "dvr": 100,                           durée de vie de référence, en années
          "date_export": "2026-10-14",          date de l'export des valeurs depuis INIES (AAAA-MM-JJ)
          "valeurs": { "production": 19.1, … }, les 13 valeurs, au format décimal standard
          "acv_dynamique_attendu": 36.722       résultat contrôlé (facultatif, 3 décimales)
        }
      ]
    }
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import List, Optional

import acv_inies_a2 as acv

# =============================================================================
# PARAMÈTRES
# =============================================================================
FORMAT_CATALOGUE = 1                                        # numéro de format géré par ce module
FICHIER_PAR_DEFAUT = Path(__file__).with_name("materiaux.json")
TOLERANCE_ACV_ATTENDUE = 0.0005                             # écart toléré (3 décimales)
NOMS_VALEURS = tuple(acv.ValeursA2.__dataclass_fields__)    # les 13 noms de champs, dans l'ordre INIES


class ErreurCatalogue(ValueError):
    """Problème dans materiaux.json, avec un message en français."""


@dataclass(frozen=True)
class MateriauEnregistre:
    """Une ligne du catalogue."""
    id: Optional[int]
    nom: str
    lien_inies: Optional[str]
    dvr: int
    date_export: str                       # AAAA-MM-JJ
    valeurs: acv.ValeursA2
    acv_dynamique_attendu: Optional[float]

    def etiquette(self) -> str:
        """Texte affiché dans la liste déroulante."""
        jour = date.fromisoformat(self.date_export).strftime("%d/%m/%Y")
        repere = f"INIES {self.id}, " if self.id else ""
        return f"{self.nom} ({repere}export du {jour})"

    def texte_inies(self) -> str:
        """Les 13 valeurs séparées par des tabulations, comme un copier-coller INIES."""
        return "\t".join(nombre(v) for v in self.valeurs.en_liste())


# =============================================================================
# LECTURE
# =============================================================================
def nombre(valeur: float) -> str:
    """Nombre au format décimal standard (jamais de notation scientifique) : 19.1, 0.0, 0.00595."""
    texte = format(Decimal(repr(float(valeur))), "f")
    return texte if "." in texte else texte + ".0"


def _lire_materiau(brut: dict, position: int) -> MateriauEnregistre:
    """Contrôle et convertit une entrée du fichier."""
    nom = brut.get("nom")
    repere = f"Matériau n°{position} ({nom!r})" if nom else f"Matériau n°{position}"

    if not isinstance(nom, str) or not nom.strip():
        raise ErreurCatalogue(f"{repere} : le « nom » est obligatoire.")

    try:
        dvr = acv.verifier_dvr(brut.get("dvr"))
    except acv.ErreurInies as erreur:
        raise ErreurCatalogue(f"{repere} : « dvr » invalide. {erreur}") from None

    jour = brut.get("date_export")
    try:
        date.fromisoformat(jour)
    except (TypeError, ValueError):
        raise ErreurCatalogue(f"{repere} : « date_export » obligatoire, au format AAAA-MM-JJ "
                              f"(reçu : {jour!r}).") from None

    valeurs_brutes = brut.get("valeurs")
    if not isinstance(valeurs_brutes, dict):
        raise ErreurCatalogue(f"{repere} : le bloc « valeurs » est manquant.")
    manquantes = [n for n in NOMS_VALEURS if n not in valeurs_brutes]
    inconnues = [n for n in valeurs_brutes if n not in NOMS_VALEURS]
    if manquantes or inconnues:
        raise ErreurCatalogue(f"{repere} : « valeurs » doit contenir exactement les {len(NOMS_VALEURS)} champs "
                              f"({', '.join(NOMS_VALEURS)}). Manquants : {manquantes or 'aucun'} ; "
                              f"en trop : {inconnues or 'aucun'}.")
    for cle, valeur in valeurs_brutes.items():
        if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
            raise ErreurCatalogue(f"{repere} : la valeur « {cle} » doit être un nombre (reçu : {valeur!r}).")

    identifiant = brut.get("id")
    if identifiant is not None and (isinstance(identifiant, bool) or not isinstance(identifiant, int)):
        raise ErreurCatalogue(f"{repere} : « id » doit être un nombre entier.")

    attendu = brut.get("acv_dynamique_attendu")
    if attendu is not None and (isinstance(attendu, bool) or not isinstance(attendu, (int, float))):
        raise ErreurCatalogue(f"{repere} : « acv_dynamique_attendu » doit être un nombre.")

    return MateriauEnregistre(
        id=identifiant, nom=nom.strip(), lien_inies=brut.get("lien_inies"), dvr=dvr, date_export=jour,
        valeurs=acv.ValeursA2(**{n: float(valeurs_brutes[n]) for n in NOMS_VALEURS}),
        acv_dynamique_attendu=None if attendu is None else float(attendu))


def lire_catalogue(texte_json: str) -> List[MateriauEnregistre]:
    """Transforme le contenu de materiaux.json en liste de matériaux (lève ErreurCatalogue si invalide)."""
    try:
        contenu = json.loads(texte_json)
    except json.JSONDecodeError as erreur:
        raise ErreurCatalogue(f"materiaux.json n'est pas un JSON valide (ligne {erreur.lineno}, "
                              f"colonne {erreur.colno}) : {erreur.msg}. Vérifiez les virgules entre deux "
                              f"matériaux.") from None
    if not isinstance(contenu, dict) or contenu.get("format") != FORMAT_CATALOGUE:
        raise ErreurCatalogue(f"materiaux.json : « format » doit valoir {FORMAT_CATALOGUE}.")
    liste = contenu.get("materiaux")
    if not isinstance(liste, list):
        raise ErreurCatalogue("materiaux.json : la liste « materiaux » est manquante.")

    materiaux = []
    for position, brut in enumerate(liste, start=1):
        if not isinstance(brut, dict):
            raise ErreurCatalogue(f"Matériau n°{position} : l'entrée doit être un objet JSON (entre accolades).")
        materiaux.append(_lire_materiau(brut, position))
    identifiants = [m.id for m in materiaux if m.id is not None]
    doublons = sorted({i for i in identifiants if identifiants.count(i) > 1})
    if doublons:
        raise ErreurCatalogue(f"materiaux.json : identifiant(s) INIES en double : {doublons}.")
    return materiaux


def charger_catalogue(chemin: Path = FICHIER_PAR_DEFAUT) -> List[MateriauEnregistre]:
    """Lit le fichier materiaux.json. Un fichier absent donne un catalogue vide."""
    chemin = Path(chemin)
    if not chemin.exists():
        return []
    return lire_catalogue(chemin.read_text(encoding="utf-8"))


# =============================================================================
# ÉCRITURE : bloc à coller dans materiaux.json
# =============================================================================
def bloc_json_materiau(nom: str, identifiant: Optional[int], lien_inies: Optional[str], dvr: int,
                       valeurs: acv.ValeursA2, acv_dynamique: float, date_export: Optional[date] = None) -> str:
    """Bloc JSON d'un matériau, prêt à être collé dans la liste « materiaux » (au format décimal standard)."""
    date_export = date_export or date.today()
    champs_valeurs = ",\n".join(f'        "{n}": {nombre(v)}' for n, v in zip(NOMS_VALEURS, valeurs.en_liste()))
    lignes = [
        f'      "id": {identifiant if identifiant else "null"}',
        f'      "nom": {json.dumps(nom, ensure_ascii=False)}',
        f'      "lien_inies": {json.dumps(lien_inies) if lien_inies else "null"}',
        f'      "dvr": {int(dvr)}',
        f'      "date_export": "{date_export.isoformat()}"',
        f'      "valeurs": {{\n{champs_valeurs}\n      }}',
        f'      "acv_dynamique_attendu": {nombre(round(acv_dynamique, 3))}',
    ]
    return "    {\n" + ",\n".join(lignes) + "\n    }"
