# tests/test_GrossAnnualPrem.py
from __future__ import annotations

import sys
from pathlib import Path

import importlib.util


def _load_module_from_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module spec: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_GrossAnnualPrem_single_case() -> None:
    out_dir = Path(__file__).resolve().parents[1]  # .../Bartek/output
    if str(out_dir) not in sys.path:
        sys.path.insert(0, str(out_dir))

    outfunc = _load_module_from_path("outfunc_under_test_ga", out_dir / "outfunc.py")

    sa = 100_000
    age = 40
    sex = "M"
    n = 30
    t = 20
    PayFreq = 12
    tariff = "KLV"

    expected = 4226.00
    tol = 1e-2

    got = float(outfunc.GrossAnnualPrem(sa, age, sex, n, t, PayFreq, tariff))
    assert abs(got - expected) <= tol, f"got={got:.6f}, expected={expected:.6f}, tol={tol}"
