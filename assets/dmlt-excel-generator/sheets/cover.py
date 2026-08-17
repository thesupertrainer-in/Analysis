"""
COVER sheet – project details, colour legend, workflow guide.
"""
from datetime import date
from openpyxl.styles import Alignment, PatternFill, Font
from openpyxl.utils import get_column_letter
from styles import (
    setup_sheet, write_title_banner, write_section_header, style_cell,
    fill_input, fill_inc, fill_col, fill_conf, fill_formula, fill_section,
    fill_subbanner, fill_title,
    font_body, font_colhdr, font_inc, font_col, font_conf, font_formula,
    font_section, font_subbanner, font_title,
    align_left, align_center, align_right, border_thin,
    C_WHITE, C_INC_FONT, C_COL_FONT, C_CONF_FONT, C_FORM_FONT
)


#: Label of the detail row that HARDWARE_SIZING divides by.
COMPRESSION_LABEL = "HANA Compression Factor"


def build(ws, run_meta: dict) -> dict:
    """
    run_meta keys used:
      runid, num_source_systems (int), sidcltns (list[str])

    Returns ``{"compression_cell": "COVER!C<row>"}`` — the address of the
    HANA Compression Factor input cell, resolved from where the row was
    actually written rather than assumed by downstream sheets.
    """
    setup_sheet(ws)

    # Column widths
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 32
    ws.column_dimensions["C"].width = 38
    ws.column_dimensions["D"].width = 18
    ws.column_dimensions["E"].width = 18
    ws.column_dimensions["F"].width = 18

    # -----------------------------------------------------------------------
    # Title banner  (row 1-2)
    # -----------------------------------------------------------------------
    next_row = write_title_banner(
        ws, row=1, col_start=2, col_end=6,
        title="SAP CONSOLIDATION VOLUME ASSESSMENT",
        subtitle="DMLT System Study  |  Full Migration — No Timeslice, No Org Delimitation",
        title_size=20, row_height=40
    )

    next_row += 1  # blank row 3

    # -----------------------------------------------------------------------
    # Project details (input cells)
    # -----------------------------------------------------------------------
    next_row = write_section_header(ws, next_row, 2, 6, "PROJECT DETAILS")

    details = [
        ("Customer Name",           ""),
        ("Study Type",              "System Consolidation (full migration)"),
        ("Number of Source Systems", run_meta.get("num_source_systems", "")),
        ("Source Systems",          ", ".join(run_meta.get("sidcltns", []))),
        ("Target System",           ""),
        ("HANA Compression Factor", 3),
        ("Assessment Date",         date.today().strftime("%d %b %Y")),
        ("Prepared By",             ""),
    ]

    compression_row = None

    for label, value in details:
        if label == COMPRESSION_LABEL:
            compression_row = next_row
        c_label = ws.cell(row=next_row, column=2, value=label)
        style_cell(c_label,
                   font=font_body(9, bold=True),
                   alignment=align_left,
                   border=border_thin)

        c_val = ws.cell(row=next_row, column=3, value=value)
        is_input = label not in ("Study Type", "Number of Source Systems",
                                 "Source Systems", "Assessment Date")
        style_cell(c_val,
                   fill=fill_input if is_input else None,
                   font=font_body(9),
                   alignment=align_left,
                   border=border_thin)

        # Merge C through F for the value cell
        ws.merge_cells(f"C{next_row}:F{next_row}")
        ws.row_dimensions[next_row].height = 16
        next_row += 1

    next_row += 1

    # -----------------------------------------------------------------------
    # Colour legend
    # -----------------------------------------------------------------------
    next_row = write_section_header(ws, next_row, 2, 6, "COLOUR LEGEND")

    legend = [
        (fill_input,   font_body(9),              "Input / Decision cell",
         "Editable by the user (e.g. Include? flag, customer name)"),
        (fill_inc,     Font(name="Arial", size=9, color=C_INC_FONT),
         "Included / Target",
         "Table or system included in the target scope"),
        (fill_col,     Font(name="Arial", size=9, color=C_COL_FONT),
         "Collision / Excluded",
         "Company-code collision — must be resolved before consolidation"),
        (fill_conf,    Font(name="Arial", size=9, color=C_CONF_FONT),
         "Conflict / Warning",
         "Number-range conflict — ranges overlap or level pointers differ"),
        (fill_formula, Font(name="Arial", size=9, color=C_FORM_FONT),
         "Formula / Auto",
         "Calculated automatically — do not edit directly"),
    ]

    for fill, fnt, label, desc in legend:
        c_swatch = ws.cell(row=next_row, column=2, value=label)
        style_cell(c_swatch, fill=fill, font=fnt,
                   alignment=align_center, border=border_thin)

        c_desc = ws.cell(row=next_row, column=3, value=desc)
        ws.merge_cells(f"C{next_row}:F{next_row}")
        style_cell(c_desc, font=font_body(9),
                   alignment=align_left, border=border_thin)
        ws.row_dimensions[next_row].height = 16
        next_row += 1

    next_row += 1

    # -----------------------------------------------------------------------
    # Workflow guide
    # -----------------------------------------------------------------------
    next_row = write_section_header(ws, next_row, 2, 6, "HOW TO USE THIS WORKBOOK")

    steps = [
        ("1", "SYSTEMS",         "Review the source system profiles — release, DB, unicode, volumes."),
        ("2", "MAIN",            "Review all tables. Change the Include? column (Y/N) to scope the migration."),
        ("3", "HARDWARE_SIZING", "Check the auto-calculated target S/4HANA hardware sizing."),
        ("4", "COLLISIONS",      "Review company-code collisions — each must be renumbered before merge."),
        ("5", "CONFLICTS",       "Review number-range conflicts — ranges must be aligned before merge."),
        ("6", "GROWTH",          "Review document growth trends — identify archiving candidates."),
        ("7", "SUMMARY",         "Share the Summary sheet with the customer as the executive view."),
        ("8", "DASHBOARD",       "Use the Dashboard for stakeholder presentations."),
    ]

    hdr_cells = ["Step", "Sheet", "Action"]
    hdr_cols  = [2, 3, 4]
    for col, h in zip(hdr_cols, hdr_cells):
        c = ws.cell(row=next_row, column=col, value=h)
        style_cell(c, fill=fill_section,
                   font=Font(name="Arial", bold=True, color="FFFFFF", size=9),
                   alignment=align_center, border=border_thin)
    ws.merge_cells(f"D{next_row}:F{next_row}")
    next_row += 1

    for step, sheet, action in steps:
        ws.cell(row=next_row, column=2, value=step).alignment  = align_center
        ws.cell(row=next_row, column=2).font   = font_body(9, bold=True)
        ws.cell(row=next_row, column=2).border = border_thin

        ws.cell(row=next_row, column=3, value=sheet).font     = font_body(9, bold=True)
        ws.cell(row=next_row, column=3).alignment             = align_left
        ws.cell(row=next_row, column=3).border                = border_thin

        ws.merge_cells(f"D{next_row}:F{next_row}")
        ws.cell(row=next_row, column=4, value=action).font    = font_body(9)
        ws.cell(row=next_row, column=4).alignment             = align_left
        ws.cell(row=next_row, column=4).border                = border_thin

        ws.row_dimensions[next_row].height = 16
        next_row += 1

    return {"compression_cell": f"COVER!C{compression_row}"}
