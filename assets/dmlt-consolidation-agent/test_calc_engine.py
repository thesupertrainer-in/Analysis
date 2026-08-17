"""
Unit tests for the deterministic calculation engine (``app/calc_engine.py``).

Two kinds of test live here:

  * **Rule tests** — small hand-built fixtures that pin each rule's exact
    behaviour, including the N-system case (a synthetic 6-system landscape with
    company code 1000 colliding across three of them).
  * **Sample-data tests** — the real 2-system extract in ``extractor_files/``,
    asserting the headline numbers the consultant checks first.

The engine has no dependencies beyond the standard library, so these run
without the agent framework installed.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))

import calc_engine as ce  # noqa: E402

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "extractor_files")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def sample_sections():
    """The real RUN_02 extract — a 2-system consolidation."""
    sections = {}
    for name in ["master", "growth", "system", "org", "nriv"]:
        path = os.path.join(SAMPLE_DIR, f"RQ1RUN_02_{name}.json")
        if not os.path.exists(path):
            pytest.skip(f"sample extract not available: {path}")
        with open(path) as fh:
            raw = json.load(fh)
        sections[name] = raw.get("data", raw) if isinstance(raw, dict) else raw
    return sections


def _six_system_org():
    """
    Synthetic 6-system org section.

    Company code 1000 exists in three systems under three different entity
    names — a genuine collision.  Code 2000 exists in four systems under one
    name — a safe duplicate.  Code 3000 exists in one system only.
    """
    rows = []
    entity_1000 = {
        "S01_100": "Acme Manufacturing GmbH",
        "S02_100": "Acme Retail Ltd",
        "S03_100": "Acme Logistics SA",
    }
    for sid in ["S01_100", "S02_100", "S03_100", "S04_100", "S05_100", "S06_100"]:
        if sid in entity_1000:
            rows.append({
                "sidclnt": sid, "from_type": "BUKRS", "from_id": "1000",
                "to_type": "CLIENT", "to_id": "100",
                "from_text": entity_1000[sid],
            })
        # Same code, same name in four systems -> safe duplicate
        if sid in ["S01_100", "S02_100", "S04_100", "S05_100"]:
            rows.append({
                "sidclnt": sid, "from_type": "BUKRS", "from_id": "2000",
                "to_type": "CLIENT", "to_id": "100",
                "from_text": "Global Shared Services BV",
            })
    # Single-system code -> neither collision nor duplicate
    rows.append({
        "sidclnt": "S06_100", "from_type": "BUKRS", "from_id": "3000",
        "to_type": "CLIENT", "to_id": "100", "from_text": "Solo Entity Oy",
    })
    # Noise the rule must ignore: BUKRS->COA carries an unrelated text, and
    # a non-BUKRS edge reuses code 1000.
    rows.append({
        "sidclnt": "S01_100", "from_type": "BUKRS", "from_id": "1000",
        "to_type": "COA", "to_id": "INT", "from_text": "TOTALLY DIFFERENT TEXT",
    })
    rows.append({
        "sidclnt": "S02_100", "from_type": "PLANT", "from_id": "1000",
        "to_type": "CLIENT", "to_id": "100", "from_text": "Plant One",
    })
    return rows


# ---------------------------------------------------------------------------
# Rule 1 — sizing
# ---------------------------------------------------------------------------

def test_sizing_uses_only_table_level_rows():
    master = [
        {"sidclnt": "A_100", "tabname": "BSEG", "agg_level": "T",
         "category": "APPL", "tab_total_cnt": 100, "tab_total_kb": 1000},
        # agg_level C is a company-code split of the same table; including it
        # would double count.
        {"sidclnt": "A_100", "tabname": "BSEG", "agg_level": "C",
         "category": "APPL", "tab_total_cnt": 60, "tab_total_kb": 600},
    ]
    r = ce.calculate_sizing(master)
    assert r["systems"]["A_100"]["total_rows"] == 100
    assert r["systems"]["A_100"]["total_kb"] == 1000
    assert r["row_count_used"] == 1


def test_sizing_consolidates_and_finds_largest():
    master = [
        {"sidclnt": "SMALL_100", "tabname": "T1", "agg_level": "T",
         "category": "APPL", "tab_total_cnt": 10, "tab_total_kb": 100},
        {"sidclnt": "BIG_100", "tabname": "T1", "agg_level": "T",
         "category": "APPL", "tab_total_cnt": 990, "tab_total_kb": 9900},
        {"sidclnt": "BIG_100", "tabname": "T2", "agg_level": "T",
         "category": "CUST", "tab_total_cnt": 0, "tab_total_kb": 50},
    ]
    r = ce.calculate_sizing(master)

    assert r["consolidated"]["total_rows"] == 1000
    assert r["consolidated"]["total_kb"] == 10050
    assert r["consolidated"]["distinct_tables"] == 2

    assert r["largest_system"]["sidclnt"] == "BIG_100"
    assert r["largest_system"]["share_of_rows_pct"] == 99.0

    # T1 exists in both systems; per-table consolidation sums across them.
    t1 = next(t for t in r["consolidated"]["per_table"] if t["tabname"] == "T1")
    assert t1["total_rows"] == 1000
    assert t1["system_count"] == 2


def test_sizing_handles_empty_input():
    r = ce.calculate_sizing([])
    assert r["systems"] == {}
    assert r["largest_system"] is None
    assert r["consolidated"]["total_rows"] == 0


# ---------------------------------------------------------------------------
# Rule 2 — collisions
# ---------------------------------------------------------------------------

def test_collision_across_three_systems():
    r = ce.calculate_collisions(_six_system_org())

    assert r["collision_count"] == 1
    coll = r["collisions"][0]
    assert coll["from_id"] == "1000"
    assert coll["system_count"] == 3
    assert sorted(s["sidclnt"] for s in coll["systems"]) == \
        ["S01_100", "S02_100", "S03_100"]
    assert len(coll["distinct_texts"]) == 3


def test_safe_duplicate_is_not_a_collision():
    r = ce.calculate_collisions(_six_system_org())
    assert r["safe_duplicate_count"] == 1
    dup = r["safe_duplicates"][0]
    assert dup["from_id"] == "2000"
    assert len(dup["sidcltns"]) == 4


def test_collision_scope_is_bukrs_to_client_only():
    """BUKRS->COA and PLANT->CLIENT edges must not create phantom collisions."""
    r = ce.calculate_collisions(_six_system_org())
    assert {c["from_id"] for c in r["collisions"]} == {"1000"}
    # code 3000 appears in one system only -> neither list
    assert "3000" not in {c["from_id"] for c in r["collisions"]}
    assert "3000" not in {d["from_id"] for d in r["safe_duplicates"]}


def test_collision_ignores_case_and_whitespace_differences():
    org = [
        {"sidclnt": "A_100", "from_type": "BUKRS", "from_id": "1000",
         "to_type": "CLIENT", "from_text": "Acme  GmbH"},
        {"sidclnt": "B_100", "from_type": "BUKRS", "from_id": "1000",
         "to_type": "CLIENT", "from_text": "acme gmbh"},
    ]
    r = ce.calculate_collisions(org)
    assert r["collision_count"] == 0
    assert r["safe_duplicate_count"] == 1


def test_collision_blank_text_is_missing_data_not_a_collision():
    org = [
        {"sidclnt": "A_100", "from_type": "BUKRS", "from_id": "1000",
         "to_type": "CLIENT", "from_text": "Acme GmbH"},
        {"sidclnt": "B_100", "from_type": "BUKRS", "from_id": "1000",
         "to_type": "CLIENT", "from_text": ""},
    ]
    r = ce.calculate_collisions(org)
    assert r["collision_count"] == 0
    assert "1000" in r["codes_missing_text"]


# ---------------------------------------------------------------------------
# Rule 3 — number-range conflicts
# ---------------------------------------------------------------------------

def _nriv(sid, obj, rng, frm, to, lvl):
    return {"sidclnt": sid, "object": obj, "subobject": "", "nrrangenr": rng,
            "fromnumber": frm, "tonumber": to, "nrlevel": lvl}


def test_conflict_level_mismatch_only():
    rows = [
        _nriv("A_100", "RF_BELEG", "01", "0100000000", "0199999999", "0000000100"),
        _nriv("B_100", "RF_BELEG", "02", "0200000000", "0299999999", "0000000200"),
        # same key, non-overlapping ranges, different level
        _nriv("A_100", "OBJ_X", "01", "0000000001", "0000000100", "0000000050"),
        _nriv("B_100", "OBJ_X", "01", "0000000200", "0000000300", "0000000250"),
    ]
    r = ce.calculate_nriv_conflicts(rows)
    assert r["conflict_count"] == 1
    c = r["conflicts"][0]
    assert (c["object"], c["nrrangenr"], c["type"]) == ("OBJ_X", "01", "LEVEL_MISMATCH")


def test_conflict_range_overlap_only():
    rows = [
        _nriv("A_100", "OBJ_Y", "01", "0000000001", "0000000500", "0000000000"),
        _nriv("B_100", "OBJ_Y", "01", "0000000400", "0000000900", "0000000000"),
    ]
    r = ce.calculate_nriv_conflicts(rows)
    assert r["conflict_count"] == 1
    assert r["conflicts"][0]["type"] == "RANGE_OVERLAP"


def test_conflict_both():
    rows = [
        _nriv("A_100", "OBJ_Z", "01", "0000000001", "0000000500", "0000000010"),
        _nriv("B_100", "OBJ_Z", "01", "0000000400", "0000000900", "0000000020"),
    ]
    r = ce.calculate_nriv_conflicts(rows)
    assert r["conflicts"][0]["type"] == "BOTH"
    assert r["both_count"] == 1


def test_identical_intervals_in_two_systems_still_overlap():
    """Same range in two systems collides on merge — that is a conflict."""
    rows = [
        _nriv("A_100", "OBJ_Q", "01", "0000000001", "0000000500", "0000000000"),
        _nriv("B_100", "OBJ_Q", "01", "0000000001", "0000000500", "0000000000"),
    ]
    r = ce.calculate_nriv_conflicts(rows)
    assert r["conflict_count"] == 1
    assert r["conflicts"][0]["type"] == "RANGE_OVERLAP"


def test_single_system_key_is_never_a_conflict():
    rows = [
        _nriv("A_100", "OBJ_S", "01", "0000000001", "0000000500", "0000000010"),
        _nriv("A_100", "OBJ_S", "02", "0000000001", "0000000500", "0000000020"),
    ]
    assert ce.calculate_nriv_conflicts(rows)["conflict_count"] == 0


def test_conflict_grouping_key_is_object_plus_rangenr_not_subobject():
    rows = [
        {"sidclnt": "A_100", "object": "OBJ_R", "subobject": "AAA",
         "nrrangenr": "01", "fromnumber": "0000000001", "tonumber": "0000000500",
         "nrlevel": "0000000010"},
        {"sidclnt": "B_100", "object": "OBJ_R", "subobject": "BBB",
         "nrrangenr": "01", "fromnumber": "0000000001", "tonumber": "0000000500",
         "nrlevel": "0000000020"},
    ]
    # Differing subobject must not split the group.
    assert ce.calculate_nriv_conflicts(rows)["conflict_count"] == 1


def test_alphanumeric_bounds_do_not_crash_and_do_not_fake_overlap():
    rows = [
        _nriv("A_100", "OBJ_A", "01", "0000000001", "ZZZZZZZZZZ", "0000000000"),
        _nriv("B_100", "OBJ_A", "01", "0000000001", "ZZZZZZZZZZ", "0000000000"),
    ]
    r = ce.calculate_nriv_conflicts(rows)
    # Bounds are not comparable arithmetically and levels match -> no conflict
    # claimed, but the rows are counted as non-numeric for data-quality review.
    assert r["conflict_count"] == 0
    assert r["non_numeric_ranges"] == 2


# ---------------------------------------------------------------------------
# Rule 4 — growth
# ---------------------------------------------------------------------------

def test_growth_sums_across_systems_and_excludes_year_zero():
    rows = [
        {"sidclnt": "A_100", "tabname": "BKPF", "gjahr": 2023, "doc_count": 100},
        {"sidclnt": "B_100", "tabname": "BKPF", "gjahr": 2023, "doc_count": 150},
        {"sidclnt": "A_100", "tabname": "BKPF", "gjahr": 2024, "doc_count": 500},
        # year 0 is the extractor's "unassigned" bucket and must be dropped
        {"sidclnt": "A_100", "tabname": "BKPF", "gjahr": 0, "doc_count": 999999},
    ]
    r = ce.calculate_growth(rows)

    tbl = r["tables"][0]
    assert tbl["tabname"] == "BKPF"
    assert tbl["by_year"] == {"2023": 250, "2024": 500}
    assert tbl["total_docs"] == 750
    assert r["excluded_zero_year_rows"] == 1
    assert 0 not in r["years"]

    assert tbl["yoy"][0]["growth_pct"] == 100.0   # 250 -> 500


def test_growth_detects_missing_years():
    rows = [
        {"sidclnt": "A_100", "tabname": "T", "gjahr": 2020, "doc_count": 1},
        {"sidclnt": "A_100", "tabname": "T", "gjahr": 2022, "doc_count": 3},
    ]
    assert ce.calculate_growth(rows)["tables"][0]["missing_years"] == [2021]


def test_growth_zero_previous_year_yields_none_not_division_error():
    rows = [
        {"sidclnt": "A_100", "tabname": "T", "gjahr": 2020, "doc_count": 0},
        {"sidclnt": "A_100", "tabname": "T", "gjahr": 2021, "doc_count": 5},
    ]
    assert ce.calculate_growth(rows)["tables"][0]["yoy"][0]["growth_pct"] is None


# ---------------------------------------------------------------------------
# Rule 5 — system profiles
# ---------------------------------------------------------------------------

def test_system_profile_fields_and_heterogeneity():
    systems = [
        {"sidclnt": "A_100", "sid": "A", "db_sys": "HDB", "rel": "108",
         "sp_level": "0003", "unicode": "X", "addons": "X1,X2",
         "total_vol": 1000, "occupied_vol": 500},
        {"sidclnt": "B_100", "sid": "B", "db_sys": "SYBASE", "rel": "617",
         "sp_level": "0026", "unicode": "", "addons": "",
         "total_vol": 2000, "occupied_vol": 1800},
    ]
    r = ce.calculate_system_profiles(systems)

    a = r["systems"][0]
    assert (a["db_sys"], a["rel"], a["sp_level"], a["is_unicode"]) == \
        ("HDB", "108", "0003", True)
    assert a["addon_count"] == 2
    assert r["utilisation"]["A_100"] == 50.0
    assert r["utilisation"]["B_100"] == 90.0

    assert set(r["heterogeneity_flags"]) == {
        "MIXED_DATABASES", "MIXED_RELEASES", "MIXED_SP_LEVELS", "MIXED_UNICODE"
    }


def test_uniform_landscape_has_no_flags():
    systems = [
        {"sidclnt": "A_100", "db_sys": "HDB", "rel": "108", "sp_level": "0003",
         "unicode": "X", "total_vol": 100, "occupied_vol": 10},
        {"sidclnt": "B_100", "db_sys": "HDB", "rel": "108", "sp_level": "0003",
         "unicode": "X", "total_vol": 100, "occupied_vol": 20},
    ]
    assert ce.calculate_system_profiles(systems)["heterogeneity_flags"] == []


def test_zero_total_volume_gives_none_not_division_error():
    systems = [{"sidclnt": "A_100", "total_vol": 0, "occupied_vol": 0}]
    r = ce.calculate_system_profiles(systems)
    assert r["systems"][0]["utilisation_pct"] is None
    assert "A_100" not in r["utilisation"]


# ---------------------------------------------------------------------------
# Determinism and orchestration
# ---------------------------------------------------------------------------

def test_run_all_is_deterministic():
    sections = {"org": _six_system_org(), "master": [], "growth": [],
                "system": [], "nriv": []}
    first = json.dumps(ce.run_all(sections), sort_keys=True)
    second = json.dumps(ce.run_all(sections), sort_keys=True)
    assert first == second


def test_run_all_tolerates_missing_sections():
    r = ce.run_all({})
    assert set(r) == {"sizing", "collisions", "conflicts", "growth",
                      "system_profiles"}
    assert r["collisions"]["collision_count"] == 0


def test_results_are_json_serialisable():
    json.dumps(ce.run_all({"org": _six_system_org()}))


# ---------------------------------------------------------------------------
# Real sample extract (2-system RUN_02)
# ---------------------------------------------------------------------------

def test_sample_sizing(sample_sections):
    r = ce.calculate_sizing(sample_sections["master"], sample_sections["system"])
    assert sorted(r["systems"]) == ["ECQ_300", "RQ1_500"]
    # The extract has 90,310 master rows, 90,289 of them table-level.
    assert r["row_count_used"] == 90289
    # RQ1_500 is far larger and must be picked as the shell/target candidate.
    assert r["largest_system"]["sidclnt"] == "RQ1_500"
    assert r["largest_system"]["share_of_rows_pct"] > 90


def test_sample_collision(sample_sections):
    r = ce.calculate_collisions(sample_sections["org"])
    assert r["collision_count"] == 1
    coll = r["collisions"][0]
    assert coll["from_id"] == "0001"
    assert coll["system_count"] == 2
    assert len(coll["distinct_texts"]) == 2


def test_sample_conflicts(sample_sections):
    r = ce.calculate_nriv_conflicts(sample_sections["nriv"])
    assert r["conflict_count"] > 1
    assert r["level_mismatch_count"] + r["range_overlap_count"] + r["both_count"] \
        == r["conflict_count"]


def test_sample_growth_excludes_nothing_but_still_sums(sample_sections):
    r = ce.calculate_growth(sample_sections["growth"])
    assert 0 not in r["years"]
    assert r["total_docs"] > 0
    # Every table's by_year total must equal its reported total.
    for t in r["tables"]:
        assert sum(t["by_year"].values()) == t["total_docs"]


def test_sample_system_profiles(sample_sections):
    r = ce.calculate_system_profiles(
        sample_sections["system"], sample_sections["master"]
    )
    assert r["system_count"] == 2
    assert "MIXED_DATABASES" in r["heterogeneity_flags"]
    assert "MIXED_RELEASES" in r["heterogeneity_flags"]
