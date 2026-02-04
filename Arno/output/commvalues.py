# commvalues.py
"""
Translation of VBA module mCommValues to Python (1:1 behavior as closely as practical).

- Mortality tables are loaded lazily from MortalityTables.xml on first access.
- Caching replicates the VBA Dictionary cache used in Act_Dx / Act_Cx / Act_Nx / Act_Mx / Act_Rx.
"""

from __future__ import annotations

import math
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional

from constants import (
    ROUND_LX,
    ROUND_TX,
    ROUND_DX,
    ROUND_CX,
    ROUND_NX,
    ROUND_MX,
    ROUND_RX,
    MAX_AGE,
)

# --- VBA: Dim cache As Object
cache: Optional[Dict[str, float]] = None

# --- Mortality table storage (lazy-loaded)
_tables_loaded: bool = False
_qx_tables: Dict[str, List[float]] = {}  # key: e.g. "DAV1994_T_M" -> list indexed by age (xy)


# ----------------------------
# Helpers (Excel-like rounding)
# ----------------------------
def _excel_round(value: float, digits: int) -> float:
    """
    Excel/VBA WorksheetFunction.Round uses "half away from zero" (ROUND_HALF_UP).
    Python's round() is bankers rounding, so we emulate Excel with Decimal.
    """
    if digits >= 0:
        quant = Decimal("1").scaleb(-digits)  # 10**(-digits)
    else:
        quant = Decimal("1").scaleb(-digits)  # still works for negative digits

    d = Decimal(str(value))
    return float(d.quantize(quant, rounding=ROUND_HALF_UP))


def InitializeCache() -> None:
    """VBA: Public Sub InitializeCache()"""
    global cache
    cache = {}


def _ensure_cache() -> None:
    global cache
    if cache is None:
        InitializeCache()


def _mortality_xml_path() -> str:
    """
    Resolve MortalityTables.xml from:
      1) same directory as this module
      2) current working directory (fallback)
    """
    here = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(here, "MortalityTables.xml")
    if os.path.isfile(candidate):
        return candidate
    return os.path.join(os.getcwd(), "MortalityTables.xml")


def _parse_float_comma_decimal(text: str) -> float:
    # XML values look like "0,01168700" -> 0.011687
    return float(text.strip().replace(".", "").replace(",", ".") if False else text.strip().replace(",", "."))


def _load_mortality_tables_if_needed() -> None:
    """
    Loads MortalityTables.xml once and fills _qx_tables with vectors indexed by age.
    """
    global _tables_loaded, _qx_tables
    if _tables_loaded:
        return

    path = _mortality_xml_path()
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Mortality table XML not found: {path}")

    tree = ET.parse(path)
    root = tree.getroot()

    # Determine all table columns by scanning first record (excluding 'xy')
    records = list(root.findall("./record"))
    if not records:
        raise ValueError("MortalityTables.xml contains no <record> elements.")

    # Collect all tag names except 'xy'
    table_tags = []
    for child in list(records[0]):
        if child.tag != "xy":
            table_tags.append(child.tag)

    # Initialize arrays sized up to MAX_AGE (or larger if XML has more)
    max_xy = 0
    for rec in records:
        xy_el = rec.find("xy")
        if xy_el is None or xy_el.text is None:
            continue
        max_xy = max(max_xy, int(xy_el.text.strip()))
    size = max(max_xy, MAX_AGE) + 1  # inclusive

    _qx_tables = {tag.upper(): [0.0] * size for tag in table_tags}

    # Fill values
    for rec in records:
        xy_el = rec.find("xy")
        if xy_el is None or xy_el.text is None:
            continue
        age = int(xy_el.text.strip())

        for tag in table_tags:
            el = rec.find(tag)
            if el is None or el.text is None:
                continue
            _qx_tables[tag.upper()][age] = _parse_float_comma_decimal(el.text)

    _tables_loaded = True


