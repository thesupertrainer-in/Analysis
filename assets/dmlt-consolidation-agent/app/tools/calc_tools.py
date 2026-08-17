"""
LangChain tool wrappers around the deterministic calculation engine.

This module deliberately contains **no calculation logic**.  Every rule lives
in ``app/calc_engine.py`` — a self-contained, stdlib-only module.  Everything
here does is:

  * accept the agent's ``sections_json`` string argument,
  * hand the parsed section arrays to the engine,
  * serialise the engine's result back as ``{"success": bool, "result": {...}}``.

Keeping the split means the calculation internals can be reworked without
touching the agent wiring, the CAP backend, or the UI.
"""
import json
import logging

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

try:                                     # normal package import (PYTHONPATH=/app)
    from app import calc_engine
except ImportError:                      # direct/relative execution fallback
    from .. import calc_engine

logger = logging.getLogger(__name__)


# ── Schema ────────────────────────────────────────────────────────────────────

class SectionsInput(BaseModel):
    sections_json: str = Field(
        description=(
            "JSON string with keys master, growth, system, org, nriv — "
            "each a list of extract records"
        )
    )


# ── Wrapper plumbing ──────────────────────────────────────────────────────────

def _sections(sections_json: str) -> dict:
    """Parse the tool argument into a ``{section: [rows]}`` mapping."""
    parsed = json.loads(sections_json) or {}
    if not isinstance(parsed, dict):
        raise ValueError("sections_json must decode to a JSON object")
    return parsed


def _wrap(name: str, fn):
    """
    Build a tool function that runs ``fn(sections)`` and serialises the result.

    Failures are returned as ``{"success": false, "error": ...}`` rather than
    raised, so a single bad section cannot abort the whole agent run.
    """
    def _run(sections_json: str) -> str:
        try:
            result = fn(_sections(sections_json))
            return json.dumps({"success": True, "result": result})
        except Exception as exc:                     # noqa: BLE001 — reported to agent
            logger.exception("%s failed", name)
            return json.dumps({"success": False, "error": str(exc)})

    _run.__name__ = name
    return _run


_calc_sizing = _wrap(
    "calc_sizing",
    lambda s: calc_engine.calculate_sizing(s.get("master") or [], s.get("system") or []),
)

_calc_collisions = _wrap(
    "calc_collisions",
    lambda s: calc_engine.calculate_collisions(s.get("org") or []),
)

_calc_nriv_conflicts = _wrap(
    "calc_nriv_conflicts",
    lambda s: calc_engine.calculate_nriv_conflicts(s.get("nriv") or []),
)

_calc_growth = _wrap(
    "calc_growth",
    lambda s: calc_engine.calculate_growth(s.get("growth") or []),
)

_calc_system_profiles = _wrap(
    "calc_system_profiles",
    lambda s: calc_engine.calculate_system_profiles(
        s.get("system") or [], s.get("master") or []
    ),
)


# ── Tool registry ─────────────────────────────────────────────────────────────

def get_calc_tools() -> list[StructuredTool]:
    return [
        StructuredTool(
            name="calc_hardware_sizing",
            description=(
                "Calculate table-volume sizing. Returns per-system total rows and KB, "
                "top-10 tables by rows and by size, per-category totals, the "
                "consolidated target totals, and the largest source system. "
                "Uses agg_level='T' rows only. "
                "Input: sections_json with master and system arrays."
            ),
            args_schema=SectionsInput,
            func=_calc_sizing,
            handle_tool_error=True,
        ),
        StructuredTool(
            name="calc_company_code_collisions",
            description=(
                "Detect company-code (BUKRS) collisions across source systems. "
                "Scope is org rows with from_type='BUKRS' and to_type='CLIENT', "
                "grouped by from_id; a collision is the same code in more than one "
                "system under a different from_text. Same code + same text is "
                "reported as a safe duplicate. "
                "Input: sections_json with org array."
            ),
            args_schema=SectionsInput,
            func=_calc_collisions,
            handle_tool_error=True,
        ),
        StructuredTool(
            name="calc_number_range_conflicts",
            description=(
                "Detect number-range conflicts across source systems. Groups nriv by "
                "object+nrrangenr; a conflict is the same key in more than one system "
                "with a different nrlevel or with overlapping fromnumber-tonumber "
                "intervals. Tagged LEVEL_MISMATCH, RANGE_OVERLAP or BOTH. "
                "Input: sections_json with nriv array."
            ),
            args_schema=SectionsInput,
            func=_calc_nriv_conflicts,
            handle_tool_error=True,
        ),
        StructuredTool(
            name="calc_growth_trends",
            description=(
                "Aggregate document growth: doc_count per table per fiscal year summed "
                "across all systems, excluding gjahr=0. Returns per-table year series, "
                "year-on-year growth rates, missing-year gaps and per-system detail. "
                "Input: sections_json with growth array."
            ),
            args_schema=SectionsInput,
            func=_calc_growth,
            handle_tool_error=True,
        ),
        StructuredTool(
            name="calc_system_profiles",
            description=(
                "Summarise each system's database, release, SP level and unicode flag, "
                "plus addons, volumes and utilisation. Flags landscape heterogeneity "
                "(MIXED_DATABASES, MIXED_RELEASES, MIXED_SP_LEVELS, MIXED_UNICODE). "
                "Input: sections_json with system and master arrays."
            ),
            args_schema=SectionsInput,
            func=_calc_system_profiles,
            handle_tool_error=True,
        ),
    ]
