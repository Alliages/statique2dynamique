"""
Tests du module acv_inies_a2.

Lancer depuis la racine du projet :  python3 -m pytest -q
Les valeurs attendues (tests/reference_excel.json) viennent de l'Excel d'origine recalculé
par LibreOffice (voir tests/generer_reference_excel.py).
"""
import json
import re
import sys
from pathlib import Path

import pytest

# ----------------------------------------------------------------------------
# VARIABLES
# ----------------------------------------------------------------------------
RACINE = Path(__file__).resolve().parent.parent
FICHIER_REFERENCE = RACINE / "tests" / "reference_excel.json"
FICHIER_CHANGELOG = RACINE / "CHANGELOG.md"
TOLERANCE_RELATIVE = 1e-9      # écart toléré avec l'Excel (arrondis de flottants)

# Correspondance : champ du résultat Python -> clé du JSON de référence
CHAMPS_COMPARES = {
    "dynamique_t0": "dyn_t0", "dynamique_intermediaire": "dyn_milieu",
    "dynamique_t50": "dyn_t50", "dynamique_total": "dyn_total",
    "statique_t0": "stat_t0", "statique_intermediaire": "stat_milieu",
    "statique_t50": "stat_t50", "statique_total": "stat_total",
}
EXEMPLE_46517 = "1.54e+1\t5.14e+0\t0.00e+0\t5.95e-3\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t5.95e-3\t4.23e-1\t2.10e+1\t-9.65e-2"

sys.path.insert(0, str(RACINE))
import acv_inies_a2 as acv  # noqa: E402

SCENARIOS = json.loads(FICHIER_REFERENCE.read_text(encoding="utf-8"))


# ----------------------------------------------------------------------------
# 1) Résultats identiques à l'Excel
# ----------------------------------------------------------------------------
@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["nom"] for s in SCENARIOS])
def test_resultat_identique_a_excel(scenario):
    resultat = acv.calculer_depuis_inies(scenario["texte_inies"], scenario["dvr"])
    for champ, cle in CHAMPS_COMPARES.items():
        assert getattr(resultat, champ) == pytest.approx(scenario["attendu"][cle], rel=TOLERANCE_RELATIVE, abs=1e-9), champ


# ----------------------------------------------------------------------------
# 2) Lecture de la ligne collée
# ----------------------------------------------------------------------------
def test_lecture_tabulations_espaces_et_retours_a_la_ligne():
    attendu = acv.lire_valeurs_inies(EXEMPLE_46517)
    assert acv.lire_valeurs_inies(EXEMPLE_46517.replace("\t", " ")) == attendu
    assert acv.lire_valeurs_inies(EXEMPLE_46517.replace("\t", "\n")) == attendu
    assert attendu.production == 15.4 and attendu.module_d == -0.0965 and attendu.total == 21.0


def test_lecture_virgule_decimale_et_vrai_signe_moins():
    texte = EXEMPLE_46517.replace(".", ",").replace("-9,65e-2", "−9,65e-2")
    assert acv.lire_valeurs_inies(texte).module_d == -0.0965


def test_lecture_ignore_les_libelles():
    texte = "Réchauffement climatique (kg CO2 eq.) " + EXEMPLE_46517
    assert len(acv.extraire_nombres(texte)) == 13


@pytest.mark.parametrize("texte, morceau_message", [
    ("", "Aucun nombre"),
    ("abc def", "Aucun nombre"),
    ("1.0e+0 2.0e+0 3.0e+0 4.0e+0 5.0e+0 6.0e+0", "+A1"),
    ("1.0e+0 2.0e+0 3.0e+0", "3 valeurs au lieu de 13"),
    (EXEMPLE_46517 + "\t1.0e+0", "14 valeurs au lieu de 13"),
])
def test_erreurs_de_saisie_claires(texte, morceau_message):
    with pytest.raises(acv.ErreurInies, match=re.escape(morceau_message)):
        acv.lire_valeurs_inies(texte)


