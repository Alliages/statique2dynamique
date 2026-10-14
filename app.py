"""
app.py — Comprendre l'impact carbone d'un matériau : ACV dynamique RE2020 (norme +A2) à partir de la base INIES.

Lancer en local :   streamlit run app.py

Organisation du projet :
    acv_inies_a2.py   le calcul (module autonome, réutilisable ailleurs)
    catalogue.py      lecture de materiaux.json et fabrication d'un nouveau bloc
    presentation.py   nombres français, graphique, tableau des étapes, styles
    app.py            cette interface (aucun calcul ici)
"""
import html
from datetime import datetime

import pandas as pd
import streamlit as st

import acv_inies_a2 as acv
import catalogue as cat
import export
import presentation as pres

# =============================================================================
# VARIABLES (tout ce qui se règle est regroupé ici)
# =============================================================================
TITRE_PAGE = "Comprendre l'impact carbone d'un matériau — L'ACV dynamique dans la RE2020"
ICONE_PAGE = "🏗️"
UNITE = pres.UNITE

# Lien vers la fiche d'un produit à partir de son identifiant ({id} est remplacé).
URL_FICHE_INIES = "https://base-inies.fr/infos-produit/{id}"
URL_SITE_INIES = "https://www.base-inies.fr/"
URL_METHODE = "https://www.linkedin.com/posts/meunierguillaume_fdes-re2020-opensource-activity-7064102175945175040-cOPY"

NB_MATERIAUX = 2
LETTRES = ("A", "B")
DVR_PAR_DEFAUT = 50          # ans
HAUTEUR_ZONE_COLLAGE = 110   # pixels
FUSEAU_HORAIRE = "Europe/Paris"    # pour dater un nouveau matériau
CHOIX_VIDE = "— choisir —"
NOM_IMAGE_GRAPHIQUE = "acv_dynamique_re2020"   # nom du fichier image (icône appareil photo du graphique)

# Exemple chargé par le bouton « Essayer avec un exemple » : A vient du catalogue, B est fictif.
EXEMPLE_B = {
    "nom": "Fiche 46517 (exemple, DVR fictive)", "id": 46517, "dvr": 50,
    "texte": "1.54e+1\t5.14e+0\t0.00e+0\t5.95e-3\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t5.95e-3\t4.23e-1\t2.10e+1\t-9.65e-2"}
PLACEHOLDER_COLLAGE = "Collez ici la ligne « Réchauffement climatique » copiée depuis INIES"

TEXTE_INTRO = """
Cet outil part des chiffres INIES et applique la méthode dynamique réglementaire RE2020 de l'ACV dynamique à votre place. \
Une lecture pédagogique, qui rappelle aussi qu'évaluer un matériau ne se résume jamais au seul carbone.

**Pourquoi « dynamique » ?** Un kilo de CO₂ émis tout de suite pèse plus qu'un kilo émis dans 50 ans. \
La RE2020 applique donc à chaque année un coefficient qui descend de 1 (année 0) à 0,578 (année 50). \
Le résultat diffère ainsi du total affiché dans INIES, qui additionne tout sans pondération.

L'objectif de la RE2020 (et de cet outil) n'est pas de classer les matériaux, mais d'inciter à concevoir des bâtiments \
sobres en carbone, en cohérence avec la trajectoire de neutralité climatique de 2050.
"""

TEXTE_ETAPES = f"""
1. **Trouvez le produit sur INIES** ([base-inies.fr]({URL_SITE_INIES})). Si vous connaissez son identifiant,
   saisissez-le ci-dessous : un bouton ouvre la fiche. Vous pouvez aussi **choisir un matériau déjà enregistré**.
2. Onglet **« Unité fonctionnelle »** : notez la **durée de vie de référence (DVR)**, en années.
3. Dans l'onglet **« Indicateurs »**, **copiez la ligne « Réchauffement climatique »** (toutes les valeurs, de
   « Étape de production » jusqu'à « D - Bénéfices et charges », sans les autres lignes) et collez-la dans la case.

*Attention : l'arrondi affiché par le site INIES peut différer légèrement des valeurs de la FDES.*
"""

