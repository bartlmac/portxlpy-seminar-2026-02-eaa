# tests/test_NormGrossAnnualPrem.py
from __future__ import annotations

import sys
from pathlib import Path

import importlib.util


def _load_module_from_path(name: str, path: Path):
    """
    Load a module from a file path AND register it in sys.modules before exec.
    This avoids issues with string annotations + dataclasses in Python 3.12.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module spec: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # critical for dataclasses resolving string annotations
    spec.loader.exec_module(mod)
    return mod


def test_NormGrossAnnualPrem_single_case() -> None:
    # Repo layout: .../Bartek/output/tests/this_file.py
    out_dir = Path(__file__).resolve().parents[1]  # .../Bartek/output
    assert out_dir.exists()

    # Ensure imports like `import basfunct` from outfunc.py resolve
    if str(out_dir) not in sys.path:
        sys.path.insert(0, str(out_dir))

    outfunc_path = out_dir / "outfunc.py"
    assert outfunc_path.exists(), f"Missing outfunc.py at {outfunc_path}"

    outfunc = _load_module_from_path("outfunc_under_test", outfunc_path)

    sa = 100_000
    age = 40
    sex = "M"
    n = 30
    t = 20
    PayFreq = 12
    tariff = "KLV"

    expected = 0.04226001
    tol = 1e-8

    got = float(outfunc.NormGrossAnnualPrem(sa, age, sex, n, t, PayFreq, tariff))
    assert abs(got - expected) <= tol, f"got={got:.12f}, expected={expected:.12f}, tol={tol}"
