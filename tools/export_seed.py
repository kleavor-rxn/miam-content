"""Exporte le seed embarqué par l'app : sous-ensemble de <pays>/seed.txt.

Copie recettes + images et écrit un index.json filtré (même format que l'index
complet — l'app charge le seed exactement comme un instantané de cache).
"""
import json
import shutil
import sys
from pathlib import Path

from tools.countries import COUNTRIES


def export_seed(root: Path, country: str, out_dir: Path) -> list[str]:
    cdir = root / country
    lines = [line.strip() for line in (cdir / "seed.txt").read_text().splitlines()]
    ids = list(dict.fromkeys(l for l in lines if l and not l.startswith("#")))
    index = json.loads((cdir / "index.json").read_text())
    known = {r["id"] for r in index["recipes"]}
    unknown = [i for i in ids if i not in known]
    if unknown:
        raise ValueError(f"ids de seed absents de l'index : {unknown}")
    out_dir = out_dir.resolve()
    rroot = root.resolve()
    forbidden = {rroot, *[(rroot / c) for c in COUNTRIES]}
    if out_dir in forbidden or out_dir in rroot.parents:
        raise ValueError(f"dossier de sortie dangereux : {out_dir}")
    if out_dir.exists() and any(out_dir.iterdir()) and not (
            (out_dir / "index.json").is_file() and (out_dir / "recipes").is_dir()):
        raise ValueError(f"refus d'écraser : {out_dir} n'est pas un export précédent")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "recipes").mkdir(parents=True)
    (out_dir / "images").mkdir()
    for rid in ids:
        shutil.copy2(cdir / "recipes" / f"{rid}.json", out_dir / "recipes")
        # exclut l'outillage du bundle app : marqueurs et prompts photo
        shutil.copytree(cdir / "images" / rid, out_dir / "images" / rid,
                        ignore=shutil.ignore_patterns(".placeholder", "PROMPTS.md", ".DS_Store"))
    seed_index = {
        "schemaVersion": index["schemaVersion"],
        "generatedAt": index["generatedAt"],
        "recipes": [r for r in index["recipes"] if r["id"] in set(ids)],
        "dailyPicks": [p for p in index["dailyPicks"] if p["recipeID"] in set(ids)],
    }
    (out_dir / "index.json").write_text(
        json.dumps(seed_index, ensure_ascii=False, indent=2) + "\n")
    return ids


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m tools.export_seed <pays> <dossier-sortie>")
        return 2
    ids = export_seed(Path.cwd(), argv[0], Path(argv[1]))
    print(f"✅ {len(ids)} recettes exportées vers {argv[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
