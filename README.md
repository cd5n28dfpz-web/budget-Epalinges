# Budget d'Épalinges en données ouvertes

Les budgets et les comptes de la Commune d'Épalinges, ligne par ligne, extraits des documents officiels de la commune et rendus lisibles : un tableau de bord interactif et des fichiers CSV réutilisables.

**Couverture actuelle** : comptes 2018 à 2025, budgets votés 2019 à 2026, projets de budget 2020 à 2022 et 2024, soit plus de 2'000 lignes du budget de fonctionnement dans 7 dicastères.

> Projet indépendant, sans lien avec l'administration communale. Les chiffres proviennent des documents publiés par la Commune d'Épalinges ; en cas de doute, le document officiel fait foi.
> Ce projet est une adaptation pour Épalinges du projet [Budget de Prilly en données ouvertes](https://github.com/andant89/budget-Prilly) (licence MIT).

## Principe de neutralité

L'outil décrit ce que montrent les chiffres. Il ne dit pas ce qu'il faudrait en conclure, ce qui relève d'un choix politique. Les textes du tableau de bord s'en tiennent aux montants, aux écarts et aux méthodes de calcul. Toute contribution doit respecter ce principe.

## Contenu

| Dossier | Contenu |
|---|---|
| `site/index.html` | Tableau de bord autonome, à ouvrir dans un navigateur (aussi publié via GitHub Pages) |
| `data/` | Données ouvertes au format CSV (UTF-8) : `lignes_large.csv`, `lignes.csv`, `sections.csv`, `natures.csv`, `resultats.csv`, `amendements.csv`, `commentaires.csv`, `controles.csv` |
| `pipeline/` | Scripts d'extraction et de fusion (Python ; `pdftotext` pour lire les PDF ; `tesseract` et `opencv` pour les pages-images) |
| `sources/` | Liste des documents, extractions brutes, résultats de l'OCR, corrections manuelles |
| `tests/` | Contrôles automatiques de cohérence |
| `docs/` | Méthodologie, ajout d'un document, mode d'emploi de l'assistant |
| `assistant/` | Outils pour interroger les données avec votre propre IA (serveur MCP et script) |

Séries : `C2025` = comptes 2025, `B2025` = budget 2025 voté par le Conseil communal, `P2024` = projet de budget 2024 de la Municipalité. Les montants sont en francs, positifs pour les charges comme pour les revenus (la colonne `sens` indique lequel). Les codes suivent le plan comptable des communes vaudoises : 3xxx pour les charges, 4xxx pour les revenus.

## Reconstruire les données

Prérequis : Python 3.9 ou plus récent.

```
make rebuild   # depuis les extractions déjà présentes dans sources/extraits/
make all       # depuis les PDF placés dans sources/pdf/ (pdftotext ; OCR : tesseract, opencv-python-headless)
make test      # contrôles uniquement
```

Pour ajouter un document, voir [docs/ajouter-un-document.md](docs/ajouter-un-document.md). Méthode et limites : [docs/methodologie.md](docs/methodologie.md).

## Licence

Code sous licence MIT (voir `LICENSE`). Les données sont issues de documents publiés par la Commune d'Épalinges ; merci de citer la source : « Commune d'Épalinges, budgets et comptes, mise en forme par le projet Budget d'Épalinges en données ouvertes ».
