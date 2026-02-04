#!/usr/bin/env python3
"""
run_calc.py

Minimal CLI runner for calculator output functions (Task 7).

- Loads inputs from var.csv and tariff.csv using pandas.
- Uses ONLY the exact variable names present in the CSV files produced in Task 3:
    var.csv   -> x, Sex, n, t, SumInsured, PayFreq
    tariff.csv-> (loaded but not required for the function call arguments)
- Maps these exact CSV fields to the function signature required by outfunc.py:
    sa      <- SumInsured
    age     <- x
    sex     <- Sex
    n       <- n
    t       <- t
    PayFreq <- PayFreq
    tariff  <- ""   (not present in the provided CSV extracts)

- Dynamically dispatches to functions in outfunc.py and prints compact JSON to STDOUT only.
"""

from __future__ import annotations

import argparse
import json
import sys
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

ALL_FUNCS = [
    "NormGrossAnnualPrem",
    "GrossAnnualPrem",
    "GrossModalPrem",
    "Pxt",
]


def _script_dir() -> Path:
    return Path(__file__).resolve().parent


def _read_name_value(path: Path) -> Dict[str, str]:
    df = pd.read_csv(path, dtype=str).fillna("")
    if "Name" not in df.columns or "Value" not in df.columns:
        raise ValueError(f"{path}: expected columns 'Name' and 'Value'")
    out: Dict[str, str] = {}
    for n, v in zip(df["Name"], df["Value"]):
        key = str(n).strip()
        if not key:
            continue
        out[key] = str(v).strip()
    return out


def _as_int(v: str, name: str) -> int:
    s = str(v).strip()
    if s == "":
        raise ValueError(f"Empty value for {name}")
    try:
        f = float(s.replace(",", "."))
    except Exception as e:
        raise ValueError(f"Non-numeric value for {name}: {v!r}") from e
    return int(f)


def _as_float(v: str, name: str) -> float:
    s = str(v).strip()
    if s == "":
        raise ValueError(f"Empty value for {name}")
    try:
        return float(s.replace(",", "."))
    except Exception as e:
        raise ValueError(f"Non-numeric value for {name}: {v!r}") from e


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run product calculator output functions from outfunc.py and print JSON.")
    p.add_argument("--var-file", default="var.csv", help="Variables CSV file (default: var.csv)")
    p.add_argument("--tariff-file", default="tariff.csv", help="Tariff CSV file (default: tariff.csv)")
    p.add_argument(
        "--funcs",
        default="",
        help="Comma-separated list of functions to run, e.g. NormGrossAnnualPrem,GrossAnnualPrem",
    )
    p.add_argument(
        "--all",
        action="store_true",
        help="Run all known functions (default if --funcs is not given)",
    )
    return p.parse_args(argv)


def _resolve_path(p: str, base_dir: Path) -> Path:
    path = Path(p)
    return path if path.is_absolute() else (base_dir / path)


def _load_inputs(var_file: Path, tariff_file: Path) -> Dict[str, Any]:
    """
    Load ONLY the exact variables provided in var.csv (Task 3 extract):
      x, Sex, n, t, SumInsured, PayFreq

    tariff.csv is loaded (per spec) but not needed for these call arguments.
    """
    var_map = _read_name_value(var_file)
    _ = _read_name_value(tariff_file)  # loaded as specified; not used in input args here

    required_var_keys = ["x", "Sex", "n", "t", "SumInsured", "PayFreq"]
    missing = [k for k in required_var_keys if k not in var_map or str(var_map[k]).strip() == ""]
    if missing:
        raise KeyError(f"Missing required keys in var.csv: {missing}")

    inputs: Dict[str, Any] = {
        "sa": _as_float(var_map["SumInsured"], "SumInsured"),
        "age": _as_int(var_map["x"], "x"),
        "sex": str(var_map["Sex"]).strip(),
        "n": _as_int(var_map["n"], "n"),
        "t": _as_int(var_map["t"], "t"),
        "PayFreq": _as_int(var_map["PayFreq"], "PayFreq"),
        # Not present in the provided CSV extracts; keep deterministic.
        "tariff": "",
    }
    return inputs


def main(argv: list[str]) -> int:
    args = _parse_args(argv)

    base_dir = _script_dir()
    var_path = _resolve_path(args.var_file, base_dir)
    tariff_path = _resolve_path(args.tariff_file, base_dir)

    # Ensure outfunc.py and its sibling modules (basfunct.py, tariff.py, CSVs) are importable.
    if str(base_dir) not in sys.path:
        sys.path.insert(0, str(base_dir))

    input_args = _load_inputs(var_path, tariff_path)

    funcs_to_run = (
        ALL_FUNCS if args.all or not args.funcs else [s.strip() for s in args.funcs.split(",") if s.strip()]
    )

    outfunc = import_module("outfunc")
    results: Dict[str, Any] = {}

    for name in funcs_to_run:
        func = getattr(outfunc, name, None)
        if func is None or getattr(func, "__doc__", None) == "PLACEHOLDER":
            results[name] = "not yet implemented"
        else:
            results[name] = func(**input_args)

    print(json.dumps(results, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