# ----------------------------
# Core functions (VBA 1:1)
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
    VBA: Public Function Act_qx(...)
    Reads qx from MortalityTables.
    """
    _load_mortality_tables_if_needed()

    sex = (Sex or "").strip().upper()
    if sex != "M":
        sex = "F"

    table_id = (TableId or "").strip().upper()

    # Implemented tables list as in VBA
    if table_id in ("DAV1994_T", "DAV2008_T"):
        table_vector = f"{table_id}_{sex}"
        vec = _qx_tables.get(table_vector)
        if vec is None:
            # Table column missing from XML
            raise KeyError(f"Mortality table column not found in XML: {table_vector}")
        if Age < 0 or Age >= len(vec):
            raise IndexError(f"Age {Age} out of bounds for table {table_vector} (size={len(vec)})")
        return float(vec[Age])

    # VBA: Act_qx = 1# : Error(1)
    # We'll raise a ValueError to reflect "table not implemented".
    raise ValueError(f"Mortality table not implemented: {TableId}")


def Vec_lx(
    EndAge: int,
    Sex: str,
    TableId: str,
    BirthYear: int = 0,
    RetirementAge: int = 0,
    Layer: int = 1,
) -> List[float]:
    """
    VBA: Private Function Vec_lx(...)
    Creates vector of lx.
    If EndAge = -1 then created up to MAX_AGE.
    """
    limit = MAX_AGE if EndAge == -1 else EndAge
    if limit < 0:
        raise ValueError("EndAge must be -1 or a non-negative integer.")

    vec: List[float] = [0.0] * (limit + 1)
    vec[0] = 1_000_000.0

    for i in range(1, limit + 1):
        qx = Act_qx(i - 1, Sex, TableId, BirthYear, RetirementAge, Layer)
        vec[i] = vec[i - 1] * (1.0 - qx)
        vec[i] = _excel_round(vec[i], ROUND_LX)

    return vec


def Act_lx(
    Age: int,
    Sex: str,
    TableId: str,
    BirthYear: int = 0,
    RetirementAge: int = 0,
    Layer: int = 1,
) -> float:
    """VBA: Public Function Act_lx(...)"""
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
    """
    VBA: Private Function Vec_tx(...)
    Creates vector of tx (# deaths)
    """
    limit = MAX_AGE if EndAge == -1 else EndAge
    if limit < 0:
        raise ValueError("EndAge must be -1 or a non-negative integer.")

    vec: List[float] = [0.0] * (limit + 1)

    tempLx = Vec_lx(limit, Sex, TableId, BirthYear, RetirementAge, Layer)

    for i in range(0, limit):
        vec[i] = tempLx[i] - tempLx[i + 1]
        vec[i] = _excel_round(vec[i], ROUND_TX)

    return vec


def Act_tx(
    Age: int,
    Sex: str,
    TableId: str,
    BirthYear: int = 0,
    RetirementAge: int = 0,
    Layer: int = 1,
) -> float:
    """VBA: Public Function Act_tx(...)"""
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
    """
    VBA: Private Function Vec_Dx(...)
    Creates vector of Dx
    """
    limit = MAX_AGE if EndAge == -1 else EndAge
    if limit < 0:
        raise ValueError("EndAge must be -1 or a non-negative integer.")

    vec: List[float] = [0.0] * (limit + 1)

    v = 1.0 / (1.0 + InterestRate)

    tempLx = Vec_lx(limit, Sex, TableId, BirthYear, RetirementAge, Layer)

    for i in range(0, limit + 1):
        vec[i] = tempLx[i] * (v ** i)
        vec[i] = _excel_round(vec[i], ROUND_DX)

    return vec


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
    """VBA: Private Function BuildCacheKey(...)"""
    return f"{Kind}_{Age}_{Sex}_{TableId}_{InterestRate}_{BirthYear}_{RetirementAge}_{Layer}"


def Act_Dx(
    Age: int,
    Sex: str,
    TableId: str,
    InterestRate: float,
    BirthYear: int = 0,
    RetirementAge: int = 0,
    Layer: int = 1,
) -> float:
    """VBA: Public Function Act_Dx(...) with caching"""
    _ensure_cache()
    key = BuildCacheKey("Dx", Age, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)

    if key in cache:  # type: ignore[operator]
        return float(cache[key])  # type: ignore[index]

    vec = Vec_Dx(Age, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
    value = float(vec[Age])
    cache[key] = value  # type: ignore[index]
    return value


def Vec_Cx(
    EndAge: int,
    Sex: str,
    TableId: str,
    InterestRate: float,
    BirthYear: int = 0,
    RetirementAge: int = 0,
    Layer: int = 1,
) -> List[float]:
    """
    VBA: Private Function Vec_Cx(...)
    Creates vector of Cx
    """
    limit = MAX_AGE if EndAge == -1 else EndAge
    if limit < 0:
        raise ValueError("EndAge must be -1 or a non-negative integer.")

    vec: List[float] = [0.0] * (limit + 1)

    v = 1.0 / (1.0 + InterestRate)

    tempTx = Vec_tx(limit, Sex, TableId, BirthYear, RetirementAge, Layer)

    for i in range(0, limit):
        vec[i] = tempTx[i] * (v ** (i + 1))
        vec[i] = _excel_round(vec[i], ROUND_CX)

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
    """VBA: Public Function Act_Cx(...) with caching"""
    _ensure_cache()
    key = BuildCacheKey("Cx", Age, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)

    if key in cache:  # type: ignore[operator]
        return float(cache[key])  # type: ignore[index]

    vec = Vec_Cx(Age, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
    value = float(vec[Age])
    cache[key] = value  # type: ignore[index]
    return value


def Vec_Nx(
    Sex: str,
    TableId: str,
    InterestRate: float,
    BirthYear: int = 0,
    RetirementAge: int = 0,
    Layer: int = 1,
) -> List[float]:
    """
    VBA: Private Function Vec_Nx(...)
    Creates vector of Nx
    """
    vec: List[float] = [0.0] * (MAX_AGE + 1)

    tempDx = Vec_Dx(-1, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)

    vec[MAX_AGE] = tempDx[MAX_AGE]
    for i in range(MAX_AGE - 1, -1, -1):
        vec[i] = vec[i + 1] + tempDx[i]
        vec[i] = _excel_round(vec[i], ROUND_DX)  # kept as in original

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
    """VBA: Public Function Act_Nx(...) with caching"""
    _ensure_cache()
    key = BuildCacheKey("Nx", Age, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)

    if key in cache:  # type: ignore[operator]
        return float(cache[key])  # type: ignore[index]

    vec = Vec_Nx(Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
    value = float(vec[Age])
    cache[key] = value  # type: ignore[index]
    return value


def Vec_Mx(
    Sex: str,
    TableId: str,
    InterestRate: float,
    BirthYear: int = 0,
    RetirementAge: int = 0,
    Layer: int = 1,
) -> List[float]:
    """
    VBA: Private Function Vec_Mx(...)
    Creates vector of Mx
    """
    vec: List[float] = [0.0] * (MAX_AGE + 1)

    tempCx = Vec_Cx(-1, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)

    # Note: Vec_Cx(-1, ...) returns length MAX_AGE+1, but its last element remains 0.0
    vec[MAX_AGE] = tempCx[MAX_AGE]
    for i in range(MAX_AGE - 1, -1, -1):
        vec[i] = vec[i + 1] + tempCx[i]
        vec[i] = _excel_round(vec[i], ROUND_MX)

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
    """VBA: Public Function Act_Mx(...) with caching"""
    _ensure_cache()
    key = BuildCacheKey("Mx", Age, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)

    if key in cache:  # type: ignore[operator]
        return float(cache[key])  # type: ignore[index]

    vec = Vec_Mx(Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
    value = float(vec[Age])
    cache[key] = value  # type: ignore[index]
    return value


def Vec_Rx(
    Sex: str,
    TableId: str,
    InterestRate: float,
    BirthYear: int = 0,
    RetirementAge: int = 0,
    Layer: int = 1,
) -> List[float]:
    """
    VBA: Private Function Vec_Rx(...)
    Creates vector of Rx
    """
    vec: List[float] = [0.0] * (MAX_AGE + 1)

    tempMx = Vec_Mx(Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)

    vec[MAX_AGE] = tempMx[MAX_AGE]
    for i in range(MAX_AGE - 1, -1, -1):
        vec[i] = vec[i + 1] + tempMx[i]
        vec[i] = _excel_round(vec[i], ROUND_RX)

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
    """VBA: Public Function Act_Rx(...) with caching"""
    _ensure_cache()
    key = BuildCacheKey("Rx", Age, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)

    if key in cache:  # type: ignore[operator]
        return float(cache[key])  # type: ignore[index]

    vec = Vec_Rx(Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
    value = float(vec[Age])
    cache[key] = value  # type: ignore[index]
    return value


def Act_AgeCalculation(BirthDate: date, ValuationDate: date, Method: str) -> int:
    """
    VBA: Public Function Act_AgeCalculation(...)
    Age calculation based on calendar-year method (K) or half-year method (H)
    """
    method = (Method or "").strip().upper()
    if method != "K":
        method = "H"

    yBirth = BirthDate.year
    yVal = ValuationDate.year
    mBirth = BirthDate.month
    mVal = ValuationDate.month

    if method == "K":
        return int(yVal - yBirth)

    # method == "H"
    # VBA: Int(yVal - yBirth + 1#/12# * (mVal - mBirth + 5))
    expr = (yVal - yBirth) + (1.0 / 12.0) * (mVal - mBirth + 5)
    return int(math.floor(expr))
