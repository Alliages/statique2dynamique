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
import lien  # noqa: E402
import presentation as pres  # noqa: E402
import acv_inies_a2 as acv  # noqa: E402

# Premier matériau du catalogue (le fichier peut évoluer : les tests ne figent pas ses valeurs)
PREMIER = cat.charger_catalogue()[0]
NOM_PREMIER = PREMIER.nom
RESULTAT_PREMIER = f">{pres.fr(acv.calculer_acv_dynamique(PREMIER.valeurs, PREMIER.dvr).dynamique_total)}<"

sys.path.insert(0, str(RACINE))


def nouvelle_app(**parametres) -> AppTest:
    """Application lancée, avec d'éventuels paramètres d'adresse (ex. materiaux="2")."""
    app = AppTest.from_file(FICHIER_APP, default_timeout=DELAI_MAX)
    for cle, valeur in parametres.items():
        app.query_params[cle] = valeur
    app.run()
    return app


def app_deux_materiaux() -> AppTest:
    """Application avec deux matériaux."""
    return nouvelle_app(materiaux="2")


def a_le_champ(app: AppTest, cle: str) -> bool:
    """Vrai si le champ texte de cette clé est affiché."""
    return any(w.key == cle for w in app.text_input)


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
    assert "Comprendre l'impact <span class=\"mot\">carbone</span> d'un matériau</h1>" in page
    assert '<div class="sous-titre">L\'ACV dynamique dans la RE2020</div>' in page
    assert "Cet outil part des chiffres INIES et applique la méthode dynamique réglementaire RE2020" in page
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
    assert "la comparaison carbone n'a de sens qu'à ce prix" not in page.replace("\n  ", " ")
    page_deux = "\n".join(m.value for m in app_deux_materiaux().markdown)
    assert "la comparaison carbone n'a de sens qu'à ce prix" in page_deux.replace("\n  ", " ")


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
    assert f"Version {acv.VERSION} du {acv.DATE_VERSION}" in page and acv.VERSION == "4.0.3"


# ----------------------------------------------------------------------------
# Exemple, catalogue, résultats
# ----------------------------------------------------------------------------
def test_exemple_affiche_les_deux_resultats_le_graphique_et_les_tableaux():
    app = app_deux_materiaux()
    bouton(app, "Essayer avec un exemple").click().run()
    assert not app.exception
    page = texte_page(app)
    assert page.count('class="carte"') == 2
    assert RESULTAT_PREMIER in page                      # premier matériau du catalogue
    assert "l'écart entre les deux matériaux est de" in page
    assert len(app.get("plotly_chart")) == 1             # un seul graphique
    assert any("Attention, une comparaison carbone n'a de sens" in c.value for c in app.caption)
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
    blocs = [c.value for c in app.code if c.language == "json"]      # (l'autre bloc est le lien pré-rempli)
    assert len(blocs) == 1
    entree = json.loads(blocs[0])
    assert entree["nom"] == "Mon matériau" and entree["id"] == 46517 and entree["dvr"] == 50
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", entree["date_export"])
    assert entree["valeurs"]["production"] == 15.4 and entree["acv_dynamique_attendu"] == pytest.approx(20.733, abs=1e-3)
    sans_chaines = re.sub(r'"[^"]*"', "", blocs[0])
    assert not re.search(r"\d[eE][+-]?\d", sans_chaines)       # pas de notation scientifique dans les valeurs


def test_une_seule_ligne_collee_en_mode_deux_materiaux():
    app = app_deux_materiaux()
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


# Un seul matériau : l'exemple remplit aussi le détail du changement climatique, donc 4 courbes (total, fossile,
# biogénique, occupation des sols) et une seule courbe statique (celle du total). Deux matériaux : une courbe chacun.
@pytest.mark.parametrize("parametres, nb, nb_avec_statique", [({}, 4, 5), ({"materiaux": "2"}, 2, 4)])
def test_case_statique_ajoute_les_courbes_pointillees(parametres, nb, nb_avec_statique):
    app = nouvelle_app(**parametres)
    bouton(app, "Essayer avec un exemple").click().run()
    case = app.checkbox(key="avec_statique")
    assert case.value is False
    def nb_courbes(a):
        figure = json.loads(a.get("plotly_chart")[0].proto.spec)
        return len([t for t in figure["data"] if t.get("mode") == "lines"])
    assert nb_courbes(app) == nb
    case.check().run()
    assert not app.exception and nb_courbes(app) == nb_avec_statique


