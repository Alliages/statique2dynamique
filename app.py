"""
app.py — Comparateur d'ACV dynamique RE2020 (norme +A2) à partir des chiffres de la base INIES.

Lancer en local :   streamlit run app.py
Tout le calcul est dans `acv_inies_a2.py` (module autonome, réutilisable ailleurs).
Ce fichier ne contient que l'interface.
"""
import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import acv_inies_a2 as acv

# =============================================================================
# VARIABLES (tout ce qui se règle est regroupé ici)
# =============================================================================
TITRE_PAGE = "ACV dynamique RE2020 — comparer deux matériaux"
ICONE_PAGE = "🏗️"
UNITE = "kg CO₂ eq."

# Lien vers la fiche d'un produit à partir de son identifiant ({id} est remplacé).
# Format repris de l'adresse d'où viennent vos copier-coller ; à ajuster si INIES le change.
URL_FICHE_INIES = "https://base-inies.fr/infos-produit/{id}"
URL_SITE_INIES = "https://www.base-inies.fr/"

NB_MATERIAUX = 2
LETTRES = ("A", "B")
DVR_PAR_DEFAUT = 50          # ans
HAUTEUR_ZONE_COLLAGE = 110   # pixels

# Couleurs des deux matériaux (palette validée : contraste et daltonisme, mode clair / sombre)
COULEURS_CLAIR = ("#2a78d6", "#eb6834")     # bleu, orange
COULEURS_SOMBRE = ("#3987e5", "#d95926")

# Exemples chargés par le bouton « Essayer avec un exemple »
EXEMPLES = (
    # Matériau A : panneau CLT, valeurs de l'Excel d'origine (DVR 100 ans)
    {"nom": "Panneau CLT (exemple)", "id": 33806, "dvr": 100,
     "texte": "-6.04e+2\t1.38e+1\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t7.58e+2\t1.67e+2\t-2.33e+2"},
    # Matériau B : fiche 46517, valeurs copiées depuis INIES ; la DVR de 50 ans est fictive (exemple)
    {"nom": "Fiche 46517 (exemple, DVR fictive)", "id": 46517, "dvr": 50,
     "texte": "1.54e+1\t5.14e+0\t0.00e+0\t5.95e-3\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t0.00e+0\t5.95e-3\t4.23e-1\t2.10e+1\t-9.65e-2"},
)
PLACEHOLDER_COLLAGE = "Collez ici la ligne « Réchauffement climatique » copiée depuis INIES"

# Style des grandes cartes de résultat (suit automatiquement le thème clair / sombre)
STYLE_CARTES = """
<style>
.carte {border-left: 6px solid var(--couleur); background: rgba(128,128,128,.10);
        border-radius: 6px; padding: .8rem 1.1rem; margin-bottom: .5rem;}
.carte .nom {font-weight: 600; font-size: 1.05rem;}
.carte .grand {font-size: 3.2rem; font-weight: 700; line-height: 1.15;}
.carte .unite {font-size: 1rem; font-weight: 400; opacity: .75; margin-left: .35rem;}
.carte .legende {font-size: .95rem; opacity: .85;}
.carte .petit {font-size: .85rem; opacity: .65; margin-top: .5rem;}
</style>
"""

TEXTE_INTRO = """
Cet outil compare l'impact carbone de **deux matériaux** avec la méthode **dynamique** de la RE2020.
Il part des chiffres affichés dans la base INIES et les transforme à votre place.

**Pourquoi « dynamique » ?** Un kilo de CO₂ émis tout de suite pèse plus qu'un kilo émis dans 40 ans.
La RE2020 applique donc à chaque année un coefficient qui descend de 1 (année 0) à 0,578 (année 50).
Le résultat diffère ainsi du total affiché dans INIES, qui additionne tout sans pondération.
"""

TEXTE_ETAPES = """
1. **Trouvez le produit sur INIES** ([base-inies.fr](""" + URL_SITE_INIES + """)). Si vous connaissez son identifiant,
   saisissez-le ci-dessous : un bouton ouvre la fiche.
2. Onglet **« Unité fonctionnelle »** : notez la **durée de vie de référence (DVR)**, en années.
3. Onglet **« Indicateurs »** : vérifiez que la norme est **+A2**. Cet outil ne traite pas la norme +A1.
4. Toujours dans « Indicateurs », **copiez la ligne « Réchauffement climatique »** (toutes les valeurs, de
   « Étape de production » jusqu'à « D - Bénéfices et charges », sans les autres lignes) et collez-la dans la case.

*Attention : l'arrondi affiché par le site INIES peut différer légèrement des valeurs de la FDES.*
"""

