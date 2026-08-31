"""
Outcome Tracker for Praecursor-EGX

Evaluates previous scanner predictions against actual market data
to determine if the targets were hit. This forms the critical feedback
loop for the ML models.
"""

import logging
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from praecursor.analysis.accuracy_tracker import track_outcomes_from_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = ROOT / "database" / "praecursor.db"


def track_outcomes():
    logger.info("Running Outcome Tracker...")
    track_outcomes_from_db(DB_PATH)


if __name__ == "__main__":
    track_outcomes()

