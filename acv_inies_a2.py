"""
acv_inies_a2.py
===============
Transformation d'une ligne « Réchauffement climatique » copiée depuis la base INIES
(norme EN 15804 +A2, 13 valeurs) en ACV *dynamique* conforme à la RE2020.

MODULE AUTONOME
    N'utilise que la bibliothèque standard de Python (3.9 ou plus récent).
    Pour le réutiliser dans un autre programme : copier ce seul fichier.

UTILISATION RAPIDE
    from acv_inies_a2 import calculer_depuis_inies

    resultat = calculer_depuis_inies("1.54e+1\\t5.14e+0\\t...", dvr=50)
    print(resultat.dynamique_total)      # kg CO2 eq. dynamique RE2020, module D inclus
    print(resultat.statique_total)       # kg CO2 eq. statique (E+C-, module D / 3)

    Pour les 4 lignes « Changement climatique » (total, fossile, biogénique, occupation des sols) :
        from acv_inies_a2 import calculer_indicateurs_climat
        resultats = calculer_indicateurs_climat(texte_des_4_lignes, dvr=50)   # dict clé -> résultat

    En ligne de commande :  python acv_inies_a2.py "<13 valeurs>" 50

ORIGINE DE LA MÉTHODE
    Logique reprise à l'identique du classeur Excel « ACV_Dynamique_INIES_V2 »
    (onglets « Interface +A2 », « Calcul +A2 » et « Art. 11 »),
    de Guillaume Meunier, licence GNU GPL v3.
    Coefficients de pondération : arrêté du 4 août 2021 relatif aux exigences de
    performance énergétique (NOR : LOGL2107359A), article 11, cas général.

PRINCIPE DE L'ACV DYNAMIQUE
    Une émission de gaz à effet de serre ne pèse pas pareil selon le moment où elle
    a lieu : le coefficient vaut 1 la première année, puis diminue (0,578 à 50 ans).
    On calcule donc les émissions année par année sur 50 ans, on multiplie chaque
    année par son coefficient, puis on additionne.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional, Tuple

# =============================================================================
# PARAMÈTRES (tout ce qui peut se régler est regroupé ici)
# =============================================================================

# --- Version (voir aussi CHANGELOG.md, à tenir à jour en même temps) ----------
VERSION = "4.0.0"
DATE_VERSION = "2026-10-16"

# Historique des versions, de la plus récente à la plus ancienne : (version, date, description).
# Les versions « Excel » sont celles de l'onglet « Infos » du classeur d'origine.
HISTORIQUE_VERSIONS: Tuple[Tuple[str, str, str], ...] = (
    ("4.0.0", "2026-10-16",
     "Détail du changement climatique d'un matériau : un second champ, sous le premier, reçoit les 4 lignes « Changement climatique » (total, fossile, biogénique, occupation des sols) ; à droite, courbes cumulées puis barres empilées par étape du cycle de vie. Palette : le biogénique en vert-bleu et l'occupation des sols en vert-jaune."),
    ("3.9.0", "2026-10-15",
     "Réorganisation de l'interface."),
    ("3.6.1", "2026-10-15",
     "Script Tampermonkey 1.2.0 : panneau déroulant à 10 px du haut, réduit au titre « ACV dynamique RE2020 » ; le survol le déroule, un clic sur le titre le garde ouvert (ou le referme)."),
    ("3.6.0", "2026-10-15",
     "Script Tampermonkey 1.1.0 : deux emplacements A et B mémorisés d'une fiche INIES à l'autre (« Mettre en A », « Mettre en B », « Voir les 2 »), lien unique contenant A et/ou B ; texte du panneau foncé."),
    ("3.5.0", "2026-10-14",
     "Script Tampermonkey pour base-inies.fr : un bouton sur la fiche (norme +A2) lit les 13 valeurs « Changement climatique - total » et la DVR, puis ouvre l'application avec le matériau A pré-rempli ; test sous Node contre lien.py."),
    ("3.4.0", "2026-10-14",
     "Liens pré-remplis : l'application lit un lien (identifiant, nom, DVR, 13 valeurs) et remplit le matériau A ou B, avec contrôle strict et messages d'erreur clairs ; bouton « Copier le lien de ce matériau » sous chaque fiche."),
    ("3.3.1", "2026-10-14",
     "Échelle verticale du graphique calée sur la valeur maximale réellement tracée (plus de haut gonflé par un grand côté négatif) ; filigrane ÉMISSIONS / SÉQUESTRATION en horizontal contre la ligne de zéro quand la place manque ; légende un peu plus haut."),
    ("3.3.0", "2026-10-14",
     "Nouveau titre et textes pédagogiques (« comparaison carbone », StockC, objectif de la RE2020) ; échelle verticale du graphique adaptée automatiquement aux courbes ; courbes statiques E+C- en option (pointillés) ; exports CSV (résumé, année par année) et image du graphique ; graphique en pleine largeur sur petit écran ; versions de Streamlit et Plotly fixées."),
    ("3.2.0", "2026-10-14",
     "Fond en dégradé diagonal aux couleurs de la palette éclaircies, boîtes blanches, matériaux en Pacific Cyan et Cotton Rose (chiffres du matériau B légèrement foncés pour rester lisibles), filigrane ÉMISSIONS / SÉQUESTRATION en gris clair. Thème clair unique."),
    ("3.1.0", "2026-10-14",
     "Graphique resserré (traits épais, axes fléchés, filigrane émissions / séquestration, valeur finale), tableau des étapes INIES, catalogue de matériaux (materiaux.json avec date d'export), palette de couleurs et nouveau titre."),
    ("3.0.0", "2026-10-13",
     "Version web (Streamlit) : norme +A2 uniquement, comparaison carbone de deux matériaux, "
     "module de calcul autonome et testé contre l'Excel."),
    ("Excel V2", "2023-05-15", "Ajout de la norme +A2 (et de l'onglet de résultats A2)."),
    ("Excel V1", "2022-06-02", "Version initiale (norme +A1)."),
)

# --- Méthode ------------------------------------------------------------------
PERIODE_ETUDE = 50          # ans : durée de l'étude RE2020 (années 0 à 50)
DECIMALES_ARRONDI = 5       # décimales conservées sur les valeurs INIES (comme l'Excel)
DVR_MIN = 1                 # ans : durée de vie de référence minimale acceptée
DVR_MAX = 1000              # ans : durée de vie de référence maximale acceptée
DIVISEUR_MODULE_D_STATIQUE = 3   # statique E+C- : le module D est compté pour 1/3

# --- Lecture de la ligne collée ----------------------------------------------
NB_VALEURS_A2 = 13          # une ligne +A2 contient 13 valeurs
NB_VALEURS_A1 = 6           # une ligne +A1 en contient 6 (non prise en charge ici)
TOLERANCE_COHERENCE = 0.02  # 2 % : écart toléré (INIES arrondit à 3 chiffres significatifs)

# Nombre « scientifique » tel qu'affiché par INIES : 1.54e+1, -9.65e-2, 0.00e+0 (virgule acceptée)
MOTIF_NOMBRE = re.compile(r"^[+-]?(\d+([.,]\d*)?|[.,]\d+)([eE][+-]?\d+)?$")

# Ordre des 13 colonnes du tableau INIES (norme +A2)
LIBELLES_VALEURS_A2: Tuple[str, ...] = (
    "Étape de production (A1-A3)",
    "Étape du processus de construction (A4-A5)",
    "B1 - Utilisation",
    "B2 - Maintenance",
    "B3 - Réparation",
    "B4 - Remplacement",
    "B5 - Réhabilitation",
    "B6 - Énergie en phase d'utilisation",
    "B7 - Eau en phase d'utilisation",
    "Étape d'utilisation (B)",
    "Étape de fin de vie (C)",
    "Total cycle de vie",
    "D - Bénéfices et charges au-delà du système",
)

# --- Les 4 lignes « Changement climatique » d'une fiche INIES +A2 -------------
# (clé, libellé affiché, mot repère cherché dans le libellé INIES, en minuscules et sans accent).
# Le total est la somme des trois autres : fossile + biogénique + occupation des sols.
INDICATEURS_CLIMAT: Tuple[Tuple[str, str, str], ...] = (
    ("total", "Total", "total"),
    ("fossile", "Fossile", "fossil"),
    ("biogenique", "Biogénique", "biogen"),
    ("sols", "Occupation des sols", "occupation"),
)
CLE_TOTAL = "total"
CLES_COMPOSANTES = ("fossile", "biogenique", "sols")
MOT_REPERE_LIGNE_CLIMAT = "changement climatique"   # toutes les lignes utiles contiennent ce libellé

# Étapes du cycle de vie retenues pour répartir le résultat dynamique : (clé, libellé).
ETAPES: Tuple[Tuple[str, str], ...] = (
    ("production", "Production (A1-A3)"),
    ("construction", "Construction (A4-A5)"),
    ("utilisation", "Utilisation (B)"),
    ("fin_de_vie", "Fin de vie (C)"),
    ("module_d", "Module D"),
)

# Coefficients de pondération dynamique, année 0 à année 50 (51 valeurs).
# Source : arrêté du 4 août 2021, article 11, cas général (fCO2).
COEFFICIENTS_ART11: Tuple[float, ...] = (
    1.000, 0.992, 0.984, 0.976, 0.969, 0.961, 0.953, 0.945, 0.937, 0.929,
    0.921, 0.913, 0.905, 0.897, 0.889, 0.880, 0.872, 0.864, 0.856, 0.848,
    0.840, 0.831, 0.823, 0.815, 0.806, 0.798, 0.790, 0.781, 0.773, 0.764,
    0.756, 0.747, 0.739, 0.730, 0.721, 0.713, 0.704, 0.695, 0.686, 0.678,
    0.669, 0.660, 0.651, 0.642, 0.633, 0.624, 0.615, 0.606, 0.597, 0.587,
    0.578,
)


# =============================================================================
# STRUCTURES DE DONNÉES
# =============================================================================
class ErreurInies(ValueError):
    """Erreur de saisie, avec un message en français destiné à l'utilisateur final."""