TEXTE_LECTURE = f"""
- **Le grand chiffre** est l'ACV dynamique RE2020 : les émissions sur 50 ans, chaque année pondérée par son
  coefficient, **module D inclus**, en {UNITE} pour l'unité fonctionnelle de la fiche.
- **Le petit chiffre** est le total affiché dans INIES (sans pondération, module D à part), pour repère.
- **Le graphique** montre le cumul année après année (en trait plein, le calcul dynamique ; en pointillés, si vous
  cochez la case, le calcul statique E+C- sans pondération, réparti à parts égales sur les années d'utilisation). Au-dessus de zéro, le matériau a émis ; en dessous, il a
  séquestré. Le chiffre au bout de chaque courbe est le résultat final.
- **Le tableau sous le graphique** reprend les chiffres INIES étape par étape, avant toute pondération.
- **Plus le chiffre est bas, mieux c'est :** un résultat négatif traduit le stockage temporaire du carbone dans les
  matériaux biosourcés, qui contribuent ainsi à la décarbonation immédiate de la construction — une contribution au
  climat du bâtiment, sans être un droit à émettre ailleurs (l'indicateur StockC de la RE2020 suit ce stockage).
- **Si la DVR est inférieure à 50 ans**, le produit est remplacé en cours de route : chaque remplacement
  est ajouté, et le dernier n'est compté qu'au prorata de sa durée utile dans les 50 ans.
- **Comparez des produits qui rendent le même service** (même unité fonctionnelle, par exemple 1 m² de mur
  de même performance) : la comparaison carbone n'a de sens qu'à ce prix.
"""

TEXTE_ENREGISTRER = """
Pour garder ce matériau dans le catalogue : copiez le bloc ci-dessous (icône en haut à droite) et ajoutez-le
dans la liste `materiaux` du fichier `materiaux.json`, **avec une virgule entre deux matériaux**.
"""


