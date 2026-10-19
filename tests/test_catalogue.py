import copy
import json
import shutil
import string

import pytest

from tests.conftest import REPO, _lt
from tools import catalogue
from tools.catalogue import MAX_FRANCE, REGION_TARGETS, RESERVES_PER_REGION, check, status

VEDETTES = [f["id"] for f in json.loads(
    (REPO / "desserts" / "ingredients.json").read_text())["featured"]]
TYPES = json.loads((REPO / "schema" / "recipe.schema.json").read_text())[
    "properties"]["dessertType"]["enum"]


def _entry(rid, country="FR", type_="gateau", **kw):
    e = {"id": rid, "title": rid, "countries": [country], "type": type_,
         "featured": [], "occasions": [], "lot": 0, "reserve": False,
         "status": "planned"}
    e.update(kw)
    return e


def _write_catalogue(root, entries):
    (root / "desserts" / "catalogue.json").write_text(
        json.dumps({"schemaVersion": 1, "entries": entries}, ensure_ascii=False))


def _errors(root, **kw):
    return [i.message for i in check(root, **kw) if i.severity == "error"]


@pytest.fixture
def small_repo(desserts_repo):
    """Collection valide à 2 fiches (ds-test-un FR gateau, ds-test-deux IT tarte) + liste assortie."""
    _write_catalogue(desserts_repo, [
        _entry("ds-test-un", "FR", "gateau", status="written", featured=["chocolat"],
               occasions=["noel", "gouter"]),
        _entry("ds-test-deux", "IT", "tarte", status="written", featured=["chocolat"]),
    ])
    return desserts_repo


def _codes():
    """Codes pays synthétiques uniques (jamais FR)."""
    for a in string.ascii_uppercase:
        for b in string.ascii_uppercase:
            if a + b != "FR":
                yield a + b


def make_balanced_repo(tmp_path):
    """Collection sans fiches : 120 actives conformes aux cibles + 2 réserves par région.

    Pays synthétiques (5 par région, dont FR pour l'Europe de l'Ouest), vedettes et types
    en rotation. Retourne (racine, entrées).
    """
    shutil.copytree(REPO / "schema", tmp_path / "schema")
    d = tmp_path / "desserts"
    d.mkdir()
    for name in ("ingredients", "occasions"):
        shutil.copy(REPO / "desserts" / f"{name}.json", d / f"{name}.json")
    codes = _codes()
    regions, countries, entries = [], [], []
    n = {False: 0, True: 0}   # rotations séparées : les réserves ne faussent pas les actives
    for region, target in REGION_TARGETS.items():
        regions.append({"id": region, "names": _lt(region)})
        own = ["FR"] if region == "europe-ouest" else []
        own += [next(codes) for _ in range(5 - len(own))]
        for c in own:
            countries.append({"code": c, "names": _lt(c), "region": region,
                              "latitude": 10.0, "longitude": 10.0})
        for j in range(target + RESERVES_PER_REGION):
            reserve = j >= target
            if region == "europe-ouest" and j < MAX_FRANCE:
                country = "FR"
            else:
                country = [c for c in own if c != "FR"][j % (len(own) - (region == "europe-ouest"))]
            entries.append(_entry(f"ds-{region}-{j}", country, TYPES[n[reserve] % len(TYPES)],
                                  featured=[VEDETTES[n[reserve] % len(VEDETTES)]],
                                  lot=n[reserve] % 7, reserve=reserve))
            n[reserve] += 1
    (d / "origins.json").write_text(json.dumps(
        {"schemaVersion": 1, "regions": regions, "countries": countries}, ensure_ascii=False))
    _write_catalogue(tmp_path, entries)
    return tmp_path, entries


@pytest.fixture
def balanced(tmp_path):
    return make_balanced_repo(tmp_path)


def _edit(root, entries, index, **changes):
    entries = copy.deepcopy(entries)
    entries[index].update(changes)
    _write_catalogue(root, entries)
    return entries


def _first(entries, region_prefix, reserve=False):
    return next(i for i, e in enumerate(entries)
                if e["id"].startswith(f"ds-{region_prefix}-") and e["reserve"] == reserve)


# --- structure -------------------------------------------------------------

def test_existing_ten_pass_structure():
    assert _errors(REPO) == []


