"""
outfunc.py

Premium calculation output functions (Task 6A + Task 6C)

Implements (Excel sheet "Calculation"):
- NormGrossAnnualPrem(sa, age, sex, n, t, PayFreq, tariff)  -> K5 (Bxt)
- GrossAnnualPrem(sa, age, sex, n, t, PayFreq, tariff)      -> K6 (BJB)
- GrossModalPrem(sa, age, sex, n, t, PayFreq, tariff)       -> K7 (BZB)
- Pxt(sa, age, sex, n, t, PayFreq, tariff)                  -> K9 (Pxt)

Exact Excel formulas:
K5:
=(act_nGrAx(x,n,Sex,MortalityTable,InterestRate)
  +Act_Dx(x+n,Sex,MortalityTable,InterestRate)/Act_Dx(x,Sex,MortalityTable,InterestRate)
  +gamma1*Act_axn_k(x,t,Sex,MortalityTable,InterestRate,1)
  +gamma2*(Act_axn_k(x,n,Sex,MortalityTable,InterestRate,1)-Act_axn_k(x,t,Sex,MortalityTable,InterestRate,1))
 ) / ((1-beta1)*Act_axn_k(x,t,Sex,MortalityTable,InterestRate,1)-alpha*t)

K6:
=SumInsured*K5

K7:
=(1+ModalSurcharge)/PayFreq*(K6+k)

K9:
=(act_nGrAx(x,n,Sex,MortalityTable,InterestRate)
  +Act_Dx(x+n,Sex,MortalityTable,InterestRate)/Act_Dx(x,Sex,MortalityTable,InterestRate)
  +t*alpha*NormGrossAnnualPrem
 ) / Act_axn_k(x,t,Sex,MortalityTable,InterestRate,1)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

import basfunct
import tariff as tariff_mod


def _data_dir() -> Path:
    # Project convention: all artifacts live next to this file (Bartek/output)
    return Path(__file__).resolve().parent


def _load_name_value_csv(path: Path) -> Dict[str, str]:
    df = pd.read_csv(path, dtype=str).fillna("")
    if "Name" not in df.columns or "Value" not in df.columns:
        raise ValueError(f"{path.name} must have columns: Name, Value")
    out: Dict[str, str] = {}
    for n, v in zip(df["Name"], df["Value"]):
        name = str(n).strip()
        if not name:
            continue
        out[name] = str(v).strip()
    return out


def _to_float(d: Dict[str, str], key: str) -> float:
    if key not in d:
        raise KeyError(f"Missing key {key!r} in tariff parameters.")
    s = str(d[key]).strip()
    if s == "":
        raise ValueError(f"Empty value for key {key!r} in tariff parameters.")
    return float(s)


@dataclass(frozen=True)
class TariffParams:
    interest_rate: float
    mortality_table: str
    alpha: float
    beta1: float
    gamma1: float
    gamma2: float
    k: float


_params_cache: Optional[TariffParams] = None


def _get_tariff_params() -> TariffParams:
    global _params_cache
    if _params_cache is not None:
        return _params_cache

    dd = _data_dir()
    tariff_path = dd / "tariff.csv"
    if not tariff_path.exists():
        raise FileNotFoundError(f"tariff.csv not found in: {dd}")

    d = _load_name_value_csv(tariff_path)

    params = TariffParams(
        interest_rate=_to_float(d, "InterestRate"),
        mortality_table=str(d.get("MortalityTable", "")).strip(),
        alpha=_to_float(d, "alpha"),
        beta1=_to_float(d, "beta1"),
        gamma1=_to_float(d, "gamma1"),
        gamma2=_to_float(d, "gamma2"),
        k=_to_float(d, "k"),
    )
    if not params.mortality_table:
        raise ValueError("MortalityTable is empty in tariff.csv")

    # Ensure basfunct reads tables.csv from the same dir
    basfunct.set_data_dir(dd)

    _params_cache = params
    return params


def NormGrossAnnualPrem(
    sa: float,
    age: int,
    sex: str,
    n: int,
    t: int,
    PayFreq: int,
    tariff: str,
) -> float:
    """
    Returns Bxt (normalized gross annual premium rate) per Excel Calculation!K5.
    """
    _ = sa, PayFreq, tariff  # not used in K5 itself

    p = _get_tariff_params()

    x = int(age)
    n_i = int(n)
    t_i = int(t)
    sex_s = str(sex)

    mt = p.mortality_table
    ir = float(p.interest_rate)

    axn_t = basfunct.Act_axn_k(x, t_i, sex_s, mt, ir, 1)
    axn_n = basfunct.Act_axn_k(x, n_i, sex_s, mt, ir, 1)
    dx_ratio = basfunct.Act_Dx(x + n_i, sex_s, mt, ir) / basfunct.Act_Dx(x, sex_s, mt, ir)

    numerator = (
        basfunct.act_nGrAx(x, n_i, sex_s, mt, ir)
        + dx_ratio
        + p.gamma1 * axn_t
        + p.gamma2 * (axn_n - axn_t)
    )
    denominator = (1.0 - p.beta1) * axn_t - p.alpha * float(t_i)

    if denominator == 0.0:
        raise ZeroDivisionError("Denominator in K5 (Bxt) is zero.")

    return float(numerator / denominator)


def GrossAnnualPrem(
    sa: float,
    age: int,
    sex: str,
    n: int,
    t: int,
    PayFreq: int,
    tariff: str,
) -> float:
    """
    Excel K6: =SumInsured*K5
    """
    rate = NormGrossAnnualPrem(sa, age, sex, n, t, PayFreq, tariff)
    return float(sa) * float(rate)


def GrossModalPrem(
    sa: float,
    age: int,
    sex: str,
    n: int,
    t: int,
    PayFreq: int,
    tariff: str,
) -> float:
    """
    Excel K7: =(1+ModalSurcharge)/PayFreq*(K6+k)
    where:
      ModalSurcharge = tariff.ModalSurcharge(PayFreq)
      k comes from tariff.csv
    """
    p = _get_tariff_params()
    annual = GrossAnnualPrem(sa, age, sex, n, t, PayFreq, tariff)
    ms = float(tariff_mod.ModalSurcharge(PayFreq))
    pf = int(PayFreq)
    if pf == 0:
        raise ZeroDivisionError("PayFreq must not be 0.")
    return (1.0 + ms) / pf * (annual + p.k)


def Pxt(
    sa: float,
    age: int,
    sex: str,
    n: int,
    t: int,
    PayFreq: int,
    tariff: str,
) -> float:
    """
    Excel K9:
    =(act_nGrAx(x,n,Sex,MortalityTable,InterestRate)
      +Act_Dx(x+n,Sex,MortalityTable,InterestRate)/Act_Dx(x,Sex,MortalityTable,InterestRate)
      +t*alpha*NormGrossAnnualPrem
     ) / Act_axn_k(x,t,Sex,MortalityTable,InterestRate,1)
    """
    _ = sa, PayFreq, tariff  # not used directly in K9 formula besides NormGrossAnnualPrem rate

    p = _get_tariff_params()
    x = int(age)
    n_i = int(n)
    t_i = int(t)
    sex_s = str(sex)
    mt = p.mortality_table
    ir = float(p.interest_rate)

    dx_ratio = basfunct.Act_Dx(x + n_i, sex_s, mt, ir) / basfunct.Act_Dx(x, sex_s, mt, ir)
    axn_t = basfunct.Act_axn_k(x, t_i, sex_s, mt, ir, 1)
    if axn_t == 0.0:
        raise ZeroDivisionError("Act_axn_k(x,t,...) is zero in K9 denominator.")

    rate = NormGrossAnnualPrem(1.0, x, sex_s, n_i, t_i, int(PayFreq), str(tariff))
    numerator = basfunct.act_nGrAx(x, n_i, sex_s, mt, ir) + dx_ratio + float(t_i) * p.alpha * rate
    return float(numerator / axn_t)

