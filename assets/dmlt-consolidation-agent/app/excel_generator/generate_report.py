"""
DMLT Consolidation Study — Excel Report Generator
==================================================

Usage (standalone):
    python generate_report.py \\
        --master  path/to/master.json \\
        --growth  path/to/growth.json \\
        --system  path/to/system.json \\
        --org     path/to/org.json \\
        --nriv    path/to/nriv.json \\
        --out     output/report.xlsx

The script is engagement-agnostic: it discovers sidclnt values, categories,
years, and system counts from the data — nothing is hardcoded.

Principles:
  - Deterministic collision / conflict detection in Python (data rows only).
  - All downstream calculations (sizing, HANA target, summaries) are Excel
    formulas — never Python-computed literals written to cells.
  - The workbook recalculates correctly when a user edits Include? in MAIN.
"""

import argparse
import json
import os
import sys

# ── make local sheets/ package importable regardless of CWD ─────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import openpyxl

from dmlt_calc import detect_collisions, detect_conflicts   # shared calculation engine

from sheets.cover          import build as build_cover
from sheets.systems        import build as build_systems
from sheets.main_sheet     import build as build_main
from sheets.collisions     import build as build_collisions
from sheets.conflicts      import build as build_conflicts
from sheets.growth         import build as build_growth
from sheets.hardware_sizing import build as build_hardware_sizing
from sheets.summary        import build as build_summary
from sheets.dashboard      import build as build_dashboard


# ---------------------------------------------------------------------------
# JSON loading helpers
# ---------------------------------------------------------------------------

def _load_section(path: str, expected_section: str) -> list:
    """Load a single-section JSON file and return its data array."""
    with open(path, "r", encoding="utf-8") as fh:
        doc = json.load(fh)

    section = doc.get("section", "")
    if section and section.lower() != expected_section.lower():
        print(
            f"[WARN] File {path!r}: section={section!r}, "
            f"expected {expected_section!r} — proceeding anyway."
        )

    data = doc.get("data", [])
    if not isinstance(data, list):
        raise ValueError(
            f"File {path!r}: 'data' field must be a JSON array, "
            f"got {type(data).__name__}."
        )
    return data