def test_small_repo_is_valid(small_repo):
    assert _errors(small_repo) == []


def test_duplicate_id_fails(small_repo):
    _write_catalogue(small_repo, [_entry("ds-test-un", status="written"),
                                  _entry("ds-test-un", "IT", status="written"),
                                  _entry("ds-test-deux", "IT", status="written")])
    assert any("id dupliqué : ds-test-un" in m for m in _errors(small_repo))


def test_unknown_country_fails(small_repo):
    _write_catalogue(small_repo, [_entry("ds-test-un", "FR", status="written"),
                                  _entry("ds-test-deux", "IT", status="written"),
                                  _entry("ds-pays-inconnu", "JP")])
    assert any("pays inconnu : JP" in m for m in _errors(small_repo))


def test_more_than_three_countries_fails(small_repo):
    _write_catalogue(small_repo, [
        _entry("ds-test-un", "FR", status="written", countries=["FR", "IT", "FR", "IT"]),
        _entry("ds-test-deux", "IT", status="written")])
    assert any("1 à 3 pays" in m or "countries" in m for m in _errors(small_repo))


def test_empty_countries_fails(small_repo):
    _write_catalogue(small_repo, [_entry("ds-test-un", status="written", countries=[]),
                                  _entry("ds-test-deux", "IT", status="written")])
    assert _errors(small_repo)


def test_unknown_type_featured_occasion_fail(small_repo):
    _write_catalogue(small_repo, [
        _entry("ds-test-un", status="written", type="soupe", featured=["truffe"],
               occasions=["diwali"]),
        _entry("ds-test-deux", "IT", status="written")])
    errs = _errors(small_repo)
    assert any("type inconnu : soupe" in m for m in errs)
    assert any("vedette inconnue : truffe" in m for m in errs)
    assert any("occasion inconnue : diwali" in m for m in errs)


def test_id_without_ds_prefix_fails(small_repo):
    _write_catalogue(small_repo, [_entry("fr-test-un", status="written"),
                                  _entry("ds-test-deux", "IT", status="written")])
    assert _errors(small_repo)


def test_rejected_requires_reason(small_repo):
    entries = [_entry("ds-test-un", status="written"),
               _entry("ds-test-deux", "IT", status="written"),
               _entry("ds-rejete", status="rejected")]
    _write_catalogue(small_repo, entries)
    assert any("reason" in m for m in _errors(small_repo))
    entries[2]["reason"] = "doublon de ds-test-un"
    _write_catalogue(small_repo, entries)
    assert _errors(small_repo) == []


def test_lot_accepts_monthly_string_and_rejects_garbage(small_repo):
    base = [_entry("ds-test-un", status="written"),
            _entry("ds-test-deux", "IT", status="written")]
    for lot, ok in ((6, True), ("m-2027-03", True), (7, False), ("m-2027-13", False),
                    ("lot-3", False)):
        _write_catalogue(small_repo, base + [_entry("ds-autre", lot=lot)])
        assert (_errors(small_repo) == []) is ok, lot


def test_written_entry_without_fiche_fails(small_repo):
    (small_repo / "desserts" / "recipes" / "ds-test-un.json").unlink()
    assert any("ds-test-un" in m and "fiche" in m for m in _errors(small_repo))


def test_fiche_without_entry_fails(small_repo):
    _write_catalogue(small_repo, [_entry("ds-test-un", status="written")])
    assert any("ds-test-deux" in m and "entrée" in m for m in _errors(small_repo))


def test_planned_entry_needs_no_fiche(small_repo):
    _write_catalogue(small_repo, [_entry("ds-test-un", status="written"),
                                  _entry("ds-test-deux", "IT", status="written"),
                                  _entry("ds-futur", "IT", status="planned")])
    assert _errors(small_repo) == []


def test_structure_check_ignores_targets(small_repo):
    assert _errors(small_repo) == []
    assert _errors(small_repo, targets=True) != []


# --- cibles ----------------------------------------------------------------

def test_balanced_repo_passes_targets(balanced):
    root, _ = balanced
    assert _errors(root) == []
    assert _errors(root, targets=True) == []


