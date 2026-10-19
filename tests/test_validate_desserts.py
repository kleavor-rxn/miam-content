import copy
import json
from datetime import date, datetime, timezone

from tests.conftest import (DESSERTS_ORIGINS, DESSERTS_OCCASIONS, DESSERTS_TAXONOMY,
                            make_dessert, write_recipe)
from tools.build_index import build_index
from tools.validate import validate_country


# Date figée : sans elle, la couverture 12 mois des occasions de la fixture (fenêtres
# jusqu'en 2028-12-26) expirerait avec le temps réel et ferait échouer les tests.
PINNED_TODAY = date(2027, 6, 1)


def _issues(root, **kw):
    kw.setdefault("today", PINNED_TODAY)
    return validate_country(root, "desserts", **kw)


def _errors(root, **kw):
    return [i.message for i in _issues(root, **kw) if i.severity == "error"]


def _rewrite(root, name, data):
    (root / "desserts" / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False))


def _drop_field(root, rid, field):
    p = root / "desserts" / "recipes" / f"{rid}.json"
    r = json.loads(p.read_text())
    del r[field]
    p.write_text(json.dumps(r, ensure_ascii=False))


def test_valid_desserts_repo_has_no_errors(desserts_repo):
    assert _errors(desserts_repo) == []


def test_missing_origin(desserts_repo):
    _drop_field(desserts_repo, "ds-test-un", "origin")
    assert any("origin" in m for m in _errors(desserts_repo))


def test_missing_dessert_type(desserts_repo):
    _drop_field(desserts_repo, "ds-test-un", "dessertType")
    assert any("dessertType" in m for m in _errors(desserts_repo))


def test_missing_story(desserts_repo):
    _drop_field(desserts_repo, "ds-test-un", "story")
    assert any("story" in m for m in _errors(desserts_repo))


def test_unknown_origin_country(desserts_repo):
    write_recipe(desserts_repo, "desserts",
                 make_dessert("ds-test-un", origin={"countries": ["FR", "JP"]}))
    assert any("pays inconnu : JP" in m for m in _errors(desserts_repo))


def test_unknown_occasion(desserts_repo):
    write_recipe(desserts_repo, "desserts",
                 make_dessert("ds-test-un", occasions=["diwali"]))
    assert any("occasion inconnue : diwali" in m for m in _errors(desserts_repo))


def test_featured_member_not_in_taxonomy(desserts_repo):
    tax = copy.deepcopy(DESSERTS_TAXONOMY)
    tax["featured"][0]["members"].append("chocolat-blanc")
    _rewrite(desserts_repo, "ingredients", tax)
    assert any("membre vedette inconnu : chocolat-blanc" in m
               for m in _errors(desserts_repo))


def test_ingredient_without_contains_or_animal(desserts_repo):
    tax = copy.deepcopy(DESSERTS_TAXONOMY)
    del tax["ingredients"][0]["contains"]
    _rewrite(desserts_repo, "ingredients", tax)
    assert any("contains/animal manquant : sucre" in m for m in _errors(desserts_repo))
    tax = copy.deepcopy(DESSERTS_TAXONOMY)
    del tax["ingredients"][0]["animal"]
    _rewrite(desserts_repo, "ingredients", tax)
    assert any("contains/animal manquant : sucre" in m for m in _errors(desserts_repo))


def test_window_start_after_end(desserts_repo):
    occ = copy.deepcopy(DESSERTS_OCCASIONS)
    occ["occasions"][0]["windows"][0] = {"start": "2027-12-26", "end": "2027-12-01"}
    _rewrite(desserts_repo, "occasions", occ)
    assert any("fenêtre invalide" in m for m in _errors(desserts_repo))


def _short_noel(root):
    occ = copy.deepcopy(DESSERTS_OCCASIONS)
    occ["occasions"][0]["windows"] = [{"start": "2027-12-01", "end": "2027-12-26"}]
    _rewrite(root, "occasions", occ)


def test_used_dated_occasion_needs_12_months(desserts_repo):
    _short_noel(desserts_repo)
    assert any("moins de 12 mois" in m
               for m in _errors(desserts_repo))


def test_used_dated_occasion_ok_with_12_months(desserts_repo):
    assert _errors(desserts_repo) == []


def _noel_windows(root, *windows):
    occ = copy.deepcopy(DESSERTS_OCCASIONS)
    occ["occasions"][0]["windows"] = [{"start": a, "end": b} for a, b in windows]
    _rewrite(root, "occasions", occ)


def _coverage_warnings(root):
    return [m for m in _warnings(root) if "occasion noel" in m]


def test_occasion_warns_under_18_months(desserts_repo):
    # dernière fenêtre finissant ~15 mois après PINNED_TODAY : une alerte, 0 erreur
    _noel_windows(desserts_repo, ("2028-08-15", "2028-09-01"))
    assert _errors(desserts_repo) == []
    warns = _coverage_warnings(desserts_repo)
    assert len(warns) == 1
    assert "moins de 18 mois" in warns[0]


def test_occasion_no_warning_from_18_months(desserts_repo):
    # fenêtre finissant à la limite exacte des 18 mois (548 jours) : aucune alerte
    _noel_windows(desserts_repo, ("2028-11-15", "2028-11-30"))
    assert _errors(desserts_repo) == []
    assert _coverage_warnings(desserts_repo) == []


def test_occasion_under_12_months_is_error_without_warning(desserts_repo):
    _short_noel(desserts_repo)
    assert _coverage_warnings(desserts_repo) == []


def test_unused_dated_occasion_is_not_checked(desserts_repo):
    _short_noel(desserts_repo)
    write_recipe(desserts_repo, "desserts", make_dessert("ds-test-un"))
    assert _errors(desserts_repo) == []


