"""
Tests des liens pré-remplis (lien.py).

Lancer depuis la racine du projet :  python3 -m pytest -q
"""
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

import pytest

# ----------------------------------------------------------------------------
# VARIABLES
# ----------------------------------------------------------------------------
RACINE = Path(__file__).resolve().parent.parent
URL_APP = "https://statique2dynamique.streamlit.app/"
# Valeurs complètes de la fiche INIES 50632 (réponse du serveur), DVR 50 ans
VALEURS_50632 = [4.23655, 1.51718, -0.445, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -0.445, 15.52815, 20.83689, -0.43737]
TEXTE_50632 = ",".join(str(v) for v in VALEURS_50632)

sys.path.insert(0, str(RACINE))
import acv_inies_a2 as acv  # noqa: E402
import lien  # noqa: E402


def parametres_de(url: str) -> dict:
    return dict(parse_qsl(urlparse(url).query))


def lien_valide(**modifs) -> dict:
    base = {"v": "1", "a_nom": "Dalle", "a_id": "50632", "a_dvr": "50", "a_v": TEXTE_50632}
    base.update(modifs)
    return {k: v for k, v in base.items() if v is not None}


# ----------------------------------------------------------------------------
# 1) Fabriquer un lien
# ----------------------------------------------------------------------------
def test_lien_part_de_l_adresse_de_l_application():
    valeurs = acv.ValeursA2(*VALEURS_50632)
    url = lien.construire_lien(URL_APP, 0, "Dalle Bois-Béton 15 cm", 50632, 50, valeurs)
    assert url.startswith(URL_APP + "?v=1&a_nom=Dalle%20Bois-B%C3%A9ton%2015%20cm&a_id=50632&a_dvr=50&a_v=")
    assert " " not in url and len(url) < 400


def test_lien_du_materiau_b_utilise_le_prefixe_b():
    url = lien.construire_lien(URL_APP, 1, "Autre", None, 30, acv.ValeursA2(*VALEURS_50632))
    p = parametres_de(url)
    assert set(p) == {"v", "b_nom", "b_dvr", "b_v"}              # pas d'identifiant, pas de préfixe a


def test_lien_sans_nom_ni_identifiant():
    p = parametres_de(lien.construire_lien(URL_APP, 0, "  ", None, 50, acv.ValeursA2(*VALEURS_50632)))
    assert set(p) == {"v", "a_dvr", "a_v"}


def test_lien_jamais_en_notation_scientifique():
    valeurs = acv.lire_valeurs_inies("1.54e+1 5.14e+0 0 5.95e-3 0 0 0 0 0 5.95e-3 4.23e-1 2.10e+1 -9.65e-2")
    texte = parametres_de(lien.construire_lien(URL_APP, 0, "x", None, 50, valeurs))["a_v"]
    assert "e" not in texte.lower() and "0.00595" in texte


@pytest.mark.parametrize("nom", ["Dalle Bois-Béton 15 cm", "Mur « béton » & co = 100 % ?", "a/b#c;d+e", "日本語 ñ ü", "x" * 200])
def test_aller_retour_nom_et_valeurs(nom):
    """Ce qu'on met dans un lien est exactement ce qu'on en relit (les 13 valeurs, le nom, la DVR, l'identifiant)."""
    valeurs = acv.ValeursA2(*VALEURS_50632)
    url = lien.construire_lien(URL_APP, 0, nom, 50632, 50, valeurs)
    materiaux, erreurs = lien.lire_lien(parametres_de(url))
    assert erreurs == [] and len(materiaux) == 1
    m = materiaux[0]
    assert m.valeurs == valeurs and m.dvr == 50 and m.identifiant == 50632
    assert m.nom == lien.nettoyer_nom(nom) and len(m.nom) <= lien.LONGUEUR_NOM_MAX


