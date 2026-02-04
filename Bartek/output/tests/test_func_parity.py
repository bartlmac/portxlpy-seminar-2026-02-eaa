# tests/test_func_parity.py
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Iterable, Set


_VBA_PUBLIC_DECL_RE = re.compile(
    r"""^\s*
    (?P<scope>Public|Private|Friend)?\s*
    (?P<kind>Function|Sub)\s+
    (?P<name>[A-Za-z_]\w*)
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _find_vba_module_files() -> list[Path]:
    """
    Prefer repo layout: Mod_*.txt next to /Bartek/output (parent of ./tests).
    Fallback to /mnt/data for sandbox runs.
    """
    out_dir = Path(__file__).resolve().parents[1]
    files = sorted(out_dir.glob("Mod_*.txt"))
    if files:
        return files

    mnt = Path("/mnt/data")
    files = sorted(mnt.glob("Mod_*.txt"))
    return files


def _extract_public_vba_names(vba_text: str) -> Set[str]:
    """
    Collect all VBA Function/Sub names that are public by the rule:
    - include declarations that are NOT marked Private
    - ignore 'Friend' (treated as non-public for parity)
    - ignore 'Declare Function/Sub' (WinAPI declarations)
    """
    names: Set[str] = set()

    for raw in vba_text.splitlines():
        line = raw.strip()

        # Ignore empty and comment-only lines
        if not line or line.startswith("'"):
            continue

        # Ignore Attribute lines
        if line.lower().startswith("attribute "):
            continue

        # Ignore Declare statements (e.g., Declare Function ...)
        if re.search(r"\bdeclare\s+(function|sub)\b", line, flags=re.IGNORECASE):
            continue

        m = _VBA_PUBLIC_DECL_RE.match(line)
        if not m:
            continue

        scope = (m.group("scope") or "").strip().lower()
        if scope == "private":
            continue
        if scope == "friend":
            continue

        name = m.group("name").strip()
        if name:
            names.add(name.lower())

    return names


def _find_basfunct_path() -> Path:
    out_dir = Path(__file__).resolve().parents[1]
    candidate = out_dir / "basfunct.py"
    if candidate.exists():
        return candidate

    mnt = Path("/mnt/data") / "basfunct.py"
    if mnt.exists():
        return mnt

    raise FileNotFoundError("basfunct.py not found next to tests/ or in /mnt/data.")


def _extract_python_def_names(py_text: str) -> Set[str]:
    """
    Extract top-level Python function defs from basfunct.py via AST.
    Helpers are allowed to exist; parity checks only that VBA names exist in Python.
    """
    tree = ast.parse(py_text)
    names: Set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name.lower())
    return names


def test_vba_to_python_function_parity() -> None:
    vba_files = _find_vba_module_files()
    assert vba_files, "No Mod_*.txt VBA module exports found."

    vba_names: Set[str] = set()
    for p in vba_files:
        vba_names |= _extract_public_vba_names(p.read_text(encoding="utf-8", errors="ignore"))

    assert vba_names, "No public VBA Function/Sub declarations found in Mod_*.txt files."

    basfunct_path = _find_basfunct_path()
    py_names = _extract_python_def_names(basfunct_path.read_text(encoding="utf-8"))

    # For each public VBA name, exactly one Python def should exist.
    # (Python module cannot have true duplicate def names; so this reduces to membership.)
    missing = sorted(n for n in vba_names if n not in py_names)

    assert not missing, (
        "Missing Python function(s) in basfunct.py for public VBA name(s):\n"
        + "\n".join(missing)
    )
