"""
AI analysis tools — applied on top of confirmed deterministic results.

These tools generate natural-language findings, risk assessments, and
consolidation recommendations by reasoning over calc_tool outputs.
They never fabricate data; all findings are grounded in the provided JSON.
"""
import json
import logging
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CalcResultInput(BaseModel):
    calc_result_json: str = Field(
        description="JSON string of a deterministic calc_tool result (the 'result' object)"
    )


class MultiCalcInput(BaseModel):
    all_results_json: str = Field(
        description="JSON string with keys sizing, collisions, nriv, growth, systems — each a calc result object"
    )


# ── AI Tool 1: Sizing Analysis ────────────────────────────────────────────────

def _analyse_sizing(calc_result_json: str) -> str:
    """
    Generate AI findings and consolidation recommendations for hardware sizing.
    """
    try:
        r = json.loads(calc_result_json)
        total_gb = r.get("totalGB", 0)
        cats     = r.get("categories", {})
        profiles = r.get("systemProfiles", [])

        findings = []

        # Volume assessment
        if total_gb > 10000:
            findings.append({
                "severity": "HIGH",
                "finding":  f"Very large consolidated volume: {total_gb:.0f} GB. "
                            "HANA in-memory storage and hardware sizing must be carefully planned.",
            })
        elif total_gb > 2000:
            findings.append({
                "severity": "MEDIUM",
                "finding":  f"Significant consolidated volume: {total_gb:.0f} GB. "
                            "Assess HANA Cloud capacity tiers.",
            })

        # APPL category (application data — largest category)
        appl = cats.get("APPL", {})
        if appl:
            pct = appl.get("pct", 0)
            findings.append({
                "severity": "INFO",
                "finding":  f"Application data (APPL) represents {pct:.1f}% of total volume "
                            f"({appl.get('mb', 0):.0f} MB). "
                            "This is the primary driver for consolidation sizing.",
            })

        # System version uniformity
        releases = list({p.get("release") for p in profiles if p.get("release")})
        if len(releases) > 1:
            findings.append({
                "severity": "HIGH",
                "finding":  f"Systems run different SAP releases: {', '.join(sorted(releases))}. "
                            "Release harmonization is required before consolidation.",
            })

        # DB type
        dbs = list({p.get("db_sys") for p in profiles if p.get("db_sys")})
        if "HDB" not in dbs:
            findings.append({
                "severity": "HIGH",
                "finding":  f"Source DB types include non-HANA: {', '.join(dbs)}. "
                            "HANA migration is a prerequisite.",
            })

        # Unicode
        non_unicode = [p for p in profiles if not p.get("unicode")]
        if non_unicode:
            findings.append({
                "severity": "HIGH",
                "finding":  f"{len(non_unicode)} non-unicode system(s): "
                            f"{', '.join(p['sidclnt'] for p in non_unicode)}. "
                            "Unicode conversion needed before consolidation.",
            })

        return json.dumps({
            "section":   "SIZING_ANALYSIS",
            "findings":  findings,
            "totalGB":   total_gb,
            "riskLevel": _max_risk(findings),
        })
    except Exception as e:
        logger.exception("analyse_sizing failed")
        return json.dumps({"section": "SIZING_ANALYSIS", "error": str(e), "findings": []})


# ── AI Tool 2: Collision Analysis ─────────────────────────────────────────────

def _analyse_collisions(calc_result_json: str) -> str:
    """
    Generate AI findings for company-code collision risks.
    """
    try:
        r = json.loads(calc_result_json)
        total      = r.get("totalCollisions", 0)
        name_conf  = r.get("nameConflicts", 0)
        collisions = r.get("collisions", [])

        findings = []

        if name_conf > 0:
            # Extract the conflicting BUKRS examples
            examples = [c["bukrs"] for c in collisions if c.get("nameConflict")][:5]
            findings.append({
                "severity": "CRITICAL",
                "finding":  f"{name_conf} company code(s) have conflicting names across systems "
                            f"(e.g. {', '.join(examples)}). "
                            "These require manual resolution before consolidation: "
                            "one BUKRS cannot represent two different legal entities.",
            })

        if total > 0 and name_conf == 0:
            findings.append({
                "severity": "MEDIUM",
                "finding":  f"{total} BUKRS appear in multiple systems with consistent names. "
                            "Verify consolidation mapping: same BUKRS may be intentionally shared "
                            "or may require remapping.",
            })

        if total == 0:
            findings.append({
                "severity": "INFO",
                "finding":  "No BUKRS collisions detected. Company code namespace is clean.",
            })

        return json.dumps({
            "section":        "COLLISION_ANALYSIS",
            "findings":       findings,
            "totalCollisions": total,
            "nameConflicts":  name_conf,
            "riskLevel":      _max_risk(findings),
        })
    except Exception as e:
        logger.exception("analyse_collisions failed")
        return json.dumps({"section": "COLLISION_ANALYSIS", "error": str(e), "findings": []})


