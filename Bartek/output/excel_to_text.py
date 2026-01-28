#!/usr/bin/env python3
"""
excel_to_text.py

Export non-empty Excel cells (formula + value) and named ranges to CSV.

Default layout for your repo:
- Project root contains folder: /Bartek
- Excel file is located in: /Bartek/input/Tariff_Calculator.xlsm
- This script is located in: /Bartek/output/excel_to_text.py
- Outputs are written to: /Bartek/output (same directory as this script):
  - excelcell.csv  columns: Sheet, Address, Formula, Value
  - excelrange.csv columns: Sheet, Name, Address

Requirements:
- xlwings (needs local Excel)
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional, Tuple

import xlwings as xw
from openpyxl.utils import get_column_letter


@dataclass(frozen=True)
class CellRow:
    sheet: str
    address: str
    formula: str
    value: str


@dataclass(frozen=True)
class RangeRow:
    sheet: str
    name: str
    address: str


def _stringify_value(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        return str(v)
    return str(v)


def _norm_2d(m: Any) -> list[list[Any]]:
    if m is None:
        return []
    if isinstance(m, (list, tuple)):
        if not m:
            return []
        if not isinstance(m[0], (list, tuple)):
            return [list(m)]
        return [list(r) for r in m]
    return [[m]]


def _a1_address(row: int, col: int) -> str:
    return f"{get_column_letter(col)}{row}"


def _is_empty_cell(formula: Any, value: Any) -> bool:
    f = "" if formula is None else str(formula)
    v = "" if value is None else str(value)
    return (f.strip() == "") and (v.strip() == "")


def _safe_has_array(cell_api: Any) -> bool:
    try:
        return bool(cell_api.HasArray)
    except Exception:
        return False


def _safe_formula_array(cell_api: Any) -> Optional[str]:
    try:
        fa = cell_api.FormulaArray
        if fa is None:
            return None
        return str(fa)
    except Exception:
        return None


def _safe_formula(cell_api: Any) -> Optional[str]:
    for attr in ("Formula2", "Formula"):
        try:
            val = getattr(cell_api, attr)
            if val is None:
                continue
            return str(val)
        except Exception:
            continue
    return None


def export_cells(book: xw.Book) -> list[CellRow]:
    rows: list[CellRow] = []

    for sh in book.sheets:
        sheet_name = sh.name
        try:
            used = sh.api.UsedRange
            start_row = int(used.Row)
            start_col = int(used.Column)
            n_rows = int(used.Rows.Count)
            n_cols = int(used.Columns.Count)
        except Exception:
            continue

        if n_rows <= 0 or n_cols <= 0:
            continue

        # Bulk read
        try:
            rng = sh.range(
                (start_row, start_col),
                (start_row + n_rows - 1, start_col + n_cols - 1),
            )
            values_2d = _norm_2d(rng.value)
            formulas_2d = _norm_2d(rng.formula)
        except Exception:
            values_2d = []
            formulas_2d = []

        if not values_2d or not formulas_2d:
            # Per-cell fallback
            for r in range(start_row, start_row + n_rows):
                for c in range(start_col, start_col + n_cols):
                    try:
                        cell = sh.range((r, c))
                        val = cell.value
                        f = _safe_formula(cell.api) or ""
                        if _is_empty_cell(f, val):
                            continue
                        if _safe_has_array(cell.api):
                            fa = _safe_formula_array(cell.api)
                            if fa:
                                f = fa
                        rows.append(CellRow(sheet_name, _a1_address(r, c), f, _stringify_value(val)))
                    except Exception:
                        continue
            continue

        # Bulk iteration + targeted COM fixes
        for r_off, (val_row, f_row) in enumerate(zip(values_2d, formulas_2d)):
            r = start_row + r_off
            max_len = max(len(val_row), len(f_row))
            for c_off in range(max_len):
                c = start_col + c_off
                val = val_row[c_off] if c_off < len(val_row) else None
                f = f_row[c_off] if c_off < len(f_row) else None

                if _is_empty_cell(f, val):
                    continue

                formula_str = "" if f is None else str(f)

                try:
                    cell_api = sh.range((r, c)).api
                    if _safe_has_array(cell_api):
                        fa = _safe_formula_array(cell_api)
                        if fa:
                            formula_str = fa
                    elif formula_str.strip() == "":
                        com_f = _safe_formula(cell_api)
                        if com_f:
                            formula_str = com_f
                except Exception:
                    pass

                rows.append(CellRow(sheet_name, _a1_address(r, c), formula_str, _stringify_value(val)))

    return rows


def _parse_refers_to(refers_to: str) -> Tuple[str, str]:
    s = (refers_to or "").strip()
    if s.startswith("="):
        s = s[1:].strip()
    if "!" not in s:
        return ("", refers_to or "")
    left, right = s.split("!", 1)
    left = left.strip()
    right = right.strip()
    if left.startswith("'") and left.endswith("'") and len(left) >= 2:
        left = left[1:-1]
    return (left, right)


def export_named_ranges(book: xw.Book) -> list[RangeRow]:
    out: list[RangeRow] = []

    try:
        wb_names = list(book.names)
    except Exception:
        wb_names = []

    for nm in wb_names:
        try:
            name_str = nm.name
        except Exception:
            name_str = ""
        try:
            refers_to = nm.refers_to
        except Exception:
            refers_to = ""

        sheet_name = ""
        address = ""
        try:
            r = nm.refers_to_range
            sheet_name = r.sheet.name
            address = r.api.Address
        except Exception:
            sheet_name, address = _parse_refers_to(refers_to)

        if not (name_str.strip() or address.strip() or sheet_name.strip()):
            continue
        out.append(RangeRow(sheet_name, name_str, address))

    for sh in book.sheets:
        try:
            sh_names = list(sh.names)
        except Exception:
            sh_names = []
        for nm in sh_names:
            try:
                name_str = nm.name
            except Exception:
                name_str = ""
            try:
                refers_to = nm.refers_to
            except Exception:
                refers_to = ""

            sheet_name = sh.name
            address = ""
            try:
                r = nm.refers_to_range
                address = r.api.Address
            except Exception:
                _, address = _parse_refers_to(refers_to)

            if not (name_str.strip() or address.strip()):
                continue
            out.append(RangeRow(sheet_name, name_str, address))

    seen: set[Tuple[str, str, str]] = set()
    deduped: list[RangeRow] = []
    for rr in out:
        key = (rr.sheet, rr.name, rr.address)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(rr)
    return deduped


def write_csv(path: Path, headers: Iterable[str], rows: Iterable[Iterable[Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(list(headers))
        for r in rows:
            w.writerow(list(r))


def _default_excel_path(script_path: Path) -> Path:
    """
    If script is /Bartek/output/excel_to_text.py -> default Excel: /Bartek/input/Tariff_Calculator.xlsm
    Otherwise, fall back to ./input/Tariff_Calculator.xlsm relative to CWD.
    """
    # Prefer repo layout relative to the script itself (robust when run from elsewhere).
    bartek_dir = script_path.parent.parent
    candidate = bartek_dir / "input" / "Tariff_Calculator.xlsm"
    if candidate.exists():
        return candidate.resolve()

    cwd_candidate = Path.cwd() / "input" / "Tariff_Calculator.xlsm"
    return cwd_candidate.resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Excel cell context and named ranges to CSV.")
    parser.add_argument(
        "--excel",
        type=str,
        default="",
        help="Path to the Excel workbook (.xlsm). If omitted, defaults to /Bartek/input/Tariff_Calculator.xlsm based on script location.",
    )
    args = parser.parse_args()

    script_path = Path(__file__).resolve()
    excel_path = Path(args.excel).resolve() if args.excel else _default_excel_path(script_path)

    if not excel_path.exists():
        print(f"ERROR: Excel file not found: {excel_path}", file=sys.stderr)
        print("Tip: pass --excel <path-to-Tariff_Calculator.xlsm>", file=sys.stderr)
        return 2

    out_dir = script_path.parent  # /Bartek/output (all generated artifacts go here)
    cell_csv = out_dir / "excelcell.csv"
    range_csv = out_dir / "excelrange.csv"

    app = xw.App(visible=False, add_book=False)
    try:
        app.display_alerts = False
        app.screen_updating = False
    except Exception:
        pass

    book: Optional[xw.Book] = None
    try:
        book = app.books.open(str(excel_path), update_links=False, read_only=True)

        cell_rows = export_cells(book)
        range_rows = export_named_ranges(book)

        write_csv(
            cell_csv,
            headers=("Sheet", "Address", "Formula", "Value"),
            rows=((r.sheet, r.address, r.formula, r.value) for r in cell_rows),
        )
        write_csv(
            range_csv,
            headers=("Sheet", "Name", "Address"),
            rows=((r.sheet, r.name, r.address) for r in range_rows),
        )

        print(f"Wrote: {cell_csv} ({len(cell_rows)} rows)")
        print(f"Wrote: {range_csv} ({len(range_rows)} rows)")
        return 0
    finally:
        try:
            if book is not None:
                book.close()
        except Exception:
            pass
        try:
            app.quit()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
