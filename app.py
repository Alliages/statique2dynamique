"""
app.py — Comprendre l'impact carbone d'un matériau : ACV dynamique RE2020 (norme +A2) à partir de la base INIES.

Lancer en local :   streamlit run app.py

Organisation du projet :
    acv_inies_a2.py   le calcul (module autonome, réutilisable ailleurs)
    catalogue.py      lecture de materiaux.json et fabrication d'un nouveau bloc
    lien.py           liens pré-remplis vers l'application (fabrication et lecture contrôlée)
    export.py         fichiers CSV téléchargeables
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
import lien
import presentation as pres

# =============================================================================
# VARIABLES (tout ce qui se règle est regroupé ici)
# =============================================================================
VERSIONS_MASQUEES = ("3.5.0", "3.6.0", "3.6.1")     # absentes de l'historique affiché (restent dans CHANGELOG.md)
TITRE_PAGE = "Comprendre l'impact carbone d'un matériau — L'ACV dynamique dans la RE2020"
ICONE_PAGE = "🏗️"
UNITE = pres.UNITE

# Lien vers la fiche d'un produit à partir de son identifiant ({id} est remplacé).
URL_FICHE_INIES = "https://base-inies.fr/infos-produit/{id}"
# Adresse de l'application déployée : les liens « pré-remplis » partent de là.
URL_APP = "https://statique2dynamique.streamlit.app/"
URL_SITE_INIES = "https://www.base-inies.fr/"
URL_METHODE = "https://www.linkedin.com/posts/meunierguillaume_fdes-re2020-opensource-activity-7064102175945175040-cOPY"

LETTRES = ("A", "B")         # emplacements des matériaux

PARAM_MODE = "materiaux"     # paramètre d'adresse lu par nombre_de_materiaux()
VALEUR_MODE_DEUX = "2"

# Un seul matériau : largeur de la saisie et des résultats (1/3 - 2/3). Sur un écran étroit (téléphone),
# Streamlit empile les colonnes : saisie, puis résultat, graphique, tableaux, les uns sous les autres.
PROPORTIONS_UN_MATERIAU = (1, 2)
PROPORTIONS_BOUTONS_CSV = {1: (1, 1), 2: (2, 2, 6)}    # selon le nombre de matériaux affichés

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

# Détail du changement climatique (un seul matériau) : les 4 lignes INIES, sous la saisie du matériau
HAUTEUR_ZONE_COLLAGE_DETAIL = 200   # pixels
PLACEHOLDER_COLLAGE_DETAIL = ("Collez ici les 4 lignes « Changement climatique » (total, fossil, biogénique, "
                              "occupation des sols) copiées depuis INIES, avec leur libellé")
NOM_IMAGE_BARRES = "acv_etapes_re2020"         # nom du fichier image du graphique par étape
ID_EXEMPLE_DETAIL = 33806                      # le bouton « exemple » remplit le détail si le matériau A est ce panneau CLT
EXEMPLE_DETAIL = (
    "Changement climatique - total (kg CO2 eq.)\t-6.04e+2\t1.38e+1\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t7.58e+2\t1.67e+2\t-2.33e+2\n"
    "Changement climatique - fossil (kg CO2 eq.)\t1.03e+2\t1.35e+1\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t3.33e+1\t1.50e+2\t-2.25e+2\n"
    "Changement climatique - biogénique (kg CO2 eq.)\t-7.08e+2\t3.06e-1\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t7.24e+2\t1.67e+1\t-8.35e+0\n"
    "Changement climatique - occupation des sols et transformation de l'occupation des sols (kg CO2 eq.)\t1.03e-1\t4.60e-4\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t4.38e-3\t1.08e-1\t-6.01e-2")

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
"""

# Ajouté à TEXTE_LECTURE quand deux matériaux sont affichés
TEXTE_LECTURE_DEUX = """
- **Comparez des produits qui rendent le même service** (même unité fonctionnelle, par exemple 1 m² de mur
  de même performance) : la comparaison carbone n'a de sens qu'à ce prix.
"""

