import sys
import pathlib

# Add …/Arno/output to sys.path so compare.py is importable
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import compare

def test_compare_results_no_diff():
    """Excel and Python results must be identical."""
    assert compare.main() == 0
