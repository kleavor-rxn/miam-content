"""Génère les photos des recettes en local avec FLUX.1 schnell (mflux, Apple Silicon).

Lit <pays>/images/<id>/PROMPTS.md (première ligne = style du pays, sections « ## hero.webp »,
« ## step-N.webp ») et écrit des PNG 3:2 dans un dossier de travail HORS repo, à relire
avant `process_images`. Seed déterministe par image : relancer redonne la même photo.

À lancer avec l'interpréteur de mflux (uv tool install mflux) :
  ~/.local/share/uv/tools/mflux/bin/python -m tools.generate_photos <sortie> <pays/id[@N]>... [--steps]

Licence : FLUX.1 schnell est Apache 2.0 — usage commercial autorisé (pas FLUX.1 dev).
"""
import re
import sys
import time
from pathlib import Path

# Le dépôt officiel black-forest-labs est désormais à accès restreint (connexion HF requise) ;
# ce miroir de la communauté mflux, pré-quantifié 8 bits, porte la même licence Apache 2.0.
MODEL_REPO = "mflux-community/flux-1-schnell-mflux-q8"
WIDTH, HEIGHT = 1536, 1024   # 3:2 comme les visuels du contenu (1200×800 après process_images)
# Pas de négation sur un objet précis : schnell n'a pas de prompt négatif et nommer
# « fromage à trous », même pour l'interdire, en fait apparaître (constaté le 14 oct. 2026).
QUALITY_SUFFIX = (
    "professional editorial food photography, appetizing, true-to-life colors, "
    "sharp focus on the food, 50mm lens, the dish centered with generous margin on all sides, "
    "one single dish as the hero, plain unbranded props, plain unpatterned tableware, "
    "absolutely no text, lettering, labels, stickers, logos or packaging anywhere, "
    "no hands in frame unless described, no people's faces"
)


def parse_prompts(path: Path) -> tuple[str, dict[str, str]]:
    """Deux formats coexistent : sections « ## hero.webp » (France) et puces « - **hero**: » (Italie)."""
    text = path.read_text(encoding="utf-8")
    style = text.split("\n", 1)[0].strip()
    shots = {name: body.strip() for name, body in re.findall(r"^## (\S+)\.webp\n(.*?)(?=^## |\Z)", text, re.S | re.M)}
    shots.update({name: body.strip() for name, body in re.findall(r"^- \*\*([\w-]+)\*\*: (.+)$", text, re.M)})
    return style, shots


def seed_for(key: str) -> int:
    h = 5381
    for b in key.encode():
        h = (h * 33 + b) & 0xFFFFFFFF
    return h


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    with_steps = "--steps" in argv
    out_root = Path(argv[0]).expanduser()
    targets = [a for a in argv[1:] if not a.startswith("--")]
    root = Path(__file__).resolve().parent.parent

    from mflux.models.common.config import ModelConfig
    from mflux.models.flux.variants.txt2img.flux import Flux1

    flux = Flux1(model_config=ModelConfig.schnell(), model_path=MODEL_REPO)
    for target in targets:
        # « pays/id@N » : autre tirage pour une photo ratée (seed décalé, fichier hero@N.png)
        target, _, variant = target.partition("@")
        country, recipe_id = target.split("/")
        style, shots = parse_prompts(root / country / "images" / recipe_id / "PROMPTS.md")
        names = [n for n in shots if n == "hero" or (with_steps and n.startswith("step-"))]
        for name in names:
            suffix = f"@{variant}" if variant else ""
            dest = out_root / country / recipe_id / f"{name}{suffix}.png"
            if dest.exists():
                continue   # reprise : ne régénère pas ce qui existe déjà
            dest.parent.mkdir(parents=True, exist_ok=True)
            prompt = f"{shots[name]} {style}, {QUALITY_SUFFIX}"
            start = time.time()
            image = flux.generate_image(seed=seed_for(f"{recipe_id}/{name}{suffix}"), prompt=prompt,
                                        num_inference_steps=4, width=WIDTH, height=HEIGHT)
            image.image.save(dest)
            print(f"✅ {dest} ({time.time() - start:.0f} s)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
