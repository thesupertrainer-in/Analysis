"""
Tests for the pivoted MAIN sheet and the MAIN_DECISION control grid.

These assert the structural contract the mockup defines — column geometry,
the Incl. MB formula, the collapsible metadata outline, the blank-Include?
rule — without pinning cosmetic details that are allowed to change.
"""
import os
import sys

import pytest

openpyxl = pytest.importorskip("openpyxl")

_GEN = os.path.join(os.path.dirname(__file__), "app", "excel_generator")
sys.path.insert(0, _GEN)

from generate_report import generate_report      # noqa: E402

FIRST_SYS_COL = 7      # G — after #, Table, Cat and 3 metadata columns
SYS_SPAN = 3           # Entries, MB, Inc?
ROW_GROUP, ROW_SUBHDR, ROW_DATA = 4, 5, 6


def _master(sid, tab, cat, kb, cnt=100, delv="A", dep="X", mod="FI"):
    return {"sidclnt": sid, "tabname": tab, "category": cat, "agg_level": "T",
            "delv_class": delv, "clnt_dep": dep, "modname": mod,
            "clnt_count": cnt, "tab_total_kb": kb}


def _system(sid):
    return {"sidclnt": sid, "sid": sid[:3], "db_sys": "HDB", "rel": "108",
            "sp_level": "0001", "unicode": "X", "total_vol": 100,
            "occupied_vol": 50}


def _build(tmp_path, sidcltns, tables, base_system=None, decisions=None):
    master = []
    for sid in sidcltns:
        for tab, cat, kb in tables:
            master.append(_master(sid, tab, cat, kb))
    sections = {"master": master, "system": [_system(s) for s in sidcltns],
                "growth": [], "org": [], "nriv": []}
    out = str(tmp_path / "wb.xlsx")
    generate_report(sections, out, base_system=base_system, decisions=decisions)
    return openpyxl.load_workbook(out)


@pytest.fixture
def wb2(tmp_path):
    return _build(tmp_path, ["A_100", "B_100"],
                  [("BSEG", "APPL", 1024 * 100), ("T001", "CONF", 1024 * 5)],
                  base_system="A_100")


# ── sheet set ────────────────────────────────────────────────────────────────

def test_output_ends_at_main(wb2):
    """This pass ships COVER -> SYSTEMS -> MAIN_DECISION -> MAIN and nothing more."""
    assert wb2.sheetnames == ["COVER", "SYSTEMS", "MAIN_DECISION", "MAIN"]


# ── MAIN geometry ────────────────────────────────────────────────────────────

def test_leading_columns(wb2):
    ws = wb2["MAIN"]
    assert [ws.cell(row=ROW_GROUP, column=c).value for c in (1, 2, 3)] == \
        ["#", "Table", "Cat"]
    assert ws.cell(row=ROW_GROUP, column=4).value == "Metadata (collapsible)"
    assert [ws.cell(row=ROW_SUBHDR, column=c).value for c in (4, 5, 6)] == \
        ["Delv", "ClntDep", "Module"]


def test_metadata_columns_are_a_collapsible_outline(wb2):
    ws = wb2["MAIN"]
    for col in ("D", "E", "F"):
        assert ws.column_dimensions[col].outlineLevel == 1
    # the columns either side must not be swept into the group
    assert ws.column_dimensions["C"].outlineLevel == 0
    assert ws.column_dimensions["G"].outlineLevel == 0


def test_one_three_column_group_per_system(wb2):
    ws = wb2["MAIN"]
    for i, sid in enumerate(["A_100", "B_100"]):
        base = FIRST_SYS_COL + i * SYS_SPAN
        assert ws.cell(row=ROW_GROUP, column=base).value == sid.replace("_", "")
        assert [ws.cell(row=ROW_SUBHDR, column=base + j).value for j in range(3)] \
            == ["Entries", "MB", "Inc?"]


def test_included_mb_is_the_final_column(wb2):
    ws = wb2["MAIN"]
    total_col = FIRST_SYS_COL + 2 * SYS_SPAN
    assert ws.cell(row=ROW_GROUP, column=total_col).value == "Incl. MB"
    assert ws.max_column == total_col


def test_frozen_header_and_hidden_gridlines(wb2):
    ws = wb2["MAIN"]
    assert ws.freeze_panes == "G6"
    assert ws.sheet_view.showGridLines is False


# ── MAIN formulas ────────────────────────────────────────────────────────────

def test_included_mb_formula_shape(wb2):
    ws = wb2["MAIN"]
    total_col = FIRST_SYS_COL + 2 * SYS_SPAN
    assert ws.cell(row=ROW_DATA, column=total_col).value == \
        '=IF(I6="Y",H6,0)+IF(L6="Y",K6,0)'


def test_formula_uses_only_excel_2007_functions(wb2):
    import re
    banned = {"XLOOKUP", "FILTER", "UNIQUE", "SORTBY", "LET", "LAMBDA",
              "IFS", "TEXTJOIN", "SEQUENCE", "XMATCH"}
    for ws in wb2.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    used = set(re.findall(r"([A-Z][A-Z0-9\.]*)\s*\(", c.value.upper()))
                    assert not (used & banned), f"{ws.title}!{c.coordinate}: {used}"


