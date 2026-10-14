"""
Tests du catalogue de matériaux (catalogue.py et materiaux.json).

Lancer depuis la racine du projet :  python3 -m pytest -q
"""
import copy
import json
import re
import sys
from datetime import date
from pathlib import Path

import pytest

# ----------------------------------------------------------------------------
# VARIABLES
# ----------------------------------------------------------------------------
RACINE = Path(__file__).resolve().parent.parent
FICHIER_CATALOGUE = RACINE / "materiaux.json"
JOUR_TEST = date(2026, 10, 14)

sys.path.insert(0, str(RACINE))
import acv_inies_a2 as acv  # noqa: E402
import catalogue as cat  # noqa: E402

BRUT = json.loads(FICHIER_CATALOGUE.read_text(encoding="utf-8"))


def catalogue_modifie(modification) -> str:
    """Copie du catalogue réel, modifiée par la fonction donnée, renvoyée en texte JSON."""
    contenu = copy.deepcopy(BRUT)
    modification(contenu)
    return json.dumps(contenu)


# ----------------------------------------------------------------------------
# 1) Le fichier réel materiaux.json
# ----------------------------------------------------------------------------
def test_fichier_reel_se_charge():
    materiaux = cat.charger_catalogue(FICHIER_CATALOGUE)
    assert len(materiaux) >= 1
    assert materiaux[0].id == 33806 and materiaux[0].dvr == 100


def test_chaque_materiau_redonne_son_acv_attendue():
    """Chaque matériau enregistré, recalculé, retombe sur le résultat noté dans le fichier."""
    for m in cat.charger_catalogue(FICHIER_CATALOGUE):
        if m.acv_dynamique_attendu is not None:
            calcule = acv.calculer_acv_dynamique(m.valeurs, m.dvr).dynamique_total
            assert calcule == pytest.approx(m.acv_dynamique_attendu, abs=cat.TOLERANCE_ACV_ATTENDUE), m.nom


def test_chaque_materiau_est_coherent():
    for m in cat.charger_catalogue(FICHIER_CATALOGUE):
        assert acv.controler_coherence(m.valeurs) == [], m.nom


def test_aucune_notation_scientifique_dans_le_fichier():
    """Les valeurs sont enregistrées au format décimal standard (19.1, jamais 1.91e+1)."""
    texte_sans_chaines = re.sub(r'"[^"]*"', "", FICHIER_CATALOGUE.read_text(encoding="utf-8"))
    assert not re.search(r"\d[eE][+-]?\d", texte_sans_chaines)


def test_la_date_d_export_est_presente_et_valide():
    for brut in BRUT["materiaux"]:
        date.fromisoformat(brut["date_export"])


def test_texte_inies_se_relit_a_l_identique():
    for m in cat.charger_catalogue(FICHIER_CATALOGUE):
        assert acv.lire_valeurs_inies(m.texte_inies()) == m.valeurs


def test_etiquette_affiche_la_date_au_format_francais():
    m = cat.charger_catalogue(FICHIER_CATALOGUE)[0]
    assert "INIES 33806" in m.etiquette() and "export du 14/10/2026" in m.etiquette()


def test_fichier_absent_donne_un_catalogue_vide(tmp_path):
    assert cat.charger_catalogue(tmp_path / "inexistant.json") == []