def test_boutons_de_telechargement_csv():
    app = nouvelle_app()
    assert not any("CSV" in str(getattr(b, "label", "")) for b in app.button)
    bouton(app, "Essayer avec un exemple").click().run()
    assert not app.exception
    page = texte_page(app)
    assert "Pour enregistrer le graphique en image" in page


# ----------------------------------------------------------------------------
# Liens pré-remplis
# ----------------------------------------------------------------------------
VALEURS_50632 = "4.23655,1.51718,-0.445,0.0,0.0,0.0,0.0,0.0,0.0,-0.445,15.52815,20.83689,-0.43737"


def app_avec_parametres(**parametres) -> AppTest:
    app = AppTest.from_file(FICHIER_APP, default_timeout=DELAI_MAX)
    for cle, valeur in parametres.items():
        app.query_params[cle] = valeur
    app.run()
    return app


def test_lien_prerempli_remplit_le_materiau_et_calcule():
    app = app_avec_parametres(v="1", a_nom="Dalle Bois-Béton 15 cm", a_id="50632", a_dvr="50", a_v=VALEURS_50632)
    assert not app.exception and not app.error
    assert app.text_input(key="nom_0").value == "Dalle Bois-Béton 15 cm"
    assert app.number_input(key="id_0").value == 50632 and app.number_input(key="dvr_0").value == 50
    page = texte_page(app)
    assert ">14,1<" in page                                          # ACV dynamique de la fiche 50632
    assert any("Lien lu : matériau pré-rempli." in s.value for s in app.success)
    assert not a_le_champ(app, "nom_1")                             # un lien A seul garde un seul matériau


def test_lien_prerempli_pour_le_materiau_b():
    app = app_avec_parametres(v="1", b_nom="Second", b_dvr="30", b_v=VALEURS_50632)
    assert app.text_input(key="nom_1").value == "Second" and app.number_input(key="dvr_1").value == 30
    assert app.text_input(key="nom_0").value == ""
    assert any("Lien lu : matériau B pré-rempli." in s.value for s in app.success)
    assert dict(app.query_params) == {"materiaux": "2"}


def test_lien_invalide_affiche_une_erreur_claire_sans_planter():
    app = app_avec_parametres(v="1", a_dvr="0", a_v="1,2,3")
    assert not app.exception
    assert any("Lien incomplet ou invalide pour le matériau A" in e.value for e in app.error)
    assert app.text_input(key="nom_0").value == "" and not any("Lien lu" in x.value for x in app.success)


def test_lien_d_un_autre_format_est_refuse():
    app = app_avec_parametres(v="2", a_dvr="50", a_v=VALEURS_50632)
    assert any("bon format" in e.value for e in app.error)


def test_nom_d_un_lien_est_echappe():
    app = app_avec_parametres(v="1", a_nom="<script>alert(1)</script>", a_dvr="50", a_v=VALEURS_50632)
    page = texte_page(app)
    assert "<script>" not in page and "&lt;script&gt;" in page


def test_le_lien_n_est_applique_qu_une_fois():
    """Après lecture, les paramètres sont retirés de l'adresse : une modification ultérieure n'est pas écrasée."""
    app = app_avec_parametres(v="1", a_nom="Dalle", a_dvr="50", a_v=VALEURS_50632)
    assert len(app.query_params) == 0
    app.number_input(key="dvr_0").set_value(20).run()
    assert app.number_input(key="dvr_0").value == 20 and not any("Lien lu" in x.value for x in app.success)


