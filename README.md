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

Convertit et redimensionne les images sources en `.webp` dans le dossier de la recette.

```bash
.venv/bin/python -m tools.process_images france fr-poulet-basquaise
```

### `placeholders`

Génère des images de substitution (`.placeholder`) pour une recette dont les photos ne sont pas encore prêtes.

```bash
.venv/bin/python -m tools.placeholders france fr-poulet-basquaise
```

### `export_seed`

Exporte un jeu de données minimal pour le seed d'un environnement de développement.

```bash
.venv/bin/python -m tools.export_seed france --out seed/
```

## Protocole d'ajout de recette

1. Créer une branche.
2. Ajouter le JSON de la recette et ses images.
3. Si les photos ne sont pas prêtes, générer des placeholders (`placeholders`).
4. Valider (`validate`).
5. Reconstruire l'index (`build_index`).
6. Ouvrir une PR.
7. Relecture humaine.
8. Merge.
