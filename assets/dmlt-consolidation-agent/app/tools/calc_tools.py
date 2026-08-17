"""
Deterministic calculation tools for DMLT Consolidation analysis.

All calculations operate exclusively on in-memory JSON data (no live SAP connectivity).
Results are 100% deterministic: identical input → identical output.
"""
import json
import logging
from collections import defaultdict
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Schema helpers ────────────────────────────────────────────────────────────

class SectionsInput(BaseModel):
    sections_json: str = Field(
        description="JSON string with keys master, growth, system, org, nriv — each a list of records"
    )


# ── Tool 1: Hardware Sizing ───────────────────────────────────────────────────

def _calc_sizing(sections_json: str) -> str:
    """
    Calculate hardware sizing from master (table volumes) and system sections.

    Returns per-category size totals (APPL, CUST, USR, ARCH, others),
    system profile (DB, release, occupied/total GB), and compression estimate.
    """
    try:
        secs = json.loads(sections_json)
        master = secs.get("master", [])
        systems = secs.get("system", [])

        category_kb: dict[str, float] = defaultdict(float)
        category_rows: dict[str, int] = defaultdict(int)
        sidclnt_kb: dict[str, float] = defaultdict(float)

        for row in master:
            cat  = str(row.get("category") or "UNKNOWN").upper()
            kb   = float(row.get("tab_total_kb") or 0)
            sid  = str(row.get("sidclnt") or "")
            category_kb[cat]   += kb
            category_rows[cat] += int(row.get("clnt_count") or 0)
            sidclnt_kb[sid]    += kb

        total_kb    = sum(category_kb.values())
        total_mb    = total_kb / 1024
        total_gb    = total_mb / 1024

        sys_profiles = []
        for s in systems:
            sys_profiles.append({
                "sidclnt":      s.get("sidclnt", ""),
                "sid":          s.get("sid", ""),
                "db_sys":       s.get("db_sys", ""),
                "release":      s.get("rel", ""),
                "sp_level":     s.get("sp_level", ""),
                "unicode":      s.get("unicode", ""),
                "occupied_vol": float(s.get("occupied_vol") or 0),
                "total_vol":    float(s.get("total_vol") or 0),
            })

        result = {
            "calculationType": "HARDWARE_SIZING",
            "totalKB":         round(total_kb, 2),
            "totalMB":         round(total_mb, 2),
            "totalGB":         round(total_gb, 2),
            "categories": {
                cat: {
                    "kb":   round(kb, 2),
                    "mb":   round(kb / 1024, 2),
                    "pct":  round(kb / total_kb * 100, 2) if total_kb else 0,
                    "rows": category_rows[cat],
                }
                for cat, kb in sorted(category_kb.items(), key=lambda x: -x[1])
            },
            "sidcltns": {
                sid: {"kb": round(kb, 2), "mb": round(kb / 1024, 2)}
                for sid, kb in sorted(sidclnt_kb.items(), key=lambda x: -x[1])
            },
            "systemProfiles":  sys_profiles,
            "tablesTotalCount": len(master),
        }
        return json.dumps({"success": True, "result": result})
    except Exception as e:
        logger.exception("calc_sizing failed")
        return json.dumps({"success": False, "error": str(e)})


# ── Tool 2: Company-Code Collisions ──────────────────────────────────────────

def _calc_collisions(sections_json: str) -> str:
    """
    Detect BUKRS (company code) collisions across source systems.

    A collision occurs when the same BUKRS appears in multiple sidcltns
    with different company names — these will conflict during consolidation.
    """
    try:
        secs  = json.loads(sections_json)
        org   = secs.get("org", [])
        master = secs.get("master", [])

        # Build bukrs→{sidclnt→name} from master data (has bukrs + name context)
        # Also check org section for BUKRS edges
        bukrs_map: dict[str, dict[str, str]] = defaultdict(dict)

        # From org: from_type==BUKRS gives us bukrs ids
        for row in org:
            if str(row.get("from_type", "")).upper() == "BUKRS":
                bukrs    = str(row.get("from_id", "")).strip()
                sidclnt  = str(row.get("sidclnt", ""))
                txt      = str(row.get("from_text", ""))
                if bukrs:
                    if sidclnt not in bukrs_map[bukrs]:
                        bukrs_map[bukrs][sidclnt] = txt

        # Detect collisions: same bukrs in >1 sidclnt
        collisions = []
        for bukrs, sys_map in sorted(bukrs_map.items()):
            if len(sys_map) > 1:
                # Check if names differ
                names = list(sys_map.values())
                unique_names = set(n.strip().upper() for n in names if n)
                collisions.append({
                    "bukrs":      bukrs,
                    "systems":    sys_map,
                    "nameConflict": len(unique_names) > 1,
                    "names":      list(sys_map.values()),
                })

        name_conflicts = [c for c in collisions if c["nameConflict"]]

        result = {
            "calculationType":    "COMPANY_CODE_COLLISIONS",
            "totalBukrs":         len(bukrs_map),
            "totalCollisions":    len(collisions),
            "nameConflicts":      len(name_conflicts),
            "collisions":         collisions[:500],  # cap for payload size
            "summary": (
                f"{len(collisions)} BUKRS collisions detected across "
                f"{len({sid for sys_map in bukrs_map.values() for sid in sys_map})} systems, "
                f"{len(name_conflicts)} with different company names"
            ),
        }
        return json.dumps({"success": True, "result": result})
    except Exception as e:
        logger.exception("calc_collisions failed")
        return json.dumps({"success": False, "error": str(e)})


