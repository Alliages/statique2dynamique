// ==UserScript==
// @name         ACV dynamique RE2020 - envoyer la fiche INIES
// @namespace    https://github.com/Alliages/statique2dynamique
// @version      1.0.0
// @description  Ajoute un bouton sur une fiche base-inies.fr (norme +A2) qui ouvre l'outil ACV dynamique RE2020 avec les valeurs de la fiche déjà remplies.
// @author       Alliages
// @match        https://www.base-inies.fr/*
// @match        https://base-inies.fr/*
// @grant        GM_openInTab
// @run-at       document-idle
// @updateURL    https://raw.githubusercontent.com/Alliages/statique2dynamique/main/tampermonkey/acv_inies.user.js
// @downloadURL  https://raw.githubusercontent.com/Alliages/statique2dynamique/main/tampermonkey/acv_inies.user.js
// ==/UserScript==

/*
 * Ce que fait ce script, et rien d'autre :
 *   1. sur une page « .../infos-produit/<id> », il affiche un bouton en bas à droite ;
 *   2. au clic, il lit la fiche ouverte (adresse /api/Produit/<id>, avec votre session, comme le fait le site) ;
 *   3. il vérifie que la fiche est en norme +A2, en extrait les 13 valeurs « Changement climatique - total »
 *      et la durée de vie de référence (DVR), arrondies à 5 décimales comme l'application ;
 *   4. il ouvre l'application dans un nouvel onglet, avec un lien pré-rempli (format identique à lien.py).
 * Aucune donnée n'est envoyée ailleurs que dans l'adresse de ce lien. Une seule fiche à la fois, sur clic.
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
const ID_BOUTON = "acv-inies-bouton";

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

/** Lien pré-rempli, identique à lien.construire_lien(url_app, 0, nom, id, dvr, valeurs) (matériau A). */
function construireLien(fiche, urlApp = URL_APP) {
  const parametres = [["v", String(FORMAT_LIEN)]];
  if (fiche.nom) parametres.push(["a_nom", fiche.nom]);
  parametres.push(["a_id", String(fiche.id)], ["a_dvr", String(fiche.dvr)], ["a_v", fiche.valeurs.map(nombre).join(",")]);
  return urlApp.replace(/\?+$/, "") + "?" + parametres.map(([c, v]) => `${encoder(c)}=${encoder(v)}`).join("&");
}

// =============================================================================
// 2) BOUTON SUR LA PAGE (non exécuté sous Node)
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

function creerBouton() {
  const bouton = document.createElement("button");
  bouton.id = ID_BOUTON;
  bouton.type = "button";
  bouton.textContent = "ACV dynamique RE2020 ▸";
  bouton.title = "Ouvre l'outil statique2dynamique avec les valeurs RE2020 de cette fiche";
  Object.assign(bouton.style, {
    position: "fixed", right: "20px", top: "20px", zIndex: "2147483647", padding: "12px 18px",
    background: "#ebbab9", color: "#fff", border: "0", borderRadius: "8px", font: "600 15px sans-serif",
    cursor: "pointer", boxShadow: "0 2px 8px rgba(0,0,0,.35)",
  });
  bouton.addEventListener("click", async () => {
    const id = idDeLaPage();
    if (!id) return;
    const libelle = bouton.textContent;
    bouton.disabled = true;
    bouton.textContent = "Lecture de la fiche…";
    try {
      ouvrir(construireLien(await lireFiche(id)));
    } catch (erreur) {
      alert("ACV dynamique RE2020 : " + erreur.message);
    } finally {
      bouton.disabled = false;
      bouton.textContent = libelle;
    }
  });
  return bouton;
}

/** Affiche le bouton seulement sur une fiche (le site est une application sans rechargement de page). */
function surveiller() {
  const present = document.getElementById(ID_BOUTON);
  if (idDeLaPage() && !present) document.body.appendChild(creerBouton());
  else if (!idDeLaPage() && present) present.remove();
}

if (typeof document !== "undefined" && typeof module === "undefined") {
  surveiller();
  setInterval(surveiller, DELAI_SURVEILLANCE_MS);
}
if (typeof module !== "undefined") {
  module.exports = { developper, nombre, arrondir, nettoyerNom, encoder, extraireFiche, construireLien, PHASES };
}
