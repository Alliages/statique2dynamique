// ==UserScript==
// @name         ACV dynamique RE2020 - envoyer les fiches INIES
// @namespace    https://github.com/Alliages/statique2dynamique
// @version      1.1.0
// @description  Ajoute un panneau sur les fiches base-inies.fr (norme +A2) : mettre une fiche en A, une autre en B, puis ouvrir l'outil ACV dynamique RE2020 avec les valeurs déjà remplies.
// @author       Alliages
// @match        https://www.base-inies.fr/*
// @match        https://base-inies.fr/*
// @grant        GM_openInTab
// @grant        GM_getValue
// @grant        GM_setValue
// @run-at       document-idle
// @updateURL    https://raw.githubusercontent.com/Alliages/statique2dynamique/main/tampermonkey/acv_inies.user.js
// @downloadURL  https://raw.githubusercontent.com/Alliages/statique2dynamique/main/tampermonkey/acv_inies.user.js
// ==/UserScript==

/*
 * Ce que fait ce script, et rien d'autre :
 *   1. sur une page « .../infos-produit/<id> », il affiche un petit panneau en haut à droite ;
 *   2. « Mettre en A » / « Mettre en B » lit la fiche ouverte (adresse /api/Produit/<id>, avec votre session,
 *      comme le fait le site), vérifie qu'elle est en norme +A2, en extrait les 13 valeurs « Changement climatique
 *      - total » et la durée de vie de référence (DVR), arrondies à 5 décimales comme l'application,
 *      et range le résultat dans l'emplacement A ou B (mémorisé par Tampermonkey d'une fiche à l'autre) ;
 *   3. « Voir les 2 » ouvre l'application dans un nouvel onglet, avec un lien pré-rempli (format identique à lien.py).
 * Aucune donnée n'est envoyée ailleurs que dans l'adresse de ce lien. Une seule fiche lue par clic.
 */