# Ajouté à TEXTE_LECTURE quand le détail du changement climatique est affiché
TEXTE_LECTURE_DETAIL = """
- **Le détail du changement climatique** sépare le total en trois composantes : **fossile**, **biogénique** et
  **occupation des sols** (fossile + biogénique + occupation des sols = total). Les courbes montrent le cumul année après
  année ; la valeur au bout est le résultat dynamique de chaque ligne.
- **Les barres** répartissent ce résultat par étape du cycle de vie. Au-dessus de zéro : émissions ; en dessous :
  carbone stocké ou évité. Le losange est le total net ; la dernière barre rejoint la fin des courbes.
- **Les barres sont dynamiques** : chaque étape est pondérée par le coefficient de l'année où elle a lieu. Elles
  diffèrent donc des valeurs brutes du tableau INIES (la production, à l'année 0, garde tout son poids ; la fin de vie,
  à l'année 50, est réduite). Avec une DVR inférieure à 50 ans, les remplacements sont comptés dans les étapes concernées.
- **L'occupation des sols** pèse très peu : sa courbe se confond avec la ligne de zéro et sa barre est presque invisible.
"""

MESSAGE_ATTENTE = ("Collez la ligne INIES d'un matériau (ou choisissez-en un dans la liste) pour voir le résultat. "
                   "Le bouton « Essayer avec un exemple » montre le principe.")

TEXTE_LIEN = """
Ce lien rouvre l'application avec ce matériau déjà rempli (nom, identifiant, DVR et valeurs).
Copiez-le (icône en haut à droite) pour le mettre en favori ou l'envoyer à quelqu'un.
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
    if indice == 0:                         # le détail du changement climatique appartient au matériau saisi : on le vide
        st.session_state["texte_detail"] = ""


def choisir_catalogue(indice: int) -> None:
    """Un matériau du catalogue vient d'être choisi dans la liste : on remplit ses champs."""
    choix = st.session_state.get(f"cat_{indice}")
    catalogue, _ = charger_catalogue()
    if choix is not None and choix < len(catalogue):
        m = catalogue[choix]
        remplir(indice, m.nom, m.id, m.dvr, m.texte_inies())


def charger_exemple(nb_materiaux: int) -> None:
    """Remplit le ou les matériaux affichés avec les exemples (appelé par le bouton)."""
    catalogue, _ = charger_catalogue()
    if catalogue:
        m = catalogue[0]
        remplir(0, m.nom, m.id, m.dvr, m.texte_inies())
        st.session_state["cat_0"] = 0
        if nb_materiaux == 1 and m.id == ID_EXEMPLE_DETAIL:          # le détail n'existe qu'avec un seul matériau
            st.session_state["texte_detail"] = EXEMPLE_DETAIL
    else:
        remplir(0, "Fiche 46517 (exemple, DVR 30)", 46517, 30, EXEMPLE_B["texte"])
    if nb_materiaux == 2:
        remplir(1, EXEMPLE_B["nom"], EXEMPLE_B["id"], EXEMPLE_B["dvr"], EXEMPLE_B["texte"])
        st.session_state["cat_1"] = None


def effacer_tout() -> None:
    """Vide tous les emplacements (appelé par le bouton)."""
    for i in range(len(LETTRES)):
        remplir(i, "", None, DVR_PAR_DEFAUT, "")
        st.session_state[f"cat_{i}"] = None


def appliquer_lien() -> tuple:
    """Si l'adresse contient un lien pré-rempli, remplit les champs. Renvoie (lettres chargées, erreurs).

    Les paramètres du lien sont retirés de l'adresse ensuite : une relance de la page ne ré-applique pas le lien
    (qui écraserait ce que l'utilisateur a modifié depuis).
    """
    parametres = dict(st.query_params)
    if not lien.contient_un_lien(parametres):
        return [], []
    materiaux, erreurs = lien.lire_lien(parametres)
    for m in materiaux:
        remplir(m.indice, m.nom, m.identifiant, m.dvr, m.texte_inies())
        st.session_state[f"cat_{m.indice}"] = None
    for cle in lien.cles_connues():
        if cle in st.query_params:
            del st.query_params[cle]
    if lien.contient_le_materiau(parametres, 1):
        st.query_params[PARAM_MODE] = VALEUR_MODE_DEUX
    return [m.lettre for m in materiaux], erreurs


