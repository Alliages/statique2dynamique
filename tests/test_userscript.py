"""
Tests du script Tampermonkey (tampermonkey/acv_inies.user.js), exécuté avec Node.

Le script doit produire EXACTEMENT les mêmes nombres, arrondis et liens que le code Python (lien.py).
Les tests sont ignorés si Node n'est pas installé. Le bouton sur la page INIES (partie DOM) ne se teste
pas ici : il se vérifie à la main sur une fiche (voir tampermonkey/infos.txt).

Lancer depuis la racine du projet :  python3 -m pytest -q
"""
import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# ----------------------------------------------------------------------------
# VARIABLES
# ----------------------------------------------------------------------------
RACINE = Path(__file__).resolve().parent.parent
SCRIPT = RACINE / "tampermonkey" / "acv_inies.user.js"
FICHE = RACINE / "tests" / "fixtures" / "fiche_50632.json"
URL_APP = "https://statique2dynamique.streamlit.app/"
VALEURS_50632 = [4.23655, 1.51718, -0.445, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -0.445, 15.52815, 20.83689, -0.43737]
# Nombres délicats pour l'arrondi et l'écriture (notation scientifique, égalités, négatifs, grands)
NOMBRES_DELICATS = [0, 5, -0.445, 0.00595, 1e-7, 1.5e-7, 4.2365533, 1.517184275, 0.015625, 1.000005, 2.675,
                    -0.000004, -0.000005, 123456789.123456, 1e21, 0.1 + 0.2, 99999.999995, 1234.5]
NOMS_DELICATS = ["Dalle Bois-Béton 15 cm", "  Mur (béton) *test* ! 'a' ", "Panneau\tà\nlignes", "x" * 300, "Ça, c'est: 100 % ☺"]

sys.path.insert(0, str(RACINE))
import acv_inies_a2 as acv  # noqa: E402
import catalogue  # noqa: E402
import lien  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="Node n'est pas installé")


def node(expression: str, donnees=None):
    """Évalue `expression` (qui peut utiliser `s` = exports du script et `d` = données) et renvoie le JSON obtenu."""
    programme = (f"const s = require({json.dumps(str(SCRIPT))}); "
                 f"const d = JSON.parse(require('fs').readFileSync(0, 'utf8')); "
                 f"process.stdout.write(JSON.stringify({expression}));")
    sortie = subprocess.run(["node", "-e", programme], input=json.dumps(donnees), capture_output=True,
                            text=True, check=True)
    return json.loads(sortie.stdout)


@pytest.fixture(scope="module")
def fiche():
    return json.loads(FICHE.read_text(encoding="utf-8"))


def test_extraction_donne_les_13_valeurs_attendues(fiche):
    res = node("s.extraireFiche(d, 50632)", fiche)
    assert res["valeurs"] == VALEURS_50632
    assert res["dvr"] == 50 and res["id"] == 50632
    assert res["nom"] == "Dalle Bois-Béton 15 cm (Hors dalle de compression)"


def test_extraction_donne_le_meme_resultat_que_l_application(fiche):
    res = node("s.extraireFiche(d, 50632)", fiche)
    r = acv.calculer_acv_dynamique(acv.ValeursA2(*res["valeurs"]), res["dvr"])
    assert round(r.dynamique_total, 4) == 14.1243


def test_le_lien_est_identique_a_celui_de_lien_py(fiche):
    res = node("s.extraireFiche(d, 50632)", fiche)
    attendu = lien.construire_lien(URL_APP, 0, res["nom"], res["id"], res["dvr"], acv.ValeursA2(*res["valeurs"]))
    assert node("s.construireLien({A: s.extraireFiche(d, 50632), B: null})", fiche) == attendu


def test_lien_pour_b_seul_et_pour_les_deux_relu_par_l_application(fiche):
    from urllib.parse import parse_qsl, urlparse
    res = node("s.extraireFiche(d, 50632)", fiche)
    # B seul : identique à lien.py pour l'indice 1
    attendu_b = lien.construire_lien(URL_APP, 1, res["nom"], res["id"], res["dvr"], acv.ValeursA2(*res["valeurs"]))
    assert node("s.construireLien({A: null, B: s.extraireFiche(d, 50632)})", fiche) == attendu_b
    # A + B : les paramètres sont la réunion de ceux de A et de B, et l'application relit bien les deux
    donnees = {"fiche": fiche, "autre": 123}
    deux = node("s.construireLien({A: s.extraireFiche(d.fiche, 50632), "
                "B: {id: 7, nom: 'Autre (test)', dvr: 30, valeurs: s.extraireFiche(d.fiche, 50632).valeurs}})", donnees)
    parametres = dict(parse_qsl(urlparse(deux).query))
    materiaux, erreurs = lien.lire_lien(parametres)
    assert erreurs == [] and [m.lettre for m in materiaux] == ["A", "B"]
    assert [m.dvr for m in materiaux] == [50, 30] and materiaux[1].nom == "Autre (test)"


