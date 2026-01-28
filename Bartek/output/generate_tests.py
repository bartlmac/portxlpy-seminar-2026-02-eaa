#!/usr/bin/env python3
"""
generate_tests.py

TASK 4 – Generate pytest fixtures/tests under ./tests

Inputs (expected next to this script, i.e. /Bartek/output):
- var.csv
- tariff.csv
- limits.csv
- tables.csv
- tariff.py

Fallback (for LLM sandbox / ad-hoc runs):
- /mnt/data/{var.csv, tariff.csv, limits.csv, tables.csv, tariff.py}

Outputs:
- ./tests/conftest.py
- ./tests/test_data_roundtrip.py

Run:
  python generate_tests.py
Then:
  pytest -q
"""

from __future__ import annotations

import csv
from pathlib import Path


def _find_source_dir(base: Path) -> Path:
    """
    Prefer data files next to this script (repo layout).
    Fallback to /mnt/data (LLM sandbox).
    """
    required = ["var.csv", "tariff.csv", "limits.csv", "tables.csv", "tariff.py"]
    if all((base / f).exists() for f in required):
        return base
    mnt = Path("/mnt/data")
    if all((mnt / f).exists() for f in required):
        return mnt
    missing = [f for f in required if not (base / f).exists() and not (mnt / f).exists()]
    raise FileNotFoundError(f"Missing required input files (checked {base} and {mnt}): {missing}")


def _copy_csv_head(src: Path, dst: Path, max_data_rows: int) -> None:
    """
    Copy CSV header + up to max_data_rows data rows (not counting header).
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    with src.open("r", newline="", encoding="utf-8") as f_in, dst.open("w", newline="", encoding="utf-8") as f_out:
        r = csv.reader(f_in)
        w = csv.writer(f_out)
        header = next(r, None)
        if header is None:
            # Empty file: still write nothing (tests will fail, which is correct)
            return
        w.writerow(header)
        for i, row in enumerate(r):
            if i >= max_data_rows:
                break
            w.writerow(row)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def main() -> int:
    out_dir = Path(__file__).resolve().parent
    src_dir = _find_source_dir(out_dir)

    tests_dir = out_dir / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    conftest_py = """\
from __future__ import annotations

import csv
import shutil
from pathlib import Path

import pytest


def _find_source_dir() -> Path:
    # Prefer repo layout: data files next to /Bartek/output
    here = Path(__file__).resolve().parents[1]
    required = ["var.csv", "tariff.csv", "limits.csv", "tables.csv", "tariff.py"]
    if all((here / f).exists() for f in required):
        return here

    # Fallback for sandbox runs
    mnt = Path("/mnt/data")
    if all((mnt / f).exists() for f in required):
        return mnt

    missing = [f for f in required if not (here / f).exists() and not (mnt / f).exists()]
    raise FileNotFoundError(f"Missing required input files (checked {here} and {mnt}): {missing}")


def _copy_csv_head(src: Path, dst: Path, max_data_rows: int) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with src.open("r", newline="", encoding="utf-8") as f_in, dst.open("w", newline="", encoding="utf-8") as f_out:
        r = csv.reader(f_in)
        w = csv.writer(f_out)
        header = next(r, None)
        if header is None:
            return
        w.writerow(header)
        for i, row in enumerate(r):
            if i >= max_data_rows:
                break
            w.writerow(row)


@pytest.fixture(scope="session")
def sample_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    \"\"\"Creates a temp directory containing mini-samples of all input artifacts.\"\"\"
    tmp = tmp_path_factory.mktemp("calc_data")
    src = _find_source_dir()

    # Small samples (keep tests fast, but ensure tables has >= 100 rows)
    _copy_csv_head(src / "var.csv", tmp / "var.csv", max_data_rows=10)
    _copy_csv_head(src / "tariff.csv", tmp / "tariff.csv", max_data_rows=20)
    _copy_csv_head(src / "limits.csv", tmp / "limits.csv", max_data_rows=10)
    _copy_csv_head(src / "tables.csv", tmp / "tables.csv", max_data_rows=150)

    # Copy python module verbatim
    shutil.copyfile(src / "tariff.py", tmp / "tariff.py")

    return tmp
"""

    test_py = """\
from __future__ import annotations

import csv
import importlib.util
from pathlib import Path
from typing import Iterable, List

import pytest


def _read_csv(path: Path) -> tuple[List[str], List[List[str]]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        header = next(r, [])
        rows = [row for row in r]
    return header, rows


def _load_module_from_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module spec: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize(
    "filename,expected_cols,min_rows",
    [
        ("var.csv", 2, 1),
        ("tariff.csv", 2, 1),
        ("limits.csv", 2, 1),
        ("tables.csv", 5, 100),
    ],
)
def test_data_roundtrip_counts(sample_dir: Path, filename: str, expected_cols: int, min_rows: int) -> None:
    path = sample_dir / filename
    assert path.exists(), f"Missing {filename} in sample_dir: {sample_dir}"

    header, rows = _read_csv(path)
    assert len(header) == expected_cols, f"{filename}: expected {expected_cols} columns, got {len(header)} ({header})"
    assert len(rows) >= min_rows, f"{filename}: expected >= {min_rows} data rows, got {len(rows)}"


def test_tariff_module_smoke(sample_dir: Path) -> None:
    tariff_path = sample_dir / "tariff.py"
    assert tariff_path.exists()

    tariff = _load_module_from_path("tariff_sample", tariff_path)
    assert hasattr(tariff, "ModalSurcharge")

    # Known from the Excel formula used in Task 3 export
    assert abs(float(tariff.ModalSurcharge(12)) - 0.05) < 1e-12
"""

    _write_text(tests_dir / "conftest.py", conftest_py)
    _write_text(tests_dir / "test_data_roundtrip.py", test_py)

    print(f"Wrote: {tests_dir / 'conftest.py'}")
    print(f"Wrote: {tests_dir / 'test_data_roundtrip.py'}")
    print("Next: run `pytest -q` from /Bartek/output (or your repo root if configured).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
