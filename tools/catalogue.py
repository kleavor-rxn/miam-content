"""Liste prévue des desserts (desserts/catalogue.json) : contrôle de structure et d'équilibre.

`check` vérifie la structure de la liste (toujours) et, avec `--targets`, son équilibre sur les
entrées actives (ni réserve, ni rejetée). `status` affiche l'avancement par région et par lot.
"""
import json
import sys
from collections import Counter
from pathlib import Path

from tools.validate import Issue, _load_checked, _load_schemas

REGION_TARGETS = {"europe-ouest": 15, "europe-sud": 14, "europe-nord-est": 12,
                  "afrique-nord-moyen-orient": 14, "afrique-subsaharienne": 8,
                  "asie-sud": 10, "asie-est": 12, "asie-sud-est": 10,
                  "amerique-nord": 8, "amerique-latine-caraibes": 11, "oceanie": 6}
TOTAL, MIN_COUNTRIES, MIN_FEATURED, MIN_TYPE, RESERVES_PER_REGION, MAX_FRANCE = 120, 40, 5, 5, 2, 8

COLLECTION = "desserts"
DEFAULT_ROOT = Path(__file__).resolve().parents[1]


def _is_active(entry: dict) -> bool:
    return not entry["reserve"] and entry["status"] != "rejected"


def _is_live_reserve(entry: dict) -> bool:
    return entry["reserve"] and entry["status"] != "rejected"


def check(root: Path, targets: bool = False) -> list[Issue]:
    cdir = root / COLLECTION
    validators = _load_schemas(root)
    rel = str((cdir / "catalogue.json").relative_to(root))

    issues: list[Issue] = []
    loaded = {}
    for name in ("catalogue", "origins", "ingredients", "occasions"):
        data, errs = _load_checked(root, cdir / f"{name}.json", validators[name], name)
        loaded[name] = data
        issues += errs
    if loaded["catalogue"] is None:   # les messages de schéma n'indiquent pas l'entrée fautive : on la précise
        issues = [i for i in issues if not i.message.startswith("schéma catalogue")]
        data = json.loads((cdir / "catalogue.json").read_text())
        for e in validators["catalogue"].iter_errors(data):
            where = "/".join(str(p) for p in e.absolute_path)
            issues.append(Issue(rel, f"schéma catalogue : {where} : {e.message}"))
    if any(d is None for d in loaded.values()):
        return issues
    entries = loaded["catalogue"]["entries"]

    country_region = {c["code"]: c["region"] for c in loaded["origins"]["countries"]}
    recipe_schema = json.loads((root / "schema" / "recipe.schema.json").read_text())
    dessert_types = recipe_schema["properties"]["dessertType"]["enum"]
    featured_ids = [g["id"] for g in loaded["ingredients"].get("featured", [])]
    occasion_ids = {o["id"] for o in loaded["occasions"]["occasions"]}

    ids = Counter(e["id"] for e in entries)
    for rid, n in sorted(ids.items()):
        if n > 1:
            issues.append(Issue(rel, f"id dupliqué : {rid}"))

    for e in entries:
        for code in e["countries"]:
            if code not in country_region:
                issues.append(Issue(rel, f"{e['id']} : pays inconnu : {code}"))
        if e["type"] not in dessert_types:
            issues.append(Issue(rel, f"{e['id']} : type inconnu : {e['type']}"))
        for v in e["featured"]:
            if v not in featured_ids:
                issues.append(Issue(rel, f"{e['id']} : vedette inconnue : {v}"))
        for oc in e["occasions"]:
            if oc not in occasion_ids:
                issues.append(Issue(rel, f"{e['id']} : occasion inconnue : {oc}"))

    fiches = {p.stem for p in (cdir / "recipes").glob("*.json")}
    for e in entries:
        if e["status"] == "written" and e["id"] not in fiches:
            issues.append(Issue(rel, f"{e['id']} : statut written mais fiche recipes/{e['id']}.json absente"))
    listed = set(ids)
    for rid in sorted(fiches - listed):
        issues.append(Issue(rel, f"{rid} : fiche sans entrée dans le catalogue"))

    if targets:
        issues += _targets(rel, entries, country_region, dessert_types, featured_ids)
    return issues


