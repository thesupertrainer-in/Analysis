"""
Shared style helpers for the DMLT Consolidation workbook.
All colours, fonts and border patterns are defined here once and
imported by every sheet builder.
"""
from openpyxl.styles import (
    PatternFill, Font, Alignment, Border, Side, numbers
)
from openpyxl.utils import get_column_letter

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
C_TITLE      = "1C2833"   # dark slate  – title banner
C_SUBBANNER  = "2E4057"   # navy        – sub-banner / column headers
C_SECTION    = "048A81"   # teal        – section headers
C_INPUT_FILL = "E3F2FD"   # light blue  – editable input cells
C_INC_FILL   = "E8F5E9"   # light green – included rows
C_INC_FONT   = "2E7D32"   # dark green
C_COL_FILL   = "FDECEA"   # light red   – collision rows
C_COL_FONT   = "B71C1C"   # dark red
C_CONF_FILL  = "FFF3E0"   # light amber – conflict rows
C_CONF_FONT  = "BF8F00"   # dark amber
C_FORM_FILL  = "ECEFF1"   # light grey  – formula / auto cells
C_FORM_FONT  = "546E7A"   # grey text
C_WHITE      = "FFFFFF"
C_BORDER     = "D0D0D0"

# ---------------------------------------------------------------------------
# Fills
# ---------------------------------------------------------------------------
fill_title     = PatternFill("solid", fgColor=C_TITLE)
fill_subbanner = PatternFill("solid", fgColor=C_SUBBANNER)
fill_section   = PatternFill("solid", fgColor=C_SECTION)
fill_colhdr    = PatternFill("solid", fgColor=C_SUBBANNER)
fill_input     = PatternFill("solid", fgColor=C_INPUT_FILL)
fill_inc       = PatternFill("solid", fgColor=C_INC_FILL)
fill_col       = PatternFill("solid", fgColor=C_COL_FILL)
fill_conf      = PatternFill("solid", fgColor=C_CONF_FILL)
fill_formula   = PatternFill("solid", fgColor=C_FORM_FILL)
fill_none      = PatternFill("none")

# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------
def font_title(size=22):
    return Font(name="Arial", bold=True, color=C_WHITE, size=size)

def font_subbanner(size=9):
    return Font(name="Arial", color=C_WHITE, size=size)

def font_section(size=10):
    return Font(name="Arial", bold=True, color=C_WHITE, size=size)

def font_colhdr(size=9):
    return Font(name="Arial", bold=True, color=C_WHITE, size=size)

def font_body(size=9, bold=False, color="000000", italic=False):
    return Font(name="Arial", size=size, bold=bold, color=color, italic=italic)

def font_inc(size=9):
    return Font(name="Arial", size=size, color=C_INC_FONT)

def font_col(size=9, bold=False):
    return Font(name="Arial", size=size, bold=bold, color=C_COL_FONT)

def font_conf(size=9, bold=False):
    return Font(name="Arial", size=size, bold=bold, color=C_CONF_FONT)

def font_formula(size=9):
    return Font(name="Arial", size=size, color=C_FORM_FONT)

# ---------------------------------------------------------------------------
# Alignments
# ---------------------------------------------------------------------------
align_left    = Alignment(horizontal="left",   vertical="center", wrap_text=False)
align_center  = Alignment(horizontal="center", vertical="center", wrap_text=False)
align_right   = Alignment(horizontal="right",  vertical="center", wrap_text=False)
align_wrap    = Alignment(horizontal="left",   vertical="top",    wrap_text=True)

# ---------------------------------------------------------------------------
# Borders
# ---------------------------------------------------------------------------
_thin_side  = Side(style="thin",   color=C_BORDER)
_med_side   = Side(style="medium", color=C_BORDER)

border_thin = Border(
    left=_thin_side, right=_thin_side,
    top=_thin_side,  bottom=_thin_side
)

border_none = Border()

def border_bottom_only():
    return Border(bottom=Side(style="thin", color=C_BORDER))

# ---------------------------------------------------------------------------
# Number formats
# ---------------------------------------------------------------------------
FMT_INT    = '#,##0'
FMT_DEC1   = '#,##0.0'
FMT_DEC2   = '#,##0.00'
FMT_PCT    = '0.0%'
FMT_TEXT   = '@'

# ---------------------------------------------------------------------------
# Helper: apply a uniform style to a single cell
# ---------------------------------------------------------------------------
def style_cell(cell, fill=None, font=None, alignment=None,
               border=None, number_format=None):
    if fill:           cell.fill          = fill
    if font:           cell.font          = font
    if alignment:      cell.alignment     = alignment
    if border:         cell.border        = border
    if number_format:  cell.number_format = number_format


# ---------------------------------------------------------------------------
# Helper: write a title banner (merged across cols, optional sub-banner row)
# ---------------------------------------------------------------------------
def write_title_banner(ws, row, col_start, col_end,
                       title, subtitle=None,
                       title_size=22, row_height=36):
    """Write a full-width title banner.  Returns next available row."""
    from openpyxl.utils import get_column_letter
    end_col_letter = get_column_letter(col_end)
    start_col_letter = get_column_letter(col_start)

    ws.merge_cells(
        f"{start_col_letter}{row}:{end_col_letter}{row}"
    )
    c = ws.cell(row=row, column=col_start, value=title)
    style_cell(c,
               fill=fill_title,
               font=font_title(title_size),
               alignment=Alignment(horizontal="left", vertical="center",
                                   indent=1))
    ws.row_dimensions[row].height = row_height
    row += 1

    if subtitle:
        ws.merge_cells(
            f"{start_col_letter}{row}:{end_col_letter}{row}"
        )
        c = ws.cell(row=row, column=col_start, value=subtitle)
        style_cell(c,
                   fill=fill_subbanner,
                   font=font_subbanner(9),
                   alignment=Alignment(horizontal="left", vertical="center",
                                       indent=1))
        ws.row_dimensions[row].height = 18
        row += 1

    return row   # first blank row after banner


# ---------------------------------------------------------------------------
# Helper: write a teal section header (merged across cols)
# ---------------------------------------------------------------------------
def write_section_header(ws, row, col_start, col_end, label, height=20):
    from openpyxl.utils import get_column_letter
    s = get_column_letter(col_start)
    e = get_column_letter(col_end)
    ws.merge_cells(f"{s}{row}:{e}{row}")
    c = ws.cell(row=row, column=col_start, value=label)
    style_cell(c,
               fill=fill_section,
               font=font_section(10),
               alignment=Alignment(horizontal="left", vertical="center",
                                   indent=1))
    ws.row_dimensions[row].height = height
    return row + 1


# ---------------------------------------------------------------------------
# Helper: write a navy column-header row
# ---------------------------------------------------------------------------
def write_col_headers(ws, row, col_start, headers, widths=None):
    """Write one row of navy column headers.  Returns next row."""
    for i, h in enumerate(headers):
        col = col_start + i
        c = ws.cell(row=row, column=col, value=h)
        style_cell(c,
                   fill=fill_colhdr,
                   font=font_colhdr(9),
                   alignment=align_center,
                   border=border_thin)
        if widths and i < len(widths):
            ws.column_dimensions[get_column_letter(col)].width = widths[i]
    ws.row_dimensions[row].height = 16
    return row + 1


# ---------------------------------------------------------------------------
# Helper: common sheet setup
# ---------------------------------------------------------------------------
def setup_sheet(ws):
    """Hide gridlines and set default row height."""
    ws.sheet_view.showGridLines = False
    ws.sheet_view.zoomScale     = 100
