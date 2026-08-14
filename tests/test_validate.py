import json
from pathlib import Path

import jsonschema

from tests.conftest import make_recipe, write_recipe

from tools.validate import validate_country

REPO = Path(__file__).resolve().parents[1]


def test_schemas_are_valid_jsonschema():
    for name in ["recipe", "ingredients", "index"]:
        schema = json.loads((REPO / "schema" / f"{name}.schema.json").read_text())
        jsonschema.Draft202012Validator.check_schema(schema)


def _errors(root):
    return [e.message for e in validate_country(root, "france")
            if e.severity == "error"]


def test_valid_repo_has_no_errors(content_repo):
    assert _errors(content_repo) == []


def test_unknown_ingredient_ref(content_repo):
    bad = make_recipe("fr-bad", ingredients=[
        {"ref": "licorne", "quantity": 1, "unit": "kg"}])
    write_recipe(content_repo, "france", bad)
    assert any("licorne" in m for m in _errors(content_repo))


def test_unknown_substitute_in_recipe(content_repo):
    bad = make_recipe("fr-bad", ingredients=[
        {"ref": "carotte", "quantity": 1, "unit": "kg", "substitutes": ["licorne"]}])
    write_recipe(content_repo, "france", bad)
    assert any("licorne" in m for m in _errors(content_repo))


def test_airfryer_tag_requires_notes(content_repo):
    write_recipe(content_repo, "france", make_recipe("fr-bad", tags=["airFryer"]))
    assert any("airFryerNotes" in m for m in _errors(content_repo))


def test_airfryer_notes_require_tag(content_repo):
    write_recipe(content_repo, "france", make_recipe("fr-bad", air_notes=True))
    assert any("airFryerNotes" in m for m in _errors(content_repo))


def test_missing_step_image_file(content_repo):
    p = write_recipe(content_repo, "france", make_recipe("fr-bad"))
    (content_repo / "france" / "images" / "fr-bad" / "step-1.webp").unlink()
    assert any("step-1.webp" in m for m in _errors(content_repo))


def test_non_staple_requires_quantity(content_repo):
    bad = make_recipe("fr-bad", ingredients=[
        {"ref": "carotte", "quantity": None, "unit": None}])
    write_recipe(content_repo, "france", bad)
    assert any("quantité" in m for m in _errors(content_repo))


def test_id_must_match_filename_and_country(content_repo):
    p = write_recipe(content_repo, "france", make_recipe("fr-bon-id"))
    p.rename(p.with_name("fr-autre-nom.json"))
    assert any("fr-autre-nom" in m for m in _errors(content_repo))


def test_placeholder_marker_warns_and_blocks_release(content_repo):
    (content_repo / "france" / "images" / "fr-test-un" / ".placeholder").write_text("")
    assert _errors(content_repo) == []  # warning seulement
    release = [e.message for e in validate_country(content_repo, "france", release=True)]
    assert any("placeholder" in m for m in release)


def test_images_must_live_in_recipe_folder(content_repo):
    bad = make_recipe("fr-bad")
    bad["heroImage"] = "images/fr-test-un/hero.webp"  # existe, mais mauvais dossier
    write_recipe(content_repo, "france", bad)
    assert any("hors du dossier" in m for m in _errors(content_repo))


def test_quantity_and_unit_must_pair(content_repo):
    bad = make_recipe("fr-bad", ingredients=[
        {"ref": "carotte", "quantity": 200, "unit": None}])
    write_recipe(content_repo, "france", bad)
    assert any("ensemble" in m for m in _errors(content_repo))


def test_id_country_prefix_must_match_folder(content_repo):
    write_recipe(content_repo, "france", make_recipe("it-mauvais-pays"))
    assert any("ne commence pas par 'fr-'" in m for m in _errors(content_repo))


def test_unknown_substitute_in_taxonomy(content_repo):
    import json
    tax = json.loads((content_repo / "france" / "ingredients.json").read_text())
    tax["ingredients"][0]["substitutes"] = ["licorne"]
    (content_repo / "france" / "ingredients.json").write_text(json.dumps(tax))
    assert any("licorne" in m for m in _errors(content_repo))


def test_index_out_of_sync_detected(content_repo):
    import json
    index = {"schemaVersion": 1, "generatedAt": "2026-08-14T00:00:00Z",
             "recipes": [], "dailyPicks": []}
    (content_repo / "france" / "index.json").write_text(json.dumps(index))
    assert any("désynchronisé" in m for m in _errors(content_repo))