# ----------------------------------------------------------------------------
# 2) Erreurs de saisie dans le fichier (messages clairs)
# ----------------------------------------------------------------------------
@pytest.mark.parametrize("modification, morceau", [
    (lambda c: c.update(format=2), "« format » doit valoir 1"),
    (lambda c: c.pop("materiaux"), "liste « materiaux » est manquante"),
    (lambda c: c["materiaux"][0].pop("date_export"), "« date_export » obligatoire"),
    (lambda c: c["materiaux"][0].update(date_export="14/10/2026"), "« date_export » obligatoire"),
    (lambda c: c["materiaux"][0].update(nom=" "), "le « nom » est obligatoire"),
    (lambda c: c["materiaux"][0].update(dvr=0), "« dvr » invalide"),
    (lambda c: c["materiaux"][0]["valeurs"].pop("b3"), "Manquants : ['b3']"),
    (lambda c: c["materiaux"][0]["valeurs"].update(inconnu=1.0), "en trop : ['inconnu']"),
    (lambda c: c["materiaux"][0]["valeurs"].update(total="38"), "doit être un nombre"),
    (lambda c: c["materiaux"][0].update(id="abc"), "« id » doit être un nombre entier"),
    (lambda c: c["materiaux"].append(copy.deepcopy(c["materiaux"][0])), "en double"),
    (lambda c: c["materiaux"].append("texte"), "doit être un objet JSON"),
])
def test_erreurs_claires(modification, morceau):
    with pytest.raises(cat.ErreurCatalogue) as erreur:
        cat.lire_catalogue(catalogue_modifie(modification))
    assert morceau in str(erreur.value)


def test_json_invalide_mentionne_les_virgules():
    with pytest.raises(cat.ErreurCatalogue, match="virgules entre deux matériaux"):
        cat.lire_catalogue('{"format": 1, "materiaux": [{"nom": "a"} {"nom": "b"}]}')


# ----------------------------------------------------------------------------
# 3) Fabrication du bloc d'un nouveau matériau
# ----------------------------------------------------------------------------
def test_nombre_jamais_en_notation_scientifique():
    assert cat.nombre(0.00595) == "0.00595" and cat.nombre(1e-05) == "0.00001"
    assert cat.nombre(38) == "38.0" and cat.nombre(-2.69) == "-2.69" and cat.nombre(1.5e7) == "15000000.0"


def test_bloc_json_est_valide_et_se_relit_dans_le_catalogue():
    m = cat.charger_catalogue(FICHIER_CATALOGUE)[0]
    resultat = acv.calculer_acv_dynamique(m.valeurs, m.dvr)
    bloc = cat.bloc_json_materiau("Nouveau « test »", 46517, "https://exemple.fr/46517", 50, m.valeurs,
                                  resultat.dynamique_total, JOUR_TEST)
    entree = json.loads(bloc)                                   # le bloc seul est un JSON valide
    assert entree["date_export"] == "2026-10-14" and entree["nom"] == "Nouveau « test »"
    assert entree["acv_dynamique_attendu"] == round(resultat.dynamique_total, 3)
    ajoute = json.dumps({"format": 1, "materiaux": [entree]})   # et il se relit dans un catalogue
    assert cat.lire_catalogue(ajoute)[0].valeurs == m.valeurs


def test_bloc_sans_identifiant_ni_lien():
    v = acv.lire_valeurs_inies("1 2 3 4 5 6 7 8 9 10 11 12 13")
    entree = json.loads(cat.bloc_json_materiau("Sans id", None, None, 50, v, 12.3456, JOUR_TEST))
    assert entree["id"] is None and entree["lien_inies"] is None
    assert cat.lire_catalogue(json.dumps({"format": 1, "materiaux": [entree]}))[0].id is None


def test_le_bloc_colle_dans_le_fichier_reel_donne_un_catalogue_valide():
    """Scénario complet : on colle un nouveau bloc dans materiaux.json, avec une virgule."""
    m = cat.charger_catalogue(FICHIER_CATALOGUE)[0]
    bloc = cat.bloc_json_materiau("Deuxième", 12345, None, 30, m.valeurs, 1.0, JOUR_TEST)
    texte = FICHIER_CATALOGUE.read_text(encoding="utf-8").rstrip()
    assert texte.endswith("]\n}")
    nouveau = texte[: -len("\n  ]\n}")] + ",\n" + bloc + "\n  ]\n}\n"
    assert [x.nom for x in cat.lire_catalogue(nouveau)][-1] == "Deuxième"
