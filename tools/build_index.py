"""Génère <pays>/index.json : summaries (updatedAt par hash) + dailyPicks.

`--check` (CI) : vérifie sans rien écrire que l'index committé est à jour
(hash de chaque fiche) et que le calendrier couvre ≥ 7 jours d'avance.
"""
import hashlib
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from tools.countries import COUNTRIES
from tools.daily_picks import extend_daily_picks


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_index(root: Path, country: str, now: datetime) -> dict:
    cdir = root / country
    previous = {}
    prev_picks = []
    index_path = cdir / "index.json"
    if index_path.exists():
        prev = json.loads(index_path.read_text())
        previous = {r["id"]: r for r in prev.get("recipes", [])}
        prev_picks = prev.get("dailyPicks", [])

    summaries = []
    for rp in sorted((cdir / "recipes").glob("*.json")):
        raw = rp.read_bytes()
        recipe = json.loads(raw)
        content_hash = hashlib.sha256(raw).hexdigest()
        prev_entry = previous.get(recipe["id"])
        if prev_entry and prev_entry["contentHash"] == content_hash:
            updated_at = prev_entry["updatedAt"]
        else:
            updated_at = _iso(now)
        summaries.append({
            "id": recipe["id"],
            "updatedAt": updated_at,
            "contentHash": content_hash,
            "title": recipe["title"],
            "heroImage": recipe["heroImage"],
            "tags": recipe["tags"],
            "totalMinutes": recipe["prepMinutes"] + recipe["cookMinutes"],
            "difficulty": recipe["difficulty"],
        })

    picks = extend_daily_picks(prev_picks, [s["id"] for s in summaries],
                               country, now.astimezone(timezone.utc).date())
    return {"schemaVersion": 1, "generatedAt": _iso(now),
            "recipes": summaries, "dailyPicks": picks}


def check_index(root: Path, country: str, today: date) -> list[str]:
    """Contrôle CI : l'index committé reflète-t-il le contenu du disque ?"""
    cdir = root / country
    index_path = cdir / "index.json"
    if not index_path.exists():
        return [f"{country}: index.json manquant — lancer build_index"]
    index = json.loads(index_path.read_text())
    by_id = {r["id"]: r for r in index.get("recipes", [])}
    errors = []
    on_disk = set()
    for rp in sorted((cdir / "recipes").glob("*.json")):
        on_disk.add(rp.stem)
        entry = by_id.get(rp.stem)
        h = hashlib.sha256(rp.read_bytes()).hexdigest()
        if entry is None or entry["contentHash"] != h:
            errors.append(f"{country}: index périmé pour {rp.stem} — relancer build_index")
    for extra in sorted(set(by_id) - on_disk):
        errors.append(f"{country}: {extra} dans l'index mais absent du disque")
    last = max((p["date"] for p in index.get("dailyPicks", [])), default="")
    if last < (today + timedelta(days=7)).isoformat():
        errors.append(f"{country}: dailyPicks couvre moins de 7 jours d'avance")
    return errors


def main(argv: list[str]) -> int:
    check = "--check" in argv
    countries = [a for a in argv if not a.startswith("--")] or list(COUNTRIES)
    now = datetime.now(timezone.utc)
    if check:
        errors = []
        for c in countries:
            errors += check_index(Path.cwd(), c, now.date())
        for e in errors:
            print(f"❌ {e}")
        return 1 if errors else 0
    for c in countries:
        index = build_index(Path.cwd(), c, now)
        out = Path.cwd() / c / "index.json"
        out.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n")
        print(f"{c}: {len(index['recipes'])} recettes, "
              f"{len(index['dailyPicks'])} dailyPicks -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
