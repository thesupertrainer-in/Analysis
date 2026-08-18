"""
MAIN — pivoted decision sheet.  One row per table, one column group per system.

Layout (matches MAIN_mockup.xlsx):

    A    #                                          spacer/sequence
    B    Table
    C    Cat
    D-F  Delv | ClntDep | Module      <- collapsible outline group (level 1)
    ...  one 3-column group per system: Entries | MB | Inc?
    last Incl. MB                     <- formula

The number of system groups is derived from the data — a run with three
systems produces three groups, a run with nine produces nine.  Nothing about
the column count is hardcoded.

Include? cells are plain editable values, not formulas.  "Y" means the table
is migrated from that system.  A blank means the table holds no data in that
system (MB = 0) and there is therefore nothing to include — see
``_include_default``.

Incl. MB sums the per-system MB for every system flagged "Y":

    =IF(I6="Y",H6,0)+IF(L6="Y",K6,0)+...

which uses only IF and addition, so it evaluates in Excel 2007 onwards.
"""
from openpyxl.utils import get_column_letter
from openpyxl.styles import Alignment

from styles import (
    setup_sheet, style_cell,
    fill_title, fill_subbanner, fill_colhdr, fill_section,
    fill_meta_hdr, fill_meta, fill_input, fill_inc, fill_formula,
    font_title, font_subbanner, font_colhdr, font_meta, font_data,
    font_subhdr,
    align_left, align_center, align_right, border_thin,
    FMT_INT, C_WHITE, C_INC_FONT, C_SUBBANNER, C_INC_FILL,
)
from openpyxl.styles import Font, PatternFill

# ── fixed leading columns ────────────────────────────────────────────────────
COL_SEQ   = 1   # A
COL_TABLE = 2   # B
COL_CAT   = 3   # C
COL_META  = 4   # D..F  (Delv, ClntDep, Module)
META_HEADERS = ["Delv", "ClntDep", "Module"]
META_WIDTHS  = [9, 9, 9]
N_META = len(META_HEADERS)

# ── per-system group ─────────────────────────────────────────────────────────
SYS_HEADERS = ["Entries", "MB", "Inc?"]
SYS_WIDTHS  = [9, 8, 6]
N_SYS_COLS  = len(SYS_HEADERS)

LEAD_WIDTHS = [4, 15, 7]      # A, B, C
TAIL_WIDTH  = 11              # Incl. MB

TITLE    = "CONSOLIDATION TABLE DECISIONS"
SUBTITLE = ("Row per table · grey metadata cols collapse (click −) · "
            "per system: Entries, MB, Include? · edit Inc? (Y/N) · "
            "Incl. MB = sum of Y systems")

ROW_TITLE   = 1
ROW_SUB     = 2
ROW_GROUP   = 4    # merged group headers
ROW_SUBHDR  = 5    # Entries / MB / Inc?
ROW_DATA    = 6    # first data row


def _include_default(mb: float, seeded: str) -> str:
    """
    Include? value for one table in one system.

    A table with no data in a system (MB rounds to 0) gets a blank rather than
    a flag: there is nothing to migrate from a system where the table does not
    hold rows, and a blank correctly contributes zero to Incl. MB.
    """
    if not mb:
        return ""
    return seeded


