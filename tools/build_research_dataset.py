"""Rebuild versioned retrospective samples without changing source prices or saved signals."""
import logging
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from praecursor.ml.research import build_dataset

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(build_dataset(ROOT/"database/praecursor.db"))
