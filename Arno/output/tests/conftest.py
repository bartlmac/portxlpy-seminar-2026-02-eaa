import os
from pathlib import Path

# Immediately switch to the output directory
os.chdir(Path(__file__).resolve().parents[1])   # …/Arno/output
