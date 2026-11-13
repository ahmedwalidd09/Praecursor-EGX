from datetime import date, datetime, timezone
import json
import sqlite3

import pytest

from praecursor.analysis.adaptive_levels import (
    adaptive_notes, economics, level_plan, record_adaptive_levels, resolve_adaptive_levels, simulate,
)
from praecursor.analysis.data_quality import SCHEMA
from praecursor.analysis.paper_portfolio import load_policy
from praecursor.core.sessions import next_session


def path(count, scale=1, noise=1):
    day = date(2025, 11, 30)
    bars = []
    for i in range(count):
        center = 100 + i % 7 / 2
        bars.append([day.isoformat(), center*scale, (center+noise)*scale,
                     (center-noise)*scale, center*scale, 100_000])
        day = next_session(day)
    return bars


def test_structure_noise_scale_and_horizon():
    bars = path(241)
    short = level_plan(bars, 1)
    swing = level_plan(bars, 20)
    assert short["stop"] == pytest.approx(short["support"] - short["noise_buffer"])
    assert short["resistance"] is not None
    assert short["target"] <= short["resistance"]
    assert short["excursion_samples"] != swing["excursion_samples"]
    louder = level_plan(path(241, noise=2), 1)
    assert louder["noise_buffer"] > short["noise_buffer"] and louder["stop"] < short["stop"]
    small = level_plan(path(241, scale=.00255), 1)
    assert small["stop"] == pytest.approx(short["stop"] * .00255)
    assert small["target"] == pytest.approx(short["target"] * .00255)


def test_unavailable_bad_flat_sparse_and_gappy_history():
    bars = path(21)
    assert level_plan(bars, 20)["status"] == "unavailable"
    assert level_plan(bars[:8] + bars[9:] + path(1), 1)["status"] == "unavailable"
    for bar in bars:
        bar[1:5] = [100] * 4
    assert level_plan(bars, 1)["status"] == "unavailable"
    bars[-1][2] = 60
    assert "Invalid OHLCV" in level_plan(bars, 1)["reason"]
    bars[-1][1:5] = [150, 151, 149, 150]
    assert "discontinuity" in level_plan(bars, 1)["reason"]


def test_costs_opening_gap_and_stop_first():
    policy = load_policy()
    terms = economics(100, 99.9, 100.4, policy)
    assert terms["gross_rr"] > 1.5 and terms["net_rr"] < 0
    plan = dict(reference=100, policy=policy, max_gap=.03, turnover=1_000_000,
                horizon_dates=["2026-11-11", "2026-11-12"],
                adaptive=dict(status="eligible", stop=97, target=108))
    day = ["2026-11-11", 100, 106, 99, 100, 100_000]
    assert simulate(plan, "adaptive", [day, None]) is None
    assert simulate(plan, "adaptive", [["2026-11-11", 96, 99, 95, 98, 100_000], day])["status"] == "unfilled_gap_or_lock"
    assert simulate(plan, "adaptive", [["2026-11-11", 109, 110, 108, 109, 100_000], day])["status"] == "unfilled_gap_or_lock"
    gap = simulate(plan, "adaptive", [day, ["2026-11-12", 96, 97, 94, 95, 100_000]])
    ambiguous = simulate(plan, "adaptive", [day, ["2026-11-12", 100, 110, 95, 100, 100_000]])
    assert gap["status"] == "gap_stop" and ambiguous["status"] == "ambiguous_stop_first"
    assert gap["trade_pct"] < ambiguous["trade_pct"] < 0


def test_frozen_preopen_pair_and_currency_gate(monkeypatch):
    import praecursor.analysis.adaptive_levels as module

    bars = path(241)
    feature = bars[-1][0]
    now = datetime.fromisoformat(feature + "T18:00:00+00:00")
    session = next_session(date.fromisoformat(feature))
    monkeypatch.setattr(module, "candidate_bars", lambda *args: bars)
    with sqlite3.connect(":memory:") as conn:
        conn.executescript(SCHEMA + """CREATE TABLE scanner_signals
            (run_id, symbol, feature_session, candidate_rank, generated_at, latest_close, indicator_values_json,
             data_quality_score, next_day_target, next_day_stop_loss, swing_target, swing_stop_loss);""")
        for rank in range(1,6):
            conn.execute("INSERT INTO scanner_signals VALUES (1,?,?,?,?,?,'{\"AvgTurnover20\":1000000}',100,125,99,135,98)",
                         (f"T{rank}",feature,rank,now.isoformat(),bars[-1][4]))
        for symbol,currency in (("T1","EGP"),("T2","USD")):
            conn.execute("INSERT INTO instrument_observations VALUES (?,'provider',?,?,'https://example.com')",
                         (symbol,now.isoformat(),currency))
        record_adaptive_levels(conn, 1, now)
        frozen = list(conn.execute("SELECT plan FROM adaptive_level_trials ORDER BY symbol,horizon"))
        assert len(frozen) == 10
        assert json.loads(frozen[0][0])["baseline"]["status"] == "eligible"
        assert json.loads(frozen[2][0])["adaptive"]["status"] == "unavailable"
        assert json.loads(frozen[4][0])["adaptive"]["status"] == "unavailable"
        assert adaptive_notes(conn, 1)["T2"][0].startswith("Shadow · 1 session · EGP")
        conn.execute("UPDATE scanner_signals SET next_day_target=200")
        record_adaptive_levels(conn, 1, now)
        assert list(conn.execute("SELECT plan FROM adaptive_level_trials ORDER BY symbol,horizon")) == frozen
        mature = datetime.combine(session, datetime.min.time(), timezone.utc).replace(hour=18)
        report = resolve_adaptive_levels(conn, mature)
        assert report["horizons"][0]["paired_sessions"] == 0
        bars.append([session.isoformat(), 101, 106, 98, 102, 100_000])
        report = resolve_adaptive_levels(conn, mature)
        assert report["horizons"][0]["paired_sessions"] == 1
        assert report["horizons"][1]["paired_sessions"] == 0
