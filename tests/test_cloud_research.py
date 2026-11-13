from datetime import date, datetime, timedelta, timezone
import json
import sqlite3
from unittest.mock import Mock

import pandas as pd
import pytest

from praecursor.analysis.data_quality import SCHEMA, audit_data, currency_evidence, refresh_quote_currencies
from praecursor.analysis.outcomes import LABEL_VERSION, outcome_category
from praecursor.analysis.shadow_experiments import choose, record_shadow, resolve_shadows, trial_decision, approved_paper_filter
from praecursor.analysis.weekly_report import build_weekly, freeze_weekly, format_weekly, completed_week
from tools.automation_watchdog import due_workflows, needs_recovery
from tools import automation_watchdog

NOW = datetime(2026,11,10,18,tzinfo=timezone.utc)


def connection():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA+"""
      CREATE TABLE source_prices(ticker,trade_date,open,high,low,close,volume,source);
      CREATE TABLE scanner_signals(run_id,symbol,candidate_rank,feature_session,indicator_values_json);
      CREATE TABLE verified_outcomes(run_id,symbol,next_day_status,next_day_net_return,resolved_session,label_version);
    """)
    return conn


def test_reference_refresh_is_independent_of_price_history_and_never_assumes_currency():
    with connection() as conn:
        fetch = Mock(return_value="<title>Bank (EGX:COMI)</title><p>Currency is EGP</p>")
        assert refresh_quote_currencies(conn,["COMI"],NOW,fetch)=={"COMI":"observed"}
        refresh_quote_currencies(conn,["COMI"],NOW,fetch)
        assert fetch.call_count==1
        assert currency_evidence(conn,"COMI",NOW)=="EGP"
        conn.execute("INSERT INTO instrument_observations VALUES ('COMI','other',?,'USD','https://example.com')",(NOW.isoformat(),))
        assert currency_evidence(conn,"COMI",NOW)=="conflicting"
        assert currency_evidence(conn,"COMI",NOW+timedelta(days=8)) is None
        assert refresh_quote_currencies(conn,["CANA"],NOW,Mock(side_effect=OSError()))=={"CANA":"unavailable"}
        assert refresh_quote_currencies(conn,["CANA"],NOW,fetch)=={"CANA":"unverified_reference"}
        assert currency_evidence(conn,"CANA",NOW) is None
        assert currency_evidence(conn,"NONE",NOW) is None
        with pytest.raises(ValueError):
            refresh_quote_currencies(conn,["../bad"],NOW,fetch)


def test_quality_audit_counts_absent_symbols_and_does_not_invent_holidays():
    with connection() as conn:
        conn.execute("INSERT INTO source_prices VALUES ('COMI','2026-11-10',100,105,99,103,1000,'tradingview')")
        report=audit_data(conn,NOW,["COMI","MISSING","OLD"])
        assert report["current_symbols"]==1 and report["market_wide_data_gap"]
        assert report["stale_or_missing"]==["MISSING","OLD"]
        assert report["unknown_or_conflicting_currency"]==["COMI","MISSING","OLD"]
        assert conn.execute("SELECT count(*) FROM quality_audits").fetchone()[0]==1


def test_audit_shows_conflict_provenance_and_latest_arabic_notice():
    from praecursor.collectors.egx_disclosures import SCHEMA as DISCLOSURES

    with connection() as conn:
        conn.executescript(DISCLOSURES)
        conn.execute("INSERT INTO source_prices VALUES ('COMI','2026-11-10',100,105,99,103,1000,'tradingview')")
        conn.execute("INSERT INTO source_prices VALUES ('COMI','2026-11-10',110,115,109,113,1000,'stockanalysis')")
        conn.execute("INSERT INTO source_prices VALUES ('ZERO','2026-11-10',100,100,100,100,0,'tradingview')")
        for rev, stamp in (("a", NOW-timedelta(days=1)), ("b", NOW), ("c", NOW+timedelta(days=1))):
            conn.execute("INSERT INTO disclosure_events VALUES ('1',?,NULL,NULL,?,?,?,'other','',?,'','','https://beta.egx.com.eg/en','{}','{}')",
                         (rev, stamp.isoformat(), stamp.isoformat(), stamp.isoformat(), f"عطلة {rev}"))
        report = audit_data(conn, NOW, ["COMI", "ZERO"])
        assert [r["price_evidence"] for r in report["symbols"]] == ["source_conflict", "invalid_or_no_trades"]
        assert report["symbols"][0]["source_sessions"] == {"stockanalysis": "2026-11-10", "tradingview": "2026-11-10"}
        assert [(r["kind"], r["title_ar"]) for r in report["review_queue"]] == [("calendar_notice", "عطلة b")]


