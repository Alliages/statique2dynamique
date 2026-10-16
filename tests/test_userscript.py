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


def node_async(corps: str, donnees=None):
    """Comme node(), pour du code asynchrone : `corps` est le corps d'une fonction async (avec `s` et `d`) qui renvoie le résultat."""
    programme = (f"const s = require({json.dumps(str(SCRIPT))}); "
                 f"const d = JSON.parse(require('fs').readFileSync(0, 'utf8')); "
                 f"(async () => {{ {corps} }})().then(r => process.stdout.write(JSON.stringify(r)));")
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


# ----------------------------------------------------------------------------
# Limitation des appels à l'API d'INIES : fiche déjà rangée, donc pas de nouvel appel
# ----------------------------------------------------------------------------
UNE_HEURE_MS = 3600 * 1000
TRENTE_JOURS_MS = 30 * 24 * UNE_HEURE_MS


def test_fiche_deja_rangee_reutilisee_pour_a_comme_pour_b():
    fiche_rangee = {"id": 7, "luLe": 1000}
    expr = "[s.ficheDejaLue(d.e1, 7, d.t), s.ficheDejaLue(d.e2, 7, d.t), s.ficheDejaLue(d.e1, '7', d.t)]"
    donnees = {"e1": {"A": fiche_rangee, "B": None}, "e2": {"A": None, "B": fiche_rangee}, "t": 1000 + UNE_HEURE_MS}
    assert node(expr, donnees) == [fiche_rangee, fiche_rangee, fiche_rangee]


def test_fiche_trop_ancienne_autre_fiche_ou_sans_date_pas_reutilisee():
    def reutilisee(fiche_rangee, id_demande, maintenant):
        return node("s.ficheDejaLue({A: d.f, B: null}, d.id, d.t)", {"f": fiche_rangee, "id": id_demande, "t": maintenant})
    assert reutilisee({"id": 7, "luLe": 0}, 7, TRENTE_JOURS_MS - 1) is not None   # juste avant 30 jours : réutilisée
    assert reutilisee({"id": 7, "luLe": 0}, 7, TRENTE_JOURS_MS) is None            # 30 jours : relue
    assert reutilisee({"id": 7, "luLe": 5000}, 7, 4000) is None                           # date dans le futur : relue
    assert reutilisee({"id": 7, "luLe": 1000}, 8, 2000) is None                           # autre fiche : lue
    assert reutilisee({"id": 7}, 7, 2000) is None                                         # sans date de lecture : relue
    assert node("s.ficheDejaLue({A: null, B: null}, 7, 2000)", {}) is None                # emplacements vides


def test_emplacements_memorises_sans_date_de_lecture_sont_relus_une_fois():
    ancienne = {"id": 7, "nom": "Ancienne fiche", "dvr": 50, "valeurs": VALEURS_50632}      # format d'avant : pas de luLe
    recente = {**ancienne, "id": 8, "luLe": 1000}
    res = node_async("globalThis.GM_getValue = () => JSON.stringify(d.stocke); const e = s.lireEmplacements();"
                     "return {e, ancienne: s.ficheDejaLue(e, 7, 2000), recente: s.ficheDejaLue(e, 8, 2000)};",
                     {"stocke": {"A": ancienne, "B": recente}})
    assert res["e"]["A"]["luLe"] is None and res["e"]["B"]["luLe"] == 1000   # la date de lecture est conservée
    assert res["ancienne"] is None and res["recente"] is not None


def test_une_fiche_deja_rangee_ne_declenche_aucun_appel_a_l_api(fiche):
    res = node_async("""
        let appels = 0;
        globalThis.fetch = async () => { appels += 1; return {ok: true, status: 200, json: async () => d}; };
        const premiere = await s.obtenirFiche(50632, {A: null, B: null});          // fiche inconnue : 1 appel
        const pour_b = await s.obtenirFiche(50632, {A: premiere, B: null});       // déjà en A : aucun appel
        const encore = await s.obtenirFiche(50632, {A: premiere, B: pour_b});      // déjà en A et B : aucun appel
        return {appels, memeFiche: pour_b === premiere && encore === premiere, luLe: Number.isFinite(premiere.luLe)};
    """, fiche)
    assert res == {"appels": 1, "memeFiche": True, "luLe": True}