def test_balance_is_warning_only(desserts_repo):
    ws = [i.message for i in _issues(desserts_repo) if i.severity == "warning"]
    assert any("région europe-ouest" in w for w in ws)   # < 6 desserts
    assert any("vedette chocolat" in w for w in ws)      # < 5 desserts
    assert any("type gateau" in w for w in ws)           # < 5 desserts
    assert _errors(desserts_repo) == []


def test_balance_counts_secondary_countries_once_per_region(desserts_repo):
    for n in range(5):
        write_recipe(desserts_repo, "desserts",
                     make_dessert(f"ds-extra-{n}", origin={"countries": ["IT", "FR"]}))
    ws = [i.message for i in _issues(desserts_repo) if i.severity == "warning"]
    # FR : ds-test-un + 5 extras (secondaire) = 6 -> pas d'alerte ; IT : ds-test-deux + 5 = 6
    assert not any("région europe-ouest" in w for w in ws)
    assert not any("région europe-sud" in w for w in ws)
    assert not any("vedette chocolat" in w for w in ws)   # 7 fiches >= 5


def test_balance_same_region_counts_once(desserts_repo):
    orig = copy.deepcopy(DESSERTS_ORIGINS)
    orig["countries"].append({"code": "BE", "names": DESSERTS_ORIGINS["regions"][0]["names"],
                              "region": "europe-ouest", "latitude": 50.5, "longitude": 4.5})
    _rewrite(desserts_repo, "origins", orig)
    for n in range(5):   # 5 fiches FR+BE (même région) + ds-test-un = 6 fiches
        write_recipe(desserts_repo, "desserts",
                     make_dessert(f"ds-extra-{n}", origin={"countries": ["FR", "BE"]}))
    ws = [i.message for i in _issues(desserts_repo) if i.severity == "warning"]
    assert not any("région europe-ouest" in w for w in ws)


def test_country_collections_ignore_dessert_rules(content_repo):
    # france sans origin / dessertType / story : aucune règle desserts
    assert [i for i in validate_country(content_repo, "france")
            if i.severity == "error"] == []


def test_invalid_origins_file_stops_early(desserts_repo):
    (desserts_repo / "desserts" / "origins.json").write_text("{pas du json")
    errs = _errors(desserts_repo)
    assert len(errs) == 1 and "origins" in errs[0]


def test_non_utf8_origins_file_gives_issue_not_crash(desserts_repo):
    (desserts_repo / "desserts" / "origins.json").write_bytes(b"\xff\xfe\x00{")
    errs = _errors(desserts_repo)
    assert len(errs) == 1 and "origins" in errs[0]


def _write_index(root, picks):
    """index.json réel (schéma, empreintes) dont le calendrier est remplacé par `picks`."""
    index = build_index(root, "desserts", now=datetime(2027, 6, 1, tzinfo=timezone.utc))
    index["dailyPicks"] = [{"date": d, "recipeID": r} for d, r in picks]
    (root / "desserts" / "index.json").write_text(json.dumps(index, ensure_ascii=False))


def _warnings(root, **kw):
    return [i.message for i in _issues(root, **kw) if i.severity == "warning"]


def test_validator_warns_same_country_consecutive(desserts_repo):
    write_recipe(desserts_repo, "desserts", make_dessert("ds-test-trois"))   # FR comme ds-test-un
    _write_index(desserts_repo, [("2027-06-01", "ds-test-un"), ("2027-06-02", "ds-test-trois"),
                                 ("2027-06-03", "ds-test-deux")])
    assert any("même pays" in m and "2027-06-02" in m for m in _warnings(desserts_repo))
    assert _errors(desserts_repo) == []


def test_validator_warns_same_region_consecutive(desserts_repo):
    origins = copy.deepcopy(DESSERTS_ORIGINS)
    origins["countries"][1]["region"] = "europe-ouest"   # IT dans la région de FR
    _rewrite(desserts_repo, "origins", origins)
    _write_index(desserts_repo, [("2027-06-01", "ds-test-un"), ("2027-06-02", "ds-test-deux")])
    warnings = _warnings(desserts_repo)
    assert any("même région" in m for m in warnings) and not any("même pays" in m for m in warnings)
    assert _errors(desserts_repo) == []


def test_validator_no_origin_warning_when_alternating(desserts_repo):
    _write_index(desserts_repo, [("2027-06-01", "ds-test-un"), ("2027-06-02", "ds-test-deux"),
                                 ("2027-06-03", "ds-test-un")])
    assert not any("deux jours de suite" in m for m in _warnings(desserts_repo))


def test_validator_origin_check_skips_gaps_between_days(desserts_repo):
    write_recipe(desserts_repo, "desserts", make_dessert("ds-test-trois"))
    _write_index(desserts_repo, [("2027-06-01", "ds-test-un"), ("2027-06-03", "ds-test-trois")])
    assert not any("deux jours de suite" in m for m in _warnings(desserts_repo))


def test_validator_repeat_window_scales_with_catalogue(desserts_repo):
    # 2 fiches : fenêtre de 2 jours (et non 14)
    _write_index(desserts_repo, [("2027-06-01", "ds-test-un"), ("2027-06-02", "ds-test-deux"),
                                 ("2027-06-03", "ds-test-un")])   # 2 jours d'écart : OK
    assert not any("répétition" in m for m in _errors(desserts_repo))
    _write_index(desserts_repo, [("2027-06-01", "ds-test-un"), ("2027-06-02", "ds-test-un")])
    assert any("répétition" in m and "2 jours" in m for m in _errors(desserts_repo))
