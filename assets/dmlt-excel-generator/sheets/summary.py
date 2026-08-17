"""
SUMMARY sheet — Q1–Q5, entirely formula-driven.

Q1: Included source size GB, Target S/4HANA size GB, tables included, tables excluded.
Q2: Included size per category (SUMIFS / 1024).
Q3: Collision count + one line per collision.
Q4: Conflict count.
Q5: Per-system included GB vs occupied GB.
"""
from openpyxl.utils import get_column_letter
from styles import (
    setup_sheet, write_title_banner, write_section_header, write_col_headers,
    style_cell, fill_formula, fill_inc, fill_col, fill_conf, fill_section,
    font_body, font_formula, font_inc, font_col, font_conf, font_section,
    align_left, align_center, align_right, border_thin,
    FMT_INT, FMT_DEC2, C_INC_FONT, C_COL_FONT, C_CONF_FONT, C_WHITE
)
from openpyxl.styles import Font


def build(ws,
          main_refs:     dict,
          hw_refs:       dict,
          collisions:    list,
          conflicts:     list,
          system_data:   list,
          categories:    list):
    """
    main_refs  – from main_sheet.build()
    hw_refs    – from hardware_sizing.build()
    collisions – list from collisions.detect_collisions()
    conflicts  – list from conflicts.detect_conflicts()
    system_data – raw system section rows
    categories  – sorted distinct category list
    """
    setup_sheet(ws)

    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 36
    ws.column_dimensions["C"].width = 22
    ws.column_dimensions["D"].width = 22
    ws.column_dimensions["E"].width = 22
    ws.column_dimensions["F"].width = 18

    start       = main_refs["data_start_row"]
    end         = main_refs["data_end_row"]
    inc_col     = main_refs["include_col"]      # e.g. "I"
    sys_col     = main_refs["system_col"]       # e.g. "D"
    cat_col     = main_refs["category_col"]     # e.g. "E"
    target_col  = main_refs["targetmb_col"]     # e.g. "J"
    sizemb_col  = main_refs["sizemb_col"]       # e.g. "G"

    total_tgt_gb_cell = f"HARDWARE_SIZING!{hw_refs['total_target_gb_cell']}"
    total_tgt_mb_cell = f"HARDWARE_SIZING!{hw_refs['total_target_mb_cell']}"

    next_row = write_title_banner(
        ws, row=1, col_start=2, col_end=6,
        title="SUMMARY",
        subtitle=(
            "Executive summary — all values are formula-driven and "
            "update automatically when Include? flags change in MAIN."
        ),
        title_size=18, row_height=36
    )
    next_row += 1

    def _kpi(label, formula, fmt=FMT_DEC2, fill=fill_formula, fnt=None):
        nonlocal next_row
        c_lbl = ws.cell(row=next_row, column=2, value=label)
        style_cell(c_lbl, font=font_body(9, bold=True),
                   alignment=align_left, border=border_thin)
        c_val = ws.cell(row=next_row, column=3, value=formula)
        style_cell(c_val, fill=fill,
                   font=fnt or font_formula(9),
                   alignment=align_right, border=border_thin,
                   number_format=fmt)
        ws.row_dimensions[next_row].height = 15
        next_row += 1

    # ===========================================================
    # Q1 — Overall sizing
    # ===========================================================
    next_row = write_section_header(ws, next_row, 2, 6,
                                    "Q1 — Overall Sizing")
    _kpi("Included Source Size (GB)",
         f"=ROUND(SUMIF(MAIN!${inc_col}${start}:${inc_col}${end},"
         f'"Y",MAIN!${sizemb_col}${start}:${sizemb_col}${end})/1024,2)',
         FMT_DEC2, fill_inc,
         Font(name="Arial", size=9, color=C_INC_FONT))

    _kpi("Target S/4HANA Size (GB)",
         f"={total_tgt_gb_cell}",
         FMT_DEC2, fill_inc,
         Font(name="Arial", size=9, color=C_INC_FONT))

    _kpi("Tables Included",
         f'=COUNTIF(MAIN!${inc_col}${start}:${inc_col}${end},"Y")',
         FMT_INT, fill_inc,
         Font(name="Arial", size=9, color=C_INC_FONT))

    _kpi("Tables Excluded",
         f'=COUNTIF(MAIN!${inc_col}${start}:${inc_col}${end},"N")',
         FMT_INT, fill_formula)

    next_row += 1

    # ===========================================================
    # Q2 — Included size per category
    # ===========================================================
    next_row = write_section_header(ws, next_row, 2, 6,
                                    "Q2 — Included Source Size by Category (GB)")
    next_row = write_col_headers(ws, next_row, 2,
                                 ["Category", "Source MB (Included)", "Source GB (Included)"],
                                 [36, 22, 22])

    for cat in sorted(categories):
        src_mb_formula = (
            f"=SUMIFS(MAIN!${target_col}${start}:${target_col}${end},"
            f'MAIN!${cat_col}${start}:${cat_col}${end},"{cat}")'
        )
        c_cat = ws.cell(row=next_row, column=2, value=cat)
        style_cell(c_cat, font=font_body(9), alignment=align_left, border=border_thin)

        c_mb = ws.cell(row=next_row, column=3, value=src_mb_formula)
        style_cell(c_mb, fill=fill_formula, font=font_formula(9),
                   alignment=align_right, border=border_thin, number_format=FMT_DEC2)

        c_gb = ws.cell(row=next_row, column=4,
                       value=f"=ROUND(C{next_row}/1024,2)")
        style_cell(c_gb, fill=fill_formula, font=font_formula(9),
                   alignment=align_right, border=border_thin, number_format=FMT_DEC2)

        ws.row_dimensions[next_row].height = 15
        next_row += 1

    next_row += 1

    # ===========================================================
    # Q3 — Company-code collisions
    # ===========================================================
    next_row = write_section_header(
        ws, next_row, 2, 6,
        f"Q3 — Company-Code Collisions ({len(collisions)} found)"
    )

    if collisions:
        next_row = write_col_headers(
            ws, next_row, 2,
            ["Company Code", "Systems Involved", "Risk"],
            [24, 30, 24]
        )
        for coll in collisions:
            systems_str = "  vs  ".join(
                f"{s['sidclnt']} ({s['name']})" for s in coll["systems"]
            )
            ws.cell(row=next_row, column=2, value=coll["bukrs"])
            ws.cell(row=next_row, column=3, value=systems_str)
            ws.cell(row=next_row, column=4, value="HIGH — renumber on merge")
            for col in [2, 3, 4]:
                c = ws.cell(row=next_row, column=col)
                style_cell(c, fill=fill_col,
                           font=Font(name="Arial", size=9, color=C_COL_FONT),
                           alignment=align_left, border=border_thin)
            ws.row_dimensions[next_row].height = 15
            next_row += 1
    else:
        ws.merge_cells(f"B{next_row}:F{next_row}")
        c = ws.cell(row=next_row, column=2, value="No collisions detected.")
        style_cell(c, font=font_body(9, color="2E7D32"), alignment=align_left)
        next_row += 1

    next_row += 1

    # ===========================================================
    # Q4 — Number-range conflicts
    # ===========================================================
    next_row = write_section_header(
        ws, next_row, 2, 6,
        f"Q4 — Number-Range Conflicts ({len(conflicts)} found)"
    )

    if conflicts:
        next_row = write_col_headers(
            ws, next_row, 2,
            ["Object", "Range#", "Conflict Type"],
            [36, 12, 30]
        )
        # Show first 20 to keep summary readable
        shown = conflicts[:20]
        for conf in shown:
            ws.cell(row=next_row, column=2, value=conf["object"])
            ws.cell(row=next_row, column=3, value=conf["nrrangenr"])
            ws.cell(row=next_row, column=4, value=conf["type"])
            for col in [2, 3, 4]:
                c = ws.cell(row=next_row, column=col)
                style_cell(c, fill=fill_conf,
                           font=Font(name="Arial", size=9, color=C_CONF_FONT),
                           alignment=align_left, border=border_thin)
            ws.row_dimensions[next_row].height = 15
            next_row += 1
        if len(conflicts) > 20:
            ws.merge_cells(f"B{next_row}:F{next_row}")
            ws.cell(row=next_row, column=2,
                    value=f"... and {len(conflicts) - 20} more — see CONFLICTS sheet for full list.")
            ws.cell(row=next_row, column=2).font = font_body(9, italic=True)
            next_row += 1
    else:
        ws.merge_cells(f"B{next_row}:F{next_row}")
        c = ws.cell(row=next_row, column=2, value="No conflicts detected.")
        style_cell(c, font=font_body(9, color="2E7D32"), alignment=align_left)
        next_row += 1

    next_row += 1

    # ===========================================================
    # Q5 — Per-system included GB vs occupied GB
    # ===========================================================
    next_row = write_section_header(
        ws, next_row, 2, 6,
        "Q5 — Per-System Included Size vs Occupied Volume"
    )
    next_row = write_col_headers(
        ws, next_row, 2,
        ["System-Client", "Included Source MB", "Included Source GB", "Occupied Vol (GB)"],
        [20, 22, 22, 22]
    )

    occ_map = {r["sidclnt"]: (r.get("occupied_vol") or 0)
               for r in system_data}
    sidcltns = sorted(occ_map.keys())

    for sid in sidcltns:
        occ_gb = round((occ_map.get(sid) or 0) / 1024, 2)

        src_mb_formula = (
            f"=SUMIFS(MAIN!${target_col}${start}:${target_col}${end},"
            f'MAIN!${sys_col}${start}:${sys_col}${end},"{sid}")'
        )
        ws.cell(row=next_row, column=2, value=sid)
        style_cell(ws.cell(row=next_row, column=2),
                   font=font_body(9), alignment=align_left, border=border_thin)

        ws.cell(row=next_row, column=3, value=src_mb_formula)
        style_cell(ws.cell(row=next_row, column=3),
                   fill=fill_formula, font=font_formula(9),
                   alignment=align_right, border=border_thin, number_format=FMT_DEC2)

        ws.cell(row=next_row, column=4, value=f"=ROUND(C{next_row}/1024,2)")
        style_cell(ws.cell(row=next_row, column=4),
                   fill=fill_formula, font=font_formula(9),
                   alignment=align_right, border=border_thin, number_format=FMT_DEC2)

        ws.cell(row=next_row, column=5, value=occ_gb)
        style_cell(ws.cell(row=next_row, column=5),
                   font=font_body(9), alignment=align_right, border=border_thin,
                   number_format=FMT_DEC2)

        ws.row_dimensions[next_row].height = 15
        next_row += 1
