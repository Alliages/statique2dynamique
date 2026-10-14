"""
presentation.py
===============
Mise en forme de l'application, SANS Streamlit (donc testable seul) :
  - nombres au format français ;
  - graphique des émissions cumulées (Plotly) ;
  - tableau des étapes INIES (HTML) ;
  - feuille de style (CSS) aux couleurs de la palette.

Palette : Yale Blue, Tomato Jam, Cotton Rose, Pacific Cyan, Aquamarine.
En thème sombre, le Yale Blue (trop sombre) est remplacé par le Pacific Cyan,
et le Tomato Jam par le Cotton Rose, pour garder des contrastes lisibles.
"""
from __future__ import annotations

import html
import math
from decimal import Decimal
from typing import Dict, List

import plotly.graph_objects as go

import acv_inies_a2 as acv

# =============================================================================
# VARIABLES (tout ce qui se règle est regroupé ici)
# =============================================================================
# --- Palette -----------------------------------------------------------------
YALE_BLUE = "#08415c"
TOMATO_JAM = "#cc2936"
COTTON_ROSE = "#ebbab9"
PACIFIC_CYAN = "#388697"
AQUAMARINE = "#b5ffe1"

# --- Couleurs selon le thème (clé : thème sombre ou non) ------------------------
THEMES: Dict[bool, dict] = {
    False: {   # thème clair
        "matieres": (YALE_BLUE, TOMATO_JAM),            # matériau A, matériau B
        "titre": YALE_BLUE, "mot_couleur": TOMATO_JAM,
        "texte_sur_couleur": "#ffffff",                 # texte posé sur une couleur de matériau
        "fond_carte": "rgba(181,255,225,.38)",          # Aquamarine léger
        "fond_ligne_valeurs": "rgba(235,186,185,.28)",  # Cotton Rose léger
        "axes": "#111111", "grille": "rgba(0,0,0,.08)", "zero": "rgba(0,0,0,.45)",
        "filigrane_emissions": "rgba(204,41,54,.18)",
        "filigrane_sequestration": "rgba(56,134,151,.28)",
        "texte": "#1f2933", "texte_discret": "#5b6670",
    },
    True: {    # thème sombre
        "matieres": (PACIFIC_CYAN, COTTON_ROSE),
        "titre": AQUAMARINE, "mot_couleur": COTTON_ROSE,
        "texte_sur_couleur": "#0e1117",
        "fond_carte": "rgba(56,134,151,.22)",
        "fond_ligne_valeurs": "rgba(235,186,185,.12)",
        "axes": "#f2f2f2", "grille": "rgba(255,255,255,.10)", "zero": "rgba(255,255,255,.5)",
        "filigrane_emissions": "rgba(235,186,185,.20)",
        "filigrane_sequestration": "rgba(181,255,225,.20)",
        "texte": "#f2f2f2", "texte_discret": "#aab3bb",
    },
}

# --- Graphique ----------------------------------------------------------------
LARGEUR_MAX_GRAPHIQUE = 760     # pixels : le graphique reste étroit sur grand écran
HAUTEUR_GRAPHIQUE = 540         # pixels
EPAISSEUR_COURBE = 6            # trait épais
TAILLE_POINT_FINAL = 13
NB_GRADUATIONS = 5              # graduations de chaque côté de zéro
MARGE_AXE = 1.12                # l'axe dépasse de 12 % la valeur maximale
LONGUEUR_NOM_LEGENDE = 38       # caractères conservés dans la légende
X_AXE = -3                      # position de l'axe vertical (en années)
X_FIN_AXE = 56                  # fin de l'axe horizontal (en années)
COLONNES_GRAPHIQUE = (1, 3, 1)      # proportions des colonnes : le graphique est dans celle du milieu
MARGES = dict(l=70, r=95, t=95, b=70)
TEXTE_EMISSIONS = "ÉMISSIONS"
TEXTE_SEQUESTRATION = "SÉQUESTRATION"
UNITE = "kg CO₂ eq."

