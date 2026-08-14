import json
import shutil
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _lt(fr):
    return {"fr": fr, "en": f"{fr} EN", "es": f"{fr} ES", "it": f"{fr} IT"}


def make_recipe(rid, tags=None, air_notes=False, ingredients=None, steps=1):
    r = {
        "schemaVersion": 1,
        "id": rid,
        "title": _lt(f"Titre {rid}"),
        "summary": _lt("Résumé"),
        "region": _lt("Région"),
        "category": "plat",
        "difficulty": 2,
        "prepMinutes": 10,
        "cookMinutes": 20,
        "servings": 4,
        "heroImage": f"images/{rid}/hero.webp",
        "tags": tags or [],
        "ingredients": ingredients
        or [{"ref": "carotte", "quantity": 200, "unit": "g"},
            {"ref": "sel", "quantity": None, "unit": None}],
        "steps": [
            {"text": _lt(f"Étape {n}"), "image": f"images/{rid}/step-{n}.webp"}
            for n in range(1, steps + 1)
        ],
    }
    if air_notes:
        r["airFryerNotes"] = _lt("Notes air fryer")
    return r


TAXONOMY = {
    "schemaVersion": 1,
    "ingredients": [
        {"id": "carotte", "names": _lt("Carotte"), "category": "legumes",
         "staple": False, "substitutes": ["panais"]},
        {"id": "panais", "names": _lt("Panais"), "category": "legumes", "staple": False},
        {"id": "sel", "names": _lt("Sel"), "category": "epicerie", "staple": True},
    ],
}


def write_recipe(root, country, recipe):
    p = root / country / "recipes" / f"{recipe['id']}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(recipe, ensure_ascii=False, indent=2))
    imgdir = root / country / "images" / recipe["id"]
    imgdir.mkdir(parents=True, exist_ok=True)
    (imgdir / "hero.webp").write_bytes(b"x")
    for s in recipe["steps"]:
        (imgdir / Path(s["image"]).name).write_bytes(b"x")
    return p


@pytest.fixture
def content_repo(tmp_path):
    """Mini-repo : schémas réels copiés + 1 pays 'france' avec 2 recettes valides."""
    shutil.copytree(REPO / "schema", tmp_path / "schema")
    (tmp_path / "france").mkdir()
    (tmp_path / "france" / "ingredients.json").write_text(
        json.dumps(TAXONOMY, ensure_ascii=False))
    write_recipe(tmp_path, "france", make_recipe("fr-test-un"))
    write_recipe(tmp_path, "france", make_recipe("fr-test-deux"))
    return tmp_path