def test_bouton_lien_sous_la_fiche_se_relit_a_l_identique():
    app = nouvelle_app()
    app.text_input(key="nom_0").set_value("Mon matériau")
    app.number_input(key="id_0").set_value(46517)
    app.text_area(key="texte_0").set_value(EXEMPLE_46517).run()
    assert any(e.label == "🔗 Copier le lien de ce matériau" for e in app.expander)
    liens = [c.value for c in app.code if c.value.startswith("https://statique2dynamique.streamlit.app/?")]
    assert len(liens) == 1
    from urllib.parse import parse_qsl, urlparse
    materiaux, erreurs = lien.lire_lien(dict(parse_qsl(urlparse(liens[0]).query)))
    assert erreurs == [] and materiaux[0].nom == "Mon matériau" and materiaux[0].identifiant == 46517
    assert materiaux[0].dvr == 50 and materiaux[0].valeurs.production == pytest.approx(15.4)


def test_pas_de_bouton_lien_tant_que_les_valeurs_ne_sont_pas_lues():
    app = nouvelle_app()
    assert not any(e.label == "🔗 Copier le lien de ce matériau" for e in app.expander)


# ----------------------------------------------------------------------------
# Interface à un ou deux matériaux
# ----------------------------------------------------------------------------
def test_par_defaut_un_seul_materiau_sans_trace_du_b():
    app = nouvelle_app()
    assert not app.exception
    assert a_le_champ(app, "nom_0") and not a_le_champ(app, "nom_1")
    page = texte_page(app)
    assert '<div class="bandeau mat-A">Matériau</div>' in page and '"bandeau mat-B"' not in page
    assert "Matériau A" not in page and "matériau B" not in page
    assert not any(b.label == "Revenir à un seul matériau" for b in app.button)


def test_exemple_en_mode_un_materiau():
    app = nouvelle_app()
    bouton(app, "Essayer avec un exemple").click().run()
    assert not app.exception
    page = texte_page(app)
    assert page.count('class="carte"') == 1 and RESULTAT_PREMIER in page
    # l'exemple remplit aussi le détail du changement climatique : deux graphiques (courbes, puis barres par étape)
    assert page.count('class="tab-etapes') == 1 and len(app.get("plotly_chart")) == 2
    assert "écart entre les deux matériaux" not in page and "omparaison" not in page


def test_une_seule_ligne_collee():
    app = nouvelle_app()
    app.text_area(key="texte_0").set_value(EXEMPLE_46517).run()
    assert not app.exception
    page = texte_page(app)
    assert page.count('class="carte"') == 1 and page.count('class="tab-etapes') == 1
    assert len(app.info) == 0                                       # aucune invitation à remplir un matériau B


def test_mode_deux_materiaux_par_l_adresse():
    app = app_deux_materiaux()
    assert not app.exception
    assert a_le_champ(app, "nom_0") and a_le_champ(app, "nom_1")
    page = texte_page(app)
    assert ">Matériau A</div>" in page and ">Matériau B</div>" in page


@pytest.mark.parametrize("valeur", ["1", "3", "deux", ""])
def test_toute_autre_valeur_de_mode_garde_un_seul_materiau(valeur):
    app = nouvelle_app(materiaux=valeur)
    assert not app.exception and not a_le_champ(app, "nom_1")


def test_bouton_revenir_a_un_seul_materiau():
    app = app_deux_materiaux()
    bouton(app, "Revenir à un seul matériau").click().run()
    assert not app.exception
    assert not a_le_champ(app, "nom_1") and "materiaux" not in app.query_params


def test_lien_avec_a_et_b_ouvre_le_mode_deux_materiaux():
    app = nouvelle_app(v="1", a_nom="Premier", a_dvr="50", a_v=VALEURS_50632,
                       b_nom="Second", b_dvr="30", b_v=VALEURS_50632)
    assert not app.exception and not app.error
    assert app.text_input(key="nom_0").value == "Premier" and app.text_input(key="nom_1").value == "Second"
    assert any("Lien lu : matériaux A et B pré-remplis." in s.value for s in app.success)
    assert texte_page(app).count('class="carte"') == 2
    assert dict(app.query_params) == {"materiaux": "2"}        # paramètres du lien retirés, le mode reste
    app.number_input(key="dvr_1").set_value(20).run()          # une relance garde bien les deux matériaux
    assert a_le_champ(app, "nom_1") and app.number_input(key="dvr_1").value == 20


