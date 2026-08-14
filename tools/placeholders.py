"""Images placeholder (couleur unie dérivée de l'id) pour développer sans photos.

Dépose un marqueur .placeholder : toléré par validate, bloquant avec --release.
"""
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image


def _color(recipe_id: str) -> tuple[int, int, int]:
    d = hashlib.sha256(recipe_id.encode()).digest()
    return (96 + d[0] % 128, 96 + d[1] % 128, 96 + d[2] % 128)


def generate_placeholders(root: Path, country: str, recipe_id: str) -> list[Path]:
    recipe = json.loads((root / country / "recipes" / f"{recipe_id}.json").read_text())
    out_dir = root / country / "images" / recipe_id
    out_dir.mkdir(parents=True, exist_ok=True)
    color = _color(recipe_id)
    targets = [("hero.webp", (1200, 800))]
    targets += [(Path(s["image"]).name, (800, 600)) for s in recipe["steps"]]
    written = []
    for name, size in targets:
        out = out_dir / name
        Image.new("RGB", size, color).save(out, "WEBP", quality=60)
        written.append(out)
    (out_dir / ".placeholder").write_text("images générées, à remplacer avant release\n")
    return written


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python -m tools.placeholders <pays> <recipe-id> [...]")
        return 2
    for rid in argv[1:]:
        for w in generate_placeholders(Path.cwd(), argv[0], rid):
            print(f"🖼️  {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
