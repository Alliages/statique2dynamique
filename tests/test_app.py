"""
Tests de l'interface Streamlit (sans navigateur) avec streamlit.testing.

Lancer :  python3 -m pytest -q
"""
import re
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

# ----------------------------------------------------------------------------
# VARIABLES
# ----------------------------------------------------------------------------
RACINE = Path(__file__).resolve().parent.parent
FICHIER_APP = str(RACINE / "app.py")
DELAI_MAX = 30   # secondes
EXEMPLE_46517 = "1.54e+1\t5.14e+0\t0.00e+0\t5.95e-3\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t5.95e-3\t4.23e-1\t2.10e+1\t-9.65e-2"

sys.path.insert(0, str(RACINE))


def nouvelle_app() -> AppTest:
    app = AppTest.from_file(FICHIER_APP, default_timeout=DELAI_MAX)
    app.run()
    return app


def texte_page(app: AppTest) -> str:
    """Tout le texte affiché (markdown, messages, légendes)."""
    morceaux = [m.value for m in app.markdown] + [m.value for m in app.caption]
    morceaux += [m.value for m in app.success] + [m.value for m in app.error]
    morceaux += [m.value for m in app.warning] + [m.value for m in app.info]
    return "\n".join(morceaux)


def bouton(app: AppTest, libelle: str):
    return next(b for b in app.button if b.label == libelle)


def test_page_vide_sans_erreur():
    app = nouvelle_app()
    assert not app.exception
    assert any("Collez la ligne INIES" in m.value for m in app.info)


def test_exemple_affiche_les_deux_resultats_et_le_total_inies():
    app = nouvelle_app()
    bouton(app, "Essayer avec un exemple").click().run()
    assert not app.exception
    page = texte_page(app)
    assert page.count('class="carte"') == 2
    assert "−286,8" in page            # CLT, DVR 100 : -286,75 de l'Excel, arrondi à 1 décimale
    assert "167,0 kg CO₂ eq." in page or "167" in page   # total INIES affiché en petit
    assert "le résultat le plus bas" in page


def test_une_seule_ligne_collee():
    app = nouvelle_app()
    app.text_area(key="texte_0").set_value(EXEMPLE_46517).run()
    assert not app.exception
    assert texte_page(app).count('class="carte"') == 1
    assert any("Collez la ligne INIES du matériau B" in m.value for m in app.info)


@pytest.mark.parametrize("texte, attendu", [
    ("1.0e+0 2.0e+0 3.0e+0 4.0e+0 5.0e+0 6.0e+0", "+A1"),
    ("n'importe quoi", "Aucun nombre"),
    ("1 2 3", "3 valeurs au lieu de 13"),
])
def test_message_d_erreur_pour_non_expert(texte, attendu):
    app = nouvelle_app()
    app.text_area(key="texte_0").set_value(texte).run()
    assert not app.exception
    assert any(attendu in e.value for e in app.error)


def test_avertissement_si_ligne_incoherente():
    app = nouvelle_app()
    app.text_area(key="texte_0").set_value(EXEMPLE_46517.replace("2.10e+1", "9.90e+1")).run()
    assert any("ne s'additionnent pas" in w.value for w in app.warning)


def test_nom_saisi_est_echappe_dans_le_html():
    app = nouvelle_app()
    app.text_input(key="nom_0").set_value("<b>pirate</b>")
    app.text_area(key="texte_0").set_value(EXEMPLE_46517).run()
    page = texte_page(app)
    assert "<b>pirate</b>" not in page and "&lt;b&gt;pirate&lt;/b&gt;" in page


def test_changement_de_dvr_change_le_resultat():
    app = nouvelle_app()
    app.text_area(key="texte_0").set_value(EXEMPLE_46517).run()
    avant = re.search(r'class="grand">([^<]+)<', texte_page(app)).group(1)
    app.number_input(key="dvr_0").set_value(20).run()
    apres = re.search(r'class="grand">([^<]+)<', texte_page(app)).group(1)
    assert avant != apres


def test_tout_effacer():
    app = nouvelle_app()
    bouton(app, "Essayer avec un exemple").click().run()
    bouton(app, "Tout effacer").click().run()
    assert not app.exception
    assert any("Collez la ligne INIES" in m.value for m in app.info)