def nombre_de_materiaux() -> int:
    """Nombre de matériaux à afficher, lu dans l'adresse (1 par défaut)."""
    return 2 if st.query_params.get(PARAM_MODE) == VALEUR_MODE_DEUX else 1


def quitter_mode_deux() -> None:
    """Revient à un seul matériau (appelé par le bouton)."""
    if PARAM_MODE in st.query_params:
        del st.query_params[PARAM_MODE]


def libelle_materiau(indice: int, nb_materiaux: int) -> str:
    """« Matériau » seul quand il n'y en a qu'un, sinon « Matériau A » / « Matériau B »."""
    return "Matériau" if nb_materiaux == 1 else f"Matériau {LETTRES[indice]}"


def message_lien(lettres: list, nb_materiaux: int) -> str:
    """Message de confirmation après lecture d'un lien pré-rempli."""
    if nb_materiaux == 1:
        return "Lien lu : matériau pré-rempli."
    pluriel = len(lettres) > 1
    return f"Lien lu : matériau{'x' if pluriel else ''} {' et '.join(lettres)} pré-rempli{'s' if pluriel else ''}."


def nom_affiche(saisie: dict) -> str:
    """Nom choisi par l'utilisateur, ou « Matériau » / « Matériau A » / « Matériau B » par défaut."""
    return saisie["nom"].strip() or saisie["libelle"]


# =============================================================================
# 1) SAISIES — une carte par matériau
# =============================================================================
def saisie_materiau(indice: int, catalogue: list, nb_materiaux: int) -> dict:
    """Affiche les champs d'un matériau, lit la ligne collée, et renvoie tout ce qu'il faut pour la suite."""
    saisie = {"indice": indice, "libelle": libelle_materiau(indice, nb_materiaux), "valeurs": None, "resultat": None}

    with st.container(border=True, key=f"boite_{LETTRES[indice]}"):   # la clé donne la classe CSS « st-key-boite_A »
        st.markdown(f'<div class="bandeau mat-{LETTRES[indice]}">{saisie["libelle"]}</div>', unsafe_allow_html=True)

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

            # Lien pré-rempli : retrouver ou partager ce matériau
            with st.expander("🔗 Copier le lien de ce matériau"):
                st.markdown(TEXTE_LIEN)
                st.code(lien.construire_lien(URL_APP, indice, saisie["nom"], saisie["identifiant"], saisie["dvr"],
                                             saisie["valeurs"]), language=None, wrap_lines=True)

    return saisie


def saisie_detail(saisie_materiau_a: dict):
    """Les 4 lignes « Changement climatique » du même matériau (sa DVR est celle du matériau ci-dessus).

    Renvoie {clé: ResultatA2} (clés de acv.INDICATEURS_CLIMAT), ou None si rien de lisible n'est collé.
    """
    detail = None
    with st.container(border=True, key="boite_detail"):
        st.markdown('<div class="bandeau mat-A">Détail du changement climatique</div>', unsafe_allow_html=True)
        texte = st.text_area(
            "Les 4 lignes « Changement climatique » copiées depuis INIES", key="texte_detail",
            height=HAUTEUR_ZONE_COLLAGE_DETAIL, placeholder=PLACEHOLDER_COLLAGE_DETAIL,
            help="Facultatif. Onglet « Indicateurs » de la fiche : les 4 lignes (total, fossil, biogénique, occupation "
                 "des sols), chacune avec son libellé. L'ordre des lignes n'a pas d'importance. La DVR est celle du "
                 "matériau ci-dessus.")
        if texte.strip():
            try:
                valeurs = acv.lire_indicateurs_climat(texte)
                detail = {cle: acv.calculer_acv_dynamique(v, saisie_materiau_a["dvr"]) for cle, v in valeurs.items()}
                st.success("4 lignes lues : total, fossile, biogénique, occupation des sols.")
                avertissements = acv.controler_coherence_indicateurs(valeurs)
                if saisie_materiau_a["valeurs"] is not None:
                    avertissements += [a for a in [acv.controler_meme_materiau(saisie_materiau_a["valeurs"],
                                                                               valeurs[acv.CLE_TOTAL])] if a]
                for avertissement in avertissements:
                    st.warning(avertissement)
            except acv.ErreurInies as erreur:
                st.error(str(erreur))
    return detail


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