# --- Tableau des étapes INIES (libellés d'INIES) ----------------------------------
COLONNES_ETAPES = (
    # (code, libellé, champ de ValeursA2)
    ("A1-A3", "Étape de production", "production"),
    ("A4-A5 Édification", "Étape du processus de construction", "construction"),
    ("B1-B7 Exploitation", "Étape d’utilisation", "utilisation"),
    ("C1-C4", "Étape de fin de vie", "fin_de_vie"),
    ("", "Total cycle de vie", "total"),
    ("D", "D-Bénéfices et charges au-delà des frontières du système", "module_d"),
)


# =============================================================================
# NOMBRES
# =============================================================================
def fr(valeur: float, decimales: int = None) -> str:
    """Nombre au format français : virgule décimale, espace fine pour les milliers, vrai signe moins."""
    if decimales is None:       # plus la valeur est petite, plus on garde de décimales
        decimales = 3 if abs(valeur) < 1 else 2 if abs(valeur) < 10 else 1
    if round(valeur, decimales) == 0:
        valeur = 0.0            # évite « −0,0 »
    texte = f"{valeur:,.{decimales}f}".replace(",", " ").replace(".", ",")
    return texte.replace("-", "−")


def fr_3_chiffres(valeur: float) -> str:
    """3 chiffres significatifs comme INIES, sans zéros inutiles : 38 ; 19,1 ; −2,69 ; 0,00595."""
    nombre = Decimal(f"{valeur:.3g}")
    if nombre == 0:
        return "0"
    texte = format(nombre, "f")
    if "." in texte:
        texte = texte.rstrip("0").rstrip(".")
    return texte.replace(".", ",").replace("-", "−")


def nom_court(nom: str, longueur: int = LONGUEUR_NOM_LEGENDE) -> str:
    """Nom raccourci pour la légende (le nom complet reste dans l'infobulle)."""
    return nom if len(nom) <= longueur else nom[:longueur - 1].rstrip() + "…"


def pas_rond(minimum: float) -> float:
    """Plus petit pas « rond » (1, 2 ou 5 × 10^k) supérieur ou égal à `minimum`."""
    if minimum <= 0:
        return 1.0
    puissance = 10 ** math.floor(math.log10(minimum))
    return next(m * puissance for m in (1, 2, 5, 10) if m * puissance >= minimum)


def limite_axe(valeur_max: float) -> float:
    """Borne de l'axe vertical (symétrique autour de zéro), avec des graduations rondes."""
    return NB_GRADUATIONS * pas_rond(valeur_max * MARGE_AXE / NB_GRADUATIONS)


def format_graduations(limite: float) -> str:
    """Format des graduations verticales : des décimales seulement si le pas est inférieur à 1."""
    pas = limite / NB_GRADUATIONS
    decimales = max(0, -math.floor(math.log10(pas))) if pas > 0 else 0
    return f",.{decimales}f"