def test_un_clic_pendant_une_lecture_est_ignore_puis_le_verrou_est_relache():
    res = node_async("""
        let appels = 0, liberer;
        const protegee = s.uneSeuleALaFois(async (x) => { appels += 1; await new Promise(r => { liberer = r; }); return x; });
        const premier = protegee("a");                 // lecture en cours...
        const pendant = await protegee("b");           // ...ce second clic est ignoré
        await new Promise(r => setTimeout(r, 0));      // laisse la première démarrer
        liberer();
        const fini = await premier;
        const apres = protegee("c");                   // le verrou est relâché : une nouvelle lecture démarre
        await new Promise(r => setTimeout(r, 0)); liberer();
        return {appels, pendant: pendant === undefined, fini, apres: await apres};
    """)
    assert res == {"appels": 2, "pendant": True, "fini": "a", "apres": "c"}


def test_le_verrou_est_relache_meme_si_la_lecture_echoue():
    res = node_async("""
        let appels = 0;
        const protegee = s.uneSeuleALaFois(async () => { appels += 1; throw new Error("échec"); });
        const erreurs = [];
        for (let i = 0; i < 2; i++) { try { await protegee(); } catch (e) { erreurs.push(e.message); } }
        return {appels, erreurs};
    """)
    assert res == {"appels": 2, "erreurs": ["échec", "échec"]}


def test_attente_restante_avant_un_nouvel_appel():
    # (dernier appel, maintenant, délai minimum) -> attente restante
    cas = [[1000, 1000, 2000], [1000, 2500, 2000], [1000, 3000, 2000], [1000, 9000, 2000], [0, 1_700_000_000_000, 2000], [5000, 1000, 2000]]
    assert node("d.map(([dernier, maintenant, minimum]) => s.attenteRestante(dernier, maintenant, minimum))", cas) == [
        2000, 500, 0, 0, 0, 2000]     # le dernier cas (horloge reculée) est plafonné au délai minimum
    assert node("s.attenteRestante(Date.now() - 5000)", {}) == 0              # délai par défaut : écoulé
    assert node("s.attenteRestante(Date.now()) > 1900", {}) is True           # délai par défaut : 2 s


def test_deux_appels_a_l_api_sont_espaces_d_au_moins_2_secondes_meme_apres_un_echec(fiche):
    res = node_async("""
        const debuts = [];
        globalThis.fetch = async () => {
          debuts.push(Date.now());
          if (debuts.length === 1) throw new Error("réseau");        // le premier appel échoue
          return {ok: true, status: 200, json: async () => d};
        };
        try { await s.lireFiche(50632); } catch (e) { /* attendu */ }
        const lue = await s.lireFiche(50632);                         // le second doit patienter
        return {appels: debuts.length, ecart: debuts[1] - debuts[0], id: lue.id};
    """, fiche)
    assert res["appels"] == 2 and res["id"] == 50632
    assert 1900 <= res["ecart"] < 4000


def test_l_appel_a_l_api_reutilise_le_cache_du_navigateur_et_la_session(fiche):
    res = node_async("""
        let recu;
        globalThis.fetch = async (url, options) => { recu = {url, options}; return {ok: true, status: 200, json: async () => d}; };
        await s.lireFiche(50632);
        return recu;
    """, fiche)
    assert res["url"] == "/api/Produit/50632"
    assert res["options"]["cache"] == "force-cache"            # copie du navigateur réutilisée si elle existe
    assert res["options"]["credentials"] == "same-origin"      # même session que la page
    assert res["options"]["headers"] == {"Accept": "application/json"}