@dataclass(frozen=True)
class ValeursA2:
    """Les 13 valeurs « Réchauffement climatique » d'une fiche INIES +A2, en kg CO2 eq."""
    production: float       # A1-A3
    construction: float     # A4-A5
    b1: float
    b2: float
    b3: float
    b4: float
    b5: float
    b6: float
    b7: float
    utilisation: float      # B (total des étapes d'utilisation)
    fin_de_vie: float       # C
    total: float            # total du cycle de vie affiché par INIES (module D exclu)
    module_d: float         # D, bénéfices et charges au-delà du système

    def en_liste(self) -> List[float]:
        """Les 13 valeurs dans l'ordre du tableau INIES."""
        return [self.production, self.construction, self.b1, self.b2, self.b3, self.b4,
                self.b5, self.b6, self.b7, self.utilisation, self.fin_de_vie,
                self.total, self.module_d]


@dataclass(frozen=True)
class ResultatA2:
    """Résultat du calcul pour un matériau (toutes les valeurs en kg CO2 eq.)."""
    dvr: int                                    # durée de vie de référence, en années
    valeurs: ValeursA2                          # valeurs INIES telles que collées
    annees: Tuple[int, ...]                     # 0 à 50
    coefficients: Tuple[float, ...]             # coefficient dynamique de chaque année
    dynamique_par_annee: Tuple[float, ...]      # émissions pondérées de chaque année
    # --- Dynamique RE2020 (module D inclus) ---
    dynamique_t0: float                         # année 0 (production + construction)
    dynamique_intermediaire: float              # années 1 à 49
    dynamique_t50: float                        # année 50 (fin de vie + module D)
    dynamique_total: float                      # somme : LE résultat à retenir
    # --- Statique E+C- (module D compté pour 1/3), pour la comparaison carbone ---
    statique_t0: float
    statique_intermediaire: float
    statique_t50: float
    statique_total: float
    # --- Répartition du total dynamique par étape : ((clé de ETAPES, valeur), ...) ; la somme = dynamique_total ---
    dynamique_par_etape: Tuple[Tuple[str, float], ...] = ()

    def cumul_dynamique(self) -> List[float]:
        """Émissions dynamiques cumulées année après année (pour tracer une courbe)."""
        cumul, somme = [], 0.0
        for valeur in self.dynamique_par_annee:
            somme += valeur
            cumul.append(somme)
        return cumul

    def cumul_statique(self) -> List[float]:
        """Émissions statiques E+C- cumulées année après année (pour tracer une courbe pointillée).

        L'Excel ne donne le statique que par phase : année 0 (production + construction), années 1 à 49
        (utilisation et remplacements) et année 50 (fin de vie + module D / 3). Pour le tracé, la phase
        intermédiaire est répartie à parts égales sur les années 1 à 49 : la courbe est une illustration,
        mais elle part de la bonne valeur et finit exactement sur `statique_total`.
        """
        par_an_intermediaire = self.statique_intermediaire / (PERIODE_ETUDE - 1)
        cumul = [self.statique_t0]
        for annee in range(1, PERIODE_ETUDE):
            cumul.append(cumul[-1] + par_an_intermediaire)
        cumul.append(cumul[-1] + self.statique_t50)
        return cumul


