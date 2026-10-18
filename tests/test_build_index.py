import hashlib
import json
from datetime import date, datetime, timezone

from tests.conftest import make_dessert, make_recipe, write_recipe

from tools.build_index import build_index, check_index

T1 = datetime(2026, 8, 14, 10, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc)


def test_index_lists_all_recipes_with_now_as_updated_at(content_repo):
    index = build_index(content_repo, "france", now=T1)
    assert {r["id"] for r in index["recipes"]} == {"fr-test-un", "fr-test-deux"}
    assert all(r["updatedAt"] == "2026-08-14T10:00:00Z" for r in index["recipes"])
    assert index["recipes"][0]["totalMinutes"] == 30
    assert len(index["dailyPicks"]) == 61   # today-30 .. today+30


def test_unmodified_recipe_keeps_updated_at(content_repo):
    first = build_index(content_repo, "france", now=T1)
    (content_repo / "france" / "index.json").write_text(json.dumps(first))
    second = build_index(content_repo, "france", now=T2)
    assert all(r["updatedAt"] == "2026-08-14T10:00:00Z" for r in second["recipes"])


def test_modified_recipe_bumps_only_its_updated_at(content_repo):
    first = build_index(content_repo, "france", now=T1)
    (content_repo / "france" / "index.json").write_text(json.dumps(first))
    changed = make_recipe("fr-test-un")
    changed["prepMinutes"] = 99
    write_recipe(content_repo, "france", changed)
    second = build_index(content_repo, "france", now=T2)
    by_id = {r["id"]: r["updatedAt"] for r in second["recipes"]}
    assert by_id["fr-test-un"] == "2026-08-20T10:00:00Z"
    assert by_id["fr-test-deux"] == "2026-08-14T10:00:00Z"


def test_existing_picks_preserved(content_repo):
    first = build_index(content_repo, "france", now=T1)
    (content_repo / "france" / "index.json").write_text(json.dumps(first))
    second = build_index(content_repo, "france", now=T2)
    old = {p["date"]: p["recipeID"] for p in first["dailyPicks"]}
    for p in second["dailyPicks"]:
        if p["date"] in old:
            assert p["recipeID"] == old[p["date"]]


def test_check_detects_stale_index(content_repo):
    index = build_index(content_repo, "france", now=T1)
    (content_repo / "france" / "index.json").write_text(json.dumps(index))
    assert check_index(content_repo, "france", today=date(2026, 8, 14)) == []
    changed = make_recipe("fr-test-un")
    changed["servings"] = 8
    write_recipe(content_repo, "france", changed)
    errors = check_index(content_repo, "france", today=date(2026, 8, 14))
    assert any("fr-test-un" in e for e in errors)


def test_check_detects_exhausted_calendar(content_repo):
    index = build_index(content_repo, "france", now=T1)  # horizon : 2026-09-13
    (content_repo / "france" / "index.json").write_text(json.dumps(index))
    errors = check_index(content_repo, "france", today=date(2026, 9, 10))
    assert any("7 jours" in e for e in errors)


def test_check_detects_orphan_index_entry(content_repo):
    index = build_index(content_repo, "france", now=T1)
    (content_repo / "france" / "index.json").write_text(json.dumps(index))
    (content_repo / "france" / "recipes" / "fr-test-deux.json").unlink()
    errors = check_index(content_repo, "france", today=date(2026, 8, 14))
    assert any("absent du disque" in e for e in errors)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_index_lists_annex_fingerprints(content_repo):
    idx = build_index(content_repo, "france", T1)
    assert idx["files"] == {"ingredients.json": _sha(content_repo / "france" / "ingredients.json")}


def test_index_lists_only_present_annexes(desserts_repo):
    (desserts_repo / "desserts" / "occasions.json").unlink()
    idx = build_index(desserts_repo, "desserts", T1)
    assert sorted(idx["files"]) == ["ingredients.json", "origins.json"]


def test_annex_change_changes_index(content_repo):
    a = build_index(content_repo, "france", T1)
    tax_path = content_repo / "france" / "ingredients.json"
    tax = json.loads(tax_path.read_text())
    tax["ingredients"][0]["names"]["fr"] = "Carotte modifiée"
    tax_path.write_text(json.dumps(tax))
    assert build_index(content_repo, "france", T1)["files"] != a["files"]


def _write_index(root, country="france"):
    index = build_index(root, country, T1)
    (root / country / "index.json").write_text(json.dumps(index))
    return index


def test_check_index_detects_stale_annex_fingerprint(content_repo):
    _write_index(content_repo)
    assert check_index(content_repo, "france", today=date(2026, 8, 14)) == []
    (content_repo / "france" / "ingredients.json").write_text('{"schemaVersion": 1}')
    errors = check_index(content_repo, "france", today=date(2026, 8, 14))
    assert any("empreinte périmée : ingredients.json" in e for e in errors)


def test_check_index_detects_annex_missing_from_files(desserts_repo):
    index = build_index(desserts_repo, "desserts", T1)
    del index["files"]["origins.json"]
    (desserts_repo / "desserts" / "index.json").write_text(json.dumps(index))
    errors = check_index(desserts_repo, "desserts", today=date(2026, 8, 14))
    assert any("empreinte manquante : origins.json" in e for e in errors)


def test_check_index_detects_annex_deleted_from_disk(desserts_repo):
    index = build_index(desserts_repo, "desserts", T1)
    (desserts_repo / "desserts" / "index.json").write_text(json.dumps(index))
    (desserts_repo / "desserts" / "occasions.json").unlink()
    errors = check_index(desserts_repo, "desserts", today=date(2026, 8, 14))
    assert any("empreinte périmée : occasions.json" in e for e in errors)


def test_check_index_flags_legacy_index_without_files(content_repo):
    index = build_index(content_repo, "france", T1)
    del index["files"]
    (content_repo / "france" / "index.json").write_text(json.dumps(index))
    errors = check_index(content_repo, "france", today=date(2026, 8, 14))
    assert any("index à régénérer" in e for e in errors)


def test_desserts_calendar_alternates_main_country(desserts_repo):
    # 2 fiches FR + 2 fiches IT : seul `origins` (pays principal via origins.json) force l'alternance
    write_recipe(desserts_repo, "desserts", make_dessert("ds-test-trois"))
    write_recipe(desserts_repo, "desserts",
                 make_dessert("ds-test-quatre", origin={"countries": ["IT", "FR"]}))
    index = build_index(desserts_repo, "desserts", now=T1)
    country = {"ds-test-un": "FR", "ds-test-trois": "FR",
               "ds-test-deux": "IT", "ds-test-quatre": "IT"}
    picks = [country[p["recipeID"]] for p in index["dailyPicks"]]
    assert len(picks) == 61
    assert all(a != b for a, b in zip(picks, picks[1:]))