def test_targets_count_only_active_entries(balanced):
    root, entries = balanced
    i = _first(entries, "asie-est")
    # rejetée : ne compte ni dans le total ni dans la région
    _edit(root, entries, i, status="rejected", reason="doublon")
    errs = _errors(root, targets=True)
    assert any("119" in m for m in errs)
    assert any("asie-est" in m and "11" in m for m in errs)
    # une réserve ne compte pas non plus parmi les actives
    _edit(root, entries, i, reserve=True)
    errs = _errors(root, targets=True)
    assert any("119" in m for m in errs)
    assert any("asie-est" in m and "11" in m for m in errs)


def test_rejection_without_replacement_fails_targets(balanced):
    root, entries = balanced
    i = _first(entries, "oceanie")
    _edit(root, entries, i, status="rejected", reason="trop proche d'un autre")
    errs = _errors(root, targets=True)
    assert any("total" in m and "119" in m for m in errs)
    assert _errors(root) == []   # la structure reste valide


def test_too_many_french_desserts_fails(balanced):
    root, entries = balanced
    i = next(i for i, e in enumerate(entries)
             if e["id"].startswith("ds-europe-ouest-") and not e["reserve"]
             and e["countries"][0] != "FR")
    _edit(root, entries, i, countries=["FR"])
    assert any("FR" in m and "9" in m for m in _errors(root, targets=True))


def test_missing_reserves_fail(balanced):
    root, entries = balanced
    i = _first(entries, "asie-sud", reserve=True)
    _edit(root, entries, i, status="rejected", reason="écartée")   # une réserve rejetée ne compte pas
    errs = _errors(root, targets=True)
    assert any("asie-sud" in m and "réserve" in m for m in errs)


def test_too_few_countries_fails(balanced):
    root, entries = balanced
    origins = json.loads((root / "desserts" / "origins.json").read_text())
    region_of = {c["code"]: c["region"] for c in origins["countries"]}
    one_per_region = {}
    new = copy.deepcopy(entries)
    for e in new:
        if e["countries"][0] != "FR":
            e["countries"] = [one_per_region.setdefault(region_of[e["countries"][0]],
                                                        e["countries"][0])]
    _write_catalogue(root, new)
    errs = _errors(root, targets=True)
    assert any("pays distincts" in m and "12" in m for m in errs)   # 11 régions + FR


def test_featured_and_type_minimums(balanced):
    root, entries = balanced
    new = copy.deepcopy(entries)
    for e in new:
        e["featured"] = [v for v in e["featured"] if v != "miel"]
        if e["type"] == "fruit":
            e["type"] = "gateau"
    _write_catalogue(root, new)
    errs = _errors(root, targets=True)
    assert any("vedette miel" in m for m in errs)
    assert any("type fruit" in m for m in errs)


# --- status ----------------------------------------------------------------

def test_status_table(small_repo):
    _write_catalogue(small_repo, [
        _entry("ds-test-un", "FR", status="written"),
        _entry("ds-test-deux", "IT", status="written"),
        _entry("ds-p1", "IT", lot=2),
        _entry("ds-p2", "IT", lot="m-2027-03"),
        _entry("ds-r1", "FR", reserve=True),
        _entry("ds-x", "FR", status="rejected", reason="doublon"),
    ])
    rows = {l.split()[0]: l.split()[1:] for l in status(small_repo).splitlines()[1:]}
    # colonnes : lots 0..6, mensuel m-2027-03, réserves
    assert rows["europe-ouest"] == ["1", "0", "0", "0", "0", "0", "0", "0", "1"]
    assert rows["europe-sud"] == ["1", "0", "1", "0", "0", "0", "0", "1", "0"]
    assert rows["total"] == ["2", "0", "1", "0", "0", "0", "0", "1", "1"]
    assert "m-2027-03" in status(small_repo).splitlines()[0]


# --- CLI -------------------------------------------------------------------

def test_cli_check_and_status(small_repo, capsys):
    assert catalogue.main(["check"], root=small_repo) == 0
    assert "0 erreur(s)." in capsys.readouterr().out
    assert catalogue.main(["check", "--targets"], root=small_repo) == 1
    assert "erreur(s)." in capsys.readouterr().out
    assert catalogue.main(["status"], root=small_repo) == 0
    assert "total" in capsys.readouterr().out