# =============================================================================
# 1) LECTURE DE LA LIGNE COLLÉE DEPUIS INIES
# =============================================================================
def extraire_nombres(texte: str) -> List[float]:
    """Extrait tous les nombres d'un texte collé, en ignorant les mots (libellés, unités).

    Accepte les séparateurs tabulation, espace et retour à la ligne, ainsi que
    la virgule décimale (1,54e+1) et le vrai signe moins (−).
    """
    nombres = []
    for jeton in (texte or "").replace("−", "-").split():
        if MOTIF_NOMBRE.match(jeton):
            nombres.append(float(jeton.replace(",", ".")))
    return nombres


def lire_valeurs_inies(texte: str) -> ValeursA2:
    """Transforme la ligne collée depuis INIES en `ValeursA2`.

    Lève `ErreurInies` (message clair) si le nombre de valeurs n'est pas celui d'une ligne +A2.
    """
    nombres = extraire_nombres(texte)
    nb = len(nombres)

    if nb == NB_VALEURS_A2:
        return ValeursA2(*nombres)
    if nb == 0:
        raise ErreurInies("Aucun nombre trouvé. Copiez la ligne « Réchauffement climatique » "
                          "du tableau INIES, puis collez-la ici.")
    if nb == NB_VALEURS_A1:
        raise ErreurInies(f"Cette ligne contient {NB_VALEURS_A1} valeurs : c'est le format de la "
                          f"norme +A1, que cet outil ne traite pas. Il faut une fiche en norme +A2 "
                          f"({NB_VALEURS_A2} valeurs).")
    raise ErreurInies(f"J'ai trouvé {nb} valeurs au lieu de {NB_VALEURS_A2}. Vérifiez que vous avez "
                      f"copié toute la ligne « Réchauffement climatique » (de « Étape de production » "
                      f"jusqu'à « D - Bénéfices et charges »), sans les autres lignes.")


