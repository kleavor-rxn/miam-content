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

## Collection desserts

`desserts/` n'est pas un pays mais une collection thématique (préfixe d'id `ds-`) : les desserts du monde entier. Elle suit le protocole d'écriture ci-dessus, avec ces différences.

**Fichiers.**

- `recipes/ds-*.json` : fiches recettes, `category` toujours `dessert`.
- `images/ds-<slug>/hero.webp` : photo principale seule. Les étapes n'ont pas d'image (`steps[].image` absent) ; la page d'étape affiche le texte et le minuteur.
- `ingredients.json` : taxonomie, ids en français. Staples : `sucre`, `eau`, `sel` (la farine n'en est pas un). Chaque ingrédient porte `contains` (allergènes parmi `gluten`, `oeuf`, `lait`, `fruits-a-coque`, `arachide`) et `animal` (œufs, produits laitiers, miel, gélatine…). Le bloc `featured` liste les ingrédients vedettes (nom, emoji, `members`) par lesquels on parcourt l'app.
- `origins.json` : les 11 régions du monde et les pays (code ISO 3166-1 alpha-2, région, latitude/longitude pour la carte). Ajouter un pays = une ligne ici.
- `occasions.json` : occasions datées (fenêtres `start`/`end` explicites, `YYYY-MM-DD`) et sans date (`anniversaire`, `gouter`). Les fêtes mobiles (Pâques, Ramadan et Aïd, Nouvel an lunaire, Diwali, Hanoucca) sont écrites à la main, vérifiées dans deux sources ; le validateur échoue s'il reste moins de 12 mois de fenêtres pour une occasion utilisée : les prolonger au moins un an à l'avance.
- `seed.txt` : tout le catalogue (le calendrier embarqué doit rester complet). `index.json` : généré par `build_index`, avec l'empreinte des fichiers annexes (`files`).

**Champs obligatoires dans une fiche dessert** (facultatifs ailleurs) :

- `origin.countries` : 1 à 3 codes de `origins.json`, le premier est le pays principal. Origine disputée : plusieurs pays, et la `story` le dit.
- `dessertType` : `gateau`, `tarte`, `creme`, `glace`, `biscuit`, `beignet`, `crepe`, `brioche`, `confiserie` ou `fruit`.
- `story` : 2 à 4 phrases par langue (histoire, contexte, quand on le mange). Uniquement des faits vérifiables ; une légende célèbre est présentée comme une légende.
- `occasions` : ids de `occasions.json` (liste éventuellement vide).

**Tags.** `noBake` quand le dessert ne passe pas au four (une cuisson sur le feu est permise) ; `airFryer` + `airFryerNotes` comme ailleurs ; jamais `vegetarian`.

**Allergènes et régimes dérivés.** Les fiches ne déclarent ni « sans gluten » ni « végétalien » : l'app les dérive des ingrédients non facultatifs (`contains`, `animal` de la taxonomie) et rappelle de vérifier les étiquettes. Un ingrédient ajouté à la taxonomie doit donc avoir des `contains` et `animal` justes — c'est d'eux que dépend l'information donnée aux personnes allergiques.

**Équilibre.** `validate` signale en alerte (non bloquante) les régions sous 6 desserts, les vedettes sous 5 et les types sous 5, ainsi que deux jours de suite du même pays ou de la même région dans le calendrier.

## Protocole d'ajout de recette

1. Créer une branche.
2. Ajouter le JSON de la recette et ses images.
3. Si les photos ne sont pas prêtes, générer des placeholders (`placeholders`).
4. Valider (`validate`).
5. Reconstruire l'index (`build_index`).
6. Ouvrir une PR.
7. Relecture humaine.
8. Merge.
