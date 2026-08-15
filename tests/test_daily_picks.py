from datetime import date, timedelta

from tools.daily_picks import NO_REPEAT_DAYS, extend_daily_picks

IDS = [f"fr-r{n:02d}" for n in range(20)]
TODAY = date(2026, 8, 14)


def test_backfills_history_window_from_empty():
    picks = extend_daily_picks([], IDS, "france", TODAY)
    assert picks[0]["date"] == "2026-07-15"   # today - 30
    assert picks[-1]["date"] == "2026-09-13"  # today + 30
    assert len(picks) == 61


def test_existing_past_entry_is_preserved():
    existing = [{"date": "2026-08-01", "recipeID": IDS[3]}]
    picks = extend_daily_picks(existing, IDS, "france", TODAY)
    assert {"date": "2026-08-01", "recipeID": IDS[3]} in picks


def test_deterministic():
    a = extend_daily_picks([], IDS, "france", TODAY)
    b = extend_daily_picks([], IDS, "france", TODAY)
    assert a == b


def test_no_repeat_within_14_days():
    picks = extend_daily_picks([], IDS, "france", TODAY)
    ids = [p["recipeID"] for p in picks]
    for i in range(len(ids)):
        assert ids[i] not in ids[max(0, i - 13):i]


def test_keeps_existing_and_drops_removed():
    existing = [{"date": "2026-08-13", "recipeID": "fr-r00"},
                {"date": "2026-08-14", "recipeID": "fr-disparue"}]
    picks = extend_daily_picks(existing, IDS, "france", TODAY)
    assert {"date": "2026-08-13", "recipeID": "fr-r00"} in picks
    assert all(p["recipeID"] != "fr-disparue" for p in picks)
    assert any(p["date"] == "2026-08-14" for p in picks)  # re-rempli


def test_small_catalog_does_not_crash():
    picks = extend_daily_picks([], ["fr-a", "fr-b"], "france", TODAY)
    assert len(picks) == 61  # répétitions autorisées si catalogue < fenêtre


def test_empty_catalog_returns_empty():
    existing = [{"date": "2026-08-13", "recipeID": "fr-x"}]
    assert extend_daily_picks(existing, [], "france", TODAY) == []


def test_refilled_hole_avoids_upcoming_preserved_picks():
    # J+1..J+13 déjà attribués ; le trou d'aujourd'hui ne doit dupliquer aucun d'eux
    existing = [{"date": (TODAY + timedelta(days=n)).isoformat(), "recipeID": IDS[n]}
                for n in range(1, 14)]
    picks = extend_daily_picks(existing, IDS, "france", TODAY)
    today_pick = next(p for p in picks if p["date"] == "2026-08-14")
    assert today_pick["recipeID"] not in {IDS[n] for n in range(1, 14)}


def test_backfilled_days_never_collide_with_preserved_future():
    """Repli gradué : quand `recent` ∪ `ahead` sature le catalogue, un jour rétro-rempli
    sacrifie la variété du passé — jamais une recette déjà PUBLIÉE dans ses 14 jours
    suivants (elle, l'utilisateur la verra vraiment)."""
    ids = [f"fr-r{n:02d}" for n in range(14)]   # catalogue juste assez petit pour saturer
    existing = [{"date": (TODAY + timedelta(days=n)).isoformat(), "recipeID": ids[n]}
                for n in range(1, NO_REPEAT_DAYS)]
    preserved = {p["date"]: p["recipeID"] for p in existing}
    picks = extend_daily_picks(existing, ids, "france", TODAY)
    filled = [p for p in picks if p["date"] not in preserved]
    assert len(filled) == 48   # 61 jours - 13 préservés : tout le reste est généré
    for p in filled:
        day = date.fromisoformat(p["date"])
        ahead = {preserved[k] for k in
                 ((day + timedelta(days=n)).isoformat() for n in range(1, NO_REPEAT_DAYS))
                 if k in preserved}
        assert p["recipeID"] not in ahead, f"{p['date']} duplique un jour déjà publié"


def test_past_older_than_60_days_pruned():
    existing = [{"date": "2026-05-01", "recipeID": IDS[0]},
                {"date": "2026-08-01", "recipeID": IDS[1]}]
    picks = extend_daily_picks(existing, IDS, "france", TODAY)
    dates = [p["date"] for p in picks]
    assert "2026-05-01" not in dates and "2026-08-01" in dates
