"""
lien.py
=======
Liens « pré-remplis » vers l'application, SANS Streamlit (donc testable seul).

Un lien porte un matériau (ou deux) dans son adresse, par exemple :
    https://statique2dynamique.streamlit.app/?v=1&a_nom=Dalle%20bois&a_id=50632&a_dvr=50&a_v=4.24,1.52,...

Il sert à retrouver un matériau plus tard, à le partager, et (plus tard) à recevoir les valeurs
envoyées par un script du navigateur depuis la fiche INIES.

Paramètres, pour chaque matériau (préfixe « a » pour le matériau A, « b » pour le B) :
    a_nom   nom du matériau (facultatif)
    a_id    identifiant INIES, entier >= 1 (facultatif)
    a_dvr   durée de vie de référence, en années (obligatoire)
    a_v     les 13 valeurs INIES +A2, séparées par des virgules, point décimal (obligatoire)
    v       numéro de format du lien (obligatoire, voir FORMAT_LIEN)

Le numéro de format permet de refuser proprement, plus tard, un lien fabriqué avec une autre version.
Tout ce qui est lu dans une adresse est contrôlé : une adresse est une entrée non fiable.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import List, Mapping, Optional, Tuple
from urllib.parse import quote, urlencode

import acv_inies_a2 as acv
from catalogue import nombre

# =============================================================================
# VARIABLES
# =============================================================================
FORMAT_LIEN = 1                         # numéro de format des liens (à changer si les paramètres changent)
PARAM_FORMAT = "v"
PREFIXES = ("a", "b")                   # matériau A, matériau B
SEPARATEUR_VALEURS = ","
LONGUEUR_NOM_MAX = 120                  # caractères conservés dans le nom
LONGUEUR_PARAM_MAX = 1000               # un paramètre plus long est refusé (protection)
VALEUR_ABSOLUE_MAX = 1e9                # une valeur INIES plus grande est considérée comme une erreur
CARACTERES_DE_CONTROLE = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True)
class MaterielLien:
    """Un matériau lu dans un lien, déjà contrôlé."""
    indice: int                         # 0 pour A, 1 pour B
    nom: str
    identifiant: Optional[int]
    dvr: int
    valeurs: acv.ValeursA2

    @property
    def lettre(self) -> str:
        """Lettre du matériau : « A » ou « B »."""
        return PREFIXES[self.indice].upper()

    def texte_inies(self) -> str:
        """Les 13 valeurs séparées par des tabulations, comme un copier-coller INIES."""
        return "\t".join(nombre(v) for v in self.valeurs.en_liste())


# =============================================================================
# FABRIQUER UN LIEN
# =============================================================================
def construire_lien(url_app: str, indice: int, nom: str, identifiant: Optional[int], dvr: int,
                    valeurs: acv.ValeursA2) -> str:
    """Adresse de l'application pré-remplie avec un matériau (placé en A ou en B selon `indice`)."""
    p = PREFIXES[indice]
    parametres = [(PARAM_FORMAT, str(FORMAT_LIEN))]
    if nom and nom.strip():
        parametres.append((f"{p}_nom", nettoyer_nom(nom)))
    if identifiant:
        parametres.append((f"{p}_id", str(int(identifiant))))
    parametres.append((f"{p}_dvr", str(int(dvr))))
    parametres.append((f"{p}_v", SEPARATEUR_VALEURS.join(nombre(v) for v in valeurs.en_liste())))
    # quote (et non quote_plus) : les espaces deviennent %20 ; la virgule reste lisible
    return url_app.rstrip("?") + "?" + urlencode(parametres, quote_via=quote, safe=SEPARATEUR_VALEURS)


# =============================================================================
# LIRE UN LIEN
# =============================================================================
def nettoyer_nom(nom: str) -> str:
    """Nom sans caractères de contrôle, espaces simplifiés, longueur limitée."""
    nom = CARACTERES_DE_CONTROLE.sub(" ", nom)
    return " ".join(nom.split())[:LONGUEUR_NOM_MAX]


def contient_un_lien(parametres: Mapping[str, str]) -> bool:
    """Vrai si l'adresse contient au moins un paramètre de ce format (même invalide)."""
    return any(cle in parametres for cle in cles_connues())


def cles_connues() -> List[str]:
    """Tous les noms de paramètres qu'un lien peut contenir (format, puis nom, id, dvr et valeurs de A et B)."""
    return [PARAM_FORMAT] + [f"{p}_{suffixe}" for p in PREFIXES for suffixe in ("nom", "id", "dvr", "v")]


