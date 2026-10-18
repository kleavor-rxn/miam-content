import hashlib
import json
from datetime import date, timedelta

from tools.daily_picks import NO_REPEAT_DAYS, extend_daily_picks, no_repeat_window

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


# --- Collection desserts : fenêtre adaptée au catalogue, alternance pays / région ---

def test_no_repeat_window_is_capped_by_catalogue_size():
    assert no_repeat_window(30) == 14
    assert no_repeat_window(14) == 14
    assert no_repeat_window(10) == 10
    assert no_repeat_window(1) == 1


def test_small_catalogue_has_no_repeat_within_its_size():
    ids = [f"ds-r{n}" for n in range(10)]
    picks = [p["recipeID"] for p in extend_daily_picks([], ids, "desserts", TODAY)]
    for i in range(len(picks)):
        assert picks[i] not in picks[max(0, i - 9):i]


def test_single_recipe_catalogue_does_not_crash():
    picks = extend_daily_picks([], ["ds-seule"], "desserts", TODAY)
    assert len(picks) == 61 and {p["recipeID"] for p in picks} == {"ds-seule"}


def test_no_same_country_or_region_two_days_running():
    # 30 ids répartis sur 6 pays / 3 régions, assez pour que la règle soit tenable
    origins = {f"ds-r{n:02d}": (["FR", "IT", "JP", "CN", "MX", "BR"][n % 6],
                                ["eu", "as", "am"][n % 6 // 2]) for n in range(30)}
    picks = extend_daily_picks([], list(origins), "desserts", TODAY, origins=origins)
    assert len(picks) == 61
    for a, b in zip(picks, picks[1:]):
        assert origins[a["recipeID"]][0] != origins[b["recipeID"]][0]
        assert origins[a["recipeID"]][1] != origins[b["recipeID"]][1]


def test_country_rule_relaxes_to_other_country_when_region_impossible():
    # deux pays dans une seule région : la région ne peut pas alterner, le pays si
    origins = {f"ds-r{n:02d}": (["FR", "BE"][n % 2], "eu") for n in range(20)}
    picks = extend_daily_picks([], list(origins), "desserts", TODAY, origins=origins)
    assert len(picks) == 61
    for a, b in zip(picks, picks[1:]):
        assert origins[a["recipeID"]][0] != origins[b["recipeID"]][0]


def test_country_rule_relaxes_when_impossible():
    origins = {f"ds-r{n}": ("FR", "eu") for n in range(20)}   # un seul pays : pas d'échec, calendrier complet
    assert len(extend_daily_picks([], list(origins), "desserts", TODAY, origins=origins)) == 61


def test_origin_rule_keeps_repeat_window():
    origins = {f"ds-r{n:02d}": (["FR", "IT", "JP", "CN", "MX", "BR"][n % 6],
                                ["eu", "as", "am"][n % 6 // 2]) for n in range(30)}
    ids = [p["recipeID"] for p in
           extend_daily_picks([], list(origins), "desserts", TODAY, origins=origins)]
    for i in range(len(ids)):
        assert ids[i] not in ids[max(0, i - 13):i]


def test_origin_rule_leaves_published_history_untouched():
    origins = {f"ds-r{n:02d}": (["FR", "IT", "JP"][n % 3], ["eu", "as", "am"][n % 3])
               for n in range(12)}
    # deux jours publiés de même pays : l'histoire n'est jamais réécrite
    existing = [{"date": "2026-08-10", "recipeID": "ds-r00"},
                {"date": "2026-08-11", "recipeID": "ds-r03"}]
    picks = extend_daily_picks(existing, list(origins), "desserts", TODAY, origins=origins)
    assert {"date": "2026-08-10", "recipeID": "ds-r00"} in picks
    assert {"date": "2026-08-11", "recipeID": "ds-r03"} in picks


# Instantané de la sortie AVANT l'ajout de `origins` / de la fenêtre adaptée : les 30 vrais
# ids de france/index.json, sans `origins`, doivent donner exactement le même calendrier.
FRANCE_IDS = [
    "fr-blanquette-de-veau", "fr-boeuf-bourguignon", "fr-camembert-roti",
    "fr-cassoulet", "fr-clafoutis-aux-cerises", "fr-coq-au-vin",
    "fr-creme-brulee", "fr-crepes", "fr-croque-monsieur",
    "fr-far-breton", "fr-flammekueche", "fr-gougeres",
    "fr-gratin-dauphinois", "fr-hachis-parmentier", "fr-madeleines",
    "fr-mousse-au-chocolat", "fr-navarin-d-agneau", "fr-oeufs-mimosa",
    "fr-poireaux-vinaigrette", "fr-pot-au-feu", "fr-poulet-basquaise",
    "fr-quiche-lorraine", "fr-ratatouille", "fr-salade-nicoise",
    "fr-soupe-a-l-oignon", "fr-steak-frites", "fr-tarte-tatin",
    "fr-tartiflette", "fr-tomates-farcies", "fr-veloute-de-potiron",
]
FRANCE_SNAPSHOT_SHA256 = "641681054be768a9a1a53b97a19b660e7c4ff70f8f10d3389febcd9c2e446af1"


def test_country_collections_unchanged():
    picks = extend_daily_picks([], FRANCE_IDS, "france", date(2026, 8, 14))
    digest = hashlib.sha256(json.dumps(picks, sort_keys=True).encode()).hexdigest()
    assert digest == FRANCE_SNAPSHOT_SHA256
