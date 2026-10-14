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
TEXTE_CLT = "-6.04e+2\t1.38e+1\t0\t0\t0\t0\t0\t0\t0\t0\t7.58e+2\t1.67e+2\t-2.33e+2"
ACV_A_ATTENDUE = 36.72175        # contrôlé avec l'Excel (arrondi : 36,722)

sys.path.insert(0, str(RACINE))
import acv_inies_a2 as acv  # noqa: E402
import presentation as pres  # noqa: E402


def serie(indice: int, nom: str, texte: str, dvr: int) -> dict:
    r = acv.calculer_depuis_inies(texte, dvr)
    return {"indice": indice, "nom": nom, "annees": list(r.annees), "cumul": r.cumul_dynamique(),
            "cumul_statique": r.cumul_statique()}


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


def test_echelle_y_suit_le_maximum_reellement_trace():
    """Le haut de l'axe se cale sur le maximum tracé : un grand côté négatif ne gonfle plus le côté positif."""
    bas, haut, pas = pres.echelle_y(-590.2, 20.7)              # exemple CLT + fiche B, courbes dynamiques
    assert haut == 25 and bas == -675 and pas == 100
    bas, haut, pas = pres.echelle_y(-591.0, 89.3)              # avec les courbes statiques (maximum 89,3)
    assert 89.3 * pres.MARGE_AXE <= haut <= 89.3 * pres.MARGE_AXE + pas / pres.SOUS_PAS_ARRONDI
    assert haut < 150                                          # et non plus 400
    bas, haut, pas = pres.echelle_y(0.0, 36.7)                 # que du positif : un petit côté négatif suffit
    assert haut >= 36.7 * pres.MARGE_AXE and 0 < -bas <= pres.PART_MIN_COTE * (haut - bas) + pas / pres.SOUS_PAS_ARRONDI
    assert pres.echelle_y(-286.75, 12.0)[0] <= -286.75 * pres.MARGE_AXE
    assert pres.echelle_y(0, 0)[1] > 0                         # aucune donnée : échelle valide


@pytest.mark.parametrize("minimum, maximum", [(0, 0.3), (0, 3), (-5, 36.7), (-286.75, 99), (0, 540), (-12345, 40), (-590.2, 20.7)])
def test_echelle_y_graduations_rondes_bornes_au_quart_de_pas(minimum, maximum):
    bas, haut, pas = pres.echelle_y(minimum, maximum)
    assert bas <= minimum * pres.MARGE_AXE + 1e-9 and haut >= maximum * pres.MARGE_AXE - 1e-9   # tout tient
    assert bas < 0 < haut                                                 # zéro visible
    mantisse = pas / 10 ** math.floor(math.log10(pas))
    assert min(abs(mantisse - m) for m in (1, 2, 5)) < 1e-9, pas          # pas rond : 1, 2 ou 5 × 10^k
    sous_pas = pas / pres.SOUS_PAS_ARRONDI
    for borne in (bas, haut):                                             # bornes au quart de pas, au plus près des données
        assert abs(borne / sous_pas - round(borne / sous_pas)) < 1e-6
    if maximum > 0:                                                       # haut au plus près du maximum tracé
        assert haut - maximum * pres.MARGE_AXE < sous_pas + 1e-9
    assert 3 <= (haut - bas) / pas <= 14                                  # ni trop ni trop peu de graduations


def test_format_graduations():
    assert pres.format_graduations(10) == ",.0f"
    assert pres.format_graduations(0.5) == ",.1f"


def test_positions_etiquettes():
    assert pres.positions_etiquettes([10.0, 50.0], 5) == [10.0, 50.0]              # loin : inchangées
    deux = pres.positions_etiquettes([20.0, 20.5], 5)                              # proches : écartées, ordre conservé
    assert deux[1] - deux[0] == pytest.approx(5) and sum(deux) / 2 == pytest.approx(20.25)
    trois = pres.positions_etiquettes([10.0, 12.0, 14.0], 5)                       # groupe étalé
    assert [round(b - a, 6) for a, b in zip(trois, trois[1:])] == [5, 5]
    chaine = pres.positions_etiquettes([30.0, 20.0, 24.0, 21.0], 5)                # ordre d'entrée quelconque
    tries = sorted(chaine)
    assert all(b - a >= 5 - 1e-9 for a, b in zip(tries, tries[1:]))
    assert pres.positions_etiquettes([], 5) == []


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

    bas, haut = figure.layout.yaxis.range
    assert bas < 0 < haut                                                   # zéro toujours visible
    assert all(bas <= v <= haut for s in series for v in s["cumul"])        # les courbes tiennent dans l'axe


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
    hauteurs = sorted(an.y for an in figure.layout.annotations if an.text == "<b>36,7</b>")
    bas, haut = figure.layout.yaxis.range
    assert hauteurs[1] - hauteurs[0] == pytest.approx(pres.ECART_MIN_ETIQUETTES * (haut - bas))


