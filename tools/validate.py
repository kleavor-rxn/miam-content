"""Validation d'un pays : schémas JSON + règles référentielles.

Erreurs -> bloquantes. Warnings (placeholders) -> bloquants seulement avec --release.
"""
import json
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from tools.build_index import annex_fingerprint_errors
from tools.countries import COUNTRIES
from tools.daily_picks import no_repeat_window


@dataclass
class Issue:
    path: str      # chemin du fichier concerné, relatif au repo
    message: str
    severity: str = "error"   # "error" | "warning"


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


MIN_PER_REGION = 6
MIN_PER_FEATURED = 5
MIN_PER_TYPE = 5
OCCASION_HORIZON_DAYS = 365
OCCASION_WARNING_DAYS = 548   # ~18 mois : alerte avant que la couverture ne devienne une erreur


def _load_checked(root: Path, path: Path, validator, label: str):
    """Lit un JSON de référence et le valide par schéma -> (données, erreurs)."""
    rel = str(path.relative_to(root))
    try:
        data = json.loads(path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        return None, [Issue(rel, f"{label} illisible : {e}")]
    errs = [Issue(rel, f"schéma {label} : {e.message}") for e in validator.iter_errors(data)]
    return (None if errs else data), errs


def _desserts_rules(root: Path, cdir: Path, recipes: list, taxonomy: dict,
                    origins: dict, occasions: dict, dessert_types: list,
                    today: date) -> list[Issue]:
    """Règles propres à la collection desserts (spec §5.2). `recipes` : [(chemin relatif, fiche)]."""
    issues: list[Issue] = []
    tax_rel = str((cdir / "ingredients.json").relative_to(root))
    occ_rel = str((cdir / "occasions.json").relative_to(root))
    known_ids = {i["id"] for i in taxonomy["ingredients"]}

    for ing in taxonomy["ingredients"]:
        if "contains" not in ing or "animal" not in ing:
            issues.append(Issue(tax_rel, f"contains/animal manquant : {ing['id']}"))
    featured = taxonomy.get("featured", [])
    for group in featured:
        for member in group["members"]:
            if member not in known_ids:
                issues.append(Issue(tax_rel, f"membre vedette inconnu : {member}"))

    region_ids = {r["id"] for r in origins["regions"]}
    country_region = {}
    for c in origins["countries"]:
        country_region[c["code"]] = c["region"]
        if c["region"] not in region_ids:
            issues.append(Issue(str((cdir / "origins.json").relative_to(root)),
                                f"région inconnue : {c['region']} (pays {c['code']})"))

    occ_by_id = {o["id"]: o for o in occasions["occasions"]}
    valid_windows: dict[str, list[date]] = {}   # occasion -> dates de fin exploitables
    for o in occasions["occasions"]:
        for w in o.get("windows", []):
            try:
                start, end = date.fromisoformat(w["start"]), date.fromisoformat(w["end"])
            except ValueError:
                issues.append(Issue(occ_rel, f"fenêtre invalide : {o['id']} {w['start']} → {w['end']}"))
                continue
            if start > end:
                issues.append(Issue(occ_rel, f"fenêtre invalide : {o['id']} {w['start']} → {w['end']}"))
                continue
            valid_windows.setdefault(o["id"], []).append(end)

    used_occasions: set[str] = set()
    by_region: dict[str, set[str]] = {r: set() for r in region_ids}
    by_featured: dict[str, set[str]] = {g["id"]: set() for g in featured}
    by_type: dict[str, set[str]] = {t: set() for t in dessert_types}
    for rel, recipe in recipes:
        rid = recipe["id"]
        for field in ("origin", "dessertType", "story"):
            if field not in recipe:
                issues.append(Issue(rel, f"champ requis pour desserts : {field}"))
        for code in recipe.get("origin", {}).get("countries", []):
            if code not in country_region:
                issues.append(Issue(rel, f"pays inconnu : {code}"))
        for oc in recipe.get("occasions", []):
            if oc not in occ_by_id:
                issues.append(Issue(rel, f"occasion inconnue : {oc}"))
            else:
                used_occasions.add(oc)
        # équilibre : une fiche compte une fois par région / vedette / type
        for code in recipe.get("origin", {}).get("countries", []):
            if country_region.get(code) in by_region:
                by_region[country_region[code]].add(rid)
        for group in featured:
            members = set(group["members"])
            if any(i["ref"] in members for i in recipe["ingredients"] if not i.get("optional")):
                by_featured[group["id"]].add(rid)
        if recipe.get("dessertType") in by_type:
            by_type[recipe["dessertType"]].add(rid)

    horizon = today + timedelta(days=OCCASION_HORIZON_DAYS)
    warning_horizon = today + timedelta(days=OCCASION_WARNING_DAYS)
    for oc in sorted(used_occasions):
        ends = valid_windows.get(oc)
        if ends is None:
            continue   # occasion sans date (gouter, anniversaire) ou fenêtres invalides déjà signalées
        if max(ends) < horizon:
            issues.append(Issue(occ_rel,
                f"occasion {oc} : couverture de moins de 12 mois (dernière fenêtre finit le "
                f"{max(ends)}, il faut au moins {horizon})"))
        elif max(ends) < warning_horizon:
            issues.append(Issue(occ_rel,
                f"occasion {oc} : couverture de moins de 18 mois (dernière fenêtre finit le "
                f"{max(ends)}, prévoir au moins {warning_horizon})",
                severity="warning"))

    bal_rel = str(cdir.relative_to(root))
    for label, minimum, groups in (("région", MIN_PER_REGION, by_region),
                                   ("vedette", MIN_PER_FEATURED, by_featured),
                                   ("type", MIN_PER_TYPE, by_type)):
        for key in sorted(groups):
            if len(groups[key]) < minimum:
                issues.append(Issue(bal_rel,
                    f"équilibre : {label} {key} a {len(groups[key])} desserts (minimum {minimum})",
                    severity="warning"))
    return issues


def validate_country(root: Path, country: str, release: bool = False,
                     today: date | None = None) -> list[Issue]:
    if country not in COUNTRIES:
        return [Issue(country, f"pays inconnu : {country} (attendus : {', '.join(COUNTRIES)})")]

    issues: list[Issue] = []
    validators = _load_schemas(root)
    prefix = COUNTRIES[country]
    cdir = root / country

    tax_path = cdir / "ingredients.json"
    try:
        taxonomy = json.loads(tax_path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        return [Issue(str(tax_path.relative_to(root)), f"taxonomie illisible : {e}")]
    tax_errs = list(validators["ingredients"].iter_errors(taxonomy))
    if tax_errs:
        # taxonomie invalide : les règles référentielles seraient du bruit
        return [Issue(str(tax_path.relative_to(root)), f"schéma taxonomie : {e.message}") for e in tax_errs]
    known = {i["id"]: i for i in taxonomy["ingredients"]}
    for ing in known.values():
        for sub in ing.get("substitutes", []):
            if sub not in known:
                issues.append(Issue(str(tax_path.relative_to(root)), f"substitut inconnu : {sub}"))

    origins = occasions = None
    country_region: dict[str, str] = {}
    if country == "desserts":
        today = today or date.today()
        origins, o_errs = _load_checked(root, cdir / "origins.json", validators["origins"], "origins")
        occasions, c_errs = _load_checked(root, cdir / "occasions.json", validators["occasions"], "occasions")
        if o_errs or c_errs:
            return issues + o_errs + c_errs
        country_region = {c["code"]: c["region"] for c in origins["countries"]}
    dessert_recipes: list = []

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
        dessert_recipes.append((rel, recipe))
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
            if (ing.get("quantity") is None) != (ing.get("unit") is None):
                issues.append(Issue(rel, f"quantité et unité doivent être renseignées ensemble : {ref}"))
        if country != "desserts":
            for s in recipe["steps"]:
                if "image" not in s:
                    issues.append(Issue(rel, "image d'étape manquante (requise hors desserts)"))
        # étape sans image (desserts) : seules les images présentes sont contrôlées
        images = [recipe["heroImage"]] + [s["image"] for s in recipe["steps"] if "image" in s]
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
                issues.append(Issue(rel, msg, severity="warning"))

    if country == "desserts":
        types = validators["recipe"].schema["properties"]["dessertType"]["enum"]
        issues += _desserts_rules(root, cdir, dessert_recipes, taxonomy, origins,
                                  occasions, types, today)

    index_path = cdir / "index.json"
    if index_path.exists():
        index = json.loads(index_path.read_text())
        for err in validators["index"].iter_errors(index):
            issues.append(Issue(str(index_path.relative_to(root)), f"schéma index : {err.message}"))
        ids_on_disk = {p.stem for p in (cdir / "recipes").glob("*.json")}
        ids_in_index = {r["id"] for r in index.get("recipes", [])}
        if ids_on_disk != ids_in_index:
            issues.append(Issue(str(index_path.relative_to(root)),
                f"index désynchronisé (disque - index : {sorted(ids_on_disk - ids_in_index)}, "
                f"index - disque : {sorted(ids_in_index - ids_on_disk)}) — relancer build_index"))
        for msg in annex_fingerprint_errors(cdir, index.get("files", {})):
            issues.append(Issue(str(index_path.relative_to(root)), msg))
        for pick in index.get("dailyPicks", []):
            if pick["recipeID"] not in ids_on_disk:
                issues.append(Issue(str(index_path.relative_to(root)),
                                    f"dailyPick vers recette inconnue : {pick['recipeID']}"))
        # Fenêtre anti-répétition (spec §5.4) : la propriété dépend de la taille du catalogue
        # (0 répétition à 30 ids, 3 à 20) — elle doit être tenue par la CI, pas par une
        # vérification manuelle ponctuelle après chaque régénération. La fenêtre est celle
        # du générateur : 14 jours, ou le nombre de fiches si le catalogue est plus petit.
        window = no_repeat_window(len(ids_on_disk))
        dated = []
        for pick in index.get("dailyPicks", []):
            try:
                dated.append((date.fromisoformat(pick["date"]), pick["recipeID"]))
            except ValueError:
                continue   # date malformée : déjà signalée par le schéma
        dated.sort()
        for i, (day, rid) in enumerate(dated):
            for prev_day, prev_rid in reversed(dated[:i]):
                if (day - prev_day).days >= window:
                    break
                if prev_rid == rid:
                    issues.append(Issue(str(index_path.relative_to(root)),
                        f"répétition de {rid} à moins de {window} jours "
                        f"({prev_day} et {day})"))
                    break
        if country == "desserts":
            # Alternance pays / région : tenue par le générateur avec repli, mais impossible
            # à garantir sur un petit catalogue (7 desserts français sur 10) : alerte seulement.
            main_country = {r["id"]: (r.get("origin", {}).get("countries") or [None])[0]
                            for _, r in dessert_recipes}
            for (prev_day, prev_rid), (day, rid) in zip(dated, dated[1:]):
                if (day - prev_day).days != 1:
                    continue
                a, b = main_country.get(prev_rid), main_country.get(rid)
                if a is None or b is None:
                    continue
                if a == b or (a in country_region and b in country_region
                              and country_region[a] == country_region[b]):
                    kind = "pays" if a == b else "région"
                    issues.append(Issue(str(index_path.relative_to(root)),
                        f"même {kind} deux jours de suite ({day} : {prev_rid}, {rid})",
                        severity="warning"))
    return issues


def main(argv: list[str]) -> int:
    release = "--release" in argv
    countries = [a for a in argv if not a.startswith("--")] or list(COUNTRIES)
    root = Path.cwd()
    all_issues = []
    for c in countries:
        all_issues += validate_country(root, c, release=release)
    errors = [i for i in all_issues if i.severity == "error"]
    for i in all_issues:
        icon = "❌" if i.severity == "error" else "⚠️ "
        print(f"{icon} {i.path}: {i.message}")
    print(f"{len(errors)} erreur(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
