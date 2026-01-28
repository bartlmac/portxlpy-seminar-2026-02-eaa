"""
tariff.py

Auto-generated from Excel export.

Source cell:
- Calculation!E12 formula: '=IF(PayFreq=2,2%,IF(PayFreq=4,3%,IF(PayFreq=12,5%,0)))'

Implements:
- ModalSurcharge(PayFreq)
"""

from __future__ import annotations


def ModalSurcharge(PayFreq: int | float) -> float:
    """
    Port of Excel Calculation!E12.

    Excel formula (expected):
      =IF(PayFreq=2,2%,IF(PayFreq=4,3%,IF(PayFreq=12,5%,0)))

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