def test_echelle_qui_suit_les_donnees_affichees():
    a = serie(0, "A", TEXTE_A, 100)
    sans = pres.figure_cumul([a]).layout.yaxis.range
    avec = pres.figure_cumul([a], avec_statique=True).layout.yaxis.range
    assert avec[1] >= sans[1]                                              # le statique (plus haut) élargit l'échelle
    petit = pres.figure_cumul([serie(1, "B", TEXTE_B, 50)]).layout.yaxis.range
    assert petit[1] < sans[1]                                              # une courbe plus basse : échelle resserrée


def test_filigrane_vertical_s_il_y_a_la_place_sinon_horizontal():
    # CLT + fiche B : le côté positif est mince (25 sur 700) -> ÉMISSIONS horizontal, SÉQUESTRATION vertical
    figure = pres.figure_cumul([serie(0, "A", TEXTE_CLT, 100), serie(1, "B", TEXTE_B, 50)])
    emissions = next(a for a in figure.layout.annotations if a.text == f"<b>{pres.TEXTE_EMISSIONS}</b>")
    sequestration = next(a for a in figure.layout.annotations if a.text == f"<b>{pres.TEXTE_SEQUESTRATION}</b>")
    assert emissions.textangle == 0 and emissions.yanchor == "bottom" and emissions.y == 0
    assert sequestration.textangle == -90
    # courbe équilibrée (de −50 à +50) : les deux mots sont verticaux
    equilibree = {"indice": 0, "nom": "E", "annees": list(range(51)), "cumul": [v - 50.0 for v in range(0, 101, 2)],
                  "cumul_statique": [0.0] * 51}
    figure = pres.figure_cumul([equilibree])
    mots = (f"<b>{pres.TEXTE_EMISSIONS}</b>", f"<b>{pres.TEXTE_SEQUESTRATION}</b>")
    assert {a.textangle for a in figure.layout.annotations if a.text in mots} == {-90}
    # courbe uniquement positive : SÉQUESTRATION n'a pas la place, il passe en horizontal sous zéro
    positive = pres.figure_cumul([serie(0, "A", TEXTE_A, 100)])
    seq = next(a for a in positive.layout.annotations if a.text == mots[1])
    assert seq.textangle == 0 and seq.yanchor == "top"


def test_la_legende_a_toujours_la_place_de_s_afficher():
    series = [serie(0, "A", TEXTE_A, 100), serie(1, "B", TEXTE_B, 50)]
    deux = pres.figure_cumul(series).layout
    quatre = pres.figure_cumul(series, avec_statique=True).layout
    assert quatre.margin.t - deux.margin.t == 2 * pres.HAUTEUR_LIGNE_LEGENDE      # une ligne de légende par courbe
    assert quatre.height - deux.height == 2 * pres.HAUTEUR_LIGNE_LEGENDE          # la zone des courbes garde sa hauteur
    assert deux.height - deux.margin.t - deux.margin.b == pres.HAUTEUR_ZONE_TRACE


def test_courbes_statiques_en_option():
    series = [serie(0, "A", TEXTE_A, 100), serie(1, "B", TEXTE_B, 50)]
    sans = pres.figure_cumul(series)
    avec = pres.figure_cumul(series, avec_statique=True)
    assert len([t for t in sans.data if t.mode == "lines"]) == 2
    traits = [t for t in avec.data if t.mode == "lines"]
    assert len(traits) == 4
    statiques = [t for t in traits if t.line.dash == "dot"]
    assert len(statiques) == 2 and all(t.name.endswith("— statique") for t in statiques)
    assert all(t.line.width == pres.EPAISSEUR_STATIQUE for t in statiques)
    textes = [a.text for a in avec.layout.annotations]
    for s in series:                                                       # valeur finale statique affichée
        assert f"<b>{pres.fr(s['cumul_statique'][-1])}</b>" in textes


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
    assert ".st-key-graphique" in feuille and "width: 100%" in feuille   # graphique plafonné mais pleine largeur sur petit écran
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