def afficher_carte(saisie: dict) -> None:
    """Affiche la grande carte d'un matériau, dans sa couleur."""
    indice = saisie["indice"]
    st.markdown(carte_resultat(saisie, pres.THEME["matieres"][indice], pres.THEME["texte_matieres"][indice]),
                unsafe_allow_html=True)


def titre_resultats() -> None:
    """Affiche le titre « Résultats » de la page."""
    st.markdown('<h2 class="titre-section">Résultats</h2>', unsafe_allow_html=True)


def config_image(nom_fichier: str) -> dict:
    """Réglages Plotly : icône appareil photo (image PNG nommée), sans logo."""
    return {"displaylogo": False, "toImageButtonOptions": {"format": "png", "filename": nom_fichier, "scale": 2}}


def series_courbes(saisies_ok: list, detail) -> list:
    """Courbes à tracer : celle de chaque matériau, ou (si le détail est collé) les 4 lignes « Changement climatique »."""
    if detail is None:
        return [{"indice": s["indice"], "nom": nom_affiche(s), "annees": list(s["resultat"].annees),
                 "cumul": s["resultat"].cumul_dynamique(), "cumul_statique": s["resultat"].cumul_statique()}
                for s in saisies_ok]
    series = []
    for cle, libelle, _ in acv.INDICATEURS_CLIMAT:
        resultat = detail[cle]
        series.append({
            "indice": 0, "nom": libelle, "annees": list(resultat.annees), "cumul": resultat.cumul_dynamique(),
            # le calcul statique E+C- n'existe que pour le total
            "cumul_statique": resultat.cumul_statique() if cle == acv.CLE_TOTAL else [],
            "couleur": pres.THEME["climat"][cle], "couleur_texte": pres.THEME["texte_climat"][cle]})
    return series


def figure_etapes(detail: dict):
    """Barres empilées par étape : composantes + total net (ligne « total »), dynamiques."""
    etapes = [libelle for _, libelle in acv.ETAPES] + [pres.LIBELLE_TOTAL_BARRES]

    def valeurs(cle: str) -> list:         # une valeur par étape, puis le total sur 50 ans
        return [v for _, v in detail[cle].dynamique_par_etape] + [detail[cle].dynamique_total]

    composantes = [{"nom": libelle, "couleur": pres.THEME["climat"][cle], "valeurs": valeurs(cle)}
                   for cle, libelle, _ in acv.INDICATEURS_CLIMAT if cle != acv.CLE_TOTAL]
    return pres.figure_barres_etapes(etapes, composantes, valeurs(acv.CLE_TOTAL))


def afficher_graphiques(saisies_ok: list, detail) -> None:
    """Graphique des courbes cumulées (largeur plafonnée par le CSS du conteneur « graphique »),
    puis, si le détail est collé, le graphique des étapes du cycle de vie."""
    with st.container(key="graphique"):
        avec_statique = st.checkbox("Afficher aussi le calcul statique E+C- (en pointillés, sans pondération)",
                                    key="avec_statique")
        if detail is not None:
            st.markdown('<div class="titre-graphique">Émissions cumulées année après année</div>', unsafe_allow_html=True)
        st.plotly_chart(pres.figure_cumul(series_courbes(saisies_ok, detail), avec_statique), width="stretch",
                        config=config_image(NOM_IMAGE_GRAPHIQUE))
        if detail is not None:
            st.markdown('<div class="titre-graphique">Répartition par étape du cycle de vie</div>', unsafe_allow_html=True)
            st.plotly_chart(figure_etapes(detail), width="stretch", config=config_image(NOM_IMAGE_BARRES))
        st.caption("Pour enregistrer le graphique en image : icône appareil photo, en haut à droite au survol.")


