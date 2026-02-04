# presentvalues.py
"""
Translation of VBA module mPresentValues to Python (1:1 behavior).

Depends on commvalues.py (Act_Dx, Act_Nx, Act_Mx, etc.).
"""

from __future__ import annotations

from typing import Optional

from commvalues import Act_Dx, Act_Nx, Act_Mx


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
    """
    VBA: Public Function Act_ax_k(...)
    """
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
    """
    VBA: Public Function Act_axn_k(...)
    """
    if k > 0:
        dx_age = Act_Dx(Age, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
        dx_agen = Act_Dx(Age + n, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)

        nx_age = Act_Nx(Age, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
        nx_agen = Act_Nx(Age + n, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)

        return (nx_age - nx_agen) / dx_age - Act_DeductionTerm(k, InterestRate) * (
            1.0 - dx_agen / dx_age
        )
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
    """
    VBA: Public Function Act_nax_k(...)
    """
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
    """
    VBA: Public Function act_nGrAx(...)
    """
    return (
        Act_Mx(Age, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
        - Act_Mx(Age + n, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)
    ) / Act_Dx(Age, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer)


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
    """
    VBA: Public Function act_nGrEx(...)
    """
    return Act_Dx(Age + n, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer) / Act_Dx(
        Age, Sex, TableId, InterestRate, BirthYear, RetirementAge, Layer
    )


def Act_ag_k(g: int, InterestRate: float, k: int) -> float:
    """
    VBA: Public Function Act_ag_k(...)
    """
    v = 1.0 / (1.0 + InterestRate)

    if k > 0:
        if InterestRate > 0:
            return (1.0 - v**g) / (1.0 - v) - Act_DeductionTerm(k, InterestRate) * (1.0 - v**g)
        else:
            return float(g)
    return 0.0


def Act_DeductionTerm(k: int, InterestRate: float) -> float:
    """
    VBA: Public Function Act_DeductionTerm(...)
    Deduction term
    """
    deduction = 0.0

    if k > 0:
        for l in range(0, k):
            deduction += (l / k) / (1.0 + (l / k) * InterestRate)
        deduction = deduction * (1.0 + InterestRate) / k

    return deduction