# =============================================================================
# GRAPHIQUE (proposition 1 : traits épais, axes fléchés, filigrane, valeur finale)
# =============================================================================
def figure_cumul(series: List[dict], sombre: bool = False) -> go.Figure:
    """Courbes dynamiques cumulées sur 50 ans.

    `series` : une entrée par matériau, avec les clés
        "indice" (0 pour A, 1 pour B : fixe la couleur), "nom", "annees", "cumul".
    """
    theme = THEMES[sombre]
    limite = limite_axe(max((abs(v) for s in series for v in s["cumul"]), default=0.0))
    dernier_x = acv.PERIODE_ETUDE
    figure = go.Figure()

    # --- courbes épaisses + point et valeur finale, dans la couleur du matériau ------
    for s in series:
        couleur = theme["matieres"][s["indice"]]
        figure.add_trace(go.Scatter(
            x=s["annees"], y=s["cumul"], mode="lines", name=nom_court(s["nom"]),
            line=dict(color=couleur, width=EPAISSEUR_COURBE),
            hovertemplate=html.escape(s["nom"]) + "<br>Année %{x} : %{y:,.2f} " + UNITE + " cumulés<extra></extra>"))
        figure.add_trace(go.Scatter(
            x=[dernier_x], y=[s["cumul"][-1]], mode="markers", showlegend=False, hoverinfo="skip",
            marker=dict(color=couleur, size=TAILLE_POINT_FINAL, line=dict(color="rgba(255,255,255,.9)", width=2))))

    # valeurs finales : si deux étiquettes se touchent, on les écarte l'une de l'autre
    finales = sorted(series, key=lambda s: s["cumul"][-1])
    proches = len(finales) == 2 and abs(finales[1]["cumul"][-1] - finales[0]["cumul"][-1]) < 0.12 * limite
    for rang, s in enumerate(finales):
        decalage = (-13 if rang == 0 else 13) if proches else 0
        figure.add_annotation(
            x=dernier_x, y=s["cumul"][-1], text=f"<b>{fr(s['cumul'][-1])}</b>", showarrow=False,
            xanchor="left", xshift=16, yshift=decalage, font=dict(size=18, color=theme["matieres"][s["indice"]]))

    # --- ligne de zéro, axes fléchés et filigrane ÉMISSIONS / SÉQUESTRATION -----------
    figure.add_hline(y=0, line_width=1.5, line_dash="dash", line_color=theme["zero"])
    flechette = dict(xref="x", yref="y", axref="x", ayref="y", showarrow=True, text="", arrowhead=2,
                     arrowsize=1.3, arrowwidth=3.5, arrowcolor=theme["axes"])
    figure.add_annotation(x=X_AXE, y=limite, ax=X_AXE, ay=-limite, **flechette)            # axe vertical
    figure.add_annotation(x=X_FIN_AXE, y=-limite, ax=X_AXE, ay=-limite, **flechette)       # axe horizontal
    hauteur_demi_trace = (HAUTEUR_GRAPHIQUE - MARGES["t"] - MARGES["b"]) / 2
    taille_filigrane = min(26, int(hauteur_demi_trace / 8.8))                               # tient dans la demi-hauteur
    for texte, y, couleur in ((TEXTE_EMISSIONS, limite / 2, theme["filigrane_emissions"]),
                              (TEXTE_SEQUESTRATION, -limite / 2, theme["filigrane_sequestration"])):
        figure.add_annotation(x=2.4, y=y, text=f"<b>{texte}</b>", textangle=-90, showarrow=False,
                              font=dict(size=taille_filigrane, color=couleur))

    # --- mise en page ---------------------------------------------------------------
    figure.update_layout(
        height=HAUTEUR_GRAPHIQUE, margin=MARGES, hovermode="closest", separators=", ",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color=theme["texte"], size=13),
        legend=dict(orientation="h", y=1.13, x=0, bgcolor="rgba(0,0,0,0)", font=dict(size=13)),
        xaxis=dict(range=[X_AXE, X_FIN_AXE], tickvals=list(range(0, acv.PERIODE_ETUDE + 1, 10)), title="années",
                   showgrid=False, zeroline=False, showline=False),
        yaxis=dict(range=[-limite, limite], dtick=limite / NB_GRADUATIONS, title=f"{UNITE} cumulés",
                   gridcolor=theme["grille"], zeroline=False, showline=False, tickformat=format_graduations(limite)))
    return figure


# =============================================================================
# TABLEAU DES ÉTAPES INIES
# =============================================================================
def tableau_etapes_html(nom: str, valeurs: acv.ValeursA2, indice: int) -> str:
    """Tableau « A1-A3 | A4-A5 | B1-B7 | C1-C4 | Total | D » d'un matériau, dans la couleur de son matériau."""
    codes = "".join(f"<th>{html.escape(code)}</th>" for code, _, _ in COLONNES_ETAPES)
    libelles = "".join(f"<td>{html.escape(libelle)}</td>" for _, libelle, _ in COLONNES_ETAPES)
    cellules = "".join(f"<td>{fr_3_chiffres(getattr(valeurs, champ))}</td>" for _, _, champ in COLONNES_ETAPES)
    return (f'<div class="tab-etapes tab-{"AB"[indice]}">'
            f'<div class="tab-nom">{html.escape(nom)} <span>— réchauffement climatique ({UNITE})</span></div>'
            f'<table><tr class="codes">{codes}</tr><tr class="libelles">{libelles}</tr>'
            f'<tr class="valeurs">{cellules}</tr></table></div>')