def afficher_details(saisies_ok: list, nb_materiaux: int, detail=None) -> None:
    """Ce qui suit le ou les résultats : écart (deux matériaux), graphique(s), tableaux des étapes, exports CSV, détail.

    `detail` : résultats des 4 lignes « Changement climatique » (un seul matériau), ou None."""
    # Phrase de comparaison carbone (deux matériaux renseignés)
    if len(saisies_ok) == 2:
        saisie_a, saisie_b = saisies_ok
        ecart = saisie_a["resultat"].dynamique_total - saisie_b["resultat"].dynamique_total
        if abs(ecart) < 0.005:
            st.markdown("Les deux matériaux ont le même impact (écart inférieur à 0,01 " + UNITE + ").")
        else:
            st.markdown(f"l'écart entre les deux matériaux est de {pres.fr(abs(ecart))} {UNITE} sur {acv.PERIODE_ETUDE} ans.")
        st.caption("Attention, une comparaison carbone n'a de sens que pour deux produits rendant le même service "
                   "(même unité fonctionnelle au minimum).")

    afficher_graphiques(saisies_ok, detail)
    for saisie in saisies_ok:
        st.markdown(pres.tableau_etapes_html(nom_affiche(saisie), saisie["valeurs"], saisie["indice"]),
                    unsafe_allow_html=True)

    colonne_resume, colonne_annees = st.columns(PROPORTIONS_BOUTONS_CSV[nb_materiaux])[:2]
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


def titre_colonne(saisie: dict, saisies_ok: list, libelle: str) -> str:
    """Titre de colonne court : le nom du matériau n'est ajouté que s'il y en a plusieurs à distinguer."""
    return f"{nom_affiche(saisie)} — {libelle}" if len(saisies_ok) > 1 else libelle[0].upper() + libelle[1:]


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
        tableau[titre_colonne(saisie, saisies_ok, "dynamique RE2020")] = [pres.fr(getattr(saisie["resultat"], ligne[1])) for ligne in lignes]
        tableau[titre_colonne(saisie, saisies_ok, "statique E+C-")] = [pres.fr(getattr(saisie["resultat"], ligne[2])) for ligne in lignes]
    return pd.DataFrame(tableau)


def tableau_annees(saisies_ok: list) -> pd.DataFrame:
    """Tableau année par année (pour vérifier le calcul)."""
    tableau = {"Année": list(range(acv.PERIODE_ETUDE + 1)),
               "Coefficient (art. 11)": [pres.fr(c, 3) for c in acv.COEFFICIENTS_ART11]}
    for saisie in saisies_ok:
        tableau[titre_colonne(saisie, saisies_ok, "émissions pondérées")] = [pres.fr(v, 3) for v in saisie["resultat"].dynamique_par_annee]
        tableau[titre_colonne(saisie, saisies_ok, "cumul")] = [pres.fr(v, 3) for v in saisie["resultat"].cumul_dynamique()]
    return pd.DataFrame(tableau)


# =============================================================================
# PAGE
# =============================================================================
st.set_page_config(page_title=TITRE_PAGE, page_icon=ICONE_PAGE, layout="wide")

LETTRES_LIEN, ERREURS_LIEN = appliquer_lien()      # doit être fait avant la création des champs de saisie
NB_MATERIAUX = nombre_de_materiaux()               # lu APRÈS le lien
DETAIL = None                                      # détail du changement climatique : un seul matériau
CATALOGUE, ERREUR_CATALOGUE = charger_catalogue()
COULEURS = pres.THEME["matieres"]

st.markdown(pres.css(), unsafe_allow_html=True)
st.markdown('<h1 class="titre-principal">Comprendre l\'impact <span class="mot">carbone</span> '
            'd\'un matériau</h1><div class="sous-titre">L\'ACV dynamique dans la RE2020</div>', unsafe_allow_html=True)
