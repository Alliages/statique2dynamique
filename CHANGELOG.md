# Historique des versions

Format : [numérotation sémantique](https://semver.org/lang/fr/) — `MAJEUR.MINEUR.CORRECTIF`.
Cet historique est repris dans l'application (rubrique « Versions ») depuis `acv_inies_a2.py`
(`HISTORIQUE_VERSIONS`) : les deux doivent rester identiques (un test le vérifie).

## 4.0.1 — 2026-10-16
Correction mineure.

## 4.0.0 — 2026-10-16
Détail du changement climatique d'un matériau : un second champ, sous le premier, reçoit les 4 lignes « Changement climatique » (total, fossile, biogénique, occupation des sols) ; à droite, courbes cumulées puis barres empilées par étape du cycle de vie. Palette : le biogénique en vert-bleu et l'occupation des sols en vert-jaune.

## 3.9.0 — 2026-10-15
Réorganisation de l'interface.

## 3.6.1 — 2026-10-15
Script Tampermonkey 1.2.0 : panneau déroulant à 10 px du haut, réduit au titre « ACV dynamique RE2020 » ; le survol le déroule, un clic sur le titre le garde ouvert (ou le referme).

## 3.6.0 — 2026-10-15
Script Tampermonkey 1.1.0 : deux emplacements A et B mémorisés d'une fiche INIES à l'autre (« Mettre en A », « Mettre en B », « Voir les 2 »), lien unique contenant A et/ou B ; texte du panneau foncé.

## 3.5.0 — 2026-10-14
Script Tampermonkey pour base-inies.fr : un bouton sur la fiche (norme +A2) lit les 13 valeurs « Changement climatique - total » et la DVR, puis ouvre l'application avec le matériau A pré-rempli ; test sous Node contre lien.py.

## 3.4.0 — 2026-10-14
Liens pré-remplis : l'application lit un lien (identifiant, nom, DVR, 13 valeurs) et remplit le matériau A ou B, avec contrôle strict et messages d'erreur clairs ; bouton « Copier le lien de ce matériau » sous chaque fiche.

## 3.3.1 — 2026-10-14
Échelle verticale du graphique calée sur la valeur maximale réellement tracée (plus de haut gonflé par un grand côté négatif) ; filigrane ÉMISSIONS / SÉQUESTRATION en horizontal contre la ligne de zéro quand la place manque ; légende un peu plus haut.

## 3.3.0 — 2026-10-14
Nouveau titre et textes pédagogiques (« comparaison carbone », StockC, objectif de la RE2020) ; échelle verticale du graphique adaptée automatiquement aux courbes ; courbes statiques E+C- en option (pointillés) ; exports CSV (résumé, année par année) et image du graphique ; graphique en pleine largeur sur petit écran ; versions de Streamlit et Plotly fixées.

## 3.2.0 — 2026-10-14
Fond en dégradé diagonal aux couleurs de la palette éclaircies, boîtes blanches, matériaux en Pacific Cyan et Cotton Rose (chiffres du matériau B légèrement foncés pour rester lisibles), filigrane ÉMISSIONS / SÉQUESTRATION en gris clair. Thème clair unique.

## 3.1.0 — 2026-10-14
Graphique resserré (traits épais, axes fléchés, filigrane émissions / séquestration, valeur finale), tableau des étapes INIES, catalogue de matériaux (materiaux.json avec date d'export), palette de couleurs et nouveau titre.

## 3.0.0 — 2026-10-13
Version web (Streamlit) : norme +A2 uniquement,
module de calcul autonome et testé contre l'Excel.

## Excel V2 — 2023-05-15
Ajout de la norme +A2 (et de l'onglet de résultats A2).

## Excel V1 — 2022-06-02
Version initiale (norme +A1).