# =============================================================================
# FEUILLE DE STYLE (injectée une fois par l'application)
# =============================================================================
_CSS = """
<style>
.titre-principal {font-size: 2.1rem; font-weight: 800; line-height: 1.2; margin: .2rem 0 .6rem 0; color: __TITRE__;}
.titre-principal .mot {color: __MOT__;}
.titre-section {font-size: 1.7rem; font-weight: 700; margin: .4rem 0 .6rem 0; color: __TITRE__;
                border-bottom: 3px solid __MOT__; display: inline-block; padding-bottom: .1rem;}
.bandeau {font-size: 1.3rem; font-weight: 700; color: __SURCOULEUR__; padding: .35rem .8rem; border-radius: 6px;
          margin-bottom: .6rem;}
.bandeau.mat-A {background: __COULEUR_A__;}
.bandeau.mat-B {background: __COULEUR_B__;}
.carte {border-left: 8px solid var(--couleur); background: __FOND_CARTE__; border-radius: 8px;
        padding: .8rem 1.1rem; margin-bottom: .5rem;}
.carte .nom {font-weight: 600; font-size: 1.05rem;}
.carte .grand {font-size: 3.4rem; font-weight: 800; line-height: 1.15; color: var(--couleur);}
.carte .unite {font-size: 1rem; font-weight: 400; opacity: .8; margin-left: .35rem; color: __TEXTE__;}
.carte .legende {font-size: .95rem; opacity: .9;}
.carte .petit {font-size: .85rem; opacity: .7; margin-top: .5rem;}
.tab-etapes {margin: 1rem auto .4rem auto; max-width: __LARGEUR__px; overflow-x: auto;}
.tab-etapes .tab-nom {font-weight: 700; margin-bottom: .3rem;}
.tab-etapes .tab-nom span {font-weight: 400; opacity: .75;}
.tab-etapes table {width: 100%; border-collapse: collapse; table-layout: fixed; text-align: center; font-size: .85rem;}
.tab-etapes th {color: __SURCOULEUR__; padding: .35rem .3rem; font-weight: 700;}
.tab-etapes td {padding: .35rem .3rem; vertical-align: top;}
.tab-etapes tr.libelles td {font-size: .72rem; opacity: .85; border-bottom: 1px solid rgba(128,128,128,.35);}
.tab-etapes tr.valeurs td {font-size: 1.15rem; font-weight: 700; background: __FOND_VALEURS__;}
.tab-A th {background: __COULEUR_A__;}
.tab-B th {background: __COULEUR_B__;}
.tab-A tr.valeurs td {color: __COULEUR_A__;}
.tab-B tr.valeurs td {color: __COULEUR_B__;}
</style>
"""


def css(sombre: bool = False) -> str:
    """Feuille de style complète (thème clair ou sombre)."""
    theme = THEMES[sombre]
    remplacements = {
        "__TITRE__": theme["titre"], "__MOT__": theme["mot_couleur"], "__SURCOULEUR__": theme["texte_sur_couleur"],
        "__COULEUR_A__": theme["matieres"][0], "__COULEUR_B__": theme["matieres"][1],
        "__FOND_CARTE__": theme["fond_carte"], "__FOND_VALEURS__": theme["fond_ligne_valeurs"],
        "__TEXTE__": theme["texte"], "__LARGEUR__": str(LARGEUR_MAX_GRAPHIQUE),
    }
    feuille = _CSS
    for cle, valeur in remplacements.items():
        feuille = feuille.replace(cle, valeur)
    return feuille
