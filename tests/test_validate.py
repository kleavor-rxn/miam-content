import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import jsonschema

from tests.conftest import _lt, make_recipe, write_recipe

from tools.build_index import build_index
from tools.validate import _load_schemas, validate_country

REPO = Path(__file__).resolve().parents[1]


def test_schemas_are_valid_jsonschema():
    for name in ["recipe", "ingredients", "index", "origins", "occasions"]:
        schema = json.loads((REPO / "schema" / f"{name}.schema.json").read_text())
        jsonschema.Draft202012Validator.check_schema(schema)


def _validator(name):
    return _load_schemas(REPO)[name]


def test_recipe_schema_accepts_dessert_fields():
    v = _validator("recipe")
    r = make_recipe("ds-brigadeiro")
    r |= {"origin": {"countries": ["BR"]}, "dessertType": "confiserie",
          "occasions": ["anniversaire"], "story": _lt("Histoire"), "tags": ["noBake"]}
    del r["steps"][0]["image"]
    assert list(v.iter_errors(r)) == []


def test_recipe_schema_rejects_bad_origin():
    v = _validator("recipe")
    for countries in [[], ["br"], ["BR", "PT", "ES", "FR"], ["BR", "BR"]]:
        r = make_recipe("ds-x") | {"origin": {"countries": countries}}
        assert list(v.iter_errors(r)), countries


def test_recipe_schema_rejects_unknown_dessert_type():
    r = make_recipe("ds-x") | {"dessertType": "tourte"}
    assert list(_validator("recipe").iter_errors(r))


def test_country_recipe_still_requires_step_image(content_repo):
    r = make_recipe("fr-sans-image"); del r["steps"][0]["image"]
    write_recipe(content_repo, "france", r)
    assert any("image d'étape" in m for m in _errors(content_repo))


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


def test_daily_picks_repeat_within_window_detected(content_repo):
    # 2 recettes : fenêtre de 2 jours ; la même recette deux jours de suite la viole.
    index = build_index(content_repo, "france",
                        now=datetime(2026, 8, 14, tzinfo=timezone.utc))
    index["dailyPicks"] = [{"date": "2026-08-14", "recipeID": "fr-test-un"},
                           {"date": "2026-08-15", "recipeID": "fr-test-un"}]
    (content_repo / "france" / "index.json").write_text(json.dumps(index))
    assert any("répétition" in m for m in _errors(content_repo))


def test_daily_picks_without_repeat_is_accepted(content_repo):
    index = build_index(content_repo, "france",
                        now=datetime(2026, 8, 14, tzinfo=timezone.utc))
    index["dailyPicks"] = [{"date": "2026-08-14", "recipeID": "fr-test-un"},
                           {"date": "2026-08-28", "recipeID": "fr-test-un"}]   # 14 j d'écart : OK (fenêtre = 2 avec 2 fiches, bien plus large ici)
    (content_repo / "france" / "index.json").write_text(json.dumps(index))
    assert not any("répétition" in m for m in _errors(content_repo))


def _france_with_14_recipes_and_picks(content_repo, gap_days):
    """14 fiches sur disque (fenêtre = 14) ; fr-test-un publiée deux fois, `gap_days` jours d'écart."""
    for n in range(12):
        write_recipe(content_repo, "france", make_recipe(f"fr-test-extra{n:02d}"))
    index = build_index(content_repo, "france",
                        now=datetime(2026, 8, 14, tzinfo=timezone.utc))
    assert len(index["recipes"]) == 14
    second = (date(2026, 8, 14) + timedelta(days=gap_days)).isoformat()
    index["dailyPicks"] = [{"date": "2026-08-14", "recipeID": "fr-test-un"},
                           {"date": second, "recipeID": "fr-test-un"}]
    (content_repo / "france" / "index.json").write_text(json.dumps(index))


def test_daily_picks_repeat_at_13_days_is_error_with_full_window(content_repo):
    _france_with_14_recipes_and_picks(content_repo, 13)
    assert any("répétition" in m and "14 jours" in m for m in _errors(content_repo))


def test_daily_picks_repeat_at_14_days_is_accepted_with_full_window(content_repo):
    _france_with_14_recipes_and_picks(content_repo, 14)
    assert not any("répétition" in m for m in _errors(content_repo))


def test_validate_detects_stale_annex_fingerprint(content_repo):
    # index écrit, puis ingredients.json modifié sans rebuild
    index = build_index(content_repo, "france",
                        now=datetime(2026, 8, 14, tzinfo=timezone.utc))
    (content_repo / "france" / "index.json").write_text(json.dumps(index))
    assert not any("empreinte" in m for m in _errors(content_repo))
    tax_path = content_repo / "france" / "ingredients.json"
    tax = json.loads(tax_path.read_text())
    tax["ingredients"][0]["names"]["fr"] = "Carotte modifiée"
    tax_path.write_text(json.dumps(tax))
    assert any("empreinte périmée : ingredients.json" in m for m in _errors(content_repo))


def test_validate_detects_annex_missing_from_files(content_repo):
    index = build_index(content_repo, "france",
                        now=datetime(2026, 8, 14, tzinfo=timezone.utc))
    index["files"] = {}
    (content_repo / "france" / "index.json").write_text(json.dumps(index))
    assert any("empreinte manquante : ingredients.json" in m for m in _errors(content_repo))