# =============================================================================
# OUTILS
# =============================================================================
def aujourd_hui():
    """Date du jour à Paris (ou date du serveur si le fuseau est indisponible)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(FUSEAU_HORAIRE)).date()
    except Exception:
        return datetime.now().date()


@st.cache_data(show_spinner=False)
def _catalogue_depuis_fichier(horodatage: float):
    """Lit materiaux.json (relu automatiquement quand le fichier change). Renvoie (liste, message d'erreur)."""
    try:
        return cat.charger_catalogue(), None
    except cat.ErreurCatalogue as erreur:
        return [], str(erreur)


def charger_catalogue():
    """Catalogue des matériaux enregistrés, et message d'erreur éventuel."""
    fichier = cat.FICHIER_PAR_DEFAUT
    return _catalogue_depuis_fichier(fichier.stat().st_mtime if fichier.exists() else 0.0)


def remplir(indice: int, nom: str, identifiant, dvr: int, texte: str) -> None:
    """Remplit les champs d'un matériau (noms de clés utilisés par les champs de saisie)."""
    st.session_state[f"nom_{indice}"] = nom
    st.session_state[f"id_{indice}"] = identifiant
    st.session_state[f"dvr_{indice}"] = dvr
    st.session_state[f"texte_{indice}"] = texte


def choisir_catalogue(indice: int) -> None:
    """Un matériau du catalogue vient d'être choisi dans la liste : on remplit ses champs."""
    choix = st.session_state.get(f"cat_{indice}")
    catalogue, _ = charger_catalogue()
    if choix is not None and choix < len(catalogue):
        m = catalogue[choix]
        remplir(indice, m.nom, m.id, m.dvr, m.texte_inies())


def charger_exemple() -> None:
    """Remplit les deux matériaux avec les exemples (appelé par le bouton)."""
    catalogue, _ = charger_catalogue()
    if catalogue:
        m = catalogue[0]
        remplir(0, m.nom, m.id, m.dvr, m.texte_inies())
        st.session_state["cat_0"] = 0
    else:
        remplir(0, "Fiche 46517 (exemple, DVR 30)", 46517, 30, EXEMPLE_B["texte"])
    remplir(1, EXEMPLE_B["nom"], EXEMPLE_B["id"], EXEMPLE_B["dvr"], EXEMPLE_B["texte"])
    st.session_state["cat_1"] = None


def effacer_tout() -> None:
    """Vide les deux matériaux (appelé par le bouton)."""
    for i in range(NB_MATERIAUX):
        remplir(i, "", None, DVR_PAR_DEFAUT, "")
        st.session_state[f"cat_{i}"] = None


def nom_affiche(saisie: dict) -> str:
    """Nom choisi par l'utilisateur, ou « Matériau A / B » par défaut."""
    return saisie["nom"].strip() or f"Matériau {LETTRES[saisie['indice']]}"


# =============================================================================
# 1) SAISIES — une carte par matériau
# =============================================================================
def saisie_materiau(indice: int, catalogue: list) -> dict:
    """Affiche les champs d'un matériau, lit la ligne collée, et renvoie tout ce qu'il faut pour la suite."""
    saisie = {"indice": indice, "valeurs": None, "resultat": None}

    with st.container(border=True, key=f"boite_{LETTRES[indice]}"):   # la clé donne la classe CSS « st-key-boite_A »
        st.markdown(f'<div class="bandeau mat-{LETTRES[indice]}">Matériau {LETTRES[indice]}</div>', unsafe_allow_html=True)

        if catalogue:
            st.selectbox(
                "Charger un matériau enregistré", options=[None] + list(range(len(catalogue))), key=f"cat_{indice}",
                format_func=lambda k: CHOIX_VIDE if k is None else catalogue[k].etiquette(),
                on_change=choisir_catalogue, args=(indice,), placeholder=CHOIX_VIDE,
                help="Les matériaux sont enregistrés dans le fichier materiaux.json du dépôt GitHub.")

        saisie["nom"] = st.text_input("Nom (facultatif)", key=f"nom_{indice}", placeholder="Ex. : panneau bois, béton…")

        colonne_id, colonne_lien = st.columns([3, 2], vertical_alignment="bottom")
        with colonne_id:
            saisie["identifiant"] = st.number_input(
                "Identifiant INIES (facultatif)", min_value=1, step=1, value=None, format="%d",
                key=f"id_{indice}", help="Le numéro à la fin de l'adresse de la fiche INIES, par exemple 46517.")
        with colonne_lien:
            identifiant = saisie["identifiant"]
            st.link_button("Ouvrir la fiche ↗", URL_FICHE_INIES.format(id=int(identifiant)) if identifiant else URL_SITE_INIES,
                           disabled=not identifiant, width="stretch")

        saisie["dvr"] = st.number_input(
            "Durée de vie de référence (DVR), en années", min_value=acv.DVR_MIN, max_value=acv.DVR_MAX, step=1,
            value=DVR_PAR_DEFAUT, key=f"dvr_{indice}",
            help="Sur la fiche INIES, onglet « Unité fonctionnelle ». C'est la durée pendant laquelle le produit "
                 "remplit sa fonction avant d'être remplacé.")

        saisie["texte"] = st.text_area(
            "Ligne « Réchauffement climatique » copiée depuis INIES", key=f"texte_{indice}",
            height=HAUTEUR_ZONE_COLLAGE, placeholder=PLACEHOLDER_COLLAGE,
            help="Onglet « Indicateurs » de la fiche : 13 valeurs. Les tabulations, espaces et retours "
                 "à la ligne sont acceptés.")

        # Lecture immédiate de ce qui a été collé, avec un retour clair
        if saisie["texte"].strip():
            try:
                saisie["valeurs"] = acv.lire_valeurs_inies(saisie["texte"])
                saisie["resultat"] = acv.calculer_acv_dynamique(saisie["valeurs"], saisie["dvr"])
                st.success(f"{acv.NB_VALEURS_A2} valeurs lues.")
                for avertissement in acv.controler_coherence(saisie["valeurs"]):
                    st.warning(avertissement)
            except acv.ErreurInies as erreur:
                st.error(str(erreur))

        # Bloc à ajouter au catalogue
        if saisie["resultat"] is not None:
            with st.expander("Enregistrer ce matériau dans le catalogue"):
                st.markdown(TEXTE_ENREGISTRER)
                identifiant = saisie["identifiant"]
                st.code(cat.bloc_json_materiau(
                    nom=nom_affiche(saisie), identifiant=int(identifiant) if identifiant else None,
                    lien_inies=URL_FICHE_INIES.format(id=int(identifiant)) if identifiant else None,
                    dvr=saisie["dvr"], valeurs=saisie["valeurs"], acv_dynamique=saisie["resultat"].dynamique_total,
                    date_export=aujourd_hui()), language="json")
                if not saisie["nom"].strip():
                    st.caption("Donnez un nom au matériau avant de copier le bloc.")

    return saisie


# =============================================================================
# 2) RÉSULTATS
# =============================================================================
def carte_resultat(saisie: dict, couleur: str, couleur_texte: str) -> str:
    """HTML de la grande carte d'un matériau : résultat dynamique en gros, total INIES en petit."""
    resultat, valeurs = saisie["resultat"], saisie["valeurs"]
    return f"""
    <div class="carte" style="--couleur:{couleur}; --couleur-texte:{couleur_texte}">
      <div class="nom">{html.escape(nom_affiche(saisie))}</div>
      <div class="grand">{pres.fr(resultat.dynamique_total)}<span class="unite">{UNITE}</span></div>
      <div class="legende">ACV dynamique RE2020 sur {acv.PERIODE_ETUDE} ans, module D inclus</div>
      <div class="petit">Total affiché dans INIES : {pres.fr(valeurs.total)} {UNITE}
        (module D, à part : {pres.fr(valeurs.module_d)}) · DVR {resultat.dvr} ans</div>
    </div>"""


def tableau_phases(saisies_ok: list) -> pd.DataFrame:
    """Tableau récapitulatif par phase, dynamique et statique, pour chaque matériau."""
    lignes = (
        ("Année 0 (production, construction)", "dynamique_t0", "statique_t0"),
        (f"Années 1 à {acv.PERIODE_ETUDE - 1} (utilisation, remplacements)", "dynamique_intermediaire", "statique_intermediaire"),
        (f"Année {acv.PERIODE_ETUDE} (fin de vie, module D)", "dynamique_t50", "statique_t50"),
        ("Total", "dynamique_total", "statique_total"),
    )
    tableau = {"Phase": [ligne[0] for ligne in lignes]}
    for saisie in saisies_ok:
        nom = nom_affiche(saisie)
        tableau[f"{nom} — dynamique RE2020"] = [pres.fr(getattr(saisie["resultat"], l[1])) for l in lignes]
        tableau[f"{nom} — statique E+C-"] = [pres.fr(getattr(saisie["resultat"], l[2])) for l in lignes]
    return pd.DataFrame(tableau)


def tableau_annees(saisies_ok: list) -> pd.DataFrame:
    """Tableau année par année (pour vérifier le calcul)."""
    tableau = {"Année": list(range(acv.PERIODE_ETUDE + 1)),
               "Coefficient (art. 11)": [pres.fr(c, 3) for c in acv.COEFFICIENTS_ART11]}
    for saisie in saisies_ok:
        nom = nom_affiche(saisie)
        tableau[f"{nom} — émissions pondérées"] = [pres.fr(v, 3) for v in saisie["resultat"].dynamique_par_annee]
        tableau[f"{nom} — cumul"] = [pres.fr(v, 3) for v in saisie["resultat"].cumul_dynamique()]
    return pd.DataFrame(tableau)


# =============================================================================
# PAGE
# =============================================================================
st.set_page_config(page_title=TITRE_PAGE, page_icon=ICONE_PAGE, layout="wide")

CATALOGUE, ERREUR_CATALOGUE = charger_catalogue()
COULEURS = pres.THEME["matieres"]

st.markdown(pres.css(), unsafe_allow_html=True)
st.markdown('<h1 class="titre-principal">Comprendre l\'impact <span class="mot">carbone</span> '
            'd\'un matériau</h1><div class="sous-titre">L\'ACV dynamique dans la RE2020</div>', unsafe_allow_html=True)
st.markdown(TEXTE_INTRO)
with st.expander("Comment faire ? (3 étapes)", expanded=True):
    st.markdown(TEXTE_ETAPES)
if ERREUR_CATALOGUE:
    st.warning(f"Le catalogue de matériaux n'a pas pu être lu. {ERREUR_CATALOGUE}")

bouton_exemple, bouton_effacer, _ = st.columns([2, 2, 6])
bouton_exemple.button("Essayer avec un exemple", on_click=charger_exemple, type="primary", width="stretch")
bouton_effacer.button("Tout effacer", on_click=effacer_tout, width="stretch")

# --- 1) Saisies ---------------------------------------------------------------
saisies = []
for i, colonne in enumerate(st.columns(NB_MATERIAUX)):
    with colonne:
        saisies.append(saisie_materiau(i, CATALOGUE))
saisies_ok = [s for s in saisies if s["resultat"] is not None]

# --- 2) Résultats -------------------------------------------------------------
st.divider()
st.markdown('<h2 class="titre-section">Résultats</h2>', unsafe_allow_html=True)

if not saisies_ok:
    st.info("Collez la ligne INIES d'au moins un matériau (ou choisissez-en un dans la liste) pour voir le résultat. "
            "Le bouton « Essayer avec un exemple » montre le principe.")
else:
    for saisie, colonne in zip(saisies, st.columns(NB_MATERIAUX)):
        with colonne:
            if saisie["resultat"] is not None:
                st.markdown(carte_resultat(saisie, COULEURS[saisie["indice"]], pres.THEME["texte_matieres"][saisie["indice"]]), unsafe_allow_html=True)
            else:
                st.info(f"Collez la ligne INIES du matériau {LETTRES[saisie['indice']]} pour la comparaison carbone.")

    # Phrase de comparaison carbone (si les deux matériaux sont renseignés)
    if len(saisies_ok) == NB_MATERIAUX:
        saisie_a, saisie_b = saisies_ok
        ecart = saisie_a["resultat"].dynamique_total - saisie_b["resultat"].dynamique_total
        if abs(ecart) < 0.005:
            st.markdown("Les deux matériaux ont le même impact (écart inférieur à 0,01 " + UNITE + ").")
        else:
            meilleur, autre = (saisie_a, saisie_b) if ecart < 0 else (saisie_b, saisie_a)
            st.markdown(f"l'écart entre les deux matériaux est de {pres.fr(abs(ecart))} {UNITE} sur {acv.PERIODE_ETUDE} ans.")
        st.caption("Attention, une comparaison carbone n'a de sens que pour deux produits rendant le même service "
                   "(même unité fonctionnelle au minimum).")

    # Graphique (largeur plafonnée par le CSS du conteneur « graphique » : pleine largeur sur un petit écran)
    series = [{"indice": s["indice"], "nom": nom_affiche(s), "annees": list(s["resultat"].annees),
               "cumul": s["resultat"].cumul_dynamique(), "cumul_statique": s["resultat"].cumul_statique()}
              for s in saisies_ok]
    with st.container(key="graphique"):
        avec_statique = st.checkbox("Afficher aussi le calcul statique E+C- (en pointillés, sans pondération)",
                                    key="avec_statique")
        st.plotly_chart(pres.figure_cumul(series, avec_statique), width="stretch",
                        config={"displaylogo": False, "toImageButtonOptions": {
                            "format": "png", "filename": NOM_IMAGE_GRAPHIQUE, "scale": 2}})
        st.caption("Pour enregistrer le graphique en image : icône appareil photo, en haut à droite au survol.")
    for saisie in saisies_ok:
        st.markdown(pres.tableau_etapes_html(nom_affiche(saisie), saisie["valeurs"], saisie["indice"]),
                    unsafe_allow_html=True)

    colonne_resume, colonne_annees, _ = st.columns([2, 2, 6])
    lignes_export = [{"nom": nom_affiche(s), "identifiant": s.get("identifiant"), "valeurs": s["valeurs"],
                      "resultat": s["resultat"]} for s in saisies_ok]
    colonne_resume.download_button("Télécharger le résumé (CSV)", export.csv_resume(lignes_export), "acv_resume.csv",
                                   "text/csv", width="stretch")
    colonne_annees.download_button("Télécharger année par année (CSV)", export.csv_annees(lignes_export),
                                   "acv_annee_par_annee.csv", "text/csv", width="stretch")

    with st.expander("Voir le détail du calcul"):
        st.markdown("**Par phase**, en " + UNITE + " (le statique E+C- compte le module D pour un tiers) :")
        st.dataframe(tableau_phases(saisies_ok), hide_index=True, width="stretch")
        st.markdown("**Année par année** (émissions de l'année × coefficient de l'article 11) :")
        st.dataframe(tableau_annees(saisies_ok), hide_index=True, width="stretch", height=300)

with st.expander("Comment lire ce résultat ?"):
    st.markdown(TEXTE_LECTURE)

# --- 3) Pied de page : version, licence, historique ----------------------------
st.divider()
st.caption(f"Version {acv.VERSION} du {acv.DATE_VERSION} · Licence GNU GPL v3 · "
           f"[Méthode issue du classeur Excel « ACV_Dynamique_INIES_V2 » de Guillaume Meunier]({URL_METHODE}) · "
           f"Coefficients : arrêté du 4 août 2021, article 11.")
with st.expander("Historique des versions"):
    st.dataframe(pd.DataFrame(acv.HISTORIQUE_VERSIONS, columns=["Version", "Date", "Changements"]),
                 hide_index=True, width="stretch")
