#!/usr/bin/env python3
"""
data_extract.py

TASK 3 – Extract data blocks from exported Excel context CSVs.

Update (per your clarification):
- tables.csv – MortalityTable from sheet "MortalityTables", columns A–E
  - headers are in row 3  (MortalityTables!A3:E3)
  - data starts in row 4  (MortalityTables!A4:E...)

Other outputs (unchanged):
- var.csv    – Calculation!A4:B9   (Name, Value)
- tariff.csv – Calculation!D4:E11  (Name, Value)
- limits.csv – Calculation!G4:H5   (Name, Value)
- tariff.py  – ModalSurcharge(PayFreq) from Calculation!E12

Inputs:
- excelcell.csv
- excelrange.csv (loaded for completeness)

Outputs go to --outdir (default: directory of this script, e.g. /Bartek/output)
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd

ADDR_RE = re.compile(r"^([A-Z]+)(\d+)$")


def _script_dir() -> Path:
    return Path(__file__).resolve().parent


def _default_in_path(filename: str) -> Path:
    local = _script_dir() / filename
    if local.exists():
        return local
    return (Path("/mnt/data") / filename).resolve()


def _parse_a1(addr: str) -> Tuple[str, int]:
    m = ADDR_RE.match(addr.strip().upper())
    if not m:
        raise ValueError(f"Invalid A1 address: {addr!r}")
    return m.group(1), int(m.group(2))


def _col_to_num(col: str) -> int:
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n


def _num_to_col(n: int) -> str:
    out = []
    while n > 0:
        n, rem = divmod(n - 1, 26)
        out.append(chr(rem + ord("A")))
    return "".join(reversed(out))


def _a1(col: str, row: int) -> str:
    return f"{col}{row}"


def _write_csv_rows(path: Path, header: Iterable[str], rows: Iterable[Iterable[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(list(header))
        for r in rows:
            w.writerow(list(r))


def _build_cell_map(excelcell: pd.DataFrame) -> Dict[Tuple[str, str], str]:
    m: Dict[Tuple[str, str], str] = {}
    for _, r in excelcell.iterrows():
        sheet = str(r.get("Sheet", "")).strip()
        addr = str(r.get("Address", "")).strip().upper()
        val = r.get("Value", "")
        val_str = "" if pd.isna(val) else str(val)
        if sheet and addr:
            m[(sheet, addr)] = val_str
    return m


def _get_val(cell_map: Dict[Tuple[str, str], str], sheet: str, addr: str) -> str:
    return cell_map.get((sheet, addr.upper()), "")


def _extract_name_value_block(
    cell_map: Dict[Tuple[str, str], str],
    sheet: str,
    left_col: str,
    right_col: str,
    row_start: int,
    row_end: int,
) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for r in range(row_start, row_end + 1):
        name = _get_val(cell_map, sheet, _a1(left_col, r)).strip()
        value = _get_val(cell_map, sheet, _a1(right_col, r)).strip()
        if not name:
            continue
        out.append((name, value))
    return out


def _extract_rect(
    excelcell: pd.DataFrame,
    sheet: str,
    col_start: str,
    col_end: str,
    row_start: int,
    row_end: Optional[int] = None,
) -> pd.DataFrame:
    """
    Extract a rectangular area from excelcell as a DataFrame with columns = A..E (or specified range).
    If row_end is None, extracts all rows >= row_start that have any non-empty value in the selected columns.
    """
    df = excelcell[excelcell["Sheet"].astype(str).str.strip() == sheet].copy()
    if df.empty:
        cols = [_num_to_col(i) for i in range(_col_to_num(col_start), _col_to_num(col_end) + 1)]
        return pd.DataFrame(columns=cols)

    parsed = df["Address"].astype(str).str.upper().str.strip().apply(_parse_a1)
    df["Col"] = parsed.apply(lambda t: t[0])
    df["Row"] = parsed.apply(lambda t: t[1])

    c0 = _col_to_num(col_start)
    c1 = _col_to_num(col_end)
    cols = [_num_to_col(i) for i in range(c0, c1 + 1)]

    df = df[df["Col"].isin(cols)].copy()
    if row_end is None:
        df = df[df["Row"] >= row_start].copy()
    else:
        df = df[(df["Row"] >= row_start) & (df["Row"] <= row_end)].copy()

    if df.empty:
        return pd.DataFrame(columns=cols)

    df["ValueStr"] = df["Value"].apply(lambda v: "" if pd.isna(v) else str(v))
    pivot = df.pivot_table(index="Row", columns="Col", values="ValueStr", aggfunc="first")

    for c in cols:
        if c not in pivot.columns:
            pivot[c] = ""
    pivot = pivot[cols].sort_index()

    pivot = pivot.replace({pd.NA: "", None: ""})
    nonempty_mask = (pivot.applymap(lambda x: str(x).strip() != "")).any(axis=1)
    pivot = pivot[nonempty_mask].copy()

    pivot.reset_index(drop=True, inplace=True)
    pivot.columns.name = None
    return pivot


def _extract_mortality_tables_with_row3_headers(excelcell: pd.DataFrame) -> pd.DataFrame:
    """
    MortalityTables sheet:
    - headers in row 3 (A3:E3)
    - data from row 4 (A4:E...)
    Output CSV should have those header labels as column names.
    """
    header_df = _extract_rect(excelcell, sheet="MortalityTables", col_start="A", col_end="E", row_start=3, row_end=3)
    data_df = _extract_rect(excelcell, sheet="MortalityTables", col_start="A", col_end="E", row_start=4, row_end=None)

    cols = ["A", "B", "C", "D", "E"]
    if header_df.empty:
        header_labels = cols[:]  # fallback
    else:
        row = header_df.iloc[0]
        header_labels = []
        for c in cols:
            lbl = str(row.get(c, "")).strip()
            header_labels.append(lbl if lbl else c)

    # Ensure data_df has the A..E columns
    for c in cols:
        if c not in data_df.columns:
            data_df[c] = ""

    out = data_df[cols].copy()
    out.columns = header_labels

    return out


def _extract_e12_formula(excelcell: pd.DataFrame) -> Optional[str]:
    m = excelcell[
        (excelcell["Sheet"].astype(str).str.strip() == "Calculation")
        & (excelcell["Address"].astype(str).str.upper().str.strip() == "E12")
    ]
    if m.empty:
        return None
    f = m.iloc[0].get("Formula", "")
    if pd.isna(f):
        return None
    return str(f)


def _write_tariff_py(out_path: Path, e12_formula: Optional[str]) -> None:
    # Keep explicit implementation for now (matches exported Excel formula used in earlier steps)
    expected = "=IF(PayFreq=2,2%,IF(PayFreq=4,3%,IF(PayFreq=12,5%,0)))"
    formula_note = (e12_formula or "").strip()
    if formula_note.startswith("'="):
        formula_note = formula_note[1:]

    code = f'''"""