def weekly_frame():
    return pd.DataFrame([dict(symbol=f"P{i}",session="2026-11-10",candidate_rank=i+1,
        benchmark_eligible=True,next_day_target_hit=hit,
        next_day_net_return_pct=net,next_day_status=status)
        for i,(status,hit,net) in enumerate([("target",1,2),("horizon_exit",0,1),
            ("unfilled",1,0),("ambiguous_barrier_order",1,-2),("pending",None,None)])])


def test_weekly_target_touch_and_profit_are_distinct_missing_is_not_a_loss():
    with connection() as conn:
        audit_data(conn,NOW,[])
        frame=weekly_frame()
        report=freeze_weekly(conn,frame,date(2026,11,12),NOW)
        assert report["target_hits"]==3 and report["target_misses"]==1
        assert report["categories"]==dict(profitable=2,loss=0,breakeven=0,not_filled=1,ambiguous=1,unresolved=1)
        assert report["performance"]["sessions"]==0  # Entire paired session remains incomplete.
        frame.loc[4,"next_day_net_return_pct"]=99
        assert freeze_weekly(conn,frame,date(2026,11,12),NOW)==report
        assert "not EGX30" in format_weekly(report)
        assert completed_week(NOW)==date(2026,11,5)
        assert outcome_category("pending",float("nan"))=="unresolved"


def test_weekly_close_uses_cairo_cutoff_even_if_thursday_is_closed(monkeypatch):
    from praecursor.core import sessions

    thursday = date(2026, 11, 12)
    monkeypatch.setattr(sessions, "is_session",
                        lambda day: day.weekday() not in (4, 5) and day != thursday)
    before_close = datetime(2026, 11, 12, 13, 59, tzinfo=timezone.utc)
    assert completed_week(before_close) == date(2026, 11, 5)
    assert completed_week(before_close + timedelta(minutes=1)) == thursday
    assert completed_week(before_close + timedelta(days=1)) == thursday


