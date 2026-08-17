"""
MAIN sheet — one row per table × system (agg_level="T").

Include? column (col I, index 9) is the user-editable toggle (default "Y").
Target MB column (col J, index 10) = =IF(I{row}="Y",G{row},0)

All downstream sizing (HARDWARE_SIZING, SUMMARY) reads the Target MB column
via SUMIFS — so toggling Include? recalculates the entire workbook.

Performance note:
  90k+ rows are written without per-cell borders (borders on 90k cells cost
  ~3 minutes in openpyxl).  The header rows carry full styling.  A worksheet-
  level print area and freeze are set.  The workbook is still fully valid .xlsx.
"""
from openpyxl.utils import get_column_letter
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side

from styles import (
    write_title_banner, write_section_header, write_col_headers,
    fill_formula, fill_input,
    FMT_INT, FMT_DEC2,
    C_FORM_FILL, C_FORM_FONT, C_INPUT_FILL,
)

# Column indices (1-based), data starts at column B=2
COL_NUM      = 2   # B
COL_TABLE    = 3   # C
COL_SYSTEM   = 4   # D
COL_CATEGORY = 5   # E
COL_DELV     = 6   # F
COL_SIZEMB   = 7   # G
COL_ENTRIES  = 8   # H
COL_INCLUDE  = 9   # I  ← user input
COL_TARGETMB = 10  # J  ← formula

HEADERS = ["#", "Table", "System", "Category", "Delv",
           "Size MB", "Entries", "Include?", "Target MB"]
WIDTHS  = [6, 22, 14, 12, 6, 12, 14, 10, 12]


def build(ws, master_data: list) -> dict:
    """
    Build the MAIN sheet.
    Returns main_refs dict for HARDWARE_SIZING and SUMMARY formulas.
    """
    ws.sheet_view.showGridLines = False

    # ── column widths ───────────────────────────────────────────────────────
    ws.column_dimensions["A"].width = 3
    for i, w in enumerate(WIDTHS):
        ws.column_dimensions[get_column_letter(i + 2)].width = w

    # ── banner + headers ────────────────────────────────────────────────────
    next_row = write_title_banner(
        ws, row=1, col_start=2, col_end=10,
        title="MAIN — TABLE VOLUMES",
        subtitle=(
            "One row per table × system (agg_level=T).  "
            "Toggle Include? (Y/N) — Target MB and all sizing recalculate automatically."
        ),
        title_size=16, row_height=30,
    )
    next_row += 1
    next_row = write_section_header(
        ws, next_row, 2, 10,
        "TABLE INVENTORY  |  Edit Include? column to scope the migration",
    )
    next_row = write_col_headers(ws, next_row, 2, HEADERS, WIDTHS)
    ws.freeze_panes = f"B{next_row}"
    data_start = next_row

    # ── shared style objects (created ONCE, reused for every row) ───────────
    f_formula = PatternFill("solid", fgColor=C_FORM_FILL)
    f_input   = PatternFill("solid", fgColor=C_INPUT_FILL)
    fn_seq    = Font(name="Arial", size=9, color=C_FORM_FONT)
    fn_body   = Font(name="Arial", size=9)
    fn_bold   = Font(name="Arial", size=9, bold=True)
    fn_input  = Font(name="Arial", size=9, bold=True)
    fn_form   = Font(name="Arial", size=9, color=C_FORM_FONT)
    al_c      = Alignment(horizontal="center", vertical="center")
    al_l      = Alignment(horizontal="left",   vertical="center")
    al_r      = Alignment(horizontal="right",  vertical="center")

    # ── filter + sort ────────────────────────────────────────────────────────
    t_rows = [r for r in master_data if r.get("agg_level") == "T"]
    t_rows.sort(key=lambda r: (r.get("sidclnt", ""), r.get("tabname", "")))

    inc_col  = get_column_letter(COL_INCLUDE)   # "I"
    size_col = get_column_letter(COL_SIZEMB)    # "G"
    total    = len(t_rows)

    report_at = max(1, total // 10)
    print(f"  MAIN: writing {total:,} rows …", flush=True)

    for seq, row_data in enumerate(t_rows, start=1):
        if seq % report_at == 0:
            print(f"  MAIN: {seq:,}/{total:,}", flush=True)

        kb      = row_data.get("tab_total_kb") or 0
        cnt     = row_data.get("clnt_count") or 0
        size_mb = round(kb / 1024, 4) if kb else 0.0
        ri      = data_start + seq - 1   # absolute Excel row

        formula = f'=IF({inc_col}{ri}="Y",{size_col}{ri},0)'

        # seq number
        c = ws.cell(row=ri, column=COL_NUM, value=seq)
        c.fill = f_formula; c.font = fn_seq
        c.alignment = al_c; c.number_format = FMT_INT

        # table
        c = ws.cell(row=ri, column=COL_TABLE, value=row_data.get("tabname", ""))
        c.font = fn_bold; c.alignment = al_l

        # system
        c = ws.cell(row=ri, column=COL_SYSTEM, value=row_data.get("sidclnt", ""))
        c.font = fn_body; c.alignment = al_c

        # category
        c = ws.cell(row=ri, column=COL_CATEGORY, value=row_data.get("category", ""))
        c.font = fn_body; c.alignment = al_c

        # delv
        c = ws.cell(row=ri, column=COL_DELV, value=row_data.get("delv_class", ""))
        c.font = fn_body; c.alignment = al_c

        # size MB
        c = ws.cell(row=ri, column=COL_SIZEMB, value=size_mb)
        c.font = fn_body; c.alignment = al_r; c.number_format = FMT_DEC2

        # entries
        c = ws.cell(row=ri, column=COL_ENTRIES, value=cnt)
        c.font = fn_body; c.alignment = al_r; c.number_format = FMT_INT

        # Include? — input cell
        c = ws.cell(row=ri, column=COL_INCLUDE, value="Y")
        c.fill = f_input; c.font = fn_input; c.alignment = al_c

        # Target MB — formula
        c = ws.cell(row=ri, column=COL_TARGETMB, value=formula)
        c.fill = f_formula; c.font = fn_form
        c.alignment = al_r; c.number_format = FMT_DEC2

        ws.row_dimensions[ri].height = 14

    data_end = data_start + total - 1
    print(f"  MAIN: complete — rows {data_start}:{data_end}", flush=True)

    # ── totals row ───────────────────────────────────────────────────────────
    tot_row = data_end + 2
    ws.cell(row=tot_row, column=COL_TABLE, value="TOTAL").font = \
        Font(name="Arial", size=9, bold=True)

    thin = Side(style="thin", color="D0D0D0")
    bdr  = Border(left=thin, right=thin, top=thin, bottom=thin)

    for col_idx, fmt in [
        (COL_ENTRIES,  FMT_INT),
        (COL_SIZEMB,   FMT_DEC2),
        (COL_TARGETMB, FMT_DEC2),
    ]:
        col_l = get_column_letter(col_idx)
        c = ws.cell(row=tot_row, column=col_idx,
                    value=f"=SUM({col_l}{data_start}:{col_l}{data_end})")
        c.fill          = f_formula
        c.font          = Font(name="Arial", size=9, bold=True, color=C_FORM_FONT)
        c.alignment     = al_r
        c.border        = bdr
        c.number_format = fmt

    return {
        "data_start_row": data_start,
        "data_end_row":   data_end,
        "include_col":    inc_col,
        "system_col":     get_column_letter(COL_SYSTEM),
        "category_col":   get_column_letter(COL_CATEGORY),
        "sizemb_col":     size_col,
        "targetmb_col":   get_column_letter(COL_TARGETMB),
    }
