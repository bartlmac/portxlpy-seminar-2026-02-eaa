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
    """Creates a temp directory containing mini-samples of all input artifacts."""
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