def test_mode_de_base_saisie_un_tiers_resultats_deux_tiers_graphique_sous_le_resultat():
    app = nouvelle_app()
    bouton(app, "Essayer avec un exemple").click().run()
    assert not app.exception
    saisie = [c for c in app.columns if c.proto.weight == pytest.approx(1 / 3)]
    resultats = [c for c in app.columns if c.proto.weight == pytest.approx(2 / 3)]
    assert len(saisie) == 1 and len(resultats) == 1
    assert any(w.key == "nom_0" for w in saisie[0].text_input)
    colonne = resultats[0]
    assert any('class="carte"' in m.value for m in colonne.markdown)            # le résultat...
    assert len(colonne.get("plotly_chart")) == 2                                  # ...et les graphiques dessous
    # le détail du changement climatique : sous la saisie du matériau, dans la même colonne de gauche
    cles = [w.key for w in saisie[0].text_area]
    assert cles == ["texte_0", "texte_detail"]
    assert any('class="tab-etapes' in m.value for m in colonne.markdown)


def test_readme_sans_tampermonkey_notice_dans_son_dossier():
    readme = (RACINE / "README.md").read_text(encoding="utf-8")
    assert "tampermonkey" not in readme.lower() and "materiaux=2" not in readme and "caché" not in readme
    notice = (RACINE / "tampermonkey" / "infos.txt").read_text(encoding="utf-8")
    assert "acv_inies.user.js" in notice and "INSTALLATION" in notice and "?materiaux=2" in notice


# ----------------------------------------------------------------------------
# Détail du changement climatique : les 4 lignes INIES d'un seul matériau
# ----------------------------------------------------------------------------
# Les 4 lignes du panneau CLT, comme copiées depuis INIES (celles du matériau 33806 du catalogue)
QUATRE_LIGNES = "\n".join([
    "Changement climatique - total (kg CO2 eq.)\t-6.04e+2\t1.38e+1\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t7.58e+2\t1.67e+2\t-2.33e+2",
    "Changement climatique - fossil (kg CO2 eq.)\t1.03e+2\t1.35e+1\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t3.33e+1\t1.50e+2\t-2.25e+2",
    "Changement climatique - biogénique (kg CO2 eq.)\t-7.08e+2\t3.06e-1\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t7.24e+2\t1.67e+1\t-8.35e+0",
    "Changement climatique - occupation des sols et transformation de l'occupation des sols (kg CO2 eq.)\t1.03e-1\t4.60e-4\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t4.38e-3\t1.08e-1\t-6.01e-2"])
DYNAMIQUE_CLT = -286.75          # Excel (DVR 100 ans)
NOMS_COURBES = ["Total", "Fossile", "Biogénique", "Occupation des sols"]
ECART_ARRONDI_INIES = 4.0        # kg CO2 eq. : INIES arrondit à 3 chiffres significatifs (environ ± 0,5 % de 700)


def figures(app: AppTest) -> list:
    """Les figures Plotly affichées, dans l'ordre."""
    return [json.loads(g.proto.spec) for g in app.get("plotly_chart")]


def app_avec_detail(**parametres) -> AppTest:
    """Application avec le premier matériau du catalogue (CLT) et les 4 lignes collées."""
    app = nouvelle_app(**parametres)
    bouton(app, "Essayer avec un exemple").click().run()
    return app


def test_le_detail_est_sous_la_saisie_du_materiau_a_gauche_et_les_graphiques_a_droite():
    app = nouvelle_app()
    gauche = next(c for c in app.columns if c.proto.weight == pytest.approx(1 / 3))
    assert [w.key for w in gauche.text_area] == ["texte_0", "texte_detail"]      # le nouveau champ, sous le 1er
    assert any("Détail du changement climatique" in m.value for m in gauche.markdown)
    assert not figures(app)                                                      # rien à tracer tant qu'rien n'est collé


