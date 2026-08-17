"""
CONFLICTS sheet — number-range conflicts detected deterministically.

Detection rule:
  Group nriv by (object, nrrangenr).
  A conflict = same (object, nrrangenr) in >1 sidclnt AND either:
    - different nrlevel (current level pointer), OR
    - overlapping fromnumber–tonumber ranges (a0<=b1 AND b0<=a1).
"""
from dmlt_calc import detect_conflicts   # shared calculation engine
from openpyxl.utils import get_column_letter
from styles import (
    setup_sheet, write_title_banner, write_section_header, write_col_headers,
    style_cell, fill_conf, fill_formula,
    font_body, font_conf, font_formula,
    align_left, align_center, align_right, border_thin,
    C_CONF_FONT, FMT_INT
)
from openpyxl.styles import Font


# Severity colours per type
_TYPE_LABELS = {
    "LEVEL_MISMATCH": "MEDIUM — level pointers differ",
    "RANGE_OVERLAP":  "HIGH — ranges overlap on merge",
    "BOTH":           "CRITICAL — overlap AND level mismatch",
}


def build(ws, nriv_data: list) -> int:
    """Build the CONFLICTS sheet.  Returns conflict count."""
    setup_sheet(ws)

    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 30   # Object
    ws.column_dimensions["C"].width = 10   # Range#
    ws.column_dimensions["D"].width = 14   # System-Client
    ws.column_dimensions["E"].width = 18   # From Number
    ws.column_dimensions["F"].width = 18   # To Number
    ws.column_dimensions["G"].width = 24   # Current Level
    ws.column_dimensions["H"].width = 32   # Conflict Type / Severity

    conflicts = detect_conflicts(nriv_data)

    subtitle = (
        f"{len(conflicts)} conflict(s) detected — "
        "number ranges must be aligned before consolidation."
    )
    next_row = write_title_banner(
        ws, row=1, col_start=2, col_end=8,
        title="NUMBER-RANGE CONFLICTS",
        subtitle=subtitle,
        title_size=16, row_height=30
    )
    next_row += 1

    if not conflicts:
        ws.merge_cells(f"B{next_row}:H{next_row}")
        c = ws.cell(row=next_row, column=2,
                    value="No number-range conflicts detected in this run.")
        c.font      = font_body(10, bold=True, color="2E7D32")
        c.alignment = align_left
        return 0

    # Summary KPI row
    ws.merge_cells(f"B{next_row}:D{next_row}")
    kpi = ws.cell(row=next_row, column=2,
                  value=f"Total Conflicts: {len(conflicts)}")
    kpi.fill      = fill_conf
    kpi.font      = Font(name="Arial", bold=True, size=11, color=C_CONF_FONT)
    kpi.alignment = align_center
    kpi.border    = border_thin
    ws.row_dimensions[next_row].height = 20
    next_row += 2

    for conf in conflicts:
        label = _TYPE_LABELS.get(conf["type"], conf["type"])
        next_row = write_section_header(
            ws, next_row, 2, 8,
            f"Object: {conf['object']}   |   Range#: {conf['nrrangenr']}   |   {label}"
        )

        next_row = write_col_headers(
            ws, next_row, 2,
            ["Object", "Range#", "System-Client",
             "From Number", "To Number", "Current Level", "Severity"],
            [30, 10, 14, 18, 18, 24, 32]
        )

        for sys_row in conf["systems"]:
            vals = [
                conf["object"],
                conf["nrrangenr"],
                sys_row["sidclnt"],
                sys_row["fromnumber"],
                sys_row["tonumber"],
                sys_row["nrlevel"],
                label,
            ]
            for i, val in enumerate(vals):
                c = ws.cell(row=next_row, column=i + 2, value=val)
                style_cell(c, fill=fill_conf, font=font_conf(9),
                           alignment=align_left if i != 1 else align_center,
                           border=border_thin)
            ws.row_dimensions[next_row].height = 15
            next_row += 1

        next_row += 1

    return len(conflicts)
