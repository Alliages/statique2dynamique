"""
Tests des 4 lignes « Changement climatique » (total, fossile, biogénique, occupation des sols)
et de la répartition du résultat dynamique par étape.

Lancer depuis la racine du projet :  python3 -m pytest -q
Les valeurs de référence viennent de l'Excel d'origine (panneau CLT, DVR 100 ans : dynamique = −286,75).
"""
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
import acv_inies_a2 as acv  # noqa: E402

# =============================================================================
# DONNÉES DE TEST (tout ce qui se règle est regroupé ici)
# =============================================================================
# Copier-coller réel depuis INIES : 13 libellés de colonnes, puis les 4 lignes avec leur libellé.
COLLAGE_INIES = """Étape de production
Étape du processus de construction
B1-Utilisation
B2-Maintenance
B3-Réparation
B4-Remplacement
B5-Réhabilitation
B6-Utilisation de l’énergie durant l’étape d’utilisation
B7-Utilisation de l’eau durant l’étape d’utilisation
Étape d’utilisation
Étape de fin de vie
Total cycle de vie
D-Bénéfices et charges au-delà des frontières du système
Changement climatique - total (kg CO2 eq.)\t-6.04e+2\t1.38e+1\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t7.58e+2\t1.67e+2\t-2.33e+2
Changement climatique - fossil (kg CO2 eq.)\t1.03e+2\t1.35e+1\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t3.33e+1\t1.50e+2\t-2.25e+2
Changement climatique - biogénique (kg CO2 eq.)\t-7.08e+2\t3.06e-1\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t7.24e+2\t1.67e+1\t-8.35e+0
Changement climatique - occupation des sols et transformation de l'occupation des sols (kg CO2 eq.)\t1.03e-1\t4.60e-4\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t4.38e-3\t1.08e-1\t-6.01e-2
"""
LIGNES = COLLAGE_INIES.strip().splitlines()[13:]      # les 4 lignes de valeurs
DVR_CLT = 100
DYNAMIQUE_TOTAL_EXCEL = -286.75                        # Excel « Interface +A2 », cellule G24
DVR_A_TESTER = (1, 7, 30, 50, 60, 100)                 # dont des DVR qui ne divisent pas 50
PRECISION = 1e-6


def _reference_total(valeurs: acv.ValeursA2, dvr: int) -> float:
    """Calcul de référence, écrit à part et sans répartition par étape (formule de la version 3.9.0)."""
    prod, constr, util, fdv, mod_d = (acv.arrondir(x) for x in (
        valeurs.production, valeurs.construction, valeurs.utilisation, valeurs.fin_de_vie, valeurs.module_d))
    cycles = 50 // dvr
    part_dernier = 50 / dvr - cycles
    total = 0.0
    for annee in range(51):
        c = acv.COEFFICIENTS_ART11[annee]
        emission = prod + constr if annee == 0 else (util / dvr + fdv + mod_d if annee == 50 else util / dvr)
        total += emission * c
        if annee > 0 and annee % dvr == 0:
            part = part_dernier if cycles > 0 and annee % (dvr * cycles) == 0 else 1.0
            total += (prod + constr + fdv) * part * c + mod_d * part * c
    return total


# =============================================================================
# LECTURE DES 4 LIGNES
# =============================================================================
def test_lecture_des_quatre_lignes_avec_libelles_de_colonnes():
    valeurs = acv.lire_indicateurs_climat(COLLAGE_INIES)
    assert list(valeurs) == ["total", "fossile", "biogenique", "sols"]
    assert valeurs["total"].production == -604 and valeurs["total"].module_d == -233
    assert valeurs["fossile"].fin_de_vie == 33.3
    assert valeurs["biogenique"].production == -708
    assert valeurs["sols"].construction == 4.6e-4


def test_lecture_independante_de_l_ordre_et_des_lignes_en_trop():
    lignes_inversees = "\n".join(reversed(LIGNES)) + "\nAcidification\t1\t2\t3\n"
    assert acv.lire_indicateurs_climat(lignes_inversees) == acv.lire_indicateurs_climat(COLLAGE_INIES)


def test_erreur_ligne_manquante():
    with pytest.raises(acv.ErreurInies, match="Biogénique"):
        acv.lire_indicateurs_climat("\n".join(LIGNES[:2] + LIGNES[3:]))


def test_erreur_nombre_de_valeurs():
    ligne_courte = LIGNES[1].rsplit("\t", 1)[0]        # 12 valeurs au lieu de 13
    with pytest.raises(acv.ErreurInies, match="Fossile.*12 valeurs"):
        acv.lire_indicateurs_climat("\n".join([LIGNES[0], ligne_courte, *LIGNES[2:]]))


