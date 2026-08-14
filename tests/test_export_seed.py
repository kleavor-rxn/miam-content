import json
from datetime import datetime, timezone

from tools.build_index import build_index
from tools.export_seed import export_seed


def test_exports_subset_with_filtered_index(content_repo, tmp_path):
    index = build_index(content_repo, "france",
                        now=datetime(2026, 8, 14, tzinfo=timezone.utc))
    (content_repo / "france" / "index.json").write_text(json.dumps(index))
    (content_repo / "france" / "seed.txt").write_text("# seed v1\nfr-test-un\n")
    (content_repo / "france" / "images" / "fr-test-un" / ".placeholder").write_text("")
    out = tmp_path / "seed"
    export_seed(content_repo, "france", out)
    assert (out / "recipes" / "fr-test-un.json").is_file()
    assert (out / "images" / "fr-test-un" / "hero.webp").is_file()
    assert not (out / "recipes" / "fr-test-deux.json").exists()
    assert not (out / "images" / "fr-test-un" / ".placeholder").exists()
    seed_index = json.loads((out / "index.json").read_text())
    assert [r["id"] for r in seed_index["recipes"]] == ["fr-test-un"]
    assert all(p["recipeID"] == "fr-test-un" for p in seed_index["dailyPicks"])


def test_unknown_seed_id_raises(content_repo, tmp_path):
    (content_repo / "france" / "index.json").write_text(json.dumps(
        build_index(content_repo, "france",
                    now=datetime(2026, 8, 14, tzinfo=timezone.utc))))
    (content_repo / "france" / "seed.txt").write_text("fr-inconnue\n")
    try:
        export_seed(content_repo, "france", tmp_path / "seed")
        assert False, "aurait dû lever"
    except ValueError as e:
        assert "fr-inconnue" in str(e)