def controler_coherence(valeurs: ValeursA2) -> List[str]:
    """Contrôles de bon sens : renvoie une liste d'avertissements (vide si tout est cohérent).

    INIES arrondit à 3 chiffres significatifs, donc on tolère un petit écart (TOLERANCE_COHERENCE).
    """
    avertissements = []

    # Le total INIES doit valoir A1-A3 + A4-A5 + B + C
    somme_etapes = valeurs.production + valeurs.construction + valeurs.utilisation + valeurs.fin_de_vie
    echelle = max(abs(valeurs.production), abs(valeurs.construction), abs(valeurs.utilisation),
                  abs(valeurs.fin_de_vie), abs(valeurs.total), 1e-12)
    if abs(somme_etapes - valeurs.total) > TOLERANCE_COHERENCE * echelle:
        avertissements.append(
            f"Les étapes ne s'additionnent pas au total : production + construction + utilisation + "
            f"fin de vie = {somme_etapes:.4g}, alors que le total INIES est {valeurs.total:.4g}. "
            f"Vérifiez que vous avez copié la bonne ligne.")

    # L'étape d'utilisation B doit valoir B1 + ... + B7
    somme_b = valeurs.b1 + valeurs.b2 + valeurs.b3 + valeurs.b4 + valeurs.b5 + valeurs.b6 + valeurs.b7
    echelle_b = max(abs(somme_b), abs(valeurs.utilisation), 1e-12)
    if abs(somme_b - valeurs.utilisation) > TOLERANCE_COHERENCE * echelle_b:
        avertissements.append(
            f"B1 à B7 s'additionnent à {somme_b:.4g}, mais l'étape d'utilisation affiche "
            f"{valeurs.utilisation:.4g}. Vérifiez la ligne copiée.")

    return avertissements


