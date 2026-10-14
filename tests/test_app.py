"""
Tests de l'interface Streamlit (sans navigateur) avec streamlit.testing.

Lancer :  python3 -m pytest -q
"""
import json
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
URL_METHODE = "linkedin.com/posts/meunierguillaume_fdes-re2020-opensource-activity-7064102175945175040-cOPY"

sys.path.insert(0, str(RACINE))
import catalogue as cat  # noqa: E402
import presentation as pres  # noqa: E402
import acv_inies_a2 as acv  # noqa: E402

# Premier matériau du catalogue (le fichier peut évoluer : les tests ne figent pas ses valeurs)
PREMIER = cat.charger_catalogue()[0]
NOM_PREMIER = PREMIER.nom
RESULTAT_PREMIER = f">{pres.fr(acv.calculer_acv_dynamique(PREMIER.valeurs, PREMIER.dvr).dynamique_total)}<"

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


# ----------------------------------------------------------------------------
# Page d'accueil, titre, étapes, pied de page
# ----------------------------------------------------------------------------
def test_page_vide_sans_erreur():
    app = nouvelle_app()
    assert not app.exception
    assert any("Collez la ligne INIES" in m.value for m in app.info)


def test_titre_et_textes_d_introduction():
    page = texte_page(nouvelle_app())
    assert "Comprendre <span class=\"mot\">RÉELLEMENT</span> l'impact carbone d'un matériau</h1>" in page
    assert '<div class="sous-titre">ACV dynamique RE2020</div>' in page
    assert "Cet outil part des chiffres INIES et applique cette méthode dynamique réglementaire RE2020" in page
    assert "Un kilo de CO₂ émis tout de suite pèse plus qu'un kilo émis dans 50 ans" in page
    assert "n'est pas de classer les matériaux" in page and "trajectoire de neutralité climatique de 2050" in page
    assert "Comparer" not in page


def test_titre_de_la_section_resultats_au_pluriel():
    page = texte_page(nouvelle_app())
    assert '<h2 class="titre-section">Résultats</h2>' in page


def test_le_mot_comparaison_est_toujours_suivi_de_carbone():
    """Partout (textes de l'app, README, historique), « comparaison » est précisé en « comparaison carbone »."""
    for nom in ("app.py", "README.md", "CHANGELOG.md", "acv_inies_a2.py", "presentation.py"):
        texte = " ".join((RACINE / nom).read_text(encoding="utf-8").split())
        assert not re.findall(r"[Cc]omparaisons?(?! carbone)", texte), nom


def test_texte_de_lecture_stockc():
    app = nouvelle_app()
    page = "\n".join(m.value for m in app.markdown)
    assert "un résultat négatif traduit le stockage temporaire du carbone dans les" in page.replace("\n  ", " ")
    assert "l'indicateur StockC de la RE2020 suit ce stockage" in page.replace("\n  ", " ")
    assert "la comparaison carbone n'a de sens qu'à ce prix" in page.replace("\n  ", " ")


def test_etapes_la_norme_a2_n_est_plus_une_etape():
    app = nouvelle_app()
    assert any(e.label == "Comment faire ? (3 étapes)" for e in app.expander)
    page = texte_page(app)
    assert "vérifiez que la norme est" not in page and "ne traite pas la norme +A1" not in page
    assert "Dans l'onglet **« Indicateurs »**, **copiez la ligne « Réchauffement climatique »**" in page
    assert "Toujours dans" not in page
    assert page.count("\n1. ") + page.count("\n2. ") + page.count("\n3. ") >= 3 and "\n4. " not in page


def test_pied_de_page_lien_vers_la_methode():
    page = texte_page(nouvelle_app())
    assert f"[Méthode issue du classeur Excel « ACV_Dynamique_INIES_V2 » de Guillaume Meunier](https://www.{URL_METHODE})" in page
    assert "Version 3.3.0 du 2026-10-14" in page


# ----------------------------------------------------------------------------
# Exemple, catalogue, résultats
# ----------------------------------------------------------------------------
def test_exemple_affiche_les_deux_resultats_le_graphique_et_les_tableaux():
    app = nouvelle_app()
    bouton(app, "Essayer avec un exemple").click().run()
    assert not app.exception
    page = texte_page(app)
    assert page.count('class="carte"') == 2
    assert RESULTAT_PREMIER in page                      # premier matériau du catalogue
    assert "a le résultat le plus bas" in page
    assert len(app.get("plotly_chart")) == 1             # un seul graphique
    assert any("Cette comparaison carbone n'a de sens" in c.value for c in app.caption)
    assert page.count('class="tab-etapes') == 2          # un tableau des étapes par matériau
    assert "A4-A5 Édification" in page and "B1-B7 Exploitation" in page


def test_choisir_un_materiau_du_catalogue_remplit_les_champs():
    app = nouvelle_app()
    liste = app.selectbox(key="cat_0")
    assert liste.options[0].startswith("— choisir —") or liste.options[0] == "— choisir —" or "choisir" in liste.options[0]
    liste.select_index(1).run()
    assert not app.exception
    assert app.text_input(key="nom_0").value == NOM_PREMIER
    assert app.number_input(key="id_0").value == PREMIER.id and app.number_input(key="dvr_0").value == PREMIER.dvr
    assert app.text_area(key="texte_0").value == PREMIER.texte_inies()
    page = texte_page(app)
    assert RESULTAT_PREMIER in page and "13 valeurs lues" in page
    assert "export du " in app.selectbox(key="cat_0").options[1]      # la date d'export est affichée


def test_bloc_pour_enregistrer_un_materiau():
    app = nouvelle_app()
    app.text_input(key="nom_0").set_value("Mon matériau")
    app.number_input(key="id_0").set_value(46517)
    app.text_area(key="texte_0").set_value(EXEMPLE_46517).run()
    blocs = [c.value for c in app.code]
    assert len(blocs) == 1
    entree = json.loads(blocs[0])
    assert entree["nom"] == "Mon matériau" and entree["id"] == 46517 and entree["dvr"] == 50
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", entree["date_export"])
    assert entree["valeurs"]["production"] == 15.4 and entree["acv_dynamique_attendu"] == pytest.approx(20.733, abs=1e-3)
    sans_chaines = re.sub(r'"[^"]*"', "", blocs[0])
    assert not re.search(r"\d[eE][+-]?\d", sans_chaines)       # pas de notation scientifique dans les valeurs


def test_une_seule_ligne_collee():
    app = nouvelle_app()
    app.text_area(key="texte_0").set_value(EXEMPLE_46517).run()
    assert not app.exception
    page = texte_page(app)
    assert page.count('class="carte"') == 1 and page.count('class="tab-etapes') == 1
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
    assert app.text_input(key="nom_0").value == "" and app.selectbox(key="cat_0").value is None


def test_case_statique_ajoute_les_courbes_pointillees():
    app = nouvelle_app()
    bouton(app, "Essayer avec un exemple").click().run()
    case = app.checkbox(key="avec_statique")
    assert case.value is False
    def nb_courbes(a):
        figure = json.loads(a.get("plotly_chart")[0].proto.spec)
        return len([t for t in figure["data"] if t.get("mode") == "lines"])
    assert nb_courbes(app) == 2
    case.check().run()
    assert not app.exception and nb_courbes(app) == 4


def test_boutons_de_telechargement_csv():
    app = nouvelle_app()
    assert not any("CSV" in str(getattr(b, "label", "")) for b in app.button)
    bouton(app, "Essayer avec un exemple").click().run()
    assert not app.exception
    page = texte_page(app)
    assert "Pour enregistrer le graphique en image" in page