def test_le_resultat_est_le_meme_avec_ou_sans_lien():
    """Le matériau retrouvé par le lien donne exactement le même résultat que le matériau d'origine."""
    valeurs = acv.ValeursA2(*VALEURS_50632)
    m = lien.lire_lien(parametres_de(lien.construire_lien(URL_APP, 0, "x", None, 50, valeurs)))[0][0]
    assert acv.calculer_depuis_inies(m.texte_inies(), m.dvr).dynamique_total == pytest.approx(
        acv.calculer_acv_dynamique(valeurs, 50).dynamique_total)
    assert acv.calculer_acv_dynamique(m.valeurs, m.dvr).dynamique_total == pytest.approx(14.1243, abs=1e-3)


# ----------------------------------------------------------------------------
# 2) Lire un lien
# ----------------------------------------------------------------------------
def test_aucun_parametre_donne_aucun_materiau_ni_erreur():
    assert lien.lire_lien({}) == ([], [])
    assert lien.lire_lien({"autre": "x", "utm_source": "y"}) == ([], [])     # paramètres étrangers ignorés


def test_les_deux_materiaux_dans_un_meme_lien():
    p = lien_valide(b_dvr="30", b_v=TEXTE_50632, b_nom="Second")
    materiaux, erreurs = lien.lire_lien(p)
    assert erreurs == [] and [m.lettre for m in materiaux] == ["A", "B"] and materiaux[1].dvr == 30


def test_materiau_invalide_ignore_l_autre_est_conserve():
    p = lien_valide(b_dvr="30", b_v="1,2,3")
    materiaux, erreurs = lien.lire_lien(p)
    assert [m.lettre for m in materiaux] == ["A"]
    assert len(erreurs) == 1 and "matériau B" in erreurs[0] and "13 valeurs" in erreurs[0] and "il y en a 3" in erreurs[0]


@pytest.mark.parametrize("modifs, morceau", [
    ({"a_v": None}, "il manque « a_v »"),
    ({"a_dvr": None}, "il manque « a_dvr »"),
    ({"a_dvr": "0"}, "entre 1 et 1000"),
    ({"a_dvr": "1001"}, "entre 1 et 1000"),
    ({"a_dvr": "cinquante"}, "nombre entier"),
    ({"a_dvr": "-5"}, "nombre entier"),
    ({"a_dvr": "50.5"}, "nombre entier"),
    ({"a_dvr": ""}, "nombre entier"),
    ({"a_id": "abc"}, "nombre entier"),
    ({"a_id": "0"}, "au moins 1"),
    ({"a_v": "1,2,3"}, "13 valeurs"),
    ({"a_v": TEXTE_50632 + ",1"}, "13 valeurs"),
    ({"a_v": TEXTE_50632.replace("1.51718", "abc")}, "n'est pas un nombre"),
    ({"a_v": TEXTE_50632.replace("1.51718", "nan")}, "hors limites"),
    ({"a_v": TEXTE_50632.replace("1.51718", "inf")}, "hors limites"),
    ({"a_v": TEXTE_50632.replace("1.51718", "1e30")}, "hors limites"),
    ({"a_v": "9" * 1500}, "trop long"),
    ({"a_nom": "x" * 1500}, "trop long"),
])
def test_erreurs_claires_en_francais(modifs, morceau):
    materiaux, erreurs = lien.lire_lien(lien_valide(**modifs))
    assert materiaux == [] and len(erreurs) == 1
    assert erreurs[0].startswith("Lien incomplet ou invalide pour le matériau A") and morceau in erreurs[0]


@pytest.mark.parametrize("format_recu", [None, "", "2", "0", "abc"])
def test_format_inconnu_refuse_proprement(format_recu):
    materiaux, erreurs = lien.lire_lien(lien_valide(v=format_recu))
    assert materiaux == [] and len(erreurs) == 1 and "bon format" in erreurs[0]


def test_nom_nettoye():
    assert lien.nettoyer_nom("  a \n\t b\x00c  ") == "a b c"
    assert len(lien.nettoyer_nom("é" * 500)) == lien.LONGUEUR_NOM_MAX


def test_lien_ne_contenant_que_le_format():
    materiaux, erreurs = lien.lire_lien({"v": "1"})
    assert materiaux == [] and erreurs == ["Ce lien ne contient aucun matériau."]