# ── Tool 3: Number-Range Conflicts ───────────────────────────────────────────

def _calc_nriv_conflicts(sections_json: str) -> str:
    """
    Detect number-range interval conflicts across source systems.

    A conflict occurs when the same object+subobject+nrrangenr combination
    appears in multiple sidcltns with overlapping or incompatible intervals.
    """
    try:
        secs = json.loads(sections_json)
        nriv = secs.get("nriv", [])

        # Group by (object, subobject, nrrangenr)
        key_map: dict[tuple, list[dict]] = defaultdict(list)
        for row in nriv:
            key = (
                str(row.get("object", "")),
                str(row.get("subobject", "")),
                str(row.get("nrrangenr", "")),
            )
            key_map[key].append(row)

        conflicts = []
        for (obj, subobj, rng), rows in key_map.items():
            # Conflict = same key from >1 sidclnt
            sidcltns_seen = {str(r.get("sidclnt", "")) for r in rows}
            if len(sidcltns_seen) > 1:
                # Check for level overlap (nrlevel = current pointer, tonumber = max)
                max_levels = {r.get("sidclnt", ""): int(r.get("nrlevel") or 0) for r in rows}
                from_nums  = {r.get("sidclnt", ""): str(r.get("fromnumber", "")) for r in rows}
                to_nums    = {r.get("sidclnt", ""): str(r.get("tonumber", ""))   for r in rows}
                conflicts.append({
                    "object":    obj,
                    "subobject": subobj,
                    "nrrangenr": rng,
                    "sidcltns":  list(sidcltns_seen),
                    "nrlevels":  max_levels,
                    "fromnumbers": from_nums,
                    "tonumbers": to_nums,
                    "levelConflict": len(set(max_levels.values())) > 1,
                })

        level_conflicts = [c for c in conflicts if c["levelConflict"]]

        result = {
            "calculationType":    "NUMBER_RANGE_CONFLICTS",
            "totalIntervals":     len(nriv),
            "uniqueKeys":         len(key_map),
            "totalConflicts":     len(conflicts),
            "levelConflicts":     len(level_conflicts),
            "conflicts":          conflicts[:1000],  # cap payload
            "summary": (
                f"{len(conflicts)} number-range conflicts detected from {len(nriv)} intervals, "
                f"{len(level_conflicts)} with current-level discrepancies"
            ),
        }
        return json.dumps({"success": True, "result": result})
    except Exception as e:
        logger.exception("calc_nriv_conflicts failed")
        return json.dumps({"success": False, "error": str(e)})


# ── Tool 4: Growth Trends ────────────────────────────────────────────────────

def _calc_growth(sections_json: str) -> str:
    """
    Analyse year-on-year document growth from the growth section.

    Returns per-table, per-sidclnt growth trajectories and CAGR estimates.
    """
    try:
        secs   = json.loads(sections_json)
        growth = secs.get("growth", [])

        # Group by (sidclnt, tabname) → sorted list of {gjahr, count}
        tbl_map: dict[tuple, dict[int, int]] = defaultdict(lambda: defaultdict(int))
        for row in growth:
            sid   = str(row.get("sidclnt", ""))
            tbl   = str(row.get("tabname", ""))
            yr    = int(row.get("gjahr") or 0)
            cnt   = int(row.get("doc_count") or 0)
            tbl_map[(sid, tbl)][yr] += cnt

        # Aggregate total per year across all tables
        year_totals: dict[int, int] = defaultdict(int)
        for year_data in tbl_map.values():
            for yr, cnt in year_data.items():
                year_totals[yr] += cnt

        sorted_years = sorted(y for y in year_totals if y > 0)
        yoy_growth: list[dict] = []
        for i in range(1, len(sorted_years)):
            prev = year_totals[sorted_years[i - 1]]
            curr = year_totals[sorted_years[i]]
            pct  = ((curr - prev) / prev * 100) if prev else None
            yoy_growth.append({
                "fromYear": sorted_years[i - 1],
                "toYear":   sorted_years[i],
                "fromCount": prev,
                "toCount":   curr,
                "growthPct": round(pct, 2) if pct is not None else None,
            })

        # Top growing tables
        top_tables = []
        for (sid, tbl), year_data in tbl_map.items():
            yrs = sorted(year_data.keys())
            if len(yrs) >= 2:
                first, last = year_data[yrs[0]], year_data[yrs[-1]]
                n = yrs[-1] - yrs[0]
                cagr = (((last / first) ** (1 / n) - 1) * 100) if first and n else None
                top_tables.append({
                    "sidclnt": sid, "tabname": tbl,
                    "firstYear": yrs[0], "lastYear": yrs[-1],
                    "firstCount": first, "lastCount": last,
                    "cagr": round(cagr, 2) if cagr is not None else None,
                })

        top_tables.sort(key=lambda x: x.get("lastCount", 0), reverse=True)

        result = {
            "calculationType": "GROWTH_TRENDS",
            "yearTotals":      {str(yr): cnt for yr, cnt in sorted(year_totals.items())},
            "yoyGrowth":       yoy_growth,
            "topGrowingTables": top_tables[:50],
            "yearsAvailable":  sorted_years,
            "totalRows":       len(growth),
        }
        return json.dumps({"success": True, "result": result})
    except Exception as e:
        logger.exception("calc_growth failed")
        return json.dumps({"success": False, "error": str(e)})


