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
        if "image" in s:   # les desserts n'ont pas d'image d'étape
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


def make_dessert(rid, **overrides):
    """Fiche dessert valide : origine, type, histoire, occasions, sans image d'étape."""
    r = make_recipe(
        rid,
        ingredients=[
            {"ref": "sucre", "quantity": None, "unit": None},
            {"ref": "chocolat-noir", "quantity": 200, "unit": "g"},
            {"ref": "beurre", "quantity": 100, "unit": "g"},
            {"ref": "oeuf", "quantity": 3, "unit": "piece"},
        ],
    )
    r["category"] = "dessert"
    r["steps"] = [{"text": _lt("Étape 1")}]
    r["origin"] = {"countries": ["FR"]}
    r["dessertType"] = "gateau"
    r["occasions"] = ["gouter"]
    r["story"] = _lt("Histoire")
    r.update(overrides)
    return r


DESSERTS_TAXONOMY = {
    "schemaVersion": 1,
    "ingredients": [
        {"id": "sucre", "names": _lt("Sucre"), "category": "epicerie",
         "staple": True, "contains": [], "animal": False},
        {"id": "chocolat-noir", "names": _lt("Chocolat noir"), "category": "epicerie",
         "staple": False, "contains": [], "animal": False},
        {"id": "beurre", "names": _lt("Beurre"), "category": "produits-laitiers",
         "staple": False, "contains": ["lait"], "animal": True},
        {"id": "oeuf", "names": _lt("Oeuf"), "category": "produits-laitiers",
         "staple": False, "contains": ["oeuf"], "animal": True},
    ],
    "featured": [
        {"id": "chocolat", "names": _lt("Chocolat"), "emoji": "🍫",
         "members": ["chocolat-noir"]},
    ],
}

DESSERTS_ORIGINS = {
    "schemaVersion": 1,
    "regions": [
        {"id": "europe-ouest", "names": _lt("Europe de l'Ouest")},
        {"id": "europe-sud", "names": _lt("Europe du Sud")},
    ],
    "countries": [
        {"code": "FR", "names": _lt("France"), "region": "europe-ouest",
         "latitude": 46.2, "longitude": 2.2},
        {"code": "IT", "names": _lt("Italie"), "region": "europe-sud",
         "latitude": 41.9, "longitude": 12.6},
    ],
}

DESSERTS_OCCASIONS = {
    "schemaVersion": 1,
    "occasions": [
        {"id": "noel", "names": _lt("Noël"),
         "windows": [{"start": "2027-12-01", "end": "2027-12-26"},
                     {"start": "2028-12-01", "end": "2028-12-26"}]},
        {"id": "gouter", "names": _lt("Goûter")},
    ],
}


@pytest.fixture
def desserts_repo(tmp_path):
    """Mini-repo : schémas réels + collection 'desserts' valide (2 fiches ds-*)."""
    shutil.copytree(REPO / "schema", tmp_path / "schema")
    d = tmp_path / "desserts"
    d.mkdir()
    for name, data in (("ingredients", DESSERTS_TAXONOMY),
                       ("origins", DESSERTS_ORIGINS),
                       ("occasions", DESSERTS_OCCASIONS)):
        (d / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False))
    write_recipe(tmp_path, "desserts",
                 make_dessert("ds-test-un", occasions=["noel", "gouter"]))
    write_recipe(tmp_path, "desserts",
                 make_dessert("ds-test-deux", origin={"countries": ["IT"]},
                              dessertType="tarte"))
    return tmp_path
