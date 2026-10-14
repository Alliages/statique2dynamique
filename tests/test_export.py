"""
Tests des exports CSV (export.py).

Lancer depuis la racine du projet :  python3 -m pytest -q
"""
import io
import sys
from pathlib import Path

import pandas as pd
import pytest

# ----------------------------------------------------------------------------
# VARIABLES
# ----------------------------------------------------------------------------
RACINE = Path(__file__).resolve().parent.parent
TEXTE_A = "1.91e+1\t1.72e+1\t-2.69e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t-2.69e+0\t4.42e+0\t3.80e+1\t-1.85e+0"
TEXTE_B = "1.54e+1\t5.14e+0\t0.00e+0\t5.95e-3\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t5.95e-3\t4.23e-1\t2.10e+1\t-9.65e-2"

sys.path.insert(0, str(RACINE))
import acv_inies_a2 as acv  # noqa: E402
import export  # noqa: E402


def materiau(nom, identifiant, texte, dvr):
    valeurs = acv.lire_valeurs_inies(texte)
    return {"nom": nom, "identifiant": identifiant, "valeurs": valeurs, "resultat": acv.calculer_acv_dynamique(valeurs, dvr)}


MATERIAUX = [materiau("Mat A", 33806, TEXTE_A, 100), materiau("Mat B", None, TEXTE_B, 50)]


def lire(octets: bytes) -> pd.DataFrame:
    """Relit un CSV comme Excel France le ferait (point-virgule, virgule décimale)."""
    return pd.read_csv(io.BytesIO(octets), sep=";", decimal=",", encoding="utf-8-sig")


def test_resume_une_ligne_par_materiau_au_format_francais():
    octets = export.csv_resume(MATERIAUX)
    assert octets.startswith(b"\xef\xbb\xbf")                      # signature UTF-8 pour Excel
    texte = octets.decode("utf-8-sig")
    assert ";" in texte and "36,7" in texte                          # virgule décimale
    tableau = lire(octets)
    assert len(tableau) == 2 and list(tableau["matériau"]) == ["Mat A", "Mat B"]
    assert tableau["identifiant INIES"][0] == 33806 and pd.isna(tableau["identifiant INIES"][1])
    assert list(tableau["DVR (ans)"]) == [100, 50]
    assert tableau["ACV dynamique RE2020 (kg CO₂ eq.)"][0] == pytest.approx(MATERIAUX[0]["resultat"].dynamique_total)
    assert tableau["INIES production"][0] == pytest.approx(19.1) and tableau["INIES module_d"][0] == pytest.approx(-1.85)
    assert sum(1 for c in tableau.columns if c.startswith("INIES ")) == acv.NB_VALEURS_A2


def test_annees_51_lignes_et_cumuls_qui_finissent_sur_les_resultats():
    tableau = lire(export.csv_annees(MATERIAUX))
    assert len(tableau) == acv.PERIODE_ETUDE + 1 and tableau["année"].iloc[-1] == 50
    for m in MATERIAUX:
        resultat, nom = m["resultat"], m["nom"]
        assert tableau[f"{nom} — cumul dynamique"].iloc[-1] == pytest.approx(resultat.dynamique_total)
        assert tableau[f"{nom} — cumul statique E+C-"].iloc[-1] == pytest.approx(resultat.statique_total)
    assert tableau["coefficient (art. 11)"].iloc[0] == 1.0
