#!/usr/bin/env python3
"""
vba_to_text.py

Extract all non-empty VBA modules from an Excel .xlsm file into text files.

Input:
- /Bartek/input/Tariff_Calculator.xlsm (default, based on script location)
  or pass: --excel <path>

Output:
- One file per non-empty module: /Bartek/output/Mod_<Name>.txt (default)
  or pass: --outdir <path>

Procedure:
- Uses oletools.olevba to parse and extract VBA streams.
- Ignores empty modules / code objects without code.

Notes:
- Filenames are sanitized for Windows.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Optional, Tuple


def _default_excel_path(script_path: Path) -> Path:
    # If script is /Bartek/output/vba_to_text.py -> default Excel: /Bartek/input/Tariff_Calculator.xlsm
    bartek_dir = script_path.parent.parent
    candidate = bartek_dir / "input" / "Tariff_Calculator.xlsm"
    if candidate.exists():
        return candidate.resolve()
    # fallback: ./input/Tariff_Calculator.xlsm relative to CWD
    return (Path.cwd() / "input" / "Tariff_Calculator.xlsm").resolve()


def _sanitize_filename(name: str) -> str:
    """
    Windows-safe filename: replace forbidden chars and trim dots/spaces.
    """
    name = name.strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", name)
    name = name.rstrip(". ").strip()
    return name or "Unnamed"


def _has_code(code: str) -> bool:
    # Consider non-empty after stripping whitespace and common module header lines
    return bool(code and code.strip())


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _extract_modules_oletools(excel_path: Path) -> Iterable[Tuple[str, str]]:
    """
    Yield (module_name, vba_code) for each extracted VBA module using oletools.
    """
    try:
        from oletools.olevba import VBA_Parser  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "oletools is required. Install with: pip install oletools"
        ) from e

    vbaparser = VBA_Parser(str(excel_path))
    try:
        if not vbaparser.detect_vba_macros():
            return []
        modules: list[Tuple[str, str]] = []
        # extract_macros yields tuples; module name is typically vba_filename
        for _fname, _stream_path, vba_filename, vba_code in vbaparser.extract_macros():
            module_name = str(vba_filename or "").strip()
            code = vba_code if isinstance(vba_code, str) else (vba_code.decode("utf-8", "ignore") if vba_code else "")
            if not _has_code(code):
                continue
            # Some code objects can appear with blank/odd names; still export
            modules.append((module_name or "Unnamed", code))
        return modules
    finally:
        try:
            vbaparser.close()
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Dump all non-empty VBA modules from an .xlsm into Mod_*.txt files.")
    parser.add_argument(
        "--excel",
        type=str,
        default="",
        help="Path to Tariff_Calculator.xlsm. If omitted, defaults to /Bartek/input/Tariff_Calculator.xlsm based on script location.",
    )
    parser.add_argument(
        "--outdir",
        type=str,
        default="",
        help="Output directory for Mod_*.txt files. If omitted, defaults to the script directory (e.g., /Bartek/output).",
    )
    args = parser.parse_args()

    script_path = Path(__file__).resolve()
    excel_path = Path(args.excel).resolve() if args.excel else _default_excel_path(script_path)
    out_dir = Path(args.outdir).resolve() if args.outdir else script_path.parent

    if not excel_path.exists():
        print(f"ERROR: Excel file not found: {excel_path}", file=sys.stderr)
        print("Tip: pass --excel <path-to-Tariff_Calculator.xlsm>", file=sys.stderr)
        return 2

    try:
        modules = list(_extract_modules_oletools(excel_path))
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 3
    except Exception as e:
        print(f"ERROR: Failed to extract VBA modules: {e}", file=sys.stderr)
        return 4

    if not modules:
        print("No non-empty VBA modules found.")
        return 0

    # Write one file per module name; de-dup by suffix
    name_counts: defaultdict[str, int] = defaultdict(int)
    written = 0
    warned_no_subfunc = 0

    for module_name, code in modules:
        safe = _sanitize_filename(module_name)
        name_counts[safe] += 1
        suffix = f"_{name_counts[safe]}" if name_counts[safe] > 1 else ""
        out_path = out_dir / f"Mod_{safe}{suffix}.txt"

        _write_text(out_path, code)
        written += 1

        # Optional warning for later success checks
        if not re.search(r"(?im)^\s*(Public\s+|Private\s+|Friend\s+)?(Sub|Function)\b", code):
            warned_no_subfunc += 1

    print(f"Excel:   {excel_path}")
    print(f"Out dir: {out_dir}")
    print(f"Wrote {written} module file(s).")

    if warned_no_subfunc:
        print(
            f"WARNING: {warned_no_subfunc} module file(s) contain no 'Sub' or 'Function' "
            f"(may be constants/declares/classes).",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
