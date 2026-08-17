"""
Tests for the LangChain calculation tool wrappers (``app/tools/calc_tools.py``).

The rules themselves are covered by ``test_calc_engine.py``.  What is asserted
here is the wrapper contract the agent depends on:

  * a ``sections_json`` string goes in,
  * a JSON string of ``{"success": true, "result": {...}}`` comes out,
  * bad input is reported as ``{"success": false, "error": ...}`` rather than
    raising and aborting the run,
  * the five tools are registered with stable names.

These tests import ``calc_tools``, which needs ``langchain_core`` and
``pydantic``; they skip cleanly when the agent framework is not installed.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))
sys.path.insert(0, os.path.dirname(__file__))

calc_tools = pytest.importorskip(
    "app.tools.calc_tools",
    reason="agent framework (langchain_core / pydantic) not installed",
)

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "extractor_files")


def load_sections() -> dict:
    sections = {}
    for name in ["master", "growth", "system", "org", "nriv"]:
        path = os.path.join(SAMPLE_DIR, f"RQ1RUN_02_{name}.json")
        if not os.path.exists(path):
            pytest.skip(f"sample extract not available: {path}")
        with open(path) as fh:
            raw = json.load(fh)
        sections[name] = raw.get("data", raw) if isinstance(raw, dict) else raw
    return sections


@pytest.fixture(scope="module")
def sections_json():
    return json.dumps(load_sections())


def _ok(raw: str) -> dict:
    parsed = json.loads(raw)
    assert parsed["success"], parsed.get("error")
    return parsed["result"]


# ---------------------------------------------------------------------------
# Happy path — each wrapper returns the engine's result
# ---------------------------------------------------------------------------

def test_sizing_wrapper(sections_json):
    r = _ok(calc_tools._calc_sizing(sections_json))
    assert r["calculationType"] == "SIZING"
    assert sorted(r["systems"]) == ["ECQ_300", "RQ1_500"]
    assert r["largest_system"]["sidclnt"] == "RQ1_500"


def test_collisions_wrapper(sections_json):
    r = _ok(calc_tools._calc_collisions(sections_json))
    assert r["calculationType"] == "COMPANY_CODE_COLLISIONS"
    assert r["collision_count"] == 1


def test_nriv_wrapper(sections_json):
    r = _ok(calc_tools._calc_nriv_conflicts(sections_json))
    assert r["calculationType"] == "NUMBER_RANGE_CONFLICTS"
    assert r["total_intervals"] == 12416
    assert r["conflict_count"] > 1


def test_growth_wrapper(sections_json):
    r = _ok(calc_tools._calc_growth(sections_json))
    assert r["calculationType"] == "GROWTH"
    assert 0 not in r["years"]


def test_system_profiles_wrapper(sections_json):
    r = _ok(calc_tools._calc_system_profiles(sections_json))
    assert r["calculationType"] == "SYSTEM_PROFILES"
    assert r["system_count"] == 2


# ---------------------------------------------------------------------------
# Contract behaviour
# ---------------------------------------------------------------------------

def test_wrappers_report_bad_json_as_error_not_exception():
    parsed = json.loads(calc_tools._calc_sizing("{not json"))
    assert parsed["success"] is False
    assert parsed["error"]


def test_wrappers_reject_non_object_payload():
    parsed = json.loads(calc_tools._calc_sizing("[1, 2, 3]"))
    assert parsed["success"] is False


def test_wrappers_tolerate_missing_sections():
    r = _ok(calc_tools._calc_collisions("{}"))
    assert r["collision_count"] == 0


def test_determinism(sections_json):
    """Identical input must produce byte-identical output."""
    runs = {calc_tools._calc_sizing(sections_json) for _ in range(5)}
    assert len(runs) == 1


def test_tool_registry_names():
    names = [t.name for t in calc_tools.get_calc_tools()]
    assert names == [
        "calc_hardware_sizing",
        "calc_company_code_collisions",
        "calc_number_range_conflicts",
        "calc_growth_trends",
        "calc_system_profiles",
    ]