# ── AI Tool 3: Number-Range Analysis ──────────────────────────────────────────

def _analyse_nriv(calc_result_json: str) -> str:
    """
    Generate AI findings for number-range conflict resolution strategy.
    """
    try:
        r = json.loads(calc_result_json)
        total       = r.get("totalConflicts", 0)
        level_conf  = r.get("levelConflicts", 0)
        conflicts   = r.get("conflicts", [])

        findings = []

        if level_conf > 0:
            top_obj = list({c["object"] for c in conflicts if c.get("levelConflict")})[:5]
            findings.append({
                "severity": "CRITICAL",
                "finding":  f"{level_conf} number-range conflicts have diverged current counters "
                            f"(nrlevel). Objects include: {', '.join(top_obj)}. "
                            "These WILL produce duplicate document numbers post-consolidation "
                            "if not resolved by range extension or external numbering.",
            })

        if total > level_conf > 0:
            findings.append({
                "severity": "HIGH",
                "finding":  f"{total - level_conf} additional number-range objects share the same "
                            "key but have consistent counters. Still require range harmonization.",
            })

        if total == 0:
            findings.append({
                "severity": "INFO",
                "finding":  "No number-range conflicts detected.",
            })

        return json.dumps({
            "section":       "NRIV_ANALYSIS",
            "findings":      findings,
            "totalConflicts": total,
            "levelConflicts": level_conf,
            "riskLevel":     _max_risk(findings),
        })
    except Exception as e:
        logger.exception("analyse_nriv failed")
        return json.dumps({"section": "NRIV_ANALYSIS", "error": str(e), "findings": []})


# ── AI Tool 4: Growth Analysis ────────────────────────────────────────────────

def _analyse_growth(calc_result_json: str) -> str:
    """
    Generate AI findings for data growth trajectory and future capacity planning.
    """
    try:
        r    = json.loads(calc_result_json)
        yoy  = r.get("yoyGrowth", [])
        tops = r.get("topGrowingTables", [])

        findings = []

        if yoy:
            avg_growth = sum(y["growthPct"] for y in yoy if y.get("growthPct") is not None)
            n = sum(1 for y in yoy if y.get("growthPct") is not None)
            avg_growth = avg_growth / n if n else 0

            if avg_growth > 15:
                findings.append({
                    "severity": "HIGH",
                    "finding":  f"Average YoY document growth is {avg_growth:.1f}%. "
                                "Post-consolidation capacity plan must account for accelerated growth.",
                })
            elif avg_growth > 5:
                findings.append({
                    "severity": "MEDIUM",
                    "finding":  f"Moderate average YoY growth: {avg_growth:.1f}%. "
                                "Include 3-year growth buffer in HANA sizing.",
                })

        if tops:
            hot_tables = [t for t in tops if t.get("cagr") and t["cagr"] > 20][:3]
            if hot_tables:
                names = [f"{t['tabname']} ({t['cagr']:.0f}% CAGR)" for t in hot_tables]
                findings.append({
                    "severity": "MEDIUM",
                    "finding":  f"High-growth tables: {', '.join(names)}. "
                                "Consider data archiving strategy for these objects.",
                })

        return json.dumps({
            "section":  "GROWTH_ANALYSIS",
            "findings": findings,
            "riskLevel": _max_risk(findings),
        })
    except Exception as e:
        logger.exception("analyse_growth failed")
        return json.dumps({"section": "GROWTH_ANALYSIS", "error": str(e), "findings": []})


# ── AI Tool 5: Executive Summary ──────────────────────────────────────────────

