"""
DASHBOARD sheet — KPI cards and bar chart of occupied volume per system.
"""
from openpyxl.utils import get_column_letter
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.styles import Font, Alignment, PatternFill
from styles import (
    setup_sheet, write_title_banner, write_section_header,
    style_cell, fill_inc, fill_col, fill_conf, fill_formula, fill_section,
    font_body, font_formula, font_inc,
    align_left, align_center, align_right, border_thin,
    FMT_INT, FMT_DEC2,
    C_INC_FONT, C_COL_FONT, C_CONF_FONT, C_WHITE, C_TITLE
)


def build(ws,
          system_data:   list,
          hw_refs:       dict,
          collision_count: int,
          conflict_count:  int,
          main_refs:     dict):
    setup_sheet(ws)

    # Column widths
    for col, w in [("A", 3), ("B", 22), ("C", 18), ("D", 4),
                   ("E", 22), ("F", 18), ("G", 4),
                   ("H", 22), ("I", 18), ("J", 4),
                   ("K", 22), ("L", 18)]:
        ws.column_dimensions[col].width = w

    next_row = write_title_banner(
        ws, row=1, col_start=2, col_end=12,
        title="DASHBOARD",
        subtitle="Key metrics — values update automatically when Include? flags change in MAIN",
        title_size=18, row_height=36
    )
    next_row += 1

    # -----------------------------------------------------------------------
    # KPI cards — 4 cards in a row (2 cols each: label + value)
    # -----------------------------------------------------------------------
    kpi_data = [
        ("Source Systems",   len(system_data),        fill_section,   C_WHITE,     FMT_INT),
        ("Collisions",       collision_count,          fill_col,       C_COL_FONT,  FMT_INT),
        ("Conflicts",        conflict_count,           fill_conf,      C_CONF_FONT, FMT_INT),
        ("Target Size (GB)", f"=HARDWARE_SIZING!{hw_refs['total_target_gb_cell']}",
                                                       fill_inc,       C_INC_FONT,  FMT_DEC2),
    ]

    card_cols = [(2, 3), (5, 6), (8, 9), (11, 12)]

    for (lc, vc), (label, value, kpi_fill, kpi_fcolor, kpi_fmt) in zip(card_cols, kpi_data):
        # Label cell
        lbl = ws.cell(row=next_row, column=lc, value=label)
        style_cell(lbl, fill=fill_section,
                   font=Font(name="Arial", bold=True, color=C_WHITE, size=9),
                   alignment=align_center, border=border_thin)

        # Value cell
        val = ws.cell(row=next_row, column=vc, value=value)
        style_cell(val, fill=kpi_fill,
                   font=Font(name="Arial", bold=True, color=kpi_fcolor, size=14),
                   alignment=align_center, border=border_thin,
                   number_format=kpi_fmt)

        ws.row_dimensions[next_row].height = 36

    next_row += 2

    # -----------------------------------------------------------------------
    # Occupied volume table (used as chart data source)
    # -----------------------------------------------------------------------
    next_row = write_section_header(ws, next_row, 2, 12,
                                    "OCCUPIED VOLUME PER SOURCE SYSTEM (GB)")

    # Header
    ws.cell(row=next_row, column=2, value="System-Client")
    ws.cell(row=next_row, column=2).fill      = PatternFill("solid", fgColor="2E4057")
    ws.cell(row=next_row, column=2).font      = Font(name="Arial", bold=True,
                                                     color=C_WHITE, size=9)
    ws.cell(row=next_row, column=2).alignment = align_center
    ws.cell(row=next_row, column=2).border    = border_thin

    ws.cell(row=next_row, column=3, value="Occupied Vol (GB)")
    ws.cell(row=next_row, column=3).fill      = PatternFill("solid", fgColor="2E4057")
    ws.cell(row=next_row, column=3).font      = Font(name="Arial", bold=True,
                                                     color=C_WHITE, size=9)
    ws.cell(row=next_row, column=3).alignment = align_center
    ws.cell(row=next_row, column=3).border    = border_thin
    ws.row_dimensions[next_row].height = 16

    chart_header_row = next_row
    next_row += 1
    chart_data_start = next_row

    for row_data in sorted(system_data, key=lambda r: r["sidclnt"]):
        occ_gb = round((row_data.get("occupied_vol") or 0) / 1024, 2)
        ws.cell(row=next_row, column=2, value=row_data["sidclnt"])
        style_cell(ws.cell(row=next_row, column=2),
                   font=font_body(9), alignment=align_center, border=border_thin)
        ws.cell(row=next_row, column=3, value=occ_gb)
        style_cell(ws.cell(row=next_row, column=3),
                   fill=fill_formula, font=font_formula(9),
                   alignment=align_right, border=border_thin, number_format=FMT_DEC2)
        ws.row_dimensions[next_row].height = 15
        next_row += 1

    chart_data_end = next_row - 1

    # -----------------------------------------------------------------------
    # Bar chart — occupied volume per system
    # -----------------------------------------------------------------------
    chart = BarChart()
    chart.type        = "col"
    chart.grouping    = "clustered"
    chart.title       = "Occupied Volume per Source System (GB)"
    chart.y_axis.title = "GB"
    chart.x_axis.title = "System-Client"
    chart.style       = 10
    chart.width       = 20
    chart.height      = 12

    # Data = occupied vol column (col 3 = C)
    data_ref = Reference(ws,
                         min_col=3, min_row=chart_header_row,
                         max_col=3, max_row=chart_data_end)
    # Categories = system names (col 2 = B)
    cats_ref = Reference(ws,
                         min_col=2, min_row=chart_data_start,
                         max_col=2, max_row=chart_data_end)

    chart.add_data(data_ref, titles_from_data=True)
    chart.set_categories(cats_ref)

    # Place chart to the right of the data table
    ws.add_chart(chart, f"E{chart_header_row}")

    # -----------------------------------------------------------------------
    # Q5 mirror: per-system included source size (formula refs to SUMMARY)
    # -----------------------------------------------------------------------
    next_row = max(next_row, chart_header_row + 22)
    next_row += 2
    next_row = write_section_header(ws, next_row, 2, 6,
                                    "INCLUDED SOURCE SIZE PER SYSTEM (GB) — from SUMMARY")
    ws.merge_cells(f"B{next_row}:F{next_row}")
    ws.cell(row=next_row, column=2,
            value="See SUMMARY sheet Q5 for the full per-system breakdown.")
    ws.cell(row=next_row, column=2).font = font_body(9, italic=True)
    ws.cell(row=next_row, column=2).alignment = align_left
