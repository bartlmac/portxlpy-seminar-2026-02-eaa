# premium_and_progress_values.py
"""
Premium and progression value calculations for an Endowment Life Insurance tariff.

This module mirrors the Excel formulas from the provided premium calculator.

Assumptions:
- The actuarial helper functions are already available as Python functions:
    - act_nGrAx and Act_axn_k in presentvalues.py
    - Act_Dx in commvalues.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Any

from presentvalues import act_nGrAx, Act_axn_k
from commvalues import Act_Dx


Number = float


@dataclass(frozen=True)
class PolicyInputs:
    x: int
    sex: str
    n: int
    t: int
    sum_insured: Number
    pay_freq: int


@dataclass(frozen=True)
class TariffInputs:
    interest_rate: Number
    mortality_table: str
    alpha: Number
    beta1: Number
    gamma1: Number
    gamma2: Number
    gamma3: Number
    k: Number
    modal_surcharge: Number


@dataclass(frozen=True)
class Limits:
    min_age_flex: int
    min_term_flex: int


def _max0(v: int) -> int:
    return v if v > 0 else 0


def calc_premium_calculation(
    policy: PolicyInputs,
    tariff: TariffInputs,
) -> Dict[str, Number]:
    """
    Mirrors Excel 'Premium calculation' block.

    Excel formulas:
      NormGrossAnnualPrem =
        ( act_nGrAx(x;n;Sex;MortalityTable;InterestRate)
          + Act_Dx(x+n)/Act_Dx(x)
          + gamma1*Act_axn_k(x;t;...;1)
          + gamma2*(Act_axn_k(x;n;...;1) - Act_axn_k(x;t;...;1))
        ) / ( (1-beta1)*Act_axn_k(x;t;...;1) - alpha*t )

      GrossAnnualPrem = SumInsured * NormGrossAnnualPrem
      GrossModalPrem  = (1+ModalSurcharge)/PayFreq * (GrossAnnualPrem + k)
      Pxt = ( act_nGrAx(x;n) + Act_Dx(x+n)/Act_Dx(x) + t*alpha*NormGrossAnnualPrem )
            / Act_axn_k(x;t;...;1)
    """
    x, sex, n, t = policy.x, policy.sex, policy.n, policy.t
    si, pf = policy.sum_insured, policy.pay_freq

    i = tariff.interest_rate
    mt = tariff.mortality_table
    alpha = tariff.alpha
    beta1 = tariff.beta1
    gamma1 = tariff.gamma1
    gamma2 = tariff.gamma2
    k_const = tariff.k
    modal_surcharge = tariff.modal_surcharge

    ax_t = Act_axn_k(x, t, sex, mt, i, 1)
    ax_n = Act_axn_k(x, n, sex, mt, i, 1)

    dx_x = Act_Dx(x, sex, mt, i)
    dx_xn = Act_Dx(x + n, sex, mt, i)

    numerator = (
        act_nGrAx(x, n, sex, mt, i)
        + (dx_xn / dx_x)
        + gamma1 * ax_t
        + gamma2 * (ax_n - ax_t)
    )
    denominator = (1.0 - beta1) * ax_t - alpha * t

    norm_gross_annual_prem = numerator / denominator

    gross_annual_prem = si * norm_gross_annual_prem
    gross_modal_prem = (1.0 + modal_surcharge) / pf * (gross_annual_prem + k_const)

    pxt = (
        act_nGrAx(x, n, sex, mt, i)
        + (dx_xn / dx_x)
        + t * alpha * norm_gross_annual_prem
    ) / ax_t

    return {
        "NormGrossAnnualPrem": float(norm_gross_annual_prem),
        "GrossAnnualPrem": float(gross_annual_prem),
        "GrossModalPrem": float(gross_modal_prem),
        "Pxt": float(pxt),
    }


def calc_progression_values(
    policy: PolicyInputs,
    tariff: TariffInputs,
    limits: Limits,
    *,
    pxt: Number,
    gross_annual_prem: Number,
    max_k: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Mirrors Excel 'Progression values' table row-by-row.

    Columns (as in screenshot/formulas):
      k,
      Axn,
      axn,
      axt,
      kVx_pp,
      kDRx_pp,
      kVx_pu,
      kVx_MRV,
      Flex_phase,
      Surrender_deduction,
      Surrender_value,
      SumInsured_pu

    Notes:
    - Excel uses IF/AND/OR/IFERROR; we reproduce equivalent logic.
    - Provide pxt and gross_annual_prem from calc_premium_calculation().
    - max_k defaults to policy.n (inclusive).
    """
    x, sex, n, t = policy.x, policy.sex, policy.n, policy.t
    si = policy.sum_insured

    i = tariff.interest_rate
    mt = tariff.mortality_table
    alpha = tariff.alpha
    gamma2 = tariff.gamma2
    gamma3 = tariff.gamma3

    min_age_flex = limits.min_age_flex
    min_term_flex = limits.min_term_flex

    if max_k is None:
        max_k = n

    # Precompute constants that Excel references repeatedly
    ax_t0 = Act_axn_k(x, t, sex, mt, i, 1)
    ax_n0 = Act_axn_k(x, n, sex, mt, i, 1)
    ax_ratio_n_over_t = ax_n0 / ax_t0

    dx_x5 = Act_Dx(x, sex, mt, i)  # for denominator in Axn formula when k=0
    ax_5_at_x = Act_axn_k(x, 5, sex, mt, i, 1)  # denominator in kVx_MRV adjustment
    dx_xn = Act_Dx(x + n, sex, mt, i)

    rows: List[Dict[str, Any]] = []

    for k in range(0, max_k + 1):
        # Axn:
        # IF(k<=n; act_nGrAx(x+k;MAX(0;n-k))+Act_Dx(x+n)/Act_Dx(x+k); 0)
        if k <= n:
            dx_xk = Act_Dx(x + k, sex, mt, i)
            Axn = act_nGrAx(x + k, _max0(n - k), sex, mt, i) + (dx_xn / dx_xk)
        else:
            Axn = 0.0

        # axn: Act_axn_k(x+k; MAX(0;n-k); ... ;1)
        axn = Act_axn_k(x + k, _max0(n - k), sex, mt, i, 1)

        # axt: Act_axn_k(x+k; MAX(0;t-k); ... ;1)
        axt = Act_axn_k(x + k, _max0(t - k), sex, mt, i, 1)

        # kVx_pp:
        # = Axn - Pxt*axt + gamma2*(axn - Act_axn_k(x;n)/Act_axn_k(x;t)*axt)
        kVx_pp = Axn - pxt * axt + gamma2 * (axn - ax_ratio_n_over_t * axt)

        # kDRx_pp: SumInsured * kVx_pp
        kDRx_pp = si * kVx_pp

        # kVx_pu: Axn + gamma3*axn
        kVx_pu = Axn + gamma3 * axn

        # kVx_MRV:
        # = kDRx_pp + alpha*t*GrossAnnualPrem
        #   * Act_axn_k(x+k; MAX(5-k;0); ...;1) / Act_axn_k(x;5;...;1)
        mr_adj_num = Act_axn_k(x + k, _max0(5 - k), sex, mt, i, 1)
        kVx_MRV = kDRx_pp + alpha * t * gross_annual_prem * (mr_adj_num / ax_5_at_x)

        # Flex. phase:
        # IF(AND(x+k>=MinAgeFlex; k>=n-MinTermFlex); 1; 0)
        flex_phase = 1 if ((x + k) >= min_age_flex and k >= (n - min_term_flex)) else 0

        # Surrender deduction:
        # IF(OR(k>n; flex_phase); 0; MIN(150; MAX(50; 1%*(SumInsured-kDRx_pp))))
        if (k > n) or (flex_phase == 1):
            surrender_deduction = 0.0
        else:
            surrender_deduction = min(150.0, max(50.0, 0.01 * (si - kDRx_pp)))

        # Surrender value: MAX(0; kVx_MRV - surrender_deduction)
        surrender_value = max(0.0, kVx_MRV - surrender_deduction)

        # SumInsured_pu:
        # IFERROR( IF(k>n;0; IF(k<t; kVx_MRV/kVx_pu; SumInsured)); 0)
        try:
            if k > n:
                suminsured_pu = 0.0
            else:
                if k < t:
                    suminsured_pu = (kVx_MRV / kVx_pu) if kVx_pu != 0 else 0.0
                else:
                    suminsured_pu = float(si)
        except Exception:
            suminsured_pu = 0.0

        rows.append(
            {
                "k": k,
                "Axn": float(Axn),
                "axn": float(axn),
                "axt": float(axt),
                "kVx_pp": float(kVx_pp),
                "kDRx_pp": float(kDRx_pp),
                "kVx_pu": float(kVx_pu),
                "kVx_MRV": float(kVx_MRV),
                "Flex_phase": int(flex_phase),
                "Surrender_deduction": float(surrender_deduction),
                "Surrender_value": float(surrender_value),
                "SumInsured_pu": float(suminsured_pu),
            }
        )

    return rows


def calc_all(
    policy: PolicyInputs,
    tariff: TariffInputs,
    limits: Limits,
    *,
    max_k: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Convenience function:
    - computes premium block
    - computes progression table using those premium outputs
    """
    prem = calc_premium_calculation(policy, tariff)
    prog = calc_progression_values(
        policy,
        tariff,
        limits,
        pxt=prem["Pxt"],
        gross_annual_prem=prem["GrossAnnualPrem"],
        max_k=max_k,
    )
    return {"premium": prem, "progression": prog}