// =============================================================================
// VARIABLES (tout ce qui peut se régler est regroupé ici)
// =============================================================================
const URL_APP = "https://statique2dynamique.streamlit.app/";   // l'application à ouvrir
const FORMAT_LIEN = 1;                       // doit être égal à FORMAT_LIEN de lien.py
const CHEMIN_FICHE = /\/infos-produit\/(\d{1,9})(?:[/?#]|$)/;  // adresse d'une fiche : /infos-produit/<id>
const CHEMIN_API = "/api/Produit/";          // + identifiant de la fiche
const ID_NORME_A2 = 5;                       // « idNorme » d'une fiche en norme +A2
const ORDRE_CHANGEMENT_CLIMATIQUE = 1;       // indicateur « Changement climatique - total » (2 fossile, 3 biogénique, 4 usage des sols)
// Les 13 valeurs, dans l'ordre attendu par l'application (même ordre que le copier-coller INIES) :
// A1-A3, A4-A5, B1 à B7, B1-B7, C1-C4, total, module D.   (identifiants « idPhaseNorme » de l'API)
const PHASES = [95, 112, 98, 99, 100, 101, 102, 103, 104, 113, 109, 110, 111];
const DECIMALES = 5;                         // comme DECIMALES_ARRONDI de acv_inies_a2.py
const DVR_MIN = 1, DVR_MAX = 1000;           // comme acv_inies_a2.py
const LONGUEUR_NOM_MAX = 120;                // comme lien.py
const DELAI_SURVEILLANCE_MS = 500;           // le site change de page sans recharger : on surveille l'adresse
const ID_PANNEAU = "acv-inies-panneau";
const CLE_MEMOIRE = "acv_emplacements";      // clé de mémorisation Tampermonkey : { A: fiche|null, B: fiche|null }
const LETTRES = ["A", "B"];
// Aspect du panneau
const COULEUR_FOND = "#ebbab9", COULEUR_TEXTE = "#08415c";
const POSITION_PANNEAU = { right: "20px", top: "85px" };
// Textes affichés
const TEXTE_TITRE = "ACV dynamique RE2020";
const TEXTE_VIDE = "(vide)";
const TEXTE_ERREUR = "ACV dynamique RE2020 : ";

// =============================================================================
// 1) EXTRACTION ET LIEN (fonctions pures, testées sous Node contre lien.py)
// =============================================================================

/** Écrit un nombre en notation décimale (jamais « 1e-7 ») : "1e-7" -> "0.0000001". */
function developper(x) {
  const texte = String(x);
  if (!/e/i.test(texte)) return texte;
  const [mantisse, exposant] = texte.toLowerCase().split("e");
  const signe = mantisse.startsWith("-") ? "-" : "";
  const [entiere, decimale = ""] = mantisse.replace("-", "").split(".");
  const chiffres = entiere + decimale;
  const virgule = entiere.length + Number(exposant);
  if (virgule <= 0) return signe + "0." + "0".repeat(-virgule) + chiffres;
  if (virgule >= chiffres.length) return signe + chiffres + "0".repeat(virgule - chiffres.length);
  return signe + chiffres.slice(0, virgule) + "." + chiffres.slice(virgule);
}

/** Comme catalogue.nombre (Python) : 5 -> "5.0", 0.00595 -> "0.00595", -0 -> "-0.0". */
function nombre(x) {
  if (Object.is(x, -0)) return "-0.0";
  const texte = developper(x);
  return texte.includes(".") ? texte : texte + ".0";
}

/** Arrondi à `DECIMALES` décimales, égalité arrondie en s'éloignant de zéro (ARRONDI d'Excel, comme arrondir() en Python). */
function arrondir(x, decimales = DECIMALES) {
  const texte = developper(x);
  const negatif = texte.startsWith("-");
  const [entiere, fraction = ""] = texte.replace("-", "").split(".");
  const conservees = (fraction + "0".repeat(decimales)).slice(0, decimales);
  let entier = BigInt(entiere + conservees);
  if (fraction.length > decimales && fraction[decimales] >= "5") entier += 1n;
  const brut = entier.toString().padStart(decimales + 1, "0");
  const resultat = Number(brut.slice(0, -decimales) + "." + brut.slice(-decimales));
  return negatif && resultat !== 0 ? -resultat : resultat;
}

/** Nom nettoyé comme lien.nettoyer_nom : sans caractères de contrôle, espaces simplifiés, longueur limitée. */
function nettoyerNom(nom) {
  const propre = String(nom).replace(/[\x00-\x1f\x7f]/g, " ").split(/\s+/).filter(Boolean).join(" ");
  return Array.from(propre).slice(0, LONGUEUR_NOM_MAX).join("");
}

/** Comme urllib.parse.quote(safe=","), sans exception sauf la virgule : seuls A-Z a-z 0-9 _ . - ~ restent tels quels. */
function encoder(texte) {
  return encodeURIComponent(texte)
    .replace(/[!'()*]/g, (c) => "%" + c.charCodeAt(0).toString(16).toUpperCase())
    .replace(/%2C/g, ",");
}

/**
 * Lit la réponse de l'API pour une fiche et renvoie { id, nom, dvr, valeurs } ou lève une Error au message clair.
 * `idAttendu` : identifiant lu dans l'adresse de la page (la réponse doit correspondre).
 */
function extraireFiche(json, idAttendu) {
  if (!json || typeof json !== "object" || !Array.isArray(json.tIndicateurQuantites)) {
    throw new Error("Réponse inattendue du site INIES (la fiche n'a pas pu être lue).");
  }
  const id = Number(json.idProduit);
  if (!Number.isInteger(id) || id < 1 || (idAttendu !== undefined && id !== Number(idAttendu))) {
    throw new Error("La réponse du site ne correspond pas à la fiche ouverte.");
  }
  if (json.idNorme !== ID_NORME_A2) {
    throw new Error("Cette fiche n'est pas en norme +A2 : l'outil ne sait traiter que les fiches +A2.");
  }
  const dvr = Number(json.dvt);
  if (!Number.isInteger(dvr) || dvr < DVR_MIN || dvr > DVR_MAX) {
    throw new Error("Durée de vie de référence (DVR) absente ou invalide sur cette fiche.");
  }
  const valeurs = PHASES.map((phase) => {
    const trouvees = json.tIndicateurQuantites.filter((q) =>
      q && q.idPhaseNorme === phase &&
      q.idIndicateurNormeNavigation && q.idIndicateurNormeNavigation.ordre === ORDRE_CHANGEMENT_CLIMATIQUE);
    if (trouvees.length !== 1 || typeof trouvees[0].quantite !== "number" || !Number.isFinite(trouvees[0].quantite)) {
      throw new Error(`Valeur « Changement climatique - total » introuvable pour la phase ${phase}.`);
    }
    return arrondir(trouvees[0].quantite);
  });
  return { id, nom: nettoyerNom(json.nomProduit || ""), dvr, valeurs };
}

/**
 * Lien pré-rempli pour les emplacements remplis, identique à lien.construire_lien (matériau A et/ou B).
 * `emplacements` = { A: fiche|null, B: fiche|null } ; renvoie null si les deux sont vides.
 */
function construireLien(emplacements, urlApp = URL_APP) {
  const parametres = [["v", String(FORMAT_LIEN)]];
  let nombreRempli = 0;
  LETTRES.forEach((lettre) => {
    const fiche = emplacements[lettre];
    if (!fiche) return;
    const p = lettre.toLowerCase();
    nombreRempli += 1;
    if (fiche.nom) parametres.push([`${p}_nom`, fiche.nom]);
    parametres.push([`${p}_id`, String(fiche.id)], [`${p}_dvr`, String(fiche.dvr)],
                    [`${p}_v`, fiche.valeurs.map(nombre).join(",")]);
  });
  if (!nombreRempli) return null;
  return urlApp.replace(/\?+$/, "") + "?" + parametres.map(([c, v]) => `${encoder(c)}=${encoder(v)}`).join("&");
}

/** Texte du bouton d'ouverture : « Voir les 2 », « Voir A » ou « Voir B » selon ce qui est rangé. */
function texteVoir(emplacements) {
  const remplis = LETTRES.filter((l) => emplacements[l]);
  if (remplis.length === 2) return "Voir les 2 ▸";
  return remplis.length === 1 ? `Voir ${remplis[0]} ▸` : "Voir ▸";
}

// =============================================================================
// 2) PANNEAU SUR LA PAGE (non exécuté sous Node)
// =============================================================================
function idDeLaPage() {
  const trouve = CHEMIN_FICHE.exec(location.pathname + location.hash);
  return trouve ? trouve[1] : null;
}

async function lireFiche(id) {
  const reponse = await fetch(CHEMIN_API + id, { credentials: "same-origin", headers: { Accept: "application/json" } });
  if (!reponse.ok) throw new Error(`Le site INIES a répondu « ${reponse.status} » : fiche illisible.`);
  return extraireFiche(await reponse.json(), id);
}

function ouvrir(lien) {
  if (typeof GM_openInTab === "function") GM_openInTab(lien, { active: true });
  else window.open(lien, "_blank", "noopener");
}

/** Emplacements mémorisés (toujours relus : un autre onglet INIES a pu les changer). Contenu invalide = vide. */
function lireEmplacements() {
  const vides = { A: null, B: null };
  try {
    const brut = typeof GM_getValue === "function" ? GM_getValue(CLE_MEMOIRE, "") : "";
    const lus = brut ? JSON.parse(brut) : vides;
    // chaque fiche mémorisée est revérifiée avant usage (ses valeurs finiront dans une adresse)
    const propre = (f) => (f && Number.isInteger(f.id) && Number.isInteger(f.dvr) && Array.isArray(f.valeurs) &&
      f.valeurs.length === PHASES.length && f.valeurs.every(Number.isFinite)
      ? { id: f.id, nom: nettoyerNom(f.nom || ""), dvr: f.dvr, valeurs: f.valeurs } : null);
    return { A: propre(lus.A), B: propre(lus.B) };
  } catch (e) {
    return vides;
  }
}

function ecrireEmplacements(emplacements) {
  if (typeof GM_setValue === "function") GM_setValue(CLE_MEMOIRE, JSON.stringify(emplacements));
}

function style(element, css) { Object.assign(element.style, css); return element; }

function creerBoutonPanneau(texte, action, principal = false) {
  const b = document.createElement("button");
  b.type = "button";
  b.textContent = texte;
  style(b, { padding: "7px 10px", border: `2px solid ${COULEUR_TEXTE}`, borderRadius: "6px", cursor: "pointer",
             font: "600 13px sans-serif", whiteSpace: "nowrap", color: principal ? COULEUR_FOND : COULEUR_TEXTE,
             background: principal ? COULEUR_TEXTE : "transparent" });
  b.addEventListener("click", action);
  return b;
}

/** (Re)dessine le contenu du panneau d'après les emplacements mémorisés. */
function dessiner(panneau) {
  const emplacements = lireEmplacements();
  panneau.replaceChildren();
  panneau.appendChild(style(document.createElement("div"), { font: "700 14px sans-serif", marginBottom: "8px" }))
    .textContent = TEXTE_TITRE;

  LETTRES.forEach((lettre) => {
    const fiche = emplacements[lettre];
    const ligne = style(document.createElement("div"), { display: "flex", gap: "6px", alignItems: "center", marginBottom: "6px" });
    ligne.appendChild(creerBoutonPanneau(`${fiche ? "Remplacer" : "Mettre en"} ${lettre}`, () => mettre(panneau, lettre)));
    const libelle = style(document.createElement("span"), { font: "13px sans-serif", maxWidth: "130px", overflow: "hidden",
                                                            textOverflow: "ellipsis", whiteSpace: "nowrap" });
    libelle.textContent = `${lettre} : ${fiche ? fiche.nom || `fiche ${fiche.id}` : TEXTE_VIDE}`;
    libelle.title = libelle.textContent;
    ligne.appendChild(libelle);
    if (fiche) {
      const croix = creerBoutonPanneau("✕", () => { ecrireEmplacements({ ...lireEmplacements(), [lettre]: null }); dessiner(panneau); });
      croix.title = `Vider l'emplacement ${lettre}`;
      ligne.appendChild(croix);
    }
    panneau.appendChild(ligne);
  });

  const voir = creerBoutonPanneau(texteVoir(emplacements), () => {
    const adresse = construireLien(lireEmplacements());
    if (adresse) ouvrir(adresse);
  }, true);
  voir.disabled = !LETTRES.some((l) => emplacements[l]);
  voir.style.width = "100%";
  voir.style.opacity = voir.disabled ? "0.5" : "1";
  panneau.appendChild(voir);
}

/** Lit la fiche ouverte et la range dans l'emplacement `lettre`. */
async function mettre(panneau, lettre) {
  const id = idDeLaPage();
  if (!id) return;
  panneau.style.opacity = "0.6";
  try {
    const fiche = await lireFiche(id);
    ecrireEmplacements({ ...lireEmplacements(), [lettre]: fiche });
  } catch (erreur) {
    alert(TEXTE_ERREUR + erreur.message);
  } finally {
    panneau.style.opacity = "1";
    dessiner(panneau);
  }
}

function creerPanneau() {
  const panneau = style(document.createElement("div"), {
    position: "fixed", ...POSITION_PANNEAU, zIndex: "2147483647", padding: "12px", width: "290px",
    background: COULEUR_FOND, color: COULEUR_TEXTE, borderRadius: "8px", boxShadow: "0 2px 8px rgba(0,0,0,.35)" });
  panneau.id = ID_PANNEAU;
  dessiner(panneau);
  return panneau;
}

/** Affiche le panneau seulement sur une fiche (le site est une application sans rechargement de page). */
function surveiller() {
  const present = document.getElementById(ID_PANNEAU);
  if (idDeLaPage() && !present) document.body.appendChild(creerPanneau());
  else if (!idDeLaPage() && present) present.remove();
}

if (typeof document !== "undefined" && typeof module === "undefined") {
  surveiller();
  setInterval(surveiller, DELAI_SURVEILLANCE_MS);
}
if (typeof module !== "undefined") {
  module.exports = { developper, nombre, arrondir, nettoyerNom, encoder, extraireFiche, construireLien, texteVoir, PHASES };
}
