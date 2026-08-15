# miam-content

Contenu des apps Miam : recettes, taxonomies, index — servi via jsDelivr.

## Commandes

### `validate`

Valide les schémas JSON et les règles référentielles d'un ou plusieurs pays.

```bash
.venv/bin/python -m tools.validate france
```

### `build_index`

Reconstruit `index.json` à partir des fiches recettes présentes sur le disque.

```bash
.venv/bin/python -m tools.build_index france
```

### `process_images`

Convertit et redimensionne les images sources (`hero.*`, `step-N.*`) d'un dossier vers des `.webp` normalisés dans le dossier de la recette, et retire le marqueur `.placeholder`.

```bash
.venv/bin/python -m tools.process_images ~/photos/poulet-basquaise france fr-poulet-basquaise
```

### `placeholders`

Génère des images de substitution (`.placeholder`) pour une recette dont les photos ne sont pas encore prêtes.

```bash
.venv/bin/python -m tools.placeholders france fr-poulet-basquaise
```

### `export_seed`

Exporte le bundle seed embarqué par l'app (recettes de `<pays>/seed.txt` + images + index filtré) vers un dossier de sortie.

```bash
.venv/bin/python -m tools.export_seed france /tmp/miam-seed-fr
```

## Protocole d'écriture d'une recette

1. **Authenticité.** La recette est un plat authentique du pays, sous son titre consacré (pas d'invention ni de fusion). `region` est la région réelle d'origine. `difficulty` est honnête : 1 = assemblage sans cuisson délicate, 2 = cuisson surveillée, 3 = technique (pâtisserie précise, gestes délicats).
2. **Étapes.** Entre 5 et 10 étapes, une seule action par étape. `timerMinutes` est renseigné dès qu'une attente existe (cuisson, repos, marinade). Les quantités d'ingrédients sont réalistes pour le nombre de `servings` indiqué.
3. **Langues.** Les 4 langues (fr, en, es, it) sont rédigées en qualité native : tournures idiomatiques, vocabulaire culinaire juste, jamais de mot-à-mot.
4. **Tags.** `airFryer` uniquement si la recette s'adapte réellement à la friteuse à air, et alors `airFryerNotes` (4 langues) précise température, durée et ajustements concrets. `vegetarian` si la recette ne contient ni viande ni poisson.
5. **Taxonomie.** Tout `ref` d'ingrédient vient de `<pays>/ingredients.json`. Si un ingrédient indispensable manque vraiment, l'ajouter à la taxonomie (names en 4 langues, catégorie de l'enum, substituts crédibles) dans le même commit que la recette.
6. **Validation.** Avant tout commit : `python -m tools.placeholders` (si les photos ne sont pas prêtes) puis `python -m tools.validate` — la sortie doit se terminer par « 0 erreur(s). ».
7. **Stabilité des fichiers.** Ne JAMAIS reformater en masse les JSON de recettes : `updatedAt` est calculé par hash d'octets, un re-indent global changerait le hash de toutes les fiches et déclencherait une vague de re-téléchargements chez tous les utilisateurs.

## Protocole d'ajout de recette

1. Créer une branche.
2. Ajouter le JSON de la recette et ses images.
3. Si les photos ne sont pas prêtes, générer des placeholders (`placeholders`).
4. Valider (`validate`).
5. Reconstruire l'index (`build_index`).
6. Ouvrir une PR.
7. Relecture humaine.
8. Merge.