# --- Les 4 lignes « Changement climatique » ----------------------------------
def _sans_accent_minuscule(texte: str) -> str:
    """« Biogénique » -> « biogenique » : sert à repérer un libellé quelle que soit sa typographie."""
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c)).lower()


def _libelle_indicateur(cle: str) -> str:
    """Libellé affiché d'un indicateur (« fossile » -> « Fossile »)."""
    return next(libelle for k, libelle, _ in INDICATEURS_CLIMAT if k == cle)


def lire_indicateurs_climat(texte: str) -> Dict[str, ValeursA2]:
    """Lit les 4 lignes « Changement climatique » collées depuis INIES.

    Chaque ligne est reconnue par son libellé (total, fossil, biogénique, occupation des sols),
    pas par sa position : l'ordre des lignes et les lignes en trop (libellés de colonnes, autres
    indicateurs) n'ont pas d'importance. Renvoie {clé: ValeursA2}, dans l'ordre de INDICATEURS_CLIMAT.
    """
    trouvees: Dict[str, ValeursA2] = {}
    for ligne in (texte or "").splitlines():
        libelle = _sans_accent_minuscule(ligne)
        if MOT_REPERE_LIGNE_CLIMAT not in libelle:
            continue                                   # libellé de colonne, autre indicateur, ligne vide
        cle = next((k for k, _, repere in INDICATEURS_CLIMAT if repere in libelle), None)
        if cle is None:
            continue                                   # ligne « Changement climatique » d'un autre type
        if cle in trouvees:
            raise ErreurInies(f"La ligne « {_libelle_indicateur(cle)} » apparaît deux fois. "
                              f"Collez les 4 lignes une seule fois.")
        nombres = extraire_nombres(ligne)
        if len(nombres) != NB_VALEURS_A2:
            raise ErreurInies(f"La ligne « {_libelle_indicateur(cle)} » contient {len(nombres)} valeurs "
                              f"au lieu de {NB_VALEURS_A2}. Copiez-la en entier.")
        trouvees[cle] = ValeursA2(*nombres)

    manquantes = [libelle for cle, libelle, _ in INDICATEURS_CLIMAT if cle not in trouvees]
    if len(manquantes) == len(INDICATEURS_CLIMAT):
        raise ErreurInies("Aucune ligne « Changement climatique » trouvée. Copiez les 4 lignes du tableau INIES "
                          "(total, fossil, biogénique, occupation des sols) avec leur libellé, puis collez-les ici.")
    if manquantes:
        raise ErreurInies("Il manque la ou les lignes : " + ", ".join(manquantes) + ". Il faut les 4 lignes "
                          "« Changement climatique » (total, fossil, biogénique, occupation des sols).")
    return {cle: trouvees[cle] for cle, _, _ in INDICATEURS_CLIMAT}


def controler_coherence_indicateurs(valeurs: Dict[str, ValeursA2]) -> List[str]:
    """Contrôles de bon sens sur les 4 lignes : renvoie la liste des avertissements (vide si tout est cohérent).

    1) chaque ligne est cohérente en elle-même (voir `controler_coherence`) ;
    2) pour chacune des 13 colonnes : fossile + biogénique + occupation des sols = total.
    """
    avertissements = []

    for cle, libelle, _ in INDICATEURS_CLIMAT:
        avertissements += [f"Ligne « {libelle} » : {a}" for a in controler_coherence(valeurs[cle])]

    colonnes_en_ecart = []
    total = valeurs[CLE_TOTAL].en_liste()
    composantes = [valeurs[cle].en_liste() for cle in CLES_COMPOSANTES]
    for i, libelle_colonne in enumerate(LIBELLES_VALEURS_A2):
        somme = sum(c[i] for c in composantes)
        echelle = max([abs(total[i])] + [abs(c[i]) for c in composantes] + [1e-12])
        if abs(somme - total[i]) > TOLERANCE_COHERENCE * echelle:
            colonnes_en_ecart.append(f"{libelle_colonne} (somme {somme:.4g}, total {total[i]:.4g})")
    if colonnes_en_ecart:
        avertissements.append("Fossile + biogénique + occupation des sols ne donne pas le total pour : "
                              + " ; ".join(colonnes_en_ecart) + ". Vérifiez les lignes copiées.")
    return avertissements


