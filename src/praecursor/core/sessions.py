"""Cairo end-of-day policy and exchange closure overrides.

16:00 Cairo is a conservative publication cutoff, not a claimed exchange close.
Verified closure dates can be maintained in config/market_closures.json.
Historical evaluation uses observed market-wide sessions instead of guessing holidays.
"""
from datetime import datetime, date, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import json

CAIRO = ZoneInfo("Africa/Cairo")


def is_session(day: date):
    path = Path(__file__).resolve().parents[3] / "config" / "market_closures.json"
    closures = json.loads(path.read_text()) if path.exists() else []
    return day.weekday() not in (4, 5) and day.isoformat() not in closures


def completed_session(now=None):
    now = (now or datetime.now(CAIRO)).astimezone(CAIRO)
    day = now.date()
    if now.time() < time(16):
        day -= timedelta(days=1)
    while not is_session(day):
        day -= timedelta(days=1)
    return day


def next_session(day: date):
    day += timedelta(days=1)
    while not is_session(day):
        day += timedelta(days=1)
    return day