@pytest.mark.parametrize("all_old", [False, True])
def test_weekly_counts_original_picks_independently_of_training(tmp_path, monkeypatch, all_old):
    from praecursor.analysis.verified_history import SCHEMA as OUTCOME_SCHEMA
    from praecursor.ml.features import FEATURE_VERSION, INDICATOR_TO_FEATURE
    from praecursor.ml.published import published_samples
    from praecursor.reporting.prediction_history import prediction_history
    from tools import weekly_review

    db = tmp_path / "database" / "praecursor.db"
    db.parent.mkdir()
    features = dict.fromkeys(INDICATOR_TO_FEATURE, 1)
    features["AvgTurnover20"] = 1_000_000
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA + OUTCOME_SCHEMA + """
            CREATE TABLE scanner_signals(id INTEGER PRIMARY KEY,run_id,symbol,company,generated_at,
            latest_close,next_day_target,feature_session,candidate_rank,next_day_label,
            feature_version,indicator_values_json,opportunity_score,data_quality_score);""")
        for run, prefix in ((1, "ORIGINAL"), (2, "RERUN")):
            for rank in range(1, 7):
                symbol = f"{prefix}{rank}"
                conn.execute("""INSERT INTO scanner_signals VALUES
                    (NULL,?,?,?, ?,100,105,'2026-11-09',?,'',?,?,70,100)""",
                    (run, symbol, symbol, f"2026-11-09T{17 + run}:00:00Z", rank if rank <= 5 else None,
                     "old" if run == 1 and (all_old or rank == 2) else FEATURE_VERSION,
                     None if run == 1 and rank == 1 else json.dumps(features)))
                if run == 1 and rank == 2:
                    continue
                conn.execute("""INSERT INTO verified_outcomes
                    (run_id,symbol,signal_date,next_day_hit,next_day_net_return,next_day_status,resolved_session,label_version)
                    VALUES (?,?,'2026-11-09',1,2,'target',?,?)""",
                    (run, symbol, "2026-11-11" if run == 1 and rank == 3 else "2026-11-10", LABEL_VERSION))
        dashboard = prediction_history(conn)
        conn.execute("""UPDATE verified_outcomes SET swing_hit=1,swing_net_return=2,
            swing_status='target',swing_resolved_session='2026-12-08' WHERE symbol='ORIGINAL4'""")
    monkeypatch.setattr(weekly_review, "ROOT", tmp_path)
    monkeypatch.setattr(weekly_review, "datetime", Mock(now=Mock(return_value=NOW + timedelta(days=3))))
    monkeypatch.setattr(weekly_review, "audit_data", Mock())
    monkeypatch.setattr(weekly_review, "resolve_shadows", Mock())
    monkeypatch.setattr("sys.argv", ["weekly_review", "--dry-run"])
    weekly_review.main()
    report = json.loads((tmp_path / "reports" / "weekly_review.json").read_text(encoding="utf-8"))
    detail = report["predictions_detail"]
    assert [(r["symbol"], r["session"], r["rank"]) for r in detail] == [
        (f"ORIGINAL{rank}", "2026-11-10", rank) for rank in range(1, 6)]
    assert [(r["symbol"], r["session"], r["candidate_rank"]) for r in dashboard] == [
        (r["symbol"], r["session"], r["rank"]) for r in detail]
    assert report["target_hits"] == 3 and report["categories"]["unresolved"] == 2
    assert report["performance"]["sessions"] == 0
    frame = published_samples(db).set_index("symbol")
    if all_old:
        assert frame.empty
    else:
        assert set(frame.index) == {"ORIGINAL3", "ORIGINAL4", "ORIGINAL5", "ORIGINAL6"}
        assert pd.isna(frame.loc["ORIGINAL3", "next_day_target_hit"])
        assert pd.isna(frame.loc["ORIGINAL4", "swing_target_hit"])


def test_shadow_plan_is_prospective_frozen_and_rejection_stays_cash():
    with connection() as conn:
        for i in range(10):
            conn.execute("INSERT INTO scanner_signals VALUES (1,?,?,?,?)",(f"P{i}",i+1 if i<5 else None,
                "2026-11-10",json.dumps(dict(AvgTurnover20=2_000_000 if i<2 else 500_000,Momentum20=1))))
            conn.execute("INSERT INTO instrument_observations VALUES (?,'stockanalysis',?,'EGP','https://stockanalysis.com/')",(f"P{i}",NOW.isoformat()))
        record_shadow(conn,1,NOW)
        row=conn.execute("SELECT * FROM shadow_sessions").fetchone()
        assert json.loads(row["choices"])["selected"]==["P0","P1"]
        conn.execute("UPDATE scanner_signals SET indicator_values_json='{}'")
        record_shadow(conn,1,NOW)
        assert dict(conn.execute("SELECT * FROM shadow_sessions").fetchone())==dict(row)
        assert approved_paper_filter(conn,1,NOW) is None
        for i in range(5):
            conn.execute("INSERT INTO verified_outcomes VALUES (1,?,'horizon_exit',?,'2026-11-11',?)",
                         (f"P{i}",2 if i<2 else -2,LABEL_VERSION))
        conn.execute("UPDATE verified_outcomes SET resolved_session='2026-11-12' WHERE symbol='P4'")
        resolve_shadows(conn, NOW+timedelta(days=1))
        assert conn.execute("SELECT result FROM shadow_sessions").fetchone()[0] is None
        conn.execute("UPDATE verified_outcomes SET resolved_session='2026-11-11' WHERE symbol='P4'")
        resolve_shadows(conn, NOW+timedelta(days=1))
        result=json.loads(conn.execute("SELECT result FROM shadow_sessions").fetchone()[0])
        assert result["candidate_return_pct"]==.8 and result["baseline_return_pct"]==-.4
        assert result["stressed_return_pct"]==pytest.approx(.6)
        assert conn.execute("SELECT count(*) FROM shadow_experiments").fetchone()[0]==1