def test_total_row_sums_mb_and_included_only(wb2):
    ws = wb2["MAIN"]
    total_col = FIRST_SYS_COL + 2 * SYS_SPAN
    trow = next(r for r in range(ROW_DATA, ws.max_row + 1)
                if ws.cell(row=r, column=2).value == "TOTAL")
    # MB column of each system is summed …
    assert ws.cell(row=trow, column=FIRST_SYS_COL + 1).value == "=SUM(H6:H7)"
    assert ws.cell(row=trow, column=FIRST_SYS_COL + SYS_SPAN + 1).value == "=SUM(K6:K7)"
    assert ws.cell(row=trow, column=total_col).value == "=SUM(M6:M7)"
    # … but Entries columns are not
    assert ws.cell(row=trow, column=FIRST_SYS_COL).value is None


# ── Include? behaviour ───────────────────────────────────────────────────────

def test_include_defaults_to_y_and_is_a_plain_value(wb2):
    ws = wb2["MAIN"]
    cell = ws.cell(row=ROW_DATA, column=FIRST_SYS_COL + 2)
    assert cell.value == "Y"
    assert not str(cell.value).startswith("=")     # editable, not a formula


def test_include_is_blank_when_the_table_is_empty_in_that_system(tmp_path):
    """MB = 0 means the table holds nothing there — no flag, contributes zero."""
    master = [_master("A_100", "ONLY_A", "CUST", 1024 * 10),
              _master("B_100", "ONLY_A", "CUST", 0, cnt=0)]
    sections = {"master": master, "system": [_system("A_100"), _system("B_100")],
                "growth": [], "org": [], "nriv": []}
    out = str(tmp_path / "z.xlsx")
    generate_report(sections, out)
    ws = openpyxl.load_workbook(out)["MAIN"]

    assert ws.cell(row=ROW_DATA, column=FIRST_SYS_COL + 2).value == "Y"       # A_100
    assert ws.cell(row=ROW_DATA, column=FIRST_SYS_COL + SYS_SPAN + 2).value is None
    # the term stays in the formula, it just evaluates to zero
    assert ws.cell(row=ROW_DATA, column=FIRST_SYS_COL + 2 * SYS_SPAN).value \
        == '=IF(I6="Y",H6,0)+IF(L6="Y",K6,0)'


def test_decisions_seed_main_include_cells(tmp_path):
    wb = _build(tmp_path, ["A_100", "B_100"],
                [("BSEG", "APPL", 1024 * 10), ("T001", "CONF", 1024 * 10)],
                decisions={"B_100": {"CONF": "N"}})
    ws = wb["MAIN"]
    rows = {ws.cell(row=r, column=2).value: r
            for r in range(ROW_DATA, ws.max_row + 1)}
    b_inc = FIRST_SYS_COL + SYS_SPAN + 2
    assert ws.cell(row=rows["T001"], column=b_inc).value == "N"
    assert ws.cell(row=rows["BSEG"], column=b_inc).value == "Y"


# ── dynamic system count ─────────────────────────────────────────────────────

@pytest.mark.parametrize("n", [1, 3, 7])
def test_system_count_is_not_hardcoded(tmp_path, n):
    sids = [f"S{i:02d}_100" for i in range(1, n + 1)]
    wb = _build(tmp_path, sids, [("BSEG", "APPL", 1024 * 10)])
    ws = wb["MAIN"]
    total_col = FIRST_SYS_COL + n * SYS_SPAN
    assert ws.cell(row=ROW_GROUP, column=total_col).value == "Incl. MB"
    assert ws.cell(row=ROW_DATA, column=total_col).value.count("IF(") == n
    assert len(wb["MAIN_DECISION"]["A"]) >= n


# ── MAIN_DECISION ────────────────────────────────────────────────────────────

def test_decision_grid_systems_as_rows_categories_as_columns(wb2):
    ws = wb2["MAIN_DECISION"]
    assert ws.cell(row=4, column=1).value == "System"
    assert [ws.cell(row=4, column=c).value for c in (2, 3)] == ["APPL", "CONF"]
    assert ws.cell(row=5, column=1).value == "A_100 (base)"
    assert ws.cell(row=6, column=1).value == "B_100"
    assert ws.cell(row=5, column=2).value == "Y"


def test_decision_grid_has_no_formulas(wb2):
    """No live link back to MAIN — the grid records the seed, MAIN rules."""
    ws = wb2["MAIN_DECISION"]
    for row in ws.iter_rows():
        for c in row:
            assert not (isinstance(c.value, str) and c.value.startswith("="))


def test_base_system_is_a_parameter_not_derived_from_volume(tmp_path):
    """The smallest system can be the base — it is a migration decision."""
    master = [_master("BIG_100", "T", "APPL", 1024 * 9999),
              _master("SMALL_100", "T", "APPL", 1024)]
    sections = {"master": master,
                "system": [_system("BIG_100"), _system("SMALL_100")],
                "growth": [], "org": [], "nriv": []}
    out = str(tmp_path / "b.xlsx")
    generate_report(sections, out, base_system="SMALL_100")
    ws = openpyxl.load_workbook(out)["MAIN_DECISION"]
    labels = [ws.cell(row=r, column=1).value for r in (5, 6)]
    assert "SMALL_100 (base)" in labels
    assert "BIG_100" in labels


def test_no_base_system_marks_nothing(tmp_path):
    wb = _build(tmp_path, ["A_100"], [("BSEG", "APPL", 1024)])
    assert wb["MAIN_DECISION"].cell(row=5, column=1).value == "A_100"


def test_categories_come_from_the_data(tmp_path):
    wb = _build(tmp_path, ["A_100"],
                [("A", "SYST_APPL", 1024), ("B", "ZCUST", 1024)])
    ws = wb["MAIN_DECISION"]
    assert [ws.cell(row=4, column=c).value for c in (2, 3)] == ["SYST_APPL", "ZCUST"]
