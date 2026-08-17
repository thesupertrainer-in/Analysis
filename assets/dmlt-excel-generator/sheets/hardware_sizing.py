"""
HARDWARE_SIZING sheet — target S/4HANA sizing, fully formula-driven off MAIN.

Structure:
  - Repository shell baseline: fixed 71,680 MB (70 GB equivalent)
  - One row per distinct category from MAIN
  - TOTAL row summing shell + all categories
  - All Source MB and Target MB cells are SUMIFS / ROUND formulas referencing MAIN
  - The sheet recalculates automatically when Include? flags change in MAIN
"""
from openpyxl.utils import get_column_letter
from styles import (
    setup_sheet, write_title_banner, write_section_header, write_col_headers,
    style_cell, fill_formula, fill_inc, fill_col, fill_section,
    font_body, font_formula, font_inc,
    align_left, align_center, align_right, border_thin,
    FMT_INT, FMT_DEC2, C_INC_FONT
)
from openpyxl.styles import Font, PatternFill

SHELL_MB = 71_680   # 70 GB repository shell baseline


def build(ws, categories: list, main_refs: dict, compression_cell: str = "COVER!C10"):
    """
    categories  – sorted list of distinct category strings from master data
    main_refs   – dict returned by main_sheet.build():
                  { data_start_row, data_end_row,
                    include_col, system_col, category_col,
                    sizemb_col, targetmb_col }
    compression_cell – Excel reference to the HANA Compression Factor input
                       on the COVER sheet (default COVER!C10).
    """
    setup_sheet(ws)

    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 28   # Category
    ws.column_dimensions["C"].width = 18   # Source MB (included)
    ws.column_dimensions["D"].width = 18   # Target MB (HANA)
    ws.column_dimensions["E"].width = 18   # Target GB (HANA)
    ws.column_dimensions["F"].width = 28   # Notes

    start = main_refs["data_start_row"]
    end   = main_refs["data_end_row"]
    cat_col    = main_refs["category_col"]    # e.g. "E"
    target_col = main_refs["targetmb_col"]    # e.g. "J"

    next_row = write_title_banner(
        ws, row=1, col_start=2, col_end=6,
        title="HARDWARE SIZING — TARGET S/4HANA",
        subtitle=(
            "Formula-driven off MAIN sheet. "
            "Change Include? flags in MAIN — this sheet recalculates automatically."
        ),
        title_size=16, row_height=30
    )
    next_row += 1

    # HANA Compression factor note
    ws.merge_cells(f"B{next_row}:F{next_row}")
    c = ws.cell(row=next_row, column=2,
                value=f"HANA Compression Factor: read from COVER sheet (cell C10).  "
                      f"Default = 3.")
    style_cell(c, font=font_body(9, italic=True),
               alignment=align_left)
    ws.row_dimensions[next_row].height = 14
    next_row += 2

    next_row = write_section_header(ws, next_row, 2, 6, "SIZING BY CATEGORY")
    next_row = write_col_headers(
        ws, next_row, 2,
        ["Category", "Source MB (Included)", "Target MB (HANA)", "Target GB (HANA)", "Notes"],
        [28, 18, 18, 18, 28]
    )

    # Track rows for TOTAL formula
    first_data_row = next_row

    # ---- Repository Shell (fixed baseline) ----
    ws.cell(row=next_row, column=2, value="Repository Shell (baseline)")
    style_cell(ws.cell(row=next_row, column=2),
               font=font_body(9, bold=True), alignment=align_left, border=border_thin)

    shell_src_mb_cell = f"C{next_row}"
    ws.cell(row=next_row, column=3, value=SHELL_MB)
    style_cell(ws.cell(row=next_row, column=3),
               fill=fill_formula, font=font_formula(9),
               alignment=align_right, border=border_thin, number_format=FMT_INT)

    # Target MB for shell = ROUND(SHELL_MB / compression, 0)
    ws.cell(row=next_row, column=4,
            value=f"=ROUND(C{next_row}/{compression_cell},0)")
    style_cell(ws.cell(row=next_row, column=4),
               fill=fill_formula, font=font_formula(9),
               alignment=align_right, border=border_thin, number_format=FMT_INT)

    ws.cell(row=next_row, column=5,
            value=f"=ROUND(D{next_row}/1024,2)")
    style_cell(ws.cell(row=next_row, column=5),
               fill=fill_formula, font=font_formula(9),
               alignment=align_right, border=border_thin, number_format=FMT_DEC2)

    ws.cell(row=next_row, column=6, value="Fixed baseline — SAP repository objects")
    style_cell(ws.cell(row=next_row, column=6),
               font=font_body(9, italic=True), alignment=align_left, border=border_thin)

    ws.row_dimensions[next_row].height = 15
    next_row += 1

    # ---- One row per category ----
    for cat in sorted(categories):
        ws.cell(row=next_row, column=2, value=cat)
        style_cell(ws.cell(row=next_row, column=2),
                   font=font_body(9), alignment=align_left, border=border_thin)

        # Source MB = SUMIFS of Target MB column from MAIN where category matches
        # Uses absolute references so they don't shift
        src_formula = (
            f"=SUMIFS(MAIN!${target_col}${start}:MAIN!${target_col}${end},"
            f"MAIN!${cat_col}${start}:MAIN!${cat_col}${end},"
            f'"{cat}")'
        )
        ws.cell(row=next_row, column=3, value=src_formula)
        style_cell(ws.cell(row=next_row, column=3),
                   fill=fill_formula, font=font_formula(9),
                   alignment=align_right, border=border_thin, number_format=FMT_DEC2)

        # Target MB = ROUND(SourceMB / compression, 0)
        ws.cell(row=next_row, column=4,
                value=f"=ROUND(C{next_row}/{compression_cell},0)")
        style_cell(ws.cell(row=next_row, column=4),
                   fill=fill_formula, font=font_formula(9),
                   alignment=align_right, border=border_thin, number_format=FMT_INT)

        # Target GB
        ws.cell(row=next_row, column=5,
                value=f"=ROUND(D{next_row}/1024,2)")
        style_cell(ws.cell(row=next_row, column=5),
                   fill=fill_formula, font=font_formula(9),
                   alignment=align_right, border=border_thin, number_format=FMT_DEC2)

        ws.cell(row=next_row, column=6, value=cat)
        style_cell(ws.cell(row=next_row, column=6),
                   font=font_body(9), alignment=align_left, border=border_thin)

        ws.row_dimensions[next_row].height = 15
        next_row += 1

    last_data_row = next_row - 1

    # ---- TOTAL row ----
    next_row += 1
    ws.cell(row=next_row, column=2, value="TOTAL")
    style_cell(ws.cell(row=next_row, column=2),
               fill=fill_section,
               font=Font(name="Arial", bold=True, color="FFFFFF", size=10),
               alignment=align_left, border=border_thin)

    for col in [3, 4, 5]:
        col_l = get_column_letter(col)
        ws.cell(row=next_row, column=col,
                value=f"=SUM({col_l}{first_data_row}:{col_l}{last_data_row})")
        style_cell(ws.cell(row=next_row, column=col),
                   fill=fill_inc,
                   font=Font(name="Arial", bold=True, color=C_INC_FONT, size=10),
                   alignment=align_right, border=border_thin,
                   number_format=FMT_INT if col < 5 else FMT_DEC2)

    ws.cell(row=next_row, column=6, value="← Total target S/4HANA disk requirement")
    style_cell(ws.cell(row=next_row, column=6),
               font=font_body(9, italic=True), alignment=align_left, border=border_thin)
    ws.row_dimensions[next_row].height = 18

    return {
        "total_source_mb_cell": f"C{next_row}",
        "total_target_mb_cell": f"D{next_row}",
        "total_target_gb_cell": f"E{next_row}",
        "total_row":            next_row,
    }
