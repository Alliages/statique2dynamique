"""
Tests de la mise en forme (presentation.py) : nombres, graphique, tableau des étapes, styles.

Lancer depuis la racine du projet :  python3 -m pytest -q
"""
import math
import re
import sys
from pathlib import Path

import pytest

# ----------------------------------------------------------------------------
# VARIABLES
# ----------------------------------------------------------------------------
RACINE = Path(__file__).resolve().parent.parent
TEXTE_A = "1.91e+1\t1.72e+1\t-2.69e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t-2.69e+0\t4.42e+0\t3.80e+1\t-1.85e+0"
TEXTE_B = "1.54e+1\t5.14e+0\t0.00e+0\t5.95e-3\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t5.95e-3\t4.23e-1\t2.10e+1\t-9.65e-2"
ACV_A_ATTENDUE = 36.72175        # contrôlé avec l'Excel (arrondi : 36,722)

sys.path.insert(0, str(RACINE))
import acv_inies_a2 as acv  # noqa: E402
import presentation as pres  # noqa: E402


def serie(indice: int, nom: str, texte: str, dvr: int) -> dict:
    r = acv.calculer_depuis_inies(texte, dvr)
    return {"indice": indice, "nom": nom, "annees": list(r.annees), "cumul": r.cumul_dynamique()}


# ----------------------------------------------------------------------------
# 1) Nombres
# ----------------------------------------------------------------------------
@pytest.mark.parametrize("valeur, attendu", [
    (36.72175, "36,7"), (-286.75, "−286,8"), (4.4, "4,40"), (0.5, "0,500"), (1234567.0, "1 234 567,0"),
    (-0.0004, "0,000"), (0.0, "0,000"),
])
def test_fr(valeur, attendu):
    assert pres.fr(valeur) == attendu


@pytest.mark.parametrize("valeur, attendu", [
    (38.0, "38"), (19.1, "19,1"), (-2.69, "−2,69"), (4.42, "4,42"), (-1.85, "−1,85"), (0.0, "0"),
    (0.00595, "0,00595"), (-0.0965, "−0,0965"), (1234.5, "1230"), (1e-05, "0,00001"), (-0.0, "0"),
])
def test_fr_3_chiffres_comme_inies(valeur, attendu):
    assert pres.fr_3_chiffres(valeur) == attendu


def test_limite_axe_symetrique_et_graduations_rondes():
    assert pres.limite_axe(36.7) == 50 and pres.limite_axe(0) == 5
    assert pres.limite_axe(286.75) == 500 and pres.limite_axe(14.0) == 25
    for valeur in (0.3, 3, 36.7, 99, 540, 12345):
        limite = pres.limite_axe(valeur)
        assert limite >= valeur * pres.MARGE_AXE - 1e-9                   # la courbe tient dans l'axe
        pas = limite / pres.NB_GRADUATIONS
        mantisse = pas / 10 ** math.floor(math.log10(pas))
        assert min(abs(mantisse - m) for m in (1, 2, 5)) < 1e-9, (valeur, pas)   # graduations rondes : 1, 2 ou 5 × 10^k


def test_format_graduations():
    assert pres.format_graduations(50) == ",.0f"
    assert pres.format_graduations(0.5) == ",.1f"


def test_nom_court():
    assert pres.nom_court("Court") == "Court"
    assert len(pres.nom_court("x" * 80)) == pres.LONGUEUR_NOM_LEGENDE and pres.nom_court("x" * 80).endswith("…")


# ----------------------------------------------------------------------------
# 2) Graphique
# ----------------------------------------------------------------------------
def test_graphique_proposition_1():
    series = [serie(0, "Panneau CLT", TEXTE_A, 100), serie(1, "Fiche 46517", TEXTE_B, 50)]
    figure = pres.figure_cumul(series)
    theme = pres.THEME

    courbes = [t for t in figure.data if t.mode == "lines"]
    assert len(courbes) == 2                                                # uniquement les courbes dynamiques
    assert all("statique" not in (t.name or "") for t in figure.data)       # pas de courbe statique
    for courbe, indice in zip(courbes, (0, 1)):
        assert courbe.line.width == pres.EPAISSEUR_COURBE                   # trait épais
        assert courbe.line.color == theme["matieres"][indice]               # couleur = celle du matériau

    textes = [a.text for a in figure.layout.annotations]
    assert f"<b>{pres.TEXTE_EMISSIONS}</b>" in textes and f"<b>{pres.TEXTE_SEQUESTRATION}</b>" in textes
    assert "<b>36,7</b>" in textes                                          # valeur finale du CLT
    final_b = pres.fr(series[1]["cumul"][-1])
    assert f"<b>{final_b}</b>" in textes
    for annotation in figure.layout.annotations:                            # valeur finale : dans la bonne couleur
        for s, indice in zip(series, (0, 1)):
            if annotation.text == f"<b>{pres.fr(s['cumul'][-1])}</b>":
                assert annotation.font.color == theme["texte_matieres"][indice]   # lisible sur fond blanc
    for texte in (pres.TEXTE_EMISSIONS, pres.TEXTE_SEQUESTRATION):                # filigrane en gris clair
        filigrane = next(a for a in figure.layout.annotations if a.text == f"<b>{texte}</b>")
        assert filigrane.font.color == "#d3d7db"
    assert figure.layout.paper_bgcolor == "#ffffff"                              # graphique sur fond blanc
    fleches = [a for a in figure.layout.annotations if a.showarrow]
    assert len(fleches) == 2                                                # deux axes fléchés

    limite = figure.layout.yaxis.range[1]
    assert figure.layout.yaxis.range[0] == -limite                          # échelle symétrique autour de zéro
    assert all(abs(v) <= limite for s in series for v in s["cumul"])