def test_pas_de_detail_en_mode_deux_materiaux():
    app = app_deux_materiaux()
    assert not any(w.key == "texte_detail" for w in app.text_area)
    bouton(app, "Essayer avec un exemple").click().run()
    assert not app.exception and len(figures(app)) == 1                          # un seul graphique, comme avant


def test_l_exemple_remplit_le_detail_et_donne_deux_graphiques():
    app = app_avec_detail()
    assert not app.exception
    assert app.text_area(key="texte_detail").value.count("Changement climatique") == 4
    assert any("4 lignes lues" in m.value for m in app.success)
    courbes, barres = figures(app)
    assert [t["name"] for t in courbes["data"] if t.get("mode") == "lines"] == NOMS_COURBES


def test_les_courbes_finissent_sur_le_resultat_dynamique_et_le_total_est_celui_de_la_carte():
    app = app_avec_detail()
    courbes, _ = figures(app)
    fins = {t["name"]: t["y"][-1] for t in courbes["data"] if t.get("mode") == "lines"}
    assert fins["Total"] == pytest.approx(DYNAMIQUE_CLT, abs=1e-6)
    assert fins["Total"] == pytest.approx(acv.calculer_acv_dynamique(PREMIER.valeurs, PREMIER.dvr).dynamique_total)
    # fossile + biogénique + occupation des sols = total, à l'arrondi INIES près
    assert fins["Fossile"] + fins["Biogénique"] + fins["Occupation des sols"] == pytest.approx(fins["Total"], abs=ECART_ARRONDI_INIES)
    assert RESULTAT_PREMIER in texte_page(app)


def test_les_barres_empilent_les_composantes_et_rejoignent_la_fin_des_courbes():
    app = app_avec_detail()
    courbes, barres = figures(app)
    empilees = [t for t in barres["data"] if t["type"] == "bar"]
    assert [t["name"] for t in empilees] == NOMS_COURBES[1:]                    # fossile, biogénique, occupation des sols
    net = next(t for t in barres["data"] if t["type"] == "scatter")
    assert len(net["y"]) == len(acv.ETAPES) + 1                                  # 5 étapes + le total
    assert net["y"][-1] == pytest.approx(DYNAMIQUE_CLT, abs=1e-6)               # la dernière barre = fin de la courbe « total »
    assert sum(net["y"][:-1]) == pytest.approx(net["y"][-1], abs=1e-6)          # les étapes s'additionnent au total
    for i in range(len(net["y"])):                                              # les composantes s'additionnent au net (arrondi INIES)
        assert sum(t["y"][i] for t in empilees) == pytest.approx(net["y"][i], abs=ECART_ARRONDI_INIES)


def test_une_seule_courbe_statique_celle_du_total():
    app = app_avec_detail()
    app.checkbox(key="avec_statique").check().run()
    courbes, _ = figures(app)
    lignes = [t["name"] for t in courbes["data"] if t.get("mode") == "lines"]
    assert lignes == NOMS_COURBES + ["Total — statique"]


def test_le_detail_utilise_la_dvr_du_materiau():
    app = app_avec_detail()
    app.number_input(key="dvr_0").set_value(30).run()
    assert not app.exception
    fin = [t for t in figures(app)[0]["data"] if t.get("name") == "Total"][0]["y"][-1]
    assert fin == pytest.approx(acv.calculer_indicateurs_climat(QUATRE_LIGNES, 30)["total"].dynamique_total)
    assert fin != pytest.approx(DYNAMIQUE_CLT)


def test_lignes_collees_dans_le_desordre_avec_les_libelles_de_colonnes():
    app = nouvelle_app()
    lignes = QUATRE_LIGNES.splitlines()
    en_tete = "Étape de production\nÉtape du processus de construction\nTotal cycle de vie\n"
    app.text_area(key="texte_detail").set_value(en_tete + "\n".join(reversed(lignes))).run()
    assert not app.exception and not app.error
    courbes = figures(app)[0]
    assert [t["name"] for t in courbes["data"] if t.get("mode") == "lines"] == NOMS_COURBES


