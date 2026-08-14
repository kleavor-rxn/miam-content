"""Convertit les images source d'une recette en WebP normalisés.

Attend dans src_dir : hero.<ext> et step-N.<ext> (png/jpg/webp).
Écrit <country>/images/<recipe_id>/{hero,step-N}.webp et supprime
le marqueur .placeholder s'il existe (de vraies images remplacent les placeholders).
"""
import sys
from pathlib import Path

from PIL import Image

MAX_WIDTH = {"hero": 1200, "step": 800}
QUALITY = 82


def process_images(src_dir: Path, root: Path, country: str, recipe_id: str) -> list[Path]:
    out_dir = root / country / "images" / recipe_id
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for src in sorted(src_dir.iterdir()):
        stem = src.stem
        if stem == "hero":
            max_w = MAX_WIDTH["hero"]
        elif stem.startswith("step-") and stem.removeprefix("step-").isdigit():
            max_w = MAX_WIDTH["step"]
        else:
            continue
        img = Image.open(src).convert("RGB")
        if img.width > max_w:
            img = img.resize((max_w, round(img.height * max_w / img.width)),
                             Image.LANCZOS)
        out = out_dir / f"{stem}.webp"
        img.save(out, "WEBP", quality=QUALITY)
        written.append(out)
    marker = out_dir / ".placeholder"
    if written and marker.exists():
        marker.unlink()
    return written


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: python -m tools.process_images <src_dir> <pays> <recipe-id>")
        return 2
    written = process_images(Path(argv[0]), Path.cwd(), argv[1], argv[2])
    for w in written:
        print(f"✅ {w}")
    return 0 if written else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