def test_valeur_finale_du_clt_est_le_resultat_du_calcul():
    s = serie(0, "CLT", TEXTE_A, 100)
    assert s["cumul"][-1] == pytest.approx(ACV_A_ATTENDUE)
    figure = pres.figure_cumul([s])
    fin = [t for t in figure.data if t.mode == "markers"][0]
    assert fin.x == (50,) and fin.y[0] == pytest.approx(ACV_A_ATTENDUE)


def test_valeurs_finales_proches_sont_ecartees():
    a = serie(0, "A", TEXTE_A, 100)
    b = dict(serie(1, "B", TEXTE_A, 100))      # même courbe : étiquettes superposées sans correction
    figure = pres.figure_cumul([a, b])
    decalages = sorted(an.yshift for an in figure.layout.annotations if an.text == "<b>36,7</b>")
    assert decalages == [-13, 13]


def test_graphique_a_une_seule_courbe_et_vide_ne_plante_pas():
    assert len(pres.figure_cumul([serie(1, "B", TEXTE_B, 50)]).data) == 2
    pres.figure_cumul([])


def test_legende_tronquee_mais_infobulle_complete():
    nom_long = "Panneau CLT (lamellé-croisé), fabriqué en France par Mathis, très long nom"
    courbe = pres.figure_cumul([serie(0, nom_long, TEXTE_A, 100)]).data[0]
    assert courbe.name.endswith("…") and nom_long in courbe.hovertemplate


# ----------------------------------------------------------------------------
# 3) Tableau des étapes
# ----------------------------------------------------------------------------
def test_tableau_des_etapes_comme_l_exemple_de_l_utilisateur():
    valeurs = acv.lire_valeurs_inies(TEXTE_A)
    tableau = pres.tableau_etapes_html("Panneau CLT", valeurs, 0)
    for code in ("A1-A3", "A4-A5 Édification", "B1-B7 Exploitation", "C1-C4", ">D<"):
        assert code in tableau
    for libelle in ("Étape de production", "Étape du processus de construction", "Étape d’utilisation",
                    "Étape de fin de vie", "Total cycle de vie", "D-Bénéfices et charges au-delà des frontières du système"):
        assert libelle in tableau
    valeurs_affichees = re.findall(r"<td>([^<]+)</td>", tableau.split('<tr class="valeurs">')[1])
    assert valeurs_affichees == ["19,1", "17,2", "−2,69", "4,42", "38", "−1,85"]
    assert "tab-A" in tableau and "tab-B" in pres.tableau_etapes_html("x", valeurs, 1)


def test_nom_echappe_dans_le_tableau():
    tableau = pres.tableau_etapes_html("<script>alert(1)</script>", acv.lire_valeurs_inies(TEXTE_A), 0)
    assert "<script>" not in tableau and "&lt;script&gt;" in tableau


# ----------------------------------------------------------------------------
# 4) Styles
# ----------------------------------------------------------------------------
def test_css_sans_marqueur_oublie_et_avec_la_palette():
    feuille = pres.css()
    assert "__" not in feuille                                  # tous les marqueurs ont été remplacés
    for couleur in pres.THEME["matieres"]:
        assert couleur in feuille
    assert pres.degrade_fond() in feuille and "linear-gradient(135deg" in feuille    # fond en dégradé diagonal
    assert f"max-width: {pres.LARGEUR_MAX_GRAPHIQUE}px" in feuille    # tableau des étapes aligné sur le graphique
    assert len(pres.COLONNES_GRAPHIQUE) == 3                          # graphique étroit : colonne centrale
    assert "background: #ffffff !important" in feuille                # boîtes blanches


def test_degrade_utilise_les_couleurs_de_la_palette_eclaircies():
    assert pres.eclaircir("#08415c", 0) == "#08415c" and pres.eclaircir("#08415c", 1) == "#ffffff"
    degrade = pres.degrade_fond()
    for couleur in pres.ORDRE_DEGRADE:
        assert pres.eclaircir(couleur) in degrade
        assert pres.eclaircir(couleur) != couleur               # éclaircies, pas pures


def test_texte_du_materiau_b_plus_fonce_que_le_cotton_rose_pour_etre_lisible():
    assert pres.THEME["texte_matieres"][0] == pres.PACIFIC_CYAN
    assert pres.assombrir("#ffffff", 0) == "#ffffff" and pres.assombrir("#ffffff", 1) == "#000000"
    assert pres.THEME["texte_matieres"][1] != pres.COTTON_ROSE and "__" not in pres.css()


def test_palette_de_l_utilisateur():
    assert (pres.YALE_BLUE, pres.TOMATO_JAM, pres.COTTON_ROSE, pres.PACIFIC_CYAN, pres.AQUAMARINE) == (
        "#08415c", "#cc2936", "#ebbab9", "#388697", "#b5ffe1")
    assert pres.THEME["matieres"] == (pres.PACIFIC_CYAN, pres.COTTON_ROSE)    # couleurs des deux matériaux
