"""
Tests for DMLT deterministic calculation tools.
These tests verify that calc tools produce correct, deterministic output
from the sample JSON data without requiring any Python packages.
"""
import json
import sys
import os

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))

# Load sample data from extractor files
SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "extractor_files")


def load_sections() -> dict:
    sections = {}
    for name in ["master", "growth", "system", "org", "nriv"]:
        fpath = os.path.join(SAMPLE_DIR, f"RQ1RUN_02_{name}.json")
        if not os.path.exists(fpath):
            raise FileNotFoundError(f"Missing: {fpath}")
        with open(fpath) as f:
            raw = json.load(f)
        sections[name] = raw.get("data", raw) if isinstance(raw, dict) else raw
    return sections


def test_calc_sizing():
    from tools.calc_tools import _calc_sizing
    sections = load_sections()
    result_raw = _calc_sizing(json.dumps(sections))
    result = json.loads(result_raw)
    assert result["success"], f"calc_sizing failed: {result.get('error')}"
    r = result["result"]
    assert r["totalKB"] > 0
    assert "APPL" in r["categories"]
    assert r["tablesTotalCount"] == 90310
    print(f"✓ calc_sizing: totalGB={r['totalGB']:.2f}, APPL={r['categories']['APPL']['mb']:.0f}MB")


def test_calc_collisions():
    from tools.calc_tools import _calc_collisions
    sections = load_sections()
    result_raw = _calc_collisions(json.dumps(sections))
    result = json.loads(result_raw)
    assert result["success"], f"calc_collisions failed: {result.get('error')}"
    r = result["result"]
    assert r["totalCollisions"] >= 0
    # Known: BUKRS 0001 appears in both ECQ_300 and RQ1_500
    assert r["totalCollisions"] > 0, "Expected at least 1 BUKRS collision from known sample data"
    print(f"✓ calc_collisions: {r['totalCollisions']} collisions, {r['nameConflicts']} name conflicts")


def test_calc_nriv():
    from tools.calc_tools import _calc_nriv_conflicts
    sections = load_sections()
    result_raw = _calc_nriv_conflicts(json.dumps(sections))
    result = json.loads(result_raw)
    assert result["success"], f"calc_nriv failed: {result.get('error')}"
    r = result["result"]
    assert r["totalIntervals"] == 12416
    # Known: >1000 conflicts (sample data shows 2025)
    assert r["totalConflicts"] > 1000
    print(f"✓ calc_nriv: {r['totalConflicts']} conflicts from {r['totalIntervals']} intervals")


def test_calc_growth():
    from tools.calc_tools import _calc_growth
    sections = load_sections()
    result_raw = _calc_growth(json.dumps(sections))
    result = json.loads(result_raw)
    assert result["success"], f"calc_growth failed: {result.get('error')}"
    r = result["result"]
    assert r["totalRows"] == 250
    assert len(r["yearsAvailable"]) > 0
    print(f"✓ calc_growth: {r['totalRows']} rows, years: {r['yearsAvailable']}")


def test_calc_system_profiles():
    from tools.calc_tools import _calc_system_profiles
    sections = load_sections()
    result_raw = _calc_system_profiles(json.dumps(sections))
    result = json.loads(result_raw)
    assert result["success"], f"calc_system_profiles failed: {result.get('error')}"
    r = result["result"]
    assert r["systemCount"] == 2  # ECQ_300 and RQ1_500
    print(f"✓ calc_system_profiles: {r['systemCount']} systems — {r['releases']}")


def test_determinism():
    """Verify identical input produces identical output (10 runs)."""
    from tools.calc_tools import _calc_sizing
    sections = load_sections()
    sj = json.dumps(sections)
    results = [json.loads(_calc_sizing(sj))["result"]["totalKB"] for _ in range(10)]
    assert len(set(results)) == 1, "calc_sizing is not deterministic!"
    print(f"✓ determinism: 10 runs of calc_sizing all returned {results[0]:.2f} KB")


if __name__ == "__main__":
    print("Running DMLT calc tool tests...")
    tests = [
        test_calc_sizing,
        test_calc_collisions,
        test_calc_nriv,
        test_calc_growth,
        test_calc_system_profiles,
        test_determinism,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"✗ {t.__name__}: {e}")
            failed += 1

    if failed:
        print(f"\n{failed}/{len(tests)} tests FAILED")
        sys.exit(1)
    else:
        print(f"\nAll {len(tests)} tests PASSED")
