"""Validation d'un pays : schémas JSON + règles référentielles.

Erreurs -> bloquantes. Warnings (placeholders) -> bloquants seulement avec --release.
"""
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from tools.countries import COUNTRIES


@dataclass
class Issue:
    path: str      # chemin du fichier concerné, relatif au repo
    message: str


def _load_schemas(root: Path):
    schemas = {}
    resources = []
    for f in (root / "schema").glob("*.schema.json"):
        s = json.loads(f.read_text())
        schemas[f.name.split(".")[0]] = s
        resources.append((s["$id"], Resource.from_contents(s)))
    registry = Registry().with_resources(resources)
    return {name: Draft202012Validator(s, registry=registry)
            for name, s in schemas.items()}


def validate_country(root: Path, country: str, release: bool = False) -> list[Issue]:
    issues: list[Issue] = []
    validators = _load_schemas(root)
    prefix = COUNTRIES[country]
    cdir = root / country

    tax_path = cdir / "ingredients.json"
    try:
        taxonomy = json.loads(tax_path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        return [Issue(str(tax_path), f"taxonomie illisible : {e}")]
    tax_errs = list(validators["ingredients"].iter_errors(taxonomy))
    if tax_errs:
        # taxonomie invalide : les règles référentielles seraient du bruit
        return [Issue(str(tax_path), f"schéma taxonomie : {e.message}") for e in tax_errs]
    known = {i["id"]: i for i in taxonomy["ingredients"]}
    for ing in known.values():
        for sub in ing.get("substitutes", []):
            if sub not in known:
                issues.append(Issue(str(tax_path), f"substitut inconnu : {sub}"))

    for rp in sorted((cdir / "recipes").glob("*.json")):
        rel = str(rp.relative_to(root))
        try:
            recipe = json.loads(rp.read_text())
        except json.JSONDecodeError as e:
            issues.append(Issue(rel, f"JSON invalide : {e}"))
            continue
        schema_errs = list(validators["recipe"].iter_errors(recipe))
        if schema_errs:
            issues += [Issue(rel, f"schéma recette : {e.message}") for e in schema_errs]
            continue  # règles référentielles inapplicables sur une fiche schéma-invalide
        rid = recipe["id"]
        if rid != rp.stem:
            issues.append(Issue(rel, f"id '{rid}' != nom de fichier '{rp.stem}'"))
        if not rid.startswith(f"{prefix}-"):
            issues.append(Issue(rel, f"id '{rid}' ne commence pas par '{prefix}-'"))
        has_tag = "airFryer" in recipe.get("tags", [])
        has_notes = "airFryerNotes" in recipe
        if has_tag != has_notes:
            issues.append(Issue(rel, "airFryerNotes doit être présent ssi tag airFryer"))
        for ing in recipe.get("ingredients", []):
            ref = ing.get("ref")
            if ref not in known:
                issues.append(Issue(rel, f"ingrédient inconnu : {ref}"))
                continue
            for sub in ing.get("substitutes", []):
                if sub not in known:
                    issues.append(Issue(rel, f"substitut inconnu : {sub}"))
            if not known[ref]["staple"] and ing.get("quantity") is None:
                issues.append(Issue(rel, f"quantité requise pour non-staple : {ref}"))
        images = [recipe["heroImage"]] + [s["image"] for s in recipe["steps"]]
        for img in images:
            if not img.startswith(f"images/{rid}/"):
                issues.append(Issue(rel, f"image hors du dossier de la recette : {img}"))
            if not (cdir / img).is_file():
                issues.append(Issue(rel, f"image manquante : {img}"))
        marker = cdir / "images" / rid / ".placeholder"
        if marker.exists():
            msg = f"images placeholder pour {rid}"
            if release:
                issues.append(Issue(rel, f"placeholder interdit en release : {msg}"))
            else:
                print(f"⚠️  {msg}")

    index_path = cdir / "index.json"
    if index_path.exists():
        index = json.loads(index_path.read_text())
        for err in validators["index"].iter_errors(index):
            issues.append(Issue(str(index_path), f"schéma index : {err.message}"))
        ids_on_disk = {p.stem for p in (cdir / "recipes").glob("*.json")}
        ids_in_index = {r["id"] for r in index.get("recipes", [])}
        if ids_on_disk != ids_in_index:
            issues.append(Issue(str(index_path),
                f"index désynchronisé (disque - index : {sorted(ids_on_disk - ids_in_index)}, "
                f"index - disque : {sorted(ids_in_index - ids_on_disk)}) — relancer build_index"))
        for pick in index.get("dailyPicks", []):
            if pick["recipeID"] not in ids_on_disk:
                issues.append(Issue(str(index_path),
                                    f"dailyPick vers recette inconnue : {pick['recipeID']}"))
    return issues


def main(argv: list[str]) -> int:
    release = "--release" in argv
    countries = [a for a in argv if not a.startswith("--")] or list(COUNTRIES)
    root = Path.cwd()
    all_issues = []
    for c in countries:
        all_issues += validate_country(root, c, release=release)
    for i in all_issues:
        print(f"❌ {i.path}: {i.message}")
    print(f"{len(all_issues)} erreur(s).")
    return 1 if all_issues else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
