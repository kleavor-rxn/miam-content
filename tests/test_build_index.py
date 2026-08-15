import json
from datetime import date, datetime, timezone

from tests.conftest import make_recipe, write_recipe

from tools.build_index import build_index, check_index

T1 = datetime(2026, 8, 14, 10, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc)


def test_index_lists_all_recipes_with_now_as_updated_at(content_repo):
    index = build_index(content_repo, "france", now=T1)
    assert {r["id"] for r in index["recipes"]} == {"fr-test-un", "fr-test-deux"}
    assert all(r["updatedAt"] == "2026-08-14T10:00:00Z" for r in index["recipes"])
    assert index["recipes"][0]["totalMinutes"] == 30
    assert len(index["dailyPicks"]) == 31


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
