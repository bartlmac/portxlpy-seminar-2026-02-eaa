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