@pytest.mark.parametrize("dvr", [0, -5, 1001, 12.5, "50", None, True])
def test_dvr_invalide(dvr):
    with pytest.raises(acv.ErreurInies):
        acv.calculer_depuis_inies(EXEMPLE_46517, dvr)


def test_dvr_entier_donne_en_flottant_est_accepte():
    assert acv.calculer_depuis_inies(EXEMPLE_46517, 50.0).dvr == 50


# ----------------------------------------------------------------------------
# 3) Contrôles de cohérence
# ----------------------------------------------------------------------------
def test_ligne_coherente_sans_avertissement():
    assert acv.controler_coherence(acv.lire_valeurs_inies(EXEMPLE_46517)) == []


def test_ligne_incoherente_avertit():
    # le total (dernier-1) est faux : 99 au lieu de ~21
    texte = EXEMPLE_46517.replace("2.10e+1", "9.90e+1")
    avertissements = acv.controler_coherence(acv.lire_valeurs_inies(texte))
    assert len(avertissements) == 1 and "ne s'additionnent pas" in avertissements[0]


# ----------------------------------------------------------------------------
# 4) Propriétés générales du calcul
# ----------------------------------------------------------------------------
def test_coefficients_art11():
    assert len(acv.COEFFICIENTS_ART11) == acv.PERIODE_ETUDE + 1 == 51
    assert acv.COEFFICIENTS_ART11[0] == 1.0 and acv.COEFFICIENTS_ART11[50] == 0.578
    assert all(a > b for a, b in zip(acv.COEFFICIENTS_ART11, acv.COEFFICIENTS_ART11[1:]))   # décroissants


def test_somme_des_phases_et_cumul():
    r = acv.calculer_depuis_inies(EXEMPLE_46517, 30)
    assert r.dynamique_t0 + r.dynamique_intermediaire + r.dynamique_t50 == pytest.approx(r.dynamique_total)
    assert r.statique_t0 + r.statique_intermediaire + r.statique_t50 == pytest.approx(r.statique_total)
    assert r.cumul_dynamique()[-1] == pytest.approx(r.dynamique_total)
    assert len(r.dynamique_par_annee) == 51


def test_arrondi_comme_excel():
    assert acv.arrondir(0.123455) == 0.12346       # égalité arrondie vers le haut (|x|)
    assert acv.arrondir(-0.123455) == -0.12346     # ... et en s'éloignant de zéro pour les négatifs
    assert str(acv.arrondir(-0.000001)) == "0.0"   # pas de « -0.0 »


# ----------------------------------------------------------------------------
# 5) Versionning cohérent
# ----------------------------------------------------------------------------
def test_version_historique_et_changelog_coherents():
    assert acv.HISTORIQUE_VERSIONS[0][0] == acv.VERSION
    assert acv.HISTORIQUE_VERSIONS[0][1] == acv.DATE_VERSION
    changelog = " ".join(FICHIER_CHANGELOG.read_text(encoding="utf-8").split())   # espaces normalisés
    for version, date, description in acv.HISTORIQUE_VERSIONS:
        assert f"## {version} — {date} {' '.join(description.split())}" in changelog, version


# ----------------------------------------------------------------------------
# Courbe statique cumulée (illustration : la phase intermédiaire est répartie à parts égales)
# ----------------------------------------------------------------------------
@pytest.mark.parametrize("dvr", [1, 20, 50, 100])
def test_cumul_statique_part_et_finit_aux_bonnes_valeurs(dvr):
    r = acv.calculer_depuis_inies("19.1 17.2 -2.69 0 0 0 0 0 0 -2.69 4.42 38.0 -1.85", dvr)
    cumul = r.cumul_statique()
    assert len(cumul) == acv.PERIODE_ETUDE + 1
    assert cumul[0] == pytest.approx(r.statique_t0)
    assert cumul[-1] == pytest.approx(r.statique_total)
    pas = [b - a for a, b in zip(cumul[1:-1], cumul[2:-1])]
    assert max(pas) - min(pas) < 1e-9                       # répartition uniforme sur les années 1 à 49