def test_promotion_gate_requires_all_fixed_sessions_and_stressed_advantage():
    good=dict(excess_pct=1,stressed_return_pct=.5)
    assert trial_decision([good]*59) is None
    assert trial_decision([good]*59+[None]) is None
    assert trial_decision([good]*60)["approved"]
    assert not trial_decision([dict(excess_pct=1,stressed_return_pct=-.1)]*60)["approved"]
    assert not trial_decision([dict(excess_pct=-1,stressed_return_pct=1)]*60)["approved"]


def test_watchdog_uses_utc_schedule_skips_previews_and_bounds_retries():
    now=NOW.replace(hour=22)
    due=dict(due_workflows(now))["daily_scan.yml"]
    assert set(dict(due_workflows(now)))=={"daily_scan.yml","model_learning.yml","disclosures.yml"}
    preview=dict(created_at="2026-11-10T19:00:00Z",status="completed",conclusion="success",event="workflow_dispatch",display_title="Daily scanner",head_branch="main")
    assert needs_recovery([preview],due)
    assert not needs_recovery([dict(preview,event="schedule")],due)
    assert not needs_recovery([dict(preview,status="queued",event="schedule",conclusion=None)],due)
    assert not needs_recovery([dict(preview,display_title="Watchdog recovery - scanner",conclusion="failure")],due)
    assert needs_recovery([dict(preview,display_title="Watchdog recovery - scanner",head_branch="test")],due)


def test_watchdog_defers_for_off_schedule_writer_then_dispatches_once(monkeypatch):
    saturday = datetime(2026, 11, 14, 22, tzinfo=timezone.utc)
    monkeypatch.setattr(automation_watchdog, "datetime", Mock(
        now=Mock(return_value=saturday), combine=datetime.combine, fromisoformat=datetime.fromisoformat))
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.delenv("PREVIEW", raising=False)
    weekly = [{"status": "queued"}]
    dispatched = []

    def gh(command, **kwargs):
        if command[1] == "api":
            runs = weekly if "/weekly_review.yml/" in command[2] else []
            return Mock(stdout=json.dumps({"workflow_runs": runs}))
        dispatched.append(command)

    monkeypatch.setattr(automation_watchdog.subprocess, "run", gh)
    automation_watchdog.main()
    assert dispatched == []
    weekly.clear()
    monkeypatch.setenv("PREVIEW", "true")
    automation_watchdog.main()
    assert dispatched == []
    monkeypatch.delenv("PREVIEW")
    automation_watchdog.main()
    assert dispatched == [["gh", "workflow", "run", "daily_scan.yml", "--repo", "owner/repo",
                           "--ref", "main", "-f", "recovery=true"]]


