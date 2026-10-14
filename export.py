"""
export.py
=========
Fabrication des fichiers CSV téléchargeables (sans Streamlit, donc testable seul).

Format « à la française » : séparateur point-virgule, virgule décimale, encodage UTF-8 avec signature,
pour que le fichier s'ouvre directement et correctement dans Excel.

Chaque matériau est un dictionnaire : "nom", "identifiant" (ou None), "valeurs" (ValeursA2), "resultat" (ResultatA2).
"""
from __future__ import annotations

import dataclasses
from typing import List

import pandas as pd

import acv_inies_a2 as acv

# =============================================================================
# VARIABLES
# =============================================================================
SEPARATEUR_CSV = ";"
SEPARATEUR_DECIMAL = ","
ENCODAGE = "utf-8-sig"
UNITE = "kg CO₂ eq."


def _en_csv(tableau: pd.DataFrame) -> bytes:
    return tableau.to_csv(index=False, sep=SEPARATEUR_CSV, decimal=SEPARATEUR_DECIMAL).encode(ENCODAGE)


def csv_resume(materiaux: List[dict]) -> bytes:
    """Un matériau par ligne : identité, 13 valeurs INIES, résultat dynamique RE2020 et statique E+C-."""
    noms_valeurs = [champ.name for champ in dataclasses.fields(acv.ValeursA2)]
    lignes = []
    for m in materiaux:
        identifiant = m.get("identifiant")
        ligne = {"matériau": m["nom"], "identifiant INIES": None if identifiant is None else int(identifiant),
                 "DVR (ans)": m["resultat"].dvr}
        ligne.update({f"INIES {nom}": v for nom, v in zip(noms_valeurs, m["valeurs"].en_liste())})
        ligne[f"ACV dynamique RE2020 ({UNITE})"] = m["resultat"].dynamique_total
        ligne[f"statique E+C- ({UNITE})"] = m["resultat"].statique_total
        lignes.append(ligne)
    return _en_csv(pd.DataFrame(lignes))


def csv_annees(materiaux: List[dict]) -> bytes:
    """Année par année : coefficient, émissions pondérées et cumuls (dynamique et statique) de chaque matériau."""
    tableau = {"année": list(range(acv.PERIODE_ETUDE + 1)), "coefficient (art. 11)": list(acv.COEFFICIENTS_ART11)}
    for m in materiaux:
        resultat = m["resultat"]
        tableau[f"{m['nom']} — émissions pondérées"] = list(resultat.dynamique_par_annee)
        tableau[f"{m['nom']} — cumul dynamique"] = resultat.cumul_dynamique()
        tableau[f"{m['nom']} — cumul statique E+C-"] = resultat.cumul_statique()
    return _en_csv(pd.DataFrame(tableau))
