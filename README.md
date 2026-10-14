# ACV dynamique RE2020 — comparer deux matériaux (norme +A2)

Application Streamlit : on colle la ligne « Réchauffement climatique » d'une fiche INIES (norme +A2),
on indique la durée de vie de référence (DVR), et l'outil donne l'**ACV dynamique RE2020** en grand,
à côté du total affiché dans INIES en petit. Deux matériaux peuvent être comparés.

La méthode reprend à l'identique le classeur Excel `ACV_Dynamique_INIES_V2`
(onglets « Interface +A2 », « Calcul +A2 », « Art. 11 »), licence GNU GPL v3.

## Fichiers

| Fichier | Rôle |
|---|---|
| `acv_inies_a2.py` | **Module de calcul autonome** (bibliothèque standard seule). À copier tel quel dans un autre programme. |
| `app.py` | Interface Streamlit (aucun calcul ici). |
| `presentation.py` | Mise en forme : palette, graphique, tableau des étapes INIES, styles (sans Streamlit). |
| `catalogue.py` | Lecture / contrôle de `materiaux.json` et fabrication du bloc d'un nouveau matériau. |
| `materiaux.json` | **Catalogue des matériaux enregistrés** (valeurs au format décimal standard, date d'export). |
| `.streamlit/config.toml` | Thème (couleur principale) de l'application. |
| `CHANGELOG.md` | Historique des versions (repris dans l'app). |
| `tests/` | Tests automatiques ; les valeurs attendues viennent de l'Excel recalculé. |
| `reference/` | Classeur Excel d'origine, pour régénérer les valeurs de référence. |

## Enregistrer un matériau

1. Dans l'app, saisir un matériau (nom, identifiant, DVR, ligne collée) : un bloc JSON apparaît dans « Enregistrer ce matériau dans le catalogue ».
2. Copier ce bloc et le coller à la fin de la liste `materiaux` de `materiaux.json` (avec une virgule entre deux matériaux).
3. Pousser sur GitHub : le matériau apparaît dans les listes de l'app. `date_export` = date à laquelle les valeurs ont été exportées d'INIES.

## Lancer en local

    pip install -r requirements.txt
    streamlit run app.py

## Publier sur streamlit.app

1. Mettre ce dossier dans un dépôt GitHub.
2. Sur <https://share.streamlit.io> : « New app », choisir le dépôt, fichier principal `app.py`.

## Réutiliser le calcul ailleurs

    from acv_inies_a2 import calculer_depuis_inies, ErreurInies

    resultat = calculer_depuis_inies(texte_colle_depuis_inies, dvr=50)
    resultat.dynamique_total      # kg CO2 eq., module D inclus
    resultat.statique_total       # E+C-, module D / 3
    resultat.dynamique_par_annee  # 51 valeurs (années 0 à 50)

Les erreurs de saisie lèvent `ErreurInies`, avec un message en français prêt à afficher.
En ligne de commande : `python acv_inies_a2.py "<13 valeurs>" 50`.

## Tests

    pip install -r requirements-dev.txt
    python -m pytest -q

Pour régénérer `tests/reference_excel.json` après une évolution de l'Excel (LibreOffice requis) :
`python tests/generer_reference_excel.py`.

## Versionner une évolution

1. Modifier `VERSION`, `DATE_VERSION` et `HISTORIQUE_VERSIONS` dans `acv_inies_a2.py`.
2. Ajouter la même entrée en tête de `CHANGELOG.md` (format `## X.Y.Z — AAAA-MM-JJ` puis la description).
3. Lancer les tests : l'un d'eux vérifie que les deux historiques sont identiques.

Numérotation : `MAJEUR.MINEUR.CORRECTIF` — correctif pour une erreur ou un texte, mineur pour une
fonction ajoutée, majeur si les résultats changent (méthode, coefficients).

## Limites connues

- Norme +A2 uniquement (13 valeurs) ; une ligne +A1 (6 valeurs) est refusée avec un message explicite.
- Le carbone biogénique stocké (« stockC » de l'Excel) n'entre dans aucune formule de l'Excel : il n'est pas repris.
- Seul l'indicateur « Réchauffement climatique – total » est traité (l'onglet « résultats » de l'Excel,
  avec fossile / biogénique / usage des sols, viendra dans un second temps).
- Le lien « Ouvrir la fiche » suppose le format `https://base-inies.fr/infos-produit/<id>` (`URL_FICHE_INIES` dans `app.py`).