TEXTE_LECTURE = f"""
- **Le grand chiffre** est l'ACV dynamique RE2020 : les émissions sur 50 ans, chaque année pondérée par son
  coefficient, **module D inclus**, en {UNITE} pour l'unité fonctionnelle de la fiche.
- **Le petit chiffre** est le total affiché dans INIES (sans pondération, module D à part), pour repère.
- **Plus le chiffre est bas, mieux c'est.** Un résultat négatif signifie que, sur la période, le matériau compense
  plus qu'il n'émet (par exemple grâce au carbone stocké dans le bois).
- **Si la DVR est inférieure à 50 ans**, le produit est remplacé en cours de route : chaque remplacement
  est ajouté, et le dernier n'est compté qu'au prorata de sa durée utile dans les 50 ans.
- **Comparez des produits qui rendent le même service** (même unité fonctionnelle, par exemple 1 m² de mur
  de même performance) : la comparaison n'a de sens qu'à ce prix.
"""


# =============================================================================
# OUTILS D'AFFICHAGE
# =============================================================================
def fr(valeur: float, decimales: int = None) -> str:
    """Nombre au format français : virgule décimale, espace fine pour les milliers, vrai signe moins."""
    if decimales is None:       # plus la valeur est petite, plus on garde de décimales
        decimales = 3 if abs(valeur) < 1 else 2 if abs(valeur) < 10 else 1
    if round(valeur, decimales) == 0:
        valeur = 0.0            # évite « −0,0 »
    texte = f"{valeur:,.{decimales}f}".replace(",", " ").replace(".", ",")
    return texte.replace("-", "−")


def theme_sombre() -> bool:
    """Vrai si l'utilisateur est en thème sombre (faux si Streamlit ne sait pas le dire)."""
    try:
        return st.context.theme.type == "dark"
    except Exception:
        return False


def nom_affiche(saisie: dict) -> str:
    """Nom choisi par l'utilisateur, ou « Matériau A / B » par défaut."""
    return saisie["nom"].strip() or f"Matériau {LETTRES[saisie['indice']]}"


def charger_exemple() -> None:
    """Remplit les deux matériaux avec les exemples (appelé par le bouton)."""
    for i, exemple in enumerate(EXEMPLES):
        st.session_state[f"nom_{i}"] = exemple["nom"]
        st.session_state[f"id_{i}"] = exemple["id"]
        st.session_state[f"dvr_{i}"] = exemple["dvr"]
        st.session_state[f"texte_{i}"] = exemple["texte"]


def effacer_tout() -> None:
    """Vide les deux matériaux (appelé par le bouton)."""
    for i in range(NB_MATERIAUX):
        st.session_state[f"nom_{i}"] = ""
        st.session_state[f"id_{i}"] = None
        st.session_state[f"dvr_{i}"] = DVR_PAR_DEFAUT
        st.session_state[f"texte_{i}"] = ""


# =============================================================================
# 1) SAISIES — une carte par matériau
# =============================================================================
def saisie_materiau(indice: int) -> dict:
    """Affiche les champs d'un matériau, lit la ligne collée, et renvoie tout ce qu'il faut pour la suite."""
    saisie = {"indice": indice, "valeurs": None, "resultat": None}

    with st.container(border=True):
        st.subheader(f"Matériau {LETTRES[indice]}")
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
            help="Onglet « Indicateurs » de la fiche, norme +A2 : 13 valeurs. Les tabulations, espaces et retours "
                 "à la ligne sont acceptés.")

        # Lecture immédiate de ce qui a été collé, avec un retour clair
        if saisie["texte"].strip():
            try:
                saisie["valeurs"] = acv.lire_valeurs_inies(saisie["texte"])
                saisie["resultat"] = acv.calculer_acv_dynamique(saisie["valeurs"], saisie["dvr"])
                st.success(f"{acv.NB_VALEURS_A2} valeurs lues (norme +A2).")
                for avertissement in acv.controler_coherence(saisie["valeurs"]):
                    st.warning(avertissement)
            except acv.ErreurInies as erreur:
                st.error(str(erreur))

    return saisie