def contient_le_materiau(parametres: Mapping[str, str], indice: int) -> bool:
    """Vrai si l'adresse contient au moins un paramètre du matériau `indice` (0 pour A, 1 pour B)."""
    p = PREFIXES[indice]
    return any(f"{p}_{suffixe}" in parametres for suffixe in ("nom", "id", "dvr", "v"))


def _entier(texte: str, nom_param: str, minimum: int, maximum: Optional[int] = None) -> int:
    """Entier strict (chiffres seulement) dans [minimum, maximum], sinon ValueError avec un message clair."""
    if not re.fullmatch(r"\d{1,9}", texte.strip()):
        raise ValueError(f"« {nom_param} » doit être un nombre entier.")
    valeur = int(texte)
    if valeur < minimum or (maximum is not None and valeur > maximum):
        intervalle = f"au moins {minimum}" if maximum is None else f"entre {minimum} et {maximum}"
        raise ValueError(f"« {nom_param} » doit être {intervalle} (valeur reçue : {valeur}).")
    return valeur


def _valeurs(texte: str, nom_param: str) -> acv.ValeursA2:
    """Les 13 valeurs d'un lien, contrôlées : nombres finis et raisonnables, exactement 13."""
    morceaux = texte.split(SEPARATEUR_VALEURS)
    if len(morceaux) != acv.NB_VALEURS_A2:
        raise ValueError(f"« {nom_param} » doit contenir {acv.NB_VALEURS_A2} valeurs séparées par des virgules "
                         f"(il y en a {len(morceaux)}).")
    nombres = []
    for morceau in morceaux:
        try:
            valeur = float(morceau.strip())
        except ValueError:
            raise ValueError(f"« {nom_param} » contient « {morceau[:20]} », qui n'est pas un nombre.") from None
        if not math.isfinite(valeur) or abs(valeur) > VALEUR_ABSOLUE_MAX:
            raise ValueError(f"« {nom_param} » contient une valeur hors limites ({morceau[:20]}).")
        nombres.append(valeur)
    return acv.ValeursA2(*nombres)


def _lire_materiau(parametres: Mapping[str, str], indice: int) -> MaterielLien:
    """Un matériau du lien (lève ValueError avec un message clair, sans le préfixe « Matériau X »)."""
    p = PREFIXES[indice]
    for suffixe in ("nom", "id", "dvr", "v"):
        if len(parametres.get(f"{p}_{suffixe}", "")) > LONGUEUR_PARAM_MAX:
            raise ValueError(f"« {p}_{suffixe} » est trop long.")
    if f"{p}_v" not in parametres:
        raise ValueError(f"il manque « {p}_v » (les {acv.NB_VALEURS_A2} valeurs INIES).")
    if f"{p}_dvr" not in parametres:
        raise ValueError(f"il manque « {p}_dvr » (la durée de vie de référence).")
    return MaterielLien(
        indice=indice,
        nom=nettoyer_nom(parametres.get(f"{p}_nom", "")),
        identifiant=_entier(parametres[f"{p}_id"], f"{p}_id", 1) if f"{p}_id" in parametres else None,
        dvr=_entier(parametres[f"{p}_dvr"], f"{p}_dvr", acv.DVR_MIN, acv.DVR_MAX),
        valeurs=_valeurs(parametres[f"{p}_v"], f"{p}_v"))


def lire_lien(parametres: Mapping[str, str]) -> Tuple[List[MaterielLien], List[str]]:
    """Lit les paramètres d'une adresse. Renvoie (matériaux valides, messages d'erreur en français).

    Sans paramètre de ce format : ([], []). Un matériau invalide est ignoré avec son message d'erreur,
    l'autre matériau du lien (s'il est valide) est conservé.
    """
    if not contient_un_lien(parametres):
        return [], []
    format_recu = parametres.get(PARAM_FORMAT, "")
    if format_recu != str(FORMAT_LIEN):
        return [], [f"Ce lien n'a pas le bon format (format « {format_recu[:10] or 'absent'} » reçu, "
                    f"format {FORMAT_LIEN} attendu). Il a peut-être été fabriqué avec une autre version de l'outil."]
    materiaux: List[MaterielLien] = []
    erreurs: List[str] = []
    for indice, p in enumerate(PREFIXES):
        if not contient_le_materiau(parametres, indice):
            continue
        try:
            materiaux.append(_lire_materiau(parametres, indice))
        except ValueError as erreur:
            erreurs.append(f"Lien incomplet ou invalide pour le matériau {p.upper()} : {erreur}")
    if not materiaux and not erreurs:
        erreurs.append("Ce lien ne contient aucun matériau.")
    return materiaux, erreurs