st.markdown(TEXTE_INTRO)
with st.expander("Comment faire ? (3 étapes)", expanded=True):
    st.markdown(TEXTE_ETAPES)
for erreur in ERREURS_LIEN:
    st.error(erreur)
if LETTRES_LIEN:
    st.success(message_lien(LETTRES_LIEN, NB_MATERIAUX))
if ERREUR_CATALOGUE:
    st.warning(f"Le catalogue de matériaux n'a pas pu être lu. {ERREUR_CATALOGUE}")

bouton_exemple, bouton_effacer, bouton_mode, _ = st.columns([2, 2, 2, 4])
bouton_exemple.button("Essayer avec un exemple", on_click=charger_exemple, args=(NB_MATERIAUX,), type="primary",
                      width="stretch")
bouton_effacer.button("Tout effacer", on_click=effacer_tout, width="stretch")
if NB_MATERIAUX == 2:
    bouton_mode.button("Revenir à un seul matériau", on_click=quitter_mode_deux, width="stretch")


# --- 1) Saisie(s) et résultat principal ----------------------------------------
if NB_MATERIAUX == 1:
    # Un seul matériau : la saisie à gauche (1/3) ; à droite (2/3) le résultat,
    # puis dessous le graphique, les tableaux et les exports
    colonne_saisie, colonne_resultats = st.columns(PROPORTIONS_UN_MATERIAU, gap="large")
    with colonne_saisie:
        saisies = [saisie_materiau(0, CATALOGUE, NB_MATERIAUX)]
        DETAIL = saisie_detail(saisies[0])         # sous la saisie du matériau
    with colonne_resultats:
        titre_resultats()
        if saisies[0]["resultat"] is not None:
            afficher_carte(saisies[0])
            afficher_details(saisies, NB_MATERIAUX, DETAIL)
        elif DETAIL is not None:                   # seules les 4 lignes sont collées : on affiche leurs graphiques
            afficher_graphiques([], DETAIL)
        else:
            st.info(MESSAGE_ATTENTE)
else:
    # Deux matériaux : les deux saisies côte à côte, puis les deux résultats côte à côte
    saisies = []
    for i, colonne in enumerate(st.columns(NB_MATERIAUX)):
        with colonne:
            saisies.append(saisie_materiau(i, CATALOGUE, NB_MATERIAUX))
    st.divider()
    titre_resultats()
    if not any(s["resultat"] is not None for s in saisies):
        st.info(MESSAGE_ATTENTE)
    else:
        for saisie, colonne in zip(saisies, st.columns(NB_MATERIAUX)):
            with colonne:
                if saisie["resultat"] is not None:
                    afficher_carte(saisie)
                else:
                    st.info(f"Collez la ligne INIES du matériau {LETTRES[saisie['indice']]} "
                            "pour afficher son résultat ici.")
saisies_ok = [s for s in saisies if s["resultat"] is not None]

# --- 2) Détails, quand deux matériaux sont affichés (sinon ils sont déjà sous le résultat)
if NB_MATERIAUX == 2 and saisies_ok:
    afficher_details(saisies_ok, NB_MATERIAUX)

with st.expander("Comment lire ce résultat ?"):
    st.markdown(TEXTE_LECTURE + (TEXTE_LECTURE_DEUX if NB_MATERIAUX == 2 else "")
                + (TEXTE_LECTURE_DETAIL if DETAIL is not None else ""))

# --- 3) Pied de page : version, licence, historique ----------------------------
st.divider()
st.caption(f"Version {acv.VERSION} du {acv.DATE_VERSION} · Licence GNU GPL v3 · "
           f"[Méthode issue du classeur Excel « ACV_Dynamique_INIES_V2 » de Guillaume Meunier]({URL_METHODE}) · "
           f"Coefficients : arrêté du 4 août 2021, article 11.")
with st.expander("Historique des versions"):
    st.dataframe(pd.DataFrame([v for v in acv.HISTORIQUE_VERSIONS if v[0] not in VERSIONS_MASQUEES], columns=["Version", "Date", "Changements"]),
                 hide_index=True, width="stretch")
