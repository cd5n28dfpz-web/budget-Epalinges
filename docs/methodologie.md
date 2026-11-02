# Méthodologie

## Documents utilisés

La liste des documents et la signification de leurs colonnes se trouvent dans `sources/documents.json`. Chaque document de la commune présente le budget de fonctionnement détaillé « par service » : dicastère (1 chiffre), groupe (2), fonction (3), service (4) et compte (`3011.000`), avec les colonnes Charges / Revenus de trois ou six années.

| Document | Colonnes |
|---|---|
| Budgets 2020, 2021, 2022, 2024 | projet N, budget voté N-1, comptes N-2 |
| Budget 2025 (version amendée) | budget voté 2025, budget 2024, comptes 2023, 2022, 2021, 2020 |
| Budget 2026 | projet 2026, budget voté 2025, comptes 2024, 2023, 2022, 2021 |
| Comptes 2022, 2023, 2025 | comptes N, budget voté N, comptes N-1 |

Trois types de séries : **comptes** (`C`), **budget voté** (`B`) et **projet de budget** de la Municipalité (`P`). Quand une série figure dans plusieurs documents, le document avec texte est préféré à un document lu par OCR, puis les comptes aux budgets, puis le plus récent ; toute différence est signalée dans `data/controles.csv`.

Le **budget 2023** n'est pas dans les documents réunis : le budget voté 2023 est repris des comptes 2023 et du budget 2024, mais le projet de la Municipalité pour 2023 manque. Les **comptes 2024** (PDF) n'ont pas de texte dans leurs pages de détail ; ils ne sont pas lus, car les mêmes données (comptes 2024 ligne par ligne) figurent en texte dans les budgets 2025 et 2026, et leur total général concorde avec celui des comptes 2024. Le **budget 2026** est le projet de la Municipalité ; le budget voté 2026 paraîtra dans les comptes 2026.

## Extraction

`pipeline/extract.py` lit la position de chaque mot avec `pdftotext -bbox` (poppler). Les colonnes sont déduites de la position des montants. Quelques particularités sont corrigées automatiquement : numéros de note en marge de certaines lignes, code de compte tronqué du budget 2025 (« 4500 4812.00 » pour 4812.000), montants sans centimes (« 45000 »), tirets typographiques des montants négatifs.

Les pages de détail des comptes 2025 sont des images. Elles sont lues par reconnaissance de caractères (tesseract, 300 dpi) ; les traits du tableau sont d'abord effacés (opencv), car un trait collé à la dernière décimale la faisait lire de travers. Le résultat brut est conservé dans `sources/ocr/`. Les confusions restantes (« § » pour 5, « _ » pour le point décimal, montants coupés en deux) sont corrigées automatiquement ; trois valeurs ont été corrigées à la main après vérification sur l'image (`sources/corrections.csv`).

## Contrôles

`pipeline/merge.py` vérifie, pour chaque document et chaque colonne :

1. le total des charges et des revenus contre la ligne « TOTAUX » du tableau récapitulatif du document, lue séparément du détail (arrondi au franc pour les comptes 2025) ;
2. le sous-total de chaque service, fonction, groupe et dicastère contre la somme de ses lignes.

Au dernier passage, les contrôles (plus de 10'000) passent tous. Le résultat 2025 (excédent de charges de 491'361.51 francs, après prélèvement de 2,5 millions sur des fonds de réserve) correspond à celui que la commune annonce dans ses comptes.

## Limites

- Seul le **budget de fonctionnement** est repris. Les investissements, le bilan, la dette et les comptes du CISTEP ne le sont pas.
- Le projet de budget 2025 de la Municipalité (avant amendements) n'est pas dans les documents ; aucun amendement n'apparaît donc dans les données, et l'onglet « Amendements » est masqué.
- Les **imputations internes** (natures 39 et 49) sont des facturations entre services ; elles s'annulent dans le résultat. Plusieurs vues les excluent et l'indiquent.
- Les **attributions et prélèvements aux fonds** (natures 38 et 48) peuvent faire varier fortement une ligne d'une année à l'autre.
- Les services sont parfois **réorganisés** : une ligne est identifiée par son service et son compte, un changement de service crée une nouvelle ligne.
- Les montants sont en **francs courants**, non corrigés de l'inflation ni de la population.