def test_erreur_ligne_en_double():
    with pytest.raises(acv.ErreurInies, match="deux fois"):
        acv.lire_indicateurs_climat("\n".join(LIGNES + [LIGNES[0]]))


def test_erreur_texte_sans_ligne_climat():
    with pytest.raises(acv.ErreurInies, match="Aucune ligne"):
        acv.lire_indicateurs_climat("n'importe quoi 1 2 3")


# =============================================================================
# COHÉRENCE
# =============================================================================
def test_coherence_des_donnees_reelles():
    assert acv.controler_coherence_indicateurs(acv.lire_indicateurs_climat(COLLAGE_INIES)) == []


def test_incoherence_detectee_quand_le_fossile_est_modifie():
    ligne_fossile_fausse = LIGNES[1].replace("1.03e+2", "9.99e+2")       # production fossile : 103 -> 999
    avertissements = acv.controler_coherence_indicateurs(
        acv.lire_indicateurs_climat("\n".join([LIGNES[0], ligne_fossile_fausse, *LIGNES[2:]])))
    assert any("ne donne pas le total" in a and "production" in a for a in avertissements)


def test_meme_materiau_la_ligne_total_est_celle_du_materiau():
    valeurs = acv.lire_indicateurs_climat(COLLAGE_INIES)
    assert acv.controler_meme_materiau(valeurs["total"], valeurs["total"]) is None
    assert "ne correspond pas" in acv.controler_meme_materiau(valeurs["fossile"], valeurs["total"])


# =============================================================================
# CALCUL
# =============================================================================
def test_resultat_conforme_a_l_excel():
    resultats = acv.calculer_indicateurs_climat(COLLAGE_INIES, DVR_CLT)
    assert resultats["total"].dynamique_total == pytest.approx(DYNAMIQUE_TOTAL_EXCEL, abs=PRECISION)


@pytest.mark.parametrize("dvr", DVR_A_TESTER)
def test_le_total_dynamique_n_a_pas_change(dvr):
    """La répartition par étape ne doit pas modifier le résultat de la version 3.9.0."""
    for valeurs in acv.lire_indicateurs_climat(COLLAGE_INIES).values():
        assert acv.calculer_acv_dynamique(valeurs, dvr).dynamique_total == pytest.approx(
            _reference_total(valeurs, dvr), abs=PRECISION)


@pytest.mark.parametrize("dvr", DVR_A_TESTER)
def test_la_somme_des_etapes_donne_le_total_dynamique(dvr):
    for resultat in acv.calculer_indicateurs_climat(COLLAGE_INIES, dvr).values():
        assert [cle for cle, _ in resultat.dynamique_par_etape] == [cle for cle, _ in acv.ETAPES]
        assert sum(v for _, v in resultat.dynamique_par_etape) == pytest.approx(
            resultat.dynamique_total, abs=PRECISION)
        assert resultat.cumul_dynamique()[-1] == pytest.approx(resultat.dynamique_total, abs=PRECISION)


def test_repartition_par_etape_du_clt_a_100_ans():
    """Production et construction à l'année 0 (coefficient 1) ; fin de vie et module D à l'année 50 (0,578)."""
    etapes = dict(acv.calculer_indicateurs_climat(COLLAGE_INIES, DVR_CLT)["total"].dynamique_par_etape)
    assert etapes["production"] == pytest.approx(-604.0)
    assert etapes["construction"] == pytest.approx(13.8)
    assert etapes["utilisation"] == pytest.approx(0.0)
    assert etapes["fin_de_vie"] == pytest.approx(758 * 0.578)
    assert etapes["module_d"] == pytest.approx(-233 * 0.578)


@pytest.mark.parametrize("dvr", DVR_A_TESTER)
def test_fossile_plus_biogenique_plus_sols_donne_le_total(dvr):
    """Le dynamique est linéaire : la cohérence des lignes INIES se retrouve dans le résultat (à l'arrondi INIES près)."""
    r = acv.calculer_indicateurs_climat(COLLAGE_INIES, dvr)
    somme = sum(r[cle].dynamique_total for cle in acv.CLES_COMPOSANTES)
    # Échelle : les flux bruts (somme des étapes en valeur absolue), car les remplacements amplifient l'arrondi INIES.
    echelle = max(sum(abs(v) for _, v in r[cle].dynamique_par_etape) for cle in r)
    assert abs(somme - r["total"].dynamique_total) <= acv.TOLERANCE_COHERENCE * echelle