@pytest.mark.parametrize("gap", [False, True])
def test_resolved_predictions_survive_vendor_revisions(gap, monkeypatch):
    from praecursor.analysis import verified_history

    monkeypatch.setattr(verified_history, "completed_session", lambda: date(2026, 11, 11))
    resolve_history = verified_history.resolve_history
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory=sqlite3.Row
        conn.executescript("""CREATE TABLE source_prices(ticker,trade_date,open,high,low,close,volume,source);
            CREATE TABLE scanner_signals(run_id,symbol,generated_at,feature_session,latest_close,
            next_day_target,next_day_stop_loss,next_day_label,swing_label);
            INSERT INTO scanner_signals VALUES (1,'COMI','2026-11-09T18:00:00Z','2026-11-09',100,105,95,'candidate','swing');
            INSERT INTO source_prices VALUES ('COMI','2026-11-09',100,103,99,100,1000,'tradingview');
            INSERT INTO source_prices VALUES ('COMI','2026-11-10',100,106,99,104,1000,'tradingview');""")
        if gap:
            conn.execute("UPDATE source_prices SET trade_date='2026-11-11' WHERE trade_date='2026-11-10'")
            resolve_history(conn,"2026-11-11")
            missing = conn.execute("SELECT * FROM verified_outcomes").fetchone()
            assert missing["next_day_status"] == "missing_or_conflicting_candle"
            assert missing["next_day_hit"] is None
            conn.execute("INSERT INTO source_prices VALUES ('COMI','2026-11-10',100,106,99,104,1000,'tradingview')")
        resolve_history(conn,"2026-11-10")
        original=dict(conn.execute("SELECT * FROM verified_outcomes").fetchone())
        assert original["next_day_hit"]==1 and original["next_day_trade_hit"]==1
        conn.execute("UPDATE source_prices SET high=101,low=94,close=96 WHERE trade_date='2026-11-10'")
        resolve_history(conn,"2026-11-10")
        assert dict(conn.execute("SELECT * FROM verified_outcomes").fetchone())==original


@pytest.mark.parametrize("holiday", [False, True])
def test_swing_keeps_the_configured_twenty_session_boundary(holiday, monkeypatch, tmp_path):
    from praecursor.analysis import verified_history
    from praecursor.core import sessions

    feature = date(2026, 8, 2)
    dates = [feature]
    for _ in range(21):
        dates.append(sessions.next_session(dates[-1]))
    missing = dates[6]
    if holiday:
        monkeypatch.setattr(sessions, "__file__", str(tmp_path / "src/praecursor/core/sessions.py"))
        (tmp_path / "config").mkdir()
        (tmp_path / "config/market_closures.json").write_text(json.dumps([missing.isoformat()]))
    monkeypatch.setattr(verified_history, "completed_session", lambda: dates[-1])
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        conn.executescript("""CREATE TABLE source_prices(ticker,trade_date,open,high,low,close,volume,source);
            CREATE TABLE scanner_signals(run_id,symbol,generated_at,feature_session,latest_close,
            next_day_target,next_day_stop_loss,next_day_label,swing_label,swing_target,swing_stop_loss);
            INSERT INTO scanner_signals VALUES
            (1,'TEST','2026-08-02T18:00:00Z','2026-08-02',100,105,95,'candidate','swing',115,90);""")
        candle = "INSERT INTO source_prices VALUES ('TEST',?,100,?,99,100,1000,'tradingview')"
        conn.executemany(candle, [(d.isoformat(), 120 if d == dates[-1] else 101)
                                 for d in dates if d != missing])

        verified_history.resolve_history(conn, dates[19].isoformat())
        early = conn.execute("SELECT * FROM verified_outcomes").fetchone()
        assert early["next_day_hit"] == 0 and early["resolved_session"] == dates[1].isoformat()
        assert early["swing_status"] == "pending"
        verified_history.resolve_history(conn, dates[-1].isoformat())
        outcome = conn.execute("SELECT * FROM verified_outcomes").fetchone()
        if holiday:
            assert outcome["swing_hit"] == 1
            assert outcome["swing_resolved_session"] == dates[-1].isoformat()
            return
        assert outcome["swing_status"] == "missing_or_conflicting_candle"
        assert outcome["swing_hit"] is None
        conn.execute(candle, (missing.isoformat(), 101))
        verified_history.resolve_history(conn, dates[-1].isoformat())
        original = dict(conn.execute("SELECT * FROM verified_outcomes").fetchone())
        assert original["swing_hit"] == 0
        assert original["swing_resolved_session"] == dates[20].isoformat()
        conn.execute("UPDATE source_prices SET high=120 WHERE trade_date=?", (missing.isoformat(),))
        verified_history.resolve_history(conn, dates[-1].isoformat())
        assert dict(conn.execute("SELECT * FROM verified_outcomes").fetchone()) == original