def test_aucun_emplacement_rempli_donne_pas_de_lien():
    assert node("s.construireLien({A: null, B: null})", {}) is None


def test_libelle_du_bouton_voir():
    assert node("[s.texteVoir({A:1,B:1}), s.texteVoir({A:1,B:null}), s.texteVoir({A:null,B:1}), s.texteVoir({A:null,B:null})]",
                {}) == ["Voir les 2 ▸", "Voir A ▸", "Voir B ▸", "Voir ▸"]


def test_le_lien_du_script_est_relu_par_l_application(fiche):
    adresse = node("s.construireLien({A: s.extraireFiche(d, 50632), B: null})", fiche)
    from urllib.parse import parse_qsl, urlparse
    parametres = dict(parse_qsl(urlparse(adresse).query))
    materiaux, erreurs = lien.lire_lien(parametres)
    assert erreurs == [] and len(materiaux) == 1
    assert materiaux[0].dvr == 50 and materiaux[0].valeurs.en_liste() == VALEURS_50632


def test_nombres_delicats_arrondi_et_ecriture_comme_en_python():
    attendu = [catalogue.nombre(acv.arrondir(x)) for x in NOMBRES_DELICATS]
    obtenu = node("d.map(x => s.nombre(s.arrondir(x)))", NOMBRES_DELICATS)
    assert obtenu == attendu


def test_noms_delicats_encodes_comme_en_python():
    for nom in NOMS_DELICATS:
        valeurs = acv.ValeursA2(*VALEURS_50632)
        attendu = lien.construire_lien(URL_APP, 0, nom, 7, 30, valeurs)
        fiche_js = {"id": 7, "nom": nom, "dvr": 30, "valeurs": VALEURS_50632}
        # le script nettoie le nom lui-même à l'extraction : on applique le même nettoyage avant de construire
        obtenu = node("s.construireLien({A: {...d, nom: s.nettoyerNom(d.nom)}, B: null})", fiche_js)
        assert obtenu == attendu, nom


@pytest.mark.parametrize("modification, message", [
    (lambda f: f.update(idNorme=4), "+A2"),
    (lambda f: f.update(dvt=0), "DVR"),
    (lambda f: f.update(dvt=None), "DVR"),
    (lambda f: f.update(idProduit=1), "ne correspond pas"),
    (lambda f: f.pop("tIndicateurQuantites"), "inattendue"),
    (lambda f: f.update(tIndicateurQuantites=[q for q in f["tIndicateurQuantites"] if q["idPhaseNorme"] != 110]),
     "phase 110"),
    (lambda f: f["tIndicateurQuantites"].append(copy.deepcopy(
        next(q for q in f["tIndicateurQuantites"] if q["idPhaseNorme"] == 110
             and q["idIndicateurNormeNavigation"]["ordre"] == 1))), "phase 110"),
    (lambda f: next(q for q in f["tIndicateurQuantites"] if q["idPhaseNorme"] == 95
                    and q["idIndicateurNormeNavigation"]["ordre"] == 1).update(quantite=None), "phase 95"),
])
def test_fiches_invalides_refusees_avec_message_clair(fiche, modification, message):
    mauvaise = copy.deepcopy(fiche)
    modification(mauvaise)
    erreur = node("(() => { try { s.extraireFiche(d, 50632); return null; } catch (e) { return e.message; } })()",
                  mauvaise)
    assert erreur and message in erreur


def test_constantes_du_script_alignees_sur_python():
    texte = SCRIPT.read_text(encoding="utf-8")
    assert f"const FORMAT_LIEN = {lien.FORMAT_LIEN};" in texte
    assert f"const DECIMALES = {acv.DECIMALES_ARRONDI};" in texte
    assert f"const DVR_MIN = {acv.DVR_MIN}, DVR_MAX = {acv.DVR_MAX};" in texte
    assert f"const LONGUEUR_NOM_MAX = {lien.LONGUEUR_NOM_MAX};" in texte
    assert f'const URL_APP = "{URL_APP}";' in texte