# =============================================================================
# 2) AFFICHAGE DES RÉSULTATS
# =============================================================================
def carte_resultat(saisie: dict, couleur: str) -> str:
    """HTML de la grande carte d'un matériau : résultat dynamique en gros, total INIES en petit."""
    resultat, valeurs = saisie["resultat"], saisie["valeurs"]
    return f"""
    <div class="carte" style="--couleur:{couleur}">
      <div class="nom">{html.escape(nom_affiche(saisie))}</div>
      <div class="grand">{fr(resultat.dynamique_total)}<span class="unite">{UNITE}</span></div>
      <div class="legende">ACV dynamique RE2020 sur {acv.PERIODE_ETUDE} ans, module D inclus</div>
      <div class="petit">Total affiché dans INIES : {fr(valeurs.total)} {UNITE}
        (module D, à part : {fr(valeurs.module_d)}) · DVR {resultat.dvr} ans</div>
    </div>"""


def graphique_cumul(saisies_ok: list, couleurs: tuple) -> go.Figure:
    """Courbes des émissions dynamiques cumulées, année après année."""
    figure = go.Figure()
    for saisie, couleur in saisies_ok:
        cumul = saisie["resultat"].cumul_dynamique()
        nom = nom_affiche(saisie)
        figure.add_trace(go.Scatter(
            x=list(saisie["resultat"].annees), y=cumul, mode="lines", name=nom,
            line=dict(color=couleur, width=2.5),
            hovertemplate=f"{html.escape(nom)}<br>Année %{{x}} : %{{y:,.2f}} {UNITE} cumulés<extra></extra>"))
        # Étiquette directe au bout de la courbe, alignée à droite pour ne jamais être coupée
        figure.add_annotation(x=acv.PERIODE_ETUDE, y=cumul[-1], text=f"<b>{html.escape(nom)}</b>", showarrow=False,
                              xanchor="right", yanchor="bottom", yshift=8, font=dict(color=couleur))
    figure.add_hline(y=0, line_width=1, line_color="rgba(128,128,128,.6)")
    figure.update_layout(
        height=420, margin=dict(l=10, r=20, t=40, b=10), hovermode="x unified",
        separators=", ", legend=dict(orientation="h", y=1.12, x=0),
        xaxis=dict(title="Année après la construction", range=[0, acv.PERIODE_ETUDE], dtick=5, showgrid=False),
        yaxis=dict(title=f"{UNITE} cumulés", gridcolor="rgba(128,128,128,.25)", zeroline=False),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return figure


def tableau_phases(saisies_ok: list) -> pd.DataFrame:
    """Tableau récapitulatif par phase, dynamique et statique, pour chaque matériau."""
    lignes = (
        ("Année 0 (production, construction)", "dynamique_t0", "statique_t0"),
        (f"Années 1 à {acv.PERIODE_ETUDE - 1} (utilisation, remplacements)", "dynamique_intermediaire", "statique_intermediaire"),
        (f"Année {acv.PERIODE_ETUDE} (fin de vie, module D)", "dynamique_t50", "statique_t50"),
        ("Total", "dynamique_total", "statique_total"),
    )
    tableau = {"Phase": [ligne[0] for ligne in lignes]}
    for saisie, _ in saisies_ok:
        nom = nom_affiche(saisie)
        tableau[f"{nom} — dynamique RE2020"] = [fr(getattr(saisie["resultat"], l[1])) for l in lignes]
        tableau[f"{nom} — statique E+C-"] = [fr(getattr(saisie["resultat"], l[2])) for l in lignes]
    return pd.DataFrame(tableau)


def tableau_annees(saisies_ok: list) -> pd.DataFrame:
    """Tableau année par année (pour vérifier le calcul)."""
    tableau = {"Année": list(range(acv.PERIODE_ETUDE + 1)),
               "Coefficient (art. 11)": [fr(c, 3) for c in acv.COEFFICIENTS_ART11]}
    for saisie, _ in saisies_ok:
        nom = nom_affiche(saisie)
        tableau[f"{nom} — émissions pondérées"] = [fr(v, 3) for v in saisie["resultat"].dynamique_par_annee]
        tableau[f"{nom} — cumul"] = [fr(v, 3) for v in saisie["resultat"].cumul_dynamique()]
    return pd.DataFrame(tableau)


# =============================================================================
# PAGE
# =============================================================================
st.set_page_config(page_title=TITRE_PAGE, page_icon=ICONE_PAGE, layout="wide")
st.markdown(STYLE_CARTES, unsafe_allow_html=True)

st.title(TITRE_PAGE)
st.markdown(TEXTE_INTRO)
with st.expander("Comment faire ? (4 étapes)", expanded=True):
    st.markdown(TEXTE_ETAPES)

bouton_exemple, bouton_effacer, _ = st.columns([2, 2, 6])
bouton_exemple.button("Essayer avec un exemple", on_click=charger_exemple, width="stretch")
bouton_effacer.button("Tout effacer", on_click=effacer_tout, width="stretch")

# --- 1) Saisies --------------------------------------------------------------
colonnes_saisie = st.columns(NB_MATERIAUX)
saisies = []
for i, colonne in enumerate(colonnes_saisie):
    with colonne:
        saisies.append(saisie_materiau(i))

# --- 2) Résultats -------------------------------------------------------------
COULEURS = COULEURS_SOMBRE if theme_sombre() else COULEURS_CLAIR
saisies_ok = [(s, COULEURS[s["indice"]]) for s in saisies if s["resultat"] is not None]

st.divider()
st.header("Résultat")

if not saisies_ok:
    st.info("Collez la ligne INIES d'au moins un matériau pour voir le résultat. "
            "Le bouton « Essayer avec un exemple » montre le principe.")
else:
    colonnes_resultat = st.columns(NB_MATERIAUX)
    for saisie, colonne in zip(saisies, colonnes_resultat):
        with colonne:
            if saisie["resultat"] is not None:
                st.markdown(carte_resultat(saisie, COULEURS[saisie["indice"]]), unsafe_allow_html=True)
            else:
                st.info(f"Collez la ligne INIES du matériau {LETTRES[saisie['indice']]} pour le comparer.")

    # Phrase de comparaison (si les deux matériaux sont renseignés)
    if len(saisies_ok) == NB_MATERIAUX:
        (saisie_a, _), (saisie_b, _) = saisies_ok
        ecart = saisie_a["resultat"].dynamique_total - saisie_b["resultat"].dynamique_total
        if abs(ecart) < 0.005:
            st.markdown("**Les deux matériaux ont le même résultat** (écart inférieur à 0,01 " + UNITE + ").")
        else:
            meilleur, autre = (saisie_a, saisie_b) if ecart < 0 else (saisie_b, saisie_a)
            st.markdown(f"**{nom_affiche(meilleur)}** a le résultat le plus bas : "
                        f"**{fr(abs(ecart))} {UNITE}** de moins que **{nom_affiche(autre)}** sur {acv.PERIODE_ETUDE} ans.")
        st.caption("Cette comparaison n'a de sens que pour deux produits rendant le même service "
                   "(même unité fonctionnelle).")

    st.plotly_chart(graphique_cumul(saisies_ok, COULEURS), width="stretch")

    with st.expander("Voir le détail du calcul"):
        st.markdown("**Par phase**, en " + UNITE + " (le statique E+C- compte le module D pour un tiers) :")
        st.dataframe(tableau_phases(saisies_ok), hide_index=True, width="stretch")
        st.markdown("**Année par année** (émissions de l'année × coefficient de l'article 11) :")
        st.dataframe(tableau_annees(saisies_ok), hide_index=True, width="stretch", height=300)

with st.expander("Comment lire ce résultat ?"):
    st.markdown(TEXTE_LECTURE)

# --- 3) Pied de page : version, licence, historique ----------------------------
st.divider()
st.caption(f"Version {acv.VERSION} du {acv.DATE_VERSION} · Licence GNU GPL v3 · Méthode issue du classeur Excel "
           f"« ACV_Dynamique_INIES_V2 » de Guillaume Meunier · Coefficients : arrêté du 4 août 2021, article 11.")
with st.expander("Historique des versions"):
    st.dataframe(pd.DataFrame(acv.HISTORIQUE_VERSIONS, columns=["Version", "Date", "Changements"]),
                 hide_index=True, width="stretch")