def test_seules_les_4_lignes_collees_les_graphiques_s_affichent_sans_la_carte():
    app = nouvelle_app()
    app.text_area(key="texte_detail").set_value(QUATRE_LIGNES).run()
    assert not app.exception and len(figures(app)) == 2
    assert 'class="carte"' not in texte_page(app)


@pytest.mark.parametrize("retirer, attendu", [
    (1, "Fossile"), (3, "Occupation des sols"),
])
def test_message_clair_si_une_ligne_manque(retirer, attendu):
    app = nouvelle_app()
    lignes = QUATRE_LIGNES.splitlines()
    app.text_area(key="texte_detail").set_value("\n".join(ligne for i, ligne in enumerate(lignes) if i != retirer)).run()
    assert not app.exception and not figures(app)
    assert any(attendu in e.value for e in app.error)


def test_avertissement_si_les_lignes_ne_s_additionnent_pas():
    app = nouvelle_app()
    fausse = QUATRE_LIGNES.replace("1.03e+2", "9.99e+2")                          # production fossile : 103 -> 999
    app.text_area(key="texte_detail").set_value(fausse).run()
    assert not app.exception and any("ne donne pas le total" in w.value for w in app.warning)


def test_avertissement_si_le_total_n_est_pas_celui_du_materiau():
    app = nouvelle_app()
    app.text_area(key="texte_0").set_value(EXEMPLE_46517).run()                  # un autre matériau...
    app.text_area(key="texte_detail").set_value(QUATRE_LIGNES).run()             # ...et les lignes du CLT
    assert any("ne correspond pas" in w.value for w in app.warning)
    bouton(app, "Essayer avec un exemple").click().run()                          # le bon matériau : plus d'avertissement
    assert not any("ne correspond pas" in w.value for w in app.warning)


def test_tout_effacer_vide_aussi_le_detail():
    app = app_avec_detail()
    bouton(app, "Tout effacer").click().run()
    assert not app.exception and app.text_area(key="texte_detail").value == "" and not figures(app)


def test_choisir_un_autre_materiau_vide_le_detail():
    app = app_avec_detail()
    app.text_area(key="texte_0").set_value(EXEMPLE_46517).run()
    app.text_area(key="texte_detail").set_value(QUATRE_LIGNES).run()
    app.selectbox(key="cat_0").set_value(1).run()                                 # un autre matériau du catalogue remplace la saisie
    assert not app.exception and app.text_area(key="texte_detail").value == ""


def test_le_texte_de_lecture_explique_le_detail_seulement_quand_il_est_affiche():
    avec = " ".join(m.value for m in app_avec_detail().markdown)
    sans = " ".join(m.value for m in nouvelle_app().markdown)
    assert "Les barres sont dynamiques" in avec and "Les barres sont dynamiques" not in sans


# =============================================================================
# 4.0.1 : historique masqué, colonnes du détail du calcul
# =============================================================================
def test_historique_affiche_sans_les_versions_masquees():
    at = AppTest.from_file(str(RACINE / "app.py"), default_timeout=30).run()
    versions = [v for df in at.dataframe for v in (df.value["Version"] if "Version" in df.value else [])]
    assert "4.0.1" in versions and "3.9.0" in versions
    assert not {"3.5.0", "3.6.0", "3.6.1"} & set(versions)
    assert {"3.5.0", "3.6.0", "3.6.1"} <= {v[0] for v in acv.HISTORIQUE_VERSIONS}      # l'historique complet reste


def test_detail_du_calcul_un_materiau_titres_courts():
    at = AppTest.from_file(FICHIER_APP, default_timeout=30).run()
    at.button[0].click().run()                                       # « Essayer avec un exemple »
    colonnes = [list(df.value.columns) for df in at.dataframe if "Phase" in df.value.columns or "Année" in df.value.columns]
    assert ["Phase", "Dynamique RE2020", "Statique E+C-"] in colonnes
    assert ["Année", "Coefficient (art. 11)", "Émissions pondérées", "Cumul"] in colonnes
