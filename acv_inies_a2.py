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
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import List, Tuple

# =============================================================================
# PARAMÈTRES (tout ce qui peut se régler est regroupé ici)
# =============================================================================

# --- Version (voir aussi CHANGELOG.md, à tenir à jour en même temps) ----------
VERSION = "3.2.0"
DATE_VERSION = "2026-10-14"

# Historique des versions, de la plus récente à la plus ancienne : (version, date, description).
# Les versions « Excel » sont celles de l'onglet « Infos » du classeur d'origine.
HISTORIQUE_VERSIONS: Tuple[Tuple[str, str, str], ...] = (
    ("3.2.0", "2026-10-14",
     "Fond en dégradé diagonal aux couleurs de la palette éclaircies, boîtes blanches, matériaux en Pacific Cyan et Cotton Rose (chiffres du matériau B légèrement foncés pour rester lisibles), filigrane ÉMISSIONS / SÉQUESTRATION en gris clair. Thème clair unique."),
    ("3.1.0", "2026-10-14",
     "Graphique resserré (traits épais, axes fléchés, filigrane émissions / séquestration, valeur finale), tableau des étapes INIES, catalogue de matériaux (materiaux.json avec date d'export), palette de couleurs et nouveau titre."),
    ("3.0.0", "2026-10-13",
     "Version web (Streamlit) : norme +A2 uniquement, comparaison de deux matériaux, "
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
    # --- Statique E+C- (module D compté pour 1/3), pour comparaison ---
    statique_t0: float
    statique_intermediaire: float
    statique_t50: float
    statique_total: float

    def cumul_dynamique(self) -> List[float]:
        """Émissions dynamiques cumulées année après année (pour tracer une courbe)."""
        cumul, somme = [], 0.0
        for valeur in self.dynamique_par_annee:
            somme += valeur
            cumul.append(somme)
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
    """Calcule l'ACV dynamique RE2020 (et le statique E+C- en comparaison).

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
    cout_remplacement = production + construction + fin_de_vie   # un remplacement complet
    nb_cycles_entiers = PERIODE_ETUDE // dvr                     # « ALPHA » de l'Excel
    part_dernier_cycle = PERIODE_ETUDE / dvr - nb_cycles_entiers  # « Futil » de l'Excel
    annee_dernier_cycle = dvr * nb_cycles_entiers                # année où tombe le dernier remplacement

    # --- Frise année par année -------------------------------------------------------------------
    annees = tuple(range(PERIODE_ETUDE + 1))
    dynamique_par_annee = []
    for annee in annees:
        coefficient = COEFFICIENTS_ART11[annee]

        # (a) produit d'origine
        if annee == 0:
            emission = production + construction
        elif annee == PERIODE_ETUDE:
            emission = utilisation_par_an + fin_de_vie + module_d
        else:
            emission = utilisation_par_an
        total_annee = emission * coefficient

        # (b) remplacements (jamais à l'année 0)
        remplacement = annee > 0 and annee % dvr == 0
        if remplacement:
            # le dernier remplacement n'est compté qu'au prorata de sa durée utile
            if nb_cycles_entiers > 0 and annee % annee_dernier_cycle == 0:
                part = part_dernier_cycle
            else:
                part = 1.0
            total_annee += cout_remplacement * part * coefficient    # produit remplacé
            total_annee += module_d * part * coefficient             # module D du remplacement

        dynamique_par_annee.append(total_annee)

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
    )


def calculer_depuis_inies(texte: str, dvr: int) -> ResultatA2:
    """Raccourci : texte collé depuis INIES + DVR -> résultat. C'est LA fonction à réutiliser."""
    return calculer_acv_dynamique(lire_valeurs_inies(texte), dvr)


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