def controler_meme_materiau(valeurs_materiau: ValeursA2, valeurs_total: ValeursA2) -> Optional[str]:
    """Message si la ligne « total » des 4 lignes n'est pas celle du matériau saisi au-dessus, sinon None.

    Les deux lignes viennent de la même fiche INIES : leurs 13 valeurs doivent être les mêmes
    (à l'arrondi près, voir TOLERANCE_COHERENCE).
    """
    a, b = valeurs_materiau.en_liste(), valeurs_total.en_liste()
    echelle = max([abs(x) for x in a + b] + [1e-12])
    if any(abs(x - y) > TOLERANCE_COHERENCE * echelle for x, y in zip(a, b)):
        return ("La ligne « total » ne correspond pas à la ligne « Réchauffement climatique » du matériau ci-dessus : "
                "vérifiez que les deux viennent de la même fiche INIES.")
    return None


# =============================================================================
# 2) CALCUL DE L'ACV DYNAMIQUE
# =============================================================================
def arrondir(valeur: float, decimales: int = DECIMALES_ARRONDI) -> float:
    """Arrondi identique à la fonction ARRONDI d'Excel (égalité arrondie en s'éloignant de zéro)."""
    pas = Decimal(1).scaleb(-decimales)
    arrondi = float(Decimal(repr(float(valeur))).quantize(pas, rounding=ROUND_HALF_UP))
    return arrondi + 0.0    # évite l'affichage d'un « -0.0 »


def verifier_dvr(dvr) -> int:
    """Contrôle la durée de vie de référence et la renvoie sous forme d'entier."""
    if isinstance(dvr, bool) or not isinstance(dvr, (int, float)) or float(dvr) != int(dvr):
        raise ErreurInies("La durée de vie de référence (DVR) doit être un nombre entier d'années.")
    dvr = int(dvr)
    if not DVR_MIN <= dvr <= DVR_MAX:
        raise ErreurInies(f"La durée de vie de référence doit être comprise entre {DVR_MIN} et {DVR_MAX} ans.")
    return dvr


