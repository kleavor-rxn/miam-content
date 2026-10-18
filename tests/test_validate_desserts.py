import copy
import json
from datetime import date

from tests.conftest import (DESSERTS_ORIGINS, DESSERTS_OCCASIONS, DESSERTS_TAXONOMY,
                            make_dessert, write_recipe)
from tools.validate import validate_country


def _issues(root, **kw):
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
               for m in _errors(desserts_repo, today=date(2027, 6, 1)))


def test_used_dated_occasion_ok_with_12_months(desserts_repo):
    assert _errors(desserts_repo, today=date(2027, 6, 1)) == []


def test_unused_dated_occasion_is_not_checked(desserts_repo):
    _short_noel(desserts_repo)
    write_recipe(desserts_repo, "desserts", make_dessert("ds-test-un"))
    assert _errors(desserts_repo, today=date(2027, 6, 1)) == []


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