# ── Tool 5: System Profiles ───────────────────────────────────────────────────

def _calc_system_profiles(sections_json: str) -> str:
    """
    Summarise system profiles: DB type, SAP release, unicode status, addon list.

    Identifies version discrepancies and upgrade requirements for consolidation.
    """
    try:
        secs    = json.loads(sections_json)
        systems = secs.get("system", [])
        master  = secs.get("master", [])

        profiles = []
        for s in systems:
            sid    = str(s.get("sidclnt", ""))
            kb_sum = sum(float(r.get("tab_total_kb") or 0)
                         for r in master if str(r.get("sidclnt", "")) == sid)
            profiles.append({
                "sidclnt":      sid,
                "sid":          s.get("sid", ""),
                "dbSystem":     s.get("db_sys", ""),
                "release":      s.get("rel", ""),
                "spLevel":      s.get("sp_level", ""),
                "unicode":      s.get("unicode", "") == "X",
                "addons":       str(s.get("addons", "") or "").split(","),
                "occupiedVolGB": round(float(s.get("occupied_vol") or 0) / 1024 / 1024, 2),
                "totalVolGB":   round(float(s.get("total_vol") or 0) / 1024 / 1024, 2),
                "dataKB":       round(kb_sum, 2),
                "dataMB":       round(kb_sum / 1024, 2),
            })

        # Check release uniformity
        releases   = list({p["release"] for p in profiles})
        db_systems = list({p["dbSystem"] for p in profiles})

        result = {
            "calculationType": "SYSTEM_PROFILES",
            "profiles":        profiles,
            "releases":        releases,
            "dbSystems":       db_systems,
            "releaseMismatch": len(releases) > 1,
            "dbMismatch":      len(db_systems) > 1,
            "allUnicode":      all(p["unicode"] for p in profiles),
            "systemCount":     len(profiles),
            "summary": (
                f"{len(profiles)} systems — releases: {', '.join(releases)} — "
                f"DB: {', '.join(db_systems)}"
            ),
        }
        return json.dumps({"success": True, "result": result})
    except Exception as e:
        logger.exception("calc_system_profiles failed")
        return json.dumps({"success": False, "error": str(e)})


# ── Tool registry ─────────────────────────────────────────────────────────────

def get_calc_tools() -> list[StructuredTool]:
    return [
        StructuredTool(
            name="calc_hardware_sizing",
            description=(
                "Calculate hardware sizing from table volumes. "
                "Returns per-category totals (APPL, CUST, USR, ARCH), "
                "system profiles, and overall MB/GB. "
                "Input: sections_json with master and system arrays."
            ),
            args_schema=SectionsInput,
            func=_calc_sizing,
            handle_tool_error=True,
        ),
        StructuredTool(
            name="calc_company_code_collisions",
            description=(
                "Detect BUKRS (company code) collisions across source systems. "
                "Returns collision list with name conflicts flagged. "
                "Input: sections_json with org array."
            ),
            args_schema=SectionsInput,
            func=_calc_collisions,
            handle_tool_error=True,
        ),
        StructuredTool(
            name="calc_number_range_conflicts",
            description=(
                "Detect number-range interval conflicts across source systems. "
                "Returns conflicts by object/subobject/nrrangenr. "
                "Input: sections_json with nriv array."
            ),
            args_schema=SectionsInput,
            func=_calc_nriv_conflicts,
            handle_tool_error=True,
        ),
        StructuredTool(
            name="calc_growth_trends",
            description=(
                "Analyse year-on-year document growth trends. "
                "Returns year totals, YoY growth %, CAGR per table. "
                "Input: sections_json with growth array."
            ),
            args_schema=SectionsInput,
            func=_calc_growth,
            handle_tool_error=True,
        ),
        StructuredTool(
            name="calc_system_profiles",
            description=(
                "Summarise system profiles (DB type, release, unicode, addons, volumes). "
                "Flags release/DB mismatches. "
                "Input: sections_json with system and master arrays."
            ),
            args_schema=SectionsInput,
            func=_calc_system_profiles,
            handle_tool_error=True,
        ),
    ]