def calculer_acv_dynamique(valeurs: ValeursA2, dvr: int) -> ResultatA2:
    """Calcule l'ACV dynamique RE2020 (et le statique E+C- pour la comparaison carbone).

    Étapes, qui suivent l'onglet « Calcul +A2 » du classeur Excel :
      1. on arrondit les valeurs INIES (5 décimales) ;
      2. on construit les émissions de chaque année de 0 à 50 :
           - année 0  : production + construction ;
           - années 1 à 49 : étape d'utilisation (B) répartie à parts égales sur la DVR ;
           - année 50 : utilisation + fin de vie + module D ;
      3. si la DVR est inférieure à 50 ans, le produit est remplacé tous les `dvr` ans :
         chaque remplacement ajoute production + construction + fin de vie (et le module D) ;
         le dernier remplacement n'est compté qu'au prorata de sa durée utile dans les 50 ans ;
      4. chaque année est multipliée par son coefficient de l'article 11, puis on additionne.

    Le résultat donne aussi la répartition du total par étape (`dynamique_par_etape`).
    """
    dvr = verifier_dvr(dvr)

    # --- Valeurs INIES arrondies (cellules C19 à H19 de l'onglet « Interface +A2 ») -------------
    production = arrondir(valeurs.production)
    construction = arrondir(valeurs.construction)
    utilisation = arrondir(valeurs.utilisation)
    fin_de_vie = arrondir(valeurs.fin_de_vie)
    total_inies = arrondir(valeurs.total)
    module_d = arrondir(valeurs.module_d)

    # --- Grandeurs dérivées ----------------------------------------------------------------------
    utilisation_par_an = utilisation / dvr                       # B réparti sur la durée de vie
    nb_cycles_entiers = PERIODE_ETUDE // dvr                     # « ALPHA » de l'Excel
    part_dernier_cycle = PERIODE_ETUDE / dvr - nb_cycles_entiers  # « Futil » de l'Excel
    annee_dernier_cycle = dvr * nb_cycles_entiers                # année où tombe le dernier remplacement

    # --- Frise année par année -------------------------------------------------------------------
    annees = tuple(range(PERIODE_ETUDE + 1))
    dynamique_par_annee = []
    par_etape = {cle: 0.0 for cle, _ in ETAPES}      # total pondéré de chaque étape, sur les 50 ans
    for annee in annees:
        coefficient = COEFFICIENTS_ART11[annee]
        emissions = {cle: 0.0 for cle, _ in ETAPES}  # émissions de l'année, par étape, avant pondération

        # (a) produit d'origine
        if annee == 0:
            emissions["production"] += production
            emissions["construction"] += construction
        else:
            emissions["utilisation"] += utilisation_par_an
        if annee == PERIODE_ETUDE:
            emissions["fin_de_vie"] += fin_de_vie
            emissions["module_d"] += module_d

        # (b) remplacements (jamais à l'année 0)
        if annee > 0 and annee % dvr == 0:
            # le dernier remplacement n'est compté qu'au prorata de sa durée utile
            if nb_cycles_entiers > 0 and annee % annee_dernier_cycle == 0:
                part = part_dernier_cycle
            else:
                part = 1.0
            emissions["production"] += production * part        # produit remplacé : production,
            emissions["construction"] += construction * part    # construction,
            emissions["fin_de_vie"] += fin_de_vie * part        # fin de vie,
            emissions["module_d"] += module_d * part            # et module D du remplacement

        # (c) pondération par le coefficient de l'année
        dynamique_par_annee.append(sum(emissions.values()) * coefficient)
        for cle, valeur in emissions.items():
            par_etape[cle] += valeur * coefficient

    # --- Regroupement par phase (cellules D24, E24, F24, G24 de l'Excel) -------------------------
    dynamique_t0 = dynamique_par_annee[0]
    dynamique_t50 = dynamique_par_annee[PERIODE_ETUDE]
    dynamique_intermediaire = sum(dynamique_par_annee[1:PERIODE_ETUDE])
    dynamique_total = sum(dynamique_par_annee)

    # --- Statique E+C- (cellules D23, E23, F23, G23 de l'Excel) ----------------------------------
    statique_t0 = production + construction
    statique_t50 = fin_de_vie + module_d / DIVISEUR_MODULE_D_STATIQUE
    statique_total = (PERIODE_ETUDE / min(PERIODE_ETUDE, dvr)) * (
        total_inies + module_d / DIVISEUR_MODULE_D_STATIQUE)
    statique_intermediaire = statique_total - statique_t50 - statique_t0

    return ResultatA2(
        dvr=dvr, valeurs=valeurs, annees=annees,
        coefficients=COEFFICIENTS_ART11, dynamique_par_annee=tuple(dynamique_par_annee),
        dynamique_t0=dynamique_t0, dynamique_intermediaire=dynamique_intermediaire,
        dynamique_t50=dynamique_t50, dynamique_total=dynamique_total,
        statique_t0=statique_t0, statique_intermediaire=statique_intermediaire,
        statique_t50=statique_t50, statique_total=statique_total,
        dynamique_par_etape=tuple(par_etape.items()),
    )


def calculer_depuis_inies(texte: str, dvr: int) -> ResultatA2:
    """Raccourci : texte collé depuis INIES + DVR -> résultat. C'est LA fonction à réutiliser."""
    return calculer_acv_dynamique(lire_valeurs_inies(texte), dvr)


def calculer_indicateurs_climat(texte: str, dvr: int) -> Dict[str, ResultatA2]:
    """Raccourci : les 4 lignes « Changement climatique » collées depuis INIES + DVR -> {clé: résultat}."""
    return {cle: calculer_acv_dynamique(v, dvr) for cle, v in lire_indicateurs_climat(texte).items()}


# =============================================================================
# 3) UTILISATION EN LIGNE DE COMMANDE
# =============================================================================
if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print(f"acv_inies_a2 v{VERSION}\nUsage : python acv_inies_a2.py \"<13 valeurs INIES>\" <DVR en années>")
        sys.exit(1)
    try:
        r = calculer_depuis_inies(sys.argv[1], int(sys.argv[2]))
    except (ErreurInies, ValueError) as erreur:
        print("Erreur :", erreur)
        sys.exit(2)
    print(f"Dynamique RE2020 : {r.dynamique_total:.4f} kg CO2 eq.")
    print(f"Statique E+C-    : {r.statique_total:.4f} kg CO2 eq.")
    print(f"Total INIES      : {r.valeurs.total:.4g} kg CO2 eq. (module D : {r.valeurs.module_d:.4g})")