def build(ws, master_data: list, sidcltns: list, decisions: dict = None) -> dict:
    """
    master_data – master section rows (agg_level "T" only are used)
    sidcltns    – ordered list of system-client ids; one column group each
    decisions   – optional {sidclnt: {category: "Y"|"N"}} seed from
                  MAIN_DECISION; missing entries default to "Y"

    Returns a refs dict describing where everything landed.
    """
    setup_sheet(ws)
    decisions = decisions or {}

    n_sys    = len(sidcltns)
    first_sys_col = COL_META + N_META                       # G when 3 metadata cols
    total_col     = first_sys_col + n_sys * N_SYS_COLS      # Incl. MB
    last_col      = total_col

    # ── column widths + the collapsible metadata outline ────────────────────
    for i, w in enumerate(LEAD_WIDTHS):
        ws.column_dimensions[get_column_letter(1 + i)].width = w
    for i, w in enumerate(META_WIDTHS):
        d = ws.column_dimensions[get_column_letter(COL_META + i)]
        d.width = w
        d.outlineLevel = 1          # user can collapse the whole group
    for s in range(n_sys):
        base = first_sys_col + s * N_SYS_COLS
        for i, w in enumerate(SYS_WIDTHS):
            ws.column_dimensions[get_column_letter(base + i)].width = w
    ws.column_dimensions[get_column_letter(total_col)].width = TAIL_WIDTH
    ws.sheet_properties.outlinePr.summaryRight = True

    # ── banner ──────────────────────────────────────────────────────────────
    last_letter = get_column_letter(last_col)
    ws.merge_cells(f"A{ROW_TITLE}:{last_letter}{ROW_TITLE}")
    style_cell(ws.cell(row=ROW_TITLE, column=1, value=TITLE),
               fill=fill_title, font=font_title(16),
               alignment=Alignment(horizontal="left", vertical="center", indent=1))
    ws.row_dimensions[ROW_TITLE].height = 30

    ws.merge_cells(f"A{ROW_SUB}:{last_letter}{ROW_SUB}")
    style_cell(ws.cell(row=ROW_SUB, column=1, value=SUBTITLE),
               fill=fill_subbanner, font=font_subbanner(9),
               alignment=Alignment(horizontal="left", vertical="center", indent=1))
    ws.row_dimensions[ROW_SUB].height = 15

    # ── group header row ────────────────────────────────────────────────────
    for col, label in [(COL_SEQ, "#"), (COL_TABLE, "Table"), (COL_CAT, "Cat")]:
        style_cell(ws.cell(row=ROW_GROUP, column=col, value=label),
                   fill=fill_colhdr, font=font_colhdr(9),
                   alignment=align_center, border=border_thin)

    meta_end = COL_META + N_META - 1
    ws.merge_cells(start_row=ROW_GROUP, start_column=COL_META,
                   end_row=ROW_GROUP, end_column=meta_end)
    style_cell(ws.cell(row=ROW_GROUP, column=COL_META,
                       value="Metadata (collapsible)"),
               fill=fill_meta_hdr,
               font=Font(name="Arial", bold=True, color=C_WHITE, size=9),
               alignment=align_center, border=border_thin)

    for s, sid in enumerate(sidcltns):
        base = first_sys_col + s * N_SYS_COLS
        ws.merge_cells(start_row=ROW_GROUP, start_column=base,
                       end_row=ROW_GROUP, end_column=base + N_SYS_COLS - 1)
        style_cell(ws.cell(row=ROW_GROUP, column=base,
                           value=str(sid).replace("_", "")),
                   fill=fill_section,
                   font=Font(name="Arial", bold=True, color=C_WHITE, size=9),
                   alignment=align_center, border=border_thin)

    style_cell(ws.cell(row=ROW_GROUP, column=total_col, value="Incl. MB"),
               fill=PatternFill("solid", fgColor=C_INC_FONT),
               font=Font(name="Arial", bold=True, color=C_WHITE, size=9),
               alignment=align_center, border=border_thin)
    ws.row_dimensions[ROW_GROUP].height = 15

    # ── sub-header row ──────────────────────────────────────────────────────
    for i, label in enumerate(META_HEADERS):
        style_cell(ws.cell(row=ROW_SUBHDR, column=COL_META + i, value=label),
                   fill=fill_meta, font=font_meta(8, bold=True),
                   alignment=align_center, border=border_thin)
    for s in range(n_sys):
        base = first_sys_col + s * N_SYS_COLS
        for i, label in enumerate(SYS_HEADERS):
            style_cell(ws.cell(row=ROW_SUBHDR, column=base + i, value=label),
                       fill=fill_formula, font=font_subhdr(8),
                       alignment=align_center, border=border_thin)
    ws.row_dimensions[ROW_SUBHDR].height = 15

    ws.freeze_panes = f"{get_column_letter(first_sys_col)}{ROW_DATA}"

    # ── pivot the master data: tabname -> sidclnt -> (entries, kb) ──────────
    t_rows = [r for r in master_data if str(r.get("agg_level", "")).upper() == "T"]

    per_table: dict[str, dict] = {}
    for r in t_rows:
        tab = str(r.get("tabname", "")).strip()
        if not tab:
            continue
        sid = str(r.get("sidclnt", "")).strip()
        rec = per_table.setdefault(tab, {
            "category": "", "delv_class": "", "clnt_dep": "", "module": "",
            "systems": {},
        })
        # Metadata is table-level; first non-blank value seen wins.
        if not rec["category"]:
            rec["category"] = str(r.get("category", "") or "").strip()
        if not rec["delv_class"]:
            rec["delv_class"] = str(r.get("delv_class", "") or "").strip()
        if not rec["clnt_dep"]:
            rec["clnt_dep"] = str(r.get("clnt_dep", "") or "").strip()
        if not rec["module"]:
            rec["module"] = str(
                r.get("modname") or r.get("component") or ""
            ).strip()

        entries = int(r.get("clnt_count") or 0)
        kb = float(r.get("tab_total_kb") or 0)
        prev = rec["systems"].get(sid, (0, 0.0))
        rec["systems"][sid] = (prev[0] + entries, prev[1] + kb)

    # Largest tables first — the sheet is a decision aid, so the rows that
    # move the number the most belong at the top.
    def _total_mb(rec):
        return sum(kb for _, kb in rec["systems"].values()) / 1024

    ordered = sorted(per_table.items(), key=lambda kv: (-_total_mb(kv[1]), kv[0]))

    # ── data rows ───────────────────────────────────────────────────────────
    fnt_seq   = font_data(8)
    fnt_body  = font_data(9)
    fnt_num   = font_data(8)
    fnt_mb    = font_data(9)
    fnt_meta  = font_meta(8)
    fnt_inc   = Font(name="Arial", size=9, bold=True, color=C_INC_FONT)
    fill_incl = fill_inc
    fnt_incl  = Font(name="Arial", size=9, color=C_INC_FONT)

    row = ROW_DATA
    for seq, (tab, rec) in enumerate(ordered, start=1):
        style_cell(ws.cell(row=row, column=COL_SEQ, value=seq),
                   font=fnt_seq, alignment=align_center)
        style_cell(ws.cell(row=row, column=COL_TABLE, value=tab),
                   font=fnt_body, alignment=align_left)
        style_cell(ws.cell(row=row, column=COL_CAT, value=rec["category"]),
                   font=fnt_body, alignment=align_center)

        for i, key in enumerate(["delv_class", "clnt_dep", "module"]):
            style_cell(ws.cell(row=row, column=COL_META + i,
                               value=rec[key] or None),
                       fill=fill_meta, font=fnt_meta, alignment=align_center)

        terms = []
        for s, sid in enumerate(sidcltns):
            base = first_sys_col + s * N_SYS_COLS
            entries, kb = rec["systems"].get(sid, (0, 0.0))
            mb = round(kb / 1024, 2)

            style_cell(ws.cell(row=row, column=base, value=entries),
                       font=fnt_num, alignment=align_right, number_format=FMT_INT)
            style_cell(ws.cell(row=row, column=base + 1, value=mb),
                       font=fnt_mb, alignment=align_right, number_format=FMT_INT)

            seeded = (decisions.get(sid, {}) or {}).get(rec["category"], "Y")
            style_cell(ws.cell(row=row, column=base + 2,
                               value=_include_default(mb, seeded) or None),
                       fill=fill_input, font=fnt_inc, alignment=align_center)

            inc_l = get_column_letter(base + 2)
            mb_l  = get_column_letter(base + 1)
            terms.append(f'IF({inc_l}{row}="Y",{mb_l}{row},0)')

        style_cell(ws.cell(row=row, column=total_col, value="=" + "+".join(terms)),
                   fill=fill_incl, font=fnt_incl,
                   alignment=align_right, number_format=FMT_INT)

        ws.row_dimensions[row].height = 15
        row += 1

    data_end = row - 1

    # ── TOTAL row: per-system MB columns and Incl. MB only ──────────────────
    total_row = data_end + 1
    style_cell(ws.cell(row=total_row, column=COL_TABLE, value="TOTAL"),
               fill=fill_colhdr,
               font=Font(name="Arial", bold=True, color=C_WHITE, size=9),
               alignment=align_left)

    for s in range(n_sys):
        mb_l = get_column_letter(first_sys_col + s * N_SYS_COLS + 1)
        style_cell(ws.cell(row=total_row, column=first_sys_col + s * N_SYS_COLS + 1,
                           value=f"=SUM({mb_l}{ROW_DATA}:{mb_l}{data_end})"),
                   fill=fill_colhdr,
                   font=Font(name="Arial", bold=True, color=C_WHITE, size=9),
                   alignment=align_right, number_format=FMT_INT)

    tot_l = get_column_letter(total_col)
    style_cell(ws.cell(row=total_row, column=total_col,
                       value=f"=SUM({tot_l}{ROW_DATA}:{tot_l}{data_end})"),
               fill=PatternFill("solid", fgColor=C_INC_FONT),
               font=Font(name="Arial", bold=True, color=C_WHITE, size=9),
               alignment=align_right, number_format=FMT_INT)
    ws.row_dimensions[total_row].height = 15

    return {
        "data_start_row": ROW_DATA,
        "data_end_row":   data_end,
        "total_row":      total_row,
        "table_col":      get_column_letter(COL_TABLE),
        "category_col":   get_column_letter(COL_CAT),
        "first_sys_col":  first_sys_col,
        "sys_col_span":   N_SYS_COLS,
        "included_col":   tot_l,
        "sidcltns":       list(sidcltns),
        "table_count":    len(ordered),
    }
