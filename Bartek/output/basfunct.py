"""
basfunct.py

1-to-1 port of VBA base functions from:
- mConstants
- mCommValues
- mPresentValues

Data access:
- Uses pandas to load tables.csv (MortalityTables extract).
- Other CSVs are supported via helper loaders for future steps.

Conventions:
- Excel ROUND (half-up) implemented via decimal quantize.
- Caching mirrors VBA: Dx/Cx/Nx/Mx/Rx are cached by scalar key.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# ----------------------------
# Constants (from mConstants)
# ----------------------------
round_lx: int = 16
round_tx: int = 16
round_Dx: int = 16
round_Cx: int = 16
round_Nx: int = 16
round_Mx: int = 16
round_Rx: int = 16
max_Age: int = 123

# ----------------------------
# Data directory / loaders
# ----------------------------


def _default_data_dir() -> Path:
    """
    Prefer data files next to this module (repo layout: /Bartek/output).
    Fallback to /mnt/data (LLM sandbox).
    """
    here = Path(__file__).resolve().parent
    if (here / "tables.csv").exists():
        return here
    mnt = Path("/mnt/data")
    return mnt


_DATA_DIR: Path = _default_data_dir()
_tables_df: Optional[pd.DataFrame] = None
_tables_header: Optional[List[str]] = None
_tables_data: Optional[pd.DataFrame] = None


def set_data_dir(path: str | Path) -> None:
    """Set directory containing tables.csv (and optionally other CSVs)."""
    global _DATA_DIR, _tables_df, _tables_header, _tables_data
    _DATA_DIR = Path(path).resolve()
    _tables_df = None
    _tables_header = None
    _tables_data = None


def _load_tables() -> Tuple[List[str], pd.DataFrame]:
    """
    Load mortality tables from tables.csv.

    Expected extraction structure (Task 3, clarified):
    - CSV header row contains column names from Excel row 3:
        x/y, DAV1994_T_M, DAV1994_T_F, DAV2008_T_M, DAV2008_T_F
    - Data starts in Excel row 4 -> CSV first data row (age 0, qx values).

    Returns:
        (table_names, data_df)
        table_names: list of qx column names (excluding the age column)
        data_df: rows for ages and numeric qx values; columns include:
                 "Age" + each table name column
    """
    global _tables_df, _tables_header, _tables_data
    if _tables_header is not None and _tables_data is not None:
        return _tables_header, _tables_data

    path = _DATA_DIR / "tables.csv"
    if not path.exists():
        raise FileNotFoundError(f"tables.csv not found in data dir: {_DATA_DIR}")

    df = pd.read_csv(path, dtype=str).fillna("")
    if df.shape[0] < 1:
        raise ValueError("tables.csv must contain at least 1 data row.")
    if df.shape[1] < 2:
        raise ValueError("tables.csv must contain an age column plus at least one qx column.")

    # First column is the age axis (e.g. 'x/y'); remaining columns are table vectors.
    age_col = df.columns[0]
    qx_cols = list(df.columns[1:])
    if len(qx_cols) < 1:
        raise ValueError("tables.csv must contain at least one qx column.")

    table_names = [str(c).strip() for c in qx_cols]

    data = df.copy()
    data[age_col] = data[age_col].astype(str).str.strip()
    data = data.rename(columns={age_col: "Age"})

    # Convert qx columns to numeric
    for c in qx_cols:
        data[c] = pd.to_numeric(data[c].astype(str).str.replace(",", ".", regex=False), errors="coerce")

    _tables_df = df
    _tables_header = table_names
    _tables_data = data
    return table_names, data


def _load_name_value_csv(filename: str) -> Dict[str, str]:
    """
    Load Name/Value CSV into dict; included to satisfy 'available data sources' rule.
    """
    path = _DATA_DIR / filename
    if not path.exists():
        return {}
    df = pd.read_csv(path, dtype=str).fillna("")
    if "Name" not in df.columns or "Value" not in df.columns:
        return {}
    return {str(n).strip(): str(v).strip() for n, v in zip(df["Name"], df["Value"])}


# ----------------------------
# Excel-like ROUND (half-up)
# ----------------------------


def excel_round(x: float, digits: int) -> float:
    """
    Excel ROUND uses half-up (away from 0 at .5), unlike Python's bankers rounding.
    """
    if digits >= 0:
        q = Decimal("1").scaleb(-digits)  # 10^-digits
    else:
        q = Decimal("1").scaleb(-digits)  # still works for negative digits
    d = Decimal(str(x)).quantize(q, rounding=ROUND_HALF_UP)
    return float(d)


# ----------------------------
# Cache (from mCommValues)
# ----------------------------

cache: Optional[Dict[str, float]] = None


def InitializeCache() -> None:
    """VBA: InitializeCache creates Scripting.Dictionary."""
    global cache
    cache = {}


def BuildCacheKey(
    Kind: str,
    Age: int,
    Sex: str,
    TableId: str,
    InterestRate: float,
    BirthYear: int,
    RetirementAge: int,
    Layer: int,
) -> str:
    return f"{Kind}_{Age}_{Sex}_{TableId}_{InterestRate}_{BirthYear}_{RetirementAge}_{Layer}"


# ----------------------------
# mCommValues – mortality / commutation
# ----------------------------


def Act_qx(
    Age: int,
    Sex: str,
    TableId: str,
    BirthYear: int = 0,
    RetirementAge: int = 0,
    Layer: int = 1,
) -> float:
    """
    VBA:
      Act_qx = Index(m_Tables, Age+1, Match(tableVector, v_Tables, 0))
    """
    _, _ = BirthYear, RetirementAge  # kept for signature parity
    _ = Layer

    sex = (Sex or "").strip().upper()
    if sex != "M":
        sex = "F"

    table_id = (TableId or "").strip().upper()
    if table_id not in {"DAV1994_T", "DAV2008_T"}:
        # VBA: Act_qx = 1#; Error(1)
        raise ValueError(f"TableId not implemented: {TableId!r}")

    table_vector = f"{table_id}_{sex}"

    table_names, data = _load_tables()
    try:
        col_idx = table_names.index(table_vector)
    except ValueError as e:
        raise KeyError(f"Table vector not found in tables.csv header row: {table_vector!r}") from e

    col = table_names[col_idx]

    # Prefer explicit ages if present; else positional (Age=0 -> first data row)
    age_series = pd.to_numeric(data["Age"], errors="coerce")
    if age_series.notna().any():
        matches = data.loc[age_series == Age, col]
        if matches.empty:
            raise IndexError(f"Age {Age} not found in tables.csv age column.")
        val = float(matches.iloc[0])
    else:
        if Age < 0 or Age >= len(data):
            raise IndexError(f"Age {Age} out of bounds for mortality table rows.")
        val = float(data.iloc[Age][col])

    return val


def Vec_lx(
    EndAge: int,
    Sex: str,
    TableId: str,
    BirthYear: int = 0,
    RetirementAge: int = 0,
    Layer: int = 1,
) -> List[float]:
    """Creates vector of lx. If EndAge = -1 then up to max_Age."""
    limit = max_Age if EndAge == -1 else EndAge
    vec: List[float] = [0.0] * (limit + 1)

    vec[0] = 1_000_000.0
    for i in range(1, limit + 1):
        qx = Act_qx(i - 1, Sex, TableId, BirthYear, RetirementAge, Layer)
        vec[i] = vec[i - 1] * (1.0 - qx)
        vec[i] = excel_round(vec[i], round_lx)

    return vec


def Act_lx(
    Age: int,
    Sex: str,
    TableId: str,
    BirthYear: int = 0,
    RetirementAge: int = 0,
    Layer: int = 1,
) -> float:
    vec = Vec_lx(Age, Sex, TableId, BirthYear, RetirementAge, Layer)
    return float(vec[Age])


def Vec_tx(
    EndAge: int,
    Sex: str,
    TableId: str,
    BirthYear: int = 0,
    RetirementAge: int = 0,
    Layer: int = 1,
) -> List[float]:
    """Creates vector of tx (# deaths)."""
    limit = max_Age if EndAge == -1 else EndAge
    vec: List[float] = [0.0] * (limit + 1)

    tempLx = Vec_lx(limit, Sex, TableId, BirthYear, RetirementAge, Layer)
    for i in range(0, limit):
        vec[i] = tempLx[i] - tempLx[i + 1]
        vec[i] = excel_round(vec[i], round_tx)

    return vec


def Act_tx(
    Age: int,
    Sex: str,
    TableId: str,
    BirthYear: int = 0,
    RetirementAge: int = 0,
    Layer: int = 1,
) -> float:
    vec = Vec_tx(Age, Sex, TableId, BirthYear, RetirementAge, Layer)
    return float(vec[Age])


def Vec_Dx(
    EndAge: int,
    Sex: str,
    TableId: str,
    InterestRate: float,
    BirthYear: int = 0,
    RetirementAge: int = 0,
    Layer: int = 1,
) -> List[float]:
    """Creates vector of Dx."""
    limit = max_Age if EndAge == -1 else EndAge
    vec: List[float] = [0.0] * (limit + 1)

    v = 1.0 / (1.0 + InterestRate)
    tempLx = Vec_lx(limit, Sex, TableId, BirthYear, RetirementAge, Layer)
    for i in range(0, limit + 1):
        vec[i] = tempLx[i] * (v**i)
        vec[i] = excel_round(vec[i], round_Dx)

    return vec


def Act_Dx(
    Age: int,
    Sex: str,
    TableId: str,
    InterestRate: float,
    BirthYear: int = 0,
    RetirementAge: int = 0,
    Layer: int = 1,
) -> float:
    global cache
    if cache is None:
        InitializeCache()

    key = BuildCacheKey("Dx", Age, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
    if key in cache:
        return float(cache[key])

    vec = Vec_Dx(Age, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
    res = float(vec[Age])
    cache[key] = res
    return res


def Vec_Cx(
    EndAge: int,
    Sex: str,
    TableId: str,
    InterestRate: float,
    BirthYear: int = 0,
    RetirementAge: int = 0,
    Layer: int = 1,
) -> List[float]:
    """Creates vector of Cx."""
    limit = max_Age if EndAge == -1 else EndAge
    vec: List[float] = [0.0] * (limit + 1)

    v = 1.0 / (1.0 + InterestRate)
    tempTx = Vec_tx(limit, Sex, TableId, BirthYear, RetirementAge, Layer)
    for i in range(0, limit):
        vec[i] = tempTx[i] * (v ** (i + 1))
        vec[i] = excel_round(vec[i], round_Cx)

    return vec


def Act_Cx(
    Age: int,
    Sex: str,
    TableId: str,
    InterestRate: float,
    BirthYear: int = 0,
    RetirementAge: int = 0,
    Layer: int = 1,
) -> float:
    global cache
    if cache is None:
        InitializeCache()

    key = BuildCacheKey("Cx", Age, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
    if key in cache:
        return float(cache[key])

    vec = Vec_Cx(Age, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
    res = float(vec[Age])
    cache[key] = res
    return res


def Vec_Nx(
    Sex: str,
    TableId: str,
    InterestRate: float,
    BirthYear: int = 0,
    RetirementAge: int = 0,
    Layer: int = 1,
) -> List[float]:
    """Creates vector of Nx."""
    vec: List[float] = [0.0] * (max_Age + 1)
    tempDx = Vec_Dx(-1, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)

    vec[max_Age] = tempDx[max_Age]
    for i in range(max_Age - 1, -1, -1):
        vec[i] = vec[i + 1] + tempDx[i]
        vec[i] = excel_round(vec[i], round_Dx)  # kept as in original

    return vec


def Act_Nx(
    Age: int,
    Sex: str,
    TableId: str,
    InterestRate: float,
    BirthYear: int = 0,
    RetirementAge: int = 0,
    Layer: int = 1,
) -> float:
    global cache
    if cache is None:
        InitializeCache()

    key = BuildCacheKey("Nx", Age, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
    if key in cache:
        return float(cache[key])

    vec = Vec_Nx(Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
    res = float(vec[Age])
    cache[key] = res
    return res


def Vec_Mx(
    Sex: str,
    TableId: str,
    InterestRate: float,
    BirthYear: int = 0,
    RetirementAge: int = 0,
    Layer: int = 1,
) -> List[float]:
    """Creates vector of Mx."""
    vec: List[float] = [0.0] * (max_Age + 1)
    tempCx = Vec_Cx(-1, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)

    # Note: in VBA, tempCx(max_Age) exists because Vec_Cx redims to max_Age
    vec[max_Age] = float(tempCx[max_Age]) if max_Age < len(tempCx) else 0.0
    for i in range(max_Age - 1, -1, -1):
        vec[i] = vec[i + 1] + tempCx[i]
        vec[i] = excel_round(vec[i], round_Mx)

    return vec


def Act_Mx(
    Age: int,
    Sex: str,
    TableId: str,
    InterestRate: float,
    BirthYear: int = 0,
    RetirementAge: int = 0,
    Layer: int = 1,
) -> float:
    global cache
    if cache is None:
        InitializeCache()

    key = BuildCacheKey("Mx", Age, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
    if key in cache:
        return float(cache[key])

    vec = Vec_Mx(Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
    res = float(vec[Age])
    cache[key] = res
    return res


def Vec_Rx(
    Sex: str,
    TableId: str,
    InterestRate: float,
    BirthYear: int = 0,
    RetirementAge: int = 0,
    Layer: int = 1,
) -> List[float]:
    """Creates vector of Rx."""
    vec: List[float] = [0.0] * (max_Age + 1)
    tempMx = Vec_Mx(Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)

    vec[max_Age] = tempMx[max_Age]
    for i in range(max_Age - 1, -1, -1):
        vec[i] = vec[i + 1] + tempMx[i]
        vec[i] = excel_round(vec[i], round_Rx)

    return vec


def Act_Rx(
    Age: int,
    Sex: str,
    TableId: str,
    InterestRate: float,
    BirthYear: int = 0,
    RetirementAge: int = 0,
    Layer: int = 1,
) -> float:
    global cache
    if cache is None:
        InitializeCache()

    key = BuildCacheKey("Rx", Age, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
    if key in cache:
        return float(cache[key])

    vec = Vec_Rx(Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
    res = float(vec[Age])
    cache[key] = res
    return res


def Act_AgeCalculation(BirthDate: date, ValuationDate: date, Method: str) -> int:
    """Age calculation based on calendar-year method (K) or half-year method (H)."""
    method = (Method or "").strip().upper()
    if method != "K":
        method = "H"

    yBirth = BirthDate.year
    yVal = ValuationDate.year
    mBirth = BirthDate.month
    mVal = ValuationDate.month

    if method == "K":
        return int(yVal - yBirth)

    # VBA Int() is floor for positive values; here yVal-yBirth is typically positive.
    return int((yVal - yBirth) + (1.0 / 12.0) * (mVal - mBirth + 5))


# ----------------------------
# mPresentValues – PV factors
# ----------------------------


def Act_ax_k(
    Age: int,
    Sex: str,
    TableId: str,
    InterestRate: float,
    k: int,
    BirthYear: int = 0,
    RetirementAge: int = 0,
    Layer: int = 1,
) -> float:
    if k > 0:
        return (
            Act_Nx(Age, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
            / Act_Dx(Age, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
            - Act_DeductionTerm(k, InterestRate)
        )
    return 0.0


def Act_axn_k(
    Age: int,
    n: int,
    Sex: str,
    TableId: str,
    InterestRate: float,
    k: int,
    BirthYear: int = 0,
    RetirementAge: int = 0,
    Layer: int = 1,
) -> float:
    if k > 0:
        NxA = Act_Nx(Age, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
        NxAn = Act_Nx(Age + n, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
        DxA = Act_Dx(Age, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
        DxAn = Act_Dx(Age + n, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
        ded = Act_DeductionTerm(k, InterestRate)
        return (NxA - NxAn) / DxA - ded * (1.0 - DxAn / DxA)
    return 0.0


def Act_nax_k(
    Age: int,
    n: int,
    Sex: str,
    TableId: str,
    InterestRate: float,
    k: int,
    BirthYear: int = 0,
    RetirementAge: int = 0,
    Layer: int = 1,
) -> float:
    if k > 0:
        return (
            Act_Dx(Age + n, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
            / Act_Dx(Age, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
            * Act_ax_k(Age + n, Sex, TableId, InterestRate, k, BirthYear, RetirementAge, Layer)
        )
    return 0.0


def act_nGrAx(
    Age: int,
    n: int,
    Sex: str,
    TableId: str,
    InterestRate: float,
    BirthYear: int = 0,
    RetirementAge: int = 0,
    Layer: int = 1,
) -> float:
    return (
        (Act_Mx(Age, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
         - Act_Mx(Age + n, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer))
        / Act_Dx(Age, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
    )


def act_nGrEx(
    Age: int,
    n: int,
    Sex: str,
    TableId: str,
    InterestRate: float,
    BirthYear: int = 0,
    RetirementAge: int = 0,
    Layer: int = 1,
) -> float:
    return (
        Act_Dx(Age + n, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
        / Act_Dx(Age, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
    )


def Act_ag_k(g: int, InterestRate: float, k: int) -> float:
    v = 1.0 / (1.0 + InterestRate)
    if k > 0:
        if InterestRate > 0:
            return (1.0 - v**g) / (1.0 - v) - Act_DeductionTerm(k, InterestRate) * (1.0 - v**g)
        return float(g)
    return 0.0


def Act_DeductionTerm(k: int, InterestRate: float) -> float:
    """Deduction term."""
    res = 0.0
    if k > 0:
        for l in range(0, k):
            res += (l / k) / (1.0 + (l / k) * InterestRate)
        res = res * (1.0 + InterestRate) / k
    return res