def _principal_region(entry: dict, country_region: dict) -> str | None:
    return country_region.get(entry["countries"][0])


def _targets(rel, entries, country_region, dessert_types, featured_ids) -> list[Issue]:
    issues: list[Issue] = []
    active = [e for e in entries if _is_active(e)]
    if len(active) < TOTAL:
        issues.append(Issue(rel, f"total : {len(active)} desserts actifs (minimum {TOTAL})"))

    countries = {e["countries"][0] for e in active}
    if len(countries) < MIN_COUNTRIES:
        issues.append(Issue(rel, f"{len(countries)} pays distincts (minimum {MIN_COUNTRIES})"))

    by_region = Counter(_principal_region(e, country_region) for e in active)
    reserves = Counter(_principal_region(e, country_region) for e in entries if _is_live_reserve(e))
    for region, target in REGION_TARGETS.items():
        if by_region[region] < target:
            issues.append(Issue(rel, f"région {region} : {by_region[region]} desserts actifs (cible {target})"))
        if reserves[region] < RESERVES_PER_REGION:
            issues.append(Issue(rel, f"région {region} : {reserves[region]} réserve(s) "
                                     f"(minimum {RESERVES_PER_REGION})"))

    by_featured = Counter(v for e in active for v in set(e["featured"]))
    for v in featured_ids:
        if by_featured[v] < MIN_FEATURED:
            issues.append(Issue(rel, f"vedette {v} : {by_featured[v]} desserts actifs (minimum {MIN_FEATURED})"))
    by_type = Counter(e["type"] for e in active)
    for t in dessert_types:
        if by_type[t] < MIN_TYPE:
            issues.append(Issue(rel, f"type {t} : {by_type[t]} desserts actifs (minimum {MIN_TYPE})"))

    french = sum(1 for e in active if e["countries"][0] == "FR")
    if french > MAX_FRANCE:
        issues.append(Issue(rel, f"France : {french} desserts actifs de pays principal FR (maximum {MAX_FRANCE})"))
    return issues


def status(root: Path) -> str:
    cdir = root / COLLECTION
    entries = json.loads((cdir / "catalogue.json").read_text())["entries"]
    origins = json.loads((cdir / "origins.json").read_text())
    country_region = {c["code"]: c["region"] for c in origins["countries"]}
    regions = [r["id"] for r in origins["regions"]]

    monthly = sorted({e["lot"] for e in entries if isinstance(e["lot"], str)})
    lots = list(range(7)) + monthly
    cells: dict[str, Counter] = {r: Counter() for r in regions}
    for e in entries:
        region = _principal_region(e, country_region)
        if region not in cells or e["status"] == "rejected":
            continue
        cells[region]["reserve" if e["reserve"] else e["lot"]] += 1

    header = ["région"] + [str(lot) for lot in lots] + ["réserves"]
    rows = [header]
    for region in regions:
        rows.append([region] + [str(cells[region][lot]) for lot in lots] + [str(cells[region]["reserve"])])
    rows.append(["total"] + [str(sum(cells[r][lot] for r in regions)) for lot in lots + ["reserve"]])
    widths = [max(len(row[i]) for row in rows) for i in range(len(header))]
    return "\n".join(
        "  ".join(cell.ljust(w) if i == 0 else cell.rjust(w)
                  for i, (cell, w) in enumerate(zip(row, widths)))
        for row in rows)


def main(argv: list[str], root: Path = DEFAULT_ROOT) -> int:
    command = argv[0] if argv else ""
    if command == "check":
        all_issues = check(root, targets="--targets" in argv[1:])
        errors = [i for i in all_issues if i.severity == "error"]
        for i in all_issues:
            icon = "❌" if i.severity == "error" else "⚠️ "
            print(f"{icon} {i.path}: {i.message}")
        print(f"{len(errors)} erreur(s).")
        return 1 if errors else 0
    if command == "status":
        print(status(root))
        return 0
    print("usage : python -m tools.catalogue check [--targets] | status", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