def load_sections(paths: dict) -> dict:
    """
    paths = { "master": "...", "growth": "...", "system": "...",
              "org": "...", "nriv": "..." }
    Returns the same dict with list values instead of path strings.
    """
    return {sec: _load_section(p, sec) for sec, p in paths.items()}


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_report(sections: dict, out_path: str) -> str:
    """
    Build the 9-sheet DMLT workbook from the five section data arrays.

    Parameters
    ----------
    sections : dict
        Keys: master, growth, system, org, nriv — each a list of row dicts.
    out_path : str
        Destination .xlsx file path (parent directory must exist or will
        be created).

    Returns
    -------
    str — absolute path of the written .xlsx file.
    """
    master_data  = sections["master"]
    growth_data  = sections["growth"]
    system_data  = sections["system"]
    org_data     = sections["org"]
    nriv_data    = sections["nriv"]

    # Derived metadata
    sidcltns = sorted({r["sidclnt"] for r in system_data})
    categories = sorted({
        r.get("category", "") or ""
        for r in master_data
        if r.get("agg_level") == "T" and r.get("category")
    })

    run_meta = {
        "sidcltns":           sidcltns,
        "num_source_systems": len(sidcltns),
    }

    # Pre-compute collisions and conflicts for SUMMARY / DASHBOARD
    collisions = detect_collisions(org_data)
    conflicts  = detect_conflicts(nriv_data)

    # ── Create workbook ────────────────────────────────────────────────────
    # We use standard (non-write_only) mode so all sheets can be
    # styled and cross-referenced.  The MAIN sheet uses an optimised
    # bulk-append path internally.
    wb = openpyxl.Workbook()

    # Remove the default sheet
    default_ws = wb.active
    wb.remove(default_ws)

    # ── Sheet 1: COVER ─────────────────────────────────────────────────────
    ws_cover = wb.create_sheet("COVER")
    cover_refs = build_cover(ws_cover, run_meta)

    # ── Sheet 2: SYSTEMS ───────────────────────────────────────────────────
    ws_systems = wb.create_sheet("SYSTEMS")
    build_systems(ws_systems, system_data)

    # ── Sheet 3: MAIN ──────────────────────────────────────────────────────
    ws_main = wb.create_sheet("MAIN")
    main_refs = build_main(ws_main, master_data)

    # ── Sheet 4: COLLISIONS ────────────────────────────────────────────────
    ws_coll = wb.create_sheet("COLLISIONS")
    collision_count = build_collisions(ws_coll, org_data)

    # ── Sheet 5: CONFLICTS ─────────────────────────────────────────────────
    ws_conf = wb.create_sheet("CONFLICTS")
    conflict_count = build_conflicts(ws_conf, nriv_data)

    # ── Sheet 6: GROWTH ────────────────────────────────────────────────────
    ws_growth = wb.create_sheet("GROWTH")
    build_growth(ws_growth, growth_data)

    # ── Sheet 7: HARDWARE_SIZING ───────────────────────────────────────────
    # The compression-factor address comes back from build_cover() rather than
    # being hardcoded, so re-ordering the COVER details cannot silently point
    # the sizing division at the wrong cell.
    ws_hw = wb.create_sheet("HARDWARE_SIZING")
    hw_refs = build_hardware_sizing(
        ws_hw,
        categories=categories,
        main_refs=main_refs,
        compression_cell=cover_refs["compression_cell"],
    )

    # ── Sheet 8: SUMMARY ───────────────────────────────────────────────────
    ws_sum = wb.create_sheet("SUMMARY")
    build_summary(
        ws_sum,
        main_refs=main_refs,
        hw_refs=hw_refs,
        collisions=collisions,
        conflicts=conflicts,
        system_data=system_data,
        categories=categories,
    )

    # ── Sheet 9: DASHBOARD ─────────────────────────────────────────────────
    ws_dash = wb.create_sheet("DASHBOARD")
    build_dashboard(
        ws_dash,
        system_data=system_data,
        hw_refs=hw_refs,
        collision_count=collision_count,
        conflict_count=conflict_count,
        main_refs=main_refs,
    )

    # ── Force recalculation on open ────────────────────────────────────────
    # openpyxl writes formulas but never their cached results, so every
    # calculated cell is empty until something evaluates it.  Setting this flag
    # makes Excel/Calc do a full recalculation the moment the file opens,
    # instead of showing blanks to whoever opens it first.
    wb.calculation.fullCalcOnLoad = True

    # ── Write file ─────────────────────────────────────────────────────────
    out_path = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    wb.save(out_path)
    print(f"[OK] Workbook written: {out_path}")
    print(f"     Sheets   : {[s.title for s in wb.worksheets]}")
    print(f"     Systems  : {sidcltns}")
    print(f"     Categories: {categories}")
    print(f"     Collisions: {collision_count}")
    print(f"     Conflicts : {conflict_count}")

    return out_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _cli():
    parser = argparse.ArgumentParser(
        description="Generate the DMLT Consolidation Study Excel report."
    )
    parser.add_argument("--master",  required=True, help="Path to master JSON file")
    parser.add_argument("--growth",  required=True, help="Path to growth JSON file")
    parser.add_argument("--system",  required=True, help="Path to system JSON file")
    parser.add_argument("--org",     required=True, help="Path to org JSON file")
    parser.add_argument("--nriv",    required=True, help="Path to nriv JSON file")
    parser.add_argument("--out",     default="output/dmlt_report.xlsx",
                        help="Output .xlsx path (default: output/dmlt_report.xlsx)")
    args = parser.parse_args()

    paths = {
        "master": args.master,
        "growth": args.growth,
        "system": args.system,
        "org":    args.org,
        "nriv":   args.nriv,
    }

    print("[INFO] Loading JSON sections …")
    sections = load_sections(paths)
    for sec, data in sections.items():
        print(f"       {sec}: {len(data):,} rows")

    generate_report(sections, args.out)


if __name__ == "__main__":
    _cli()