def _generate_executive_summary(all_results_json: str) -> str:
    """
    Generate an executive summary consolidating all analysis findings into
    a risk-ranked consolidation roadmap.
    """
    try:
        all_res  = json.loads(all_results_json)
        sizing   = all_res.get("sizing", {})
        colls    = all_res.get("collisions", {})
        nriv     = all_res.get("nriv", {})
        growth   = all_res.get("growth", {})
        systems  = all_res.get("systems", {})

        total_gb       = sizing.get("totalGB", 0)
        sys_count      = systems.get("systemCount", len(sizing.get("systemProfiles", [])))
        name_conflicts = colls.get("nameConflicts", 0)
        nriv_crit      = nriv.get("levelConflicts", 0)
        release_mm     = systems.get("releaseMismatch", False)
        unicode_issue  = not systems.get("allUnicode", True)

        risks = []
        if name_conflicts > 0:
            risks.append(f"CRITICAL: {name_conflicts} BUKRS name conflicts requiring manual resolution")
        if nriv_crit > 0:
            risks.append(f"CRITICAL: {nriv_crit} number-range level conflicts (duplicate document risk)")
        if release_mm:
            risks.append("HIGH: SAP release mismatch — harmonization required")
        if unicode_issue:
            risks.append("HIGH: Non-unicode system(s) — unicode conversion required")

        prereqs = []
        if release_mm:
            prereqs.append("1. Align SAP releases across all source systems")
        if unicode_issue:
            prereqs.append("2. Unicode conversion for non-unicode systems")
        if name_conflicts > 0:
            prereqs.append("3. Resolve BUKRS name conflicts via consolidation mapping")
        if nriv_crit > 0:
            prereqs.append("4. Number-range harmonization / external numbering setup")

        overall_risk = "CRITICAL" if (name_conflicts > 0 or nriv_crit > 0) else (
            "HIGH" if (release_mm or unicode_issue) else "MEDIUM"
        )

        summary = {
            "executiveSummary": {
                "systemsAnalyzed": sys_count,
                "totalDataGB":     round(total_gb, 1),
                "overallRisk":     overall_risk,
                "criticalIssues":  [r for r in risks if r.startswith("CRITICAL")],
                "highIssues":      [r for r in risks if r.startswith("HIGH")],
                "prerequisites":   prereqs,
                "recommendation": (
                    "Consolidation is technically feasible but requires resolution of critical "
                    "blocking issues before Go-Live. Engage SAP consolidation team for BUKRS "
                    "and number-range remediation."
                    if overall_risk == "CRITICAL" else
                    "Consolidation is feasible after completing the listed prerequisites. "
                    "Plan for a minimum 6-month preparation phase."
                    if overall_risk == "HIGH" else
                    "Consolidation prerequisites are largely met. "
                    "Proceed with detailed technical planning."
                ),
            }
        }
        return json.dumps({"section": "EXECUTIVE_SUMMARY", "findings": [summary]})
    except Exception as e:
        logger.exception("generate_executive_summary failed")
        return json.dumps({
            "section": "EXECUTIVE_SUMMARY", "error": str(e), "findings": []
        })


# ── Helpers ───────────────────────────────────────────────────────────────────

_RISK_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "INFO": 0}

def _max_risk(findings: list[dict]) -> str:
    if not findings:
        return "INFO"
    return max(
        (f.get("severity", "INFO") for f in findings),
        key=lambda s: _RISK_ORDER.get(s, 0),
        default="INFO",
    )


# ── Tool registry ─────────────────────────────────────────────────────────────

def get_ai_analysis_tools() -> list[StructuredTool]:
    return [
        StructuredTool(
            name="analyse_sizing",
            description=(
                "Generate AI findings and recommendations for hardware sizing results. "
                "Input: calc_result_json from calc_hardware_sizing."
            ),
            args_schema=CalcResultInput,
            func=_analyse_sizing,
            handle_tool_error=True,
        ),
        StructuredTool(
            name="analyse_collisions",
            description=(
                "Generate AI findings for company-code collision risks. "
                "Input: calc_result_json from calc_company_code_collisions."
            ),
            args_schema=CalcResultInput,
            func=_analyse_collisions,
            handle_tool_error=True,
        ),
        StructuredTool(
            name="analyse_nriv",
            description=(
                "Generate AI findings for number-range conflict resolution. "
                "Input: calc_result_json from calc_number_range_conflicts."
            ),
            args_schema=CalcResultInput,
            func=_analyse_nriv,
            handle_tool_error=True,
        ),
        StructuredTool(
            name="analyse_growth",
            description=(
                "Generate AI findings for data growth trajectory and capacity planning. "
                "Input: calc_result_json from calc_growth_trends."
            ),
            args_schema=CalcResultInput,
            func=_analyse_growth,
            handle_tool_error=True,
        ),
        StructuredTool(
            name="generate_executive_summary",
            description=(
                "Generate a consolidated executive summary with risk ranking and roadmap. "
                "Input: all_results_json with keys sizing, collisions, nriv, growth, systems — "
                "each the 'result' object from the respective calc tool."
            ),
            args_schema=MultiCalcInput,
            func=_generate_executive_summary,
            handle_tool_error=True,
        ),
    ]