tariff.py

Auto-generated from Excel export.

Source cell:
- Calculation!E12 formula: {formula_note!r}

Implements:
- ModalSurcharge(PayFreq)
"""

from __future__ import annotations


def ModalSurcharge(PayFreq: int | float) -> float:
    """
    Port of Excel Calculation!E12.

    Excel formula (expected):
      {expected}

    Returns a modal surcharge (as decimal, e.g. 0.05 == 5%).
    """
    try:
        pf = int(PayFreq)
    except Exception:
        pf = int(float(PayFreq))

    if pf == 2:
        return 0.02
    if pf == 4:
        return 0.03
    if pf == 12:
        return 0.05
    return 0.0
'''
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(code, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract calculator data blocks from excelcell/excelrange CSV exports.")
    parser.add_argument("--excelcell", type=str, default="", help="Path to excelcell.csv")
    parser.add_argument("--excelrange", type=str, default="", help="Path to excelrange.csv")
    parser.add_argument("--outdir", type=str, default="", help="Output directory (defaults to script directory)")
    args = parser.parse_args()

    excelcell_path = Path(args.excelcell).resolve() if args.excelcell else _default_in_path("excelcell.csv")
    excelrange_path = Path(args.excelrange).resolve() if args.excelrange else _default_in_path("excelrange.csv")
    out_dir = Path(args.outdir).resolve() if args.outdir else _script_dir()

    if not excelcell_path.exists():
        raise SystemExit(f"ERROR: excelcell.csv not found: {excelcell_path}")
    if not excelrange_path.exists():
        raise SystemExit(f"ERROR: excelrange.csv not found: {excelrange_path}")

    excelcell = pd.read_csv(excelcell_path)
    _ = pd.read_csv(excelrange_path)  # exists; currently not needed for these blocks

    cell_map = _build_cell_map(excelcell)

    # var.csv – Calculation A4:B9
    var_rows = _extract_name_value_block(cell_map, "Calculation", "A", "B", 4, 9)
    _write_csv_rows(out_dir / "var.csv", header=("Name", "Value"), rows=var_rows)

    # tariff.csv – Calculation D4:E11
    tariff_rows = _extract_name_value_block(cell_map, "Calculation", "D", "E", 4, 11)
    _write_csv_rows(out_dir / "tariff.csv", header=("Name", "Value"), rows=tariff_rows)

    # limits.csv – Calculation G4:H5
    limits_rows = _extract_name_value_block(cell_map, "Calculation", "G", "H", 4, 5)
    _write_csv_rows(out_dir / "limits.csv", header=("Name", "Value"), rows=limits_rows)

    # tables.csv – MortalityTables A:E, headers row 3, data from row 4
    tables_df = _extract_mortality_tables_with_row3_headers(excelcell)
    (out_dir / "tables.csv").parent.mkdir(parents=True, exist_ok=True)
    tables_df.to_csv(out_dir / "tables.csv", index=False, encoding="utf-8", lineterminator="\n")

    # tariff.py – ModalSurcharge(PayFreq) from Calculation!E12 formula
    e12_formula = _extract_e12_formula(excelcell)
    _write_tariff_py(out_dir / "tariff.py", e12_formula)

    print(f"Wrote: {out_dir / 'var.csv'} ({len(var_rows)} rows)")
    print(f"Wrote: {out_dir / 'tariff.csv'} ({len(tariff_rows)} rows)")
    print(f"Wrote: {out_dir / 'limits.csv'} ({len(limits_rows)} rows)")
    print(f"Wrote: {out_dir / 'tables.csv'} ({len(tables_df)} rows) [headers from MortalityTables row 3]")
    print(f"Wrote: {out_dir / 'tariff.py'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
