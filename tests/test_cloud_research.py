from datetime import date, datetime, timedelta, timezone
import json
import sqlite3
from unittest.mock import Mock

import pandas as pd
import pytest

from praecursor.analysis.data_quality import SCHEMA, audit_data, currency_evidence, refresh_quote_currencies
from praecursor.analysis.outcomes import outcome_category
from praecursor.analysis.shadow_experiments import choose, record_shadow, resolve_shadows, trial_decision, approved_paper_filter
from praecursor.analysis.weekly_report import build_weekly, freeze_weekly, format_weekly, completed_week
from tools.automation_watchdog import due_workflows, needs_recovery

NOW = datetime(2026,11,10,18,tzinfo=timezone.utc)


def connection():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA+"""
      CREATE TABLE source_prices(ticker,trade_date,open,high,low,close,volume,source);
      CREATE TABLE scanner_signals(run_id,symbol,candidate_rank,feature_session,indicator_values_json);
      CREATE TABLE verified_outcomes(run_id,symbol,next_day_status,next_day_net_return);
    """)
    return conn


def test_reference_refresh_is_independent_of_price_history_and_never_assumes_currency():
    with connection() as conn:
        fetch = Mock(return_value="<p>Currency is EGP</p>")
        assert refresh_quote_currencies(conn,["COMI"],NOW,fetch)=={"COMI":"observed"}
        refresh_quote_currencies(conn,["COMI"],NOW,fetch)
        assert fetch.call_count==1
        assert currency_evidence(conn,"COMI",NOW)=="EGP"
        conn.execute("INSERT INTO instrument_observations VALUES ('COMI','other',?,'USD','https://example.com')",(NOW.isoformat(),))
        assert currency_evidence(conn,"COMI",NOW)=="conflicting"
        assert currency_evidence(conn,"COMI",NOW+timedelta(days=8)) is None
        assert refresh_quote_currencies(conn,["NONE"],NOW,Mock(side_effect=OSError()))=={"NONE":"unavailable"}
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


def weekly_frame():
    return pd.DataFrame([dict(symbol=f"P{i}",session="2026-11-09",candidate_rank=i+1,
        next_day_resolved_session="2026-11-10",next_day_target_hit=hit,
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
            conn.execute("INSERT INTO verified_outcomes VALUES (1,?,'horizon_exit',?)",(f"P{i}",2 if i<2 else -2))
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
    preview=dict(created_at="2026-11-10T19:00:00Z",status="completed",conclusion="success",event="workflow_dispatch",display_title="Daily scanner")
    assert needs_recovery([preview],due)
    assert not needs_recovery([dict(preview,event="schedule")],due)
    assert not needs_recovery([dict(preview,status="queued",event="schedule",conclusion=None)],due)
    assert not needs_recovery([dict(preview,display_title="Watchdog recovery - scanner",conclusion="failure")],due)


def test_resolved_predictions_survive_vendor_revisions():
    from praecursor.analysis.verified_history import resolve_history
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory=sqlite3.Row
        conn.executescript("""CREATE TABLE source_prices(ticker,trade_date,open,high,low,close,volume,source);
            CREATE TABLE scanner_signals(run_id,symbol,generated_at,feature_session,latest_close,
            next_day_target,next_day_stop_loss,next_day_label,swing_label);
            INSERT INTO scanner_signals VALUES (1,'COMI','2026-11-09T18:00:00Z','2026-11-09',100,105,95,'candidate','swing');
            INSERT INTO source_prices VALUES ('COMI','2026-11-09',100,103,99,100,1000,'tradingview');
            INSERT INTO source_prices VALUES ('COMI','2026-11-10',100,106,99,104,1000,'tradingview');""")
        resolve_history(conn,"2026-11-10")
        original=dict(conn.execute("SELECT * FROM verified_outcomes").fetchone())
        assert original["next_day_hit"]==1 and original["next_day_trade_hit"]==1
        conn.execute("UPDATE source_prices SET high=101,low=94,close=96 WHERE trade_date='2026-11-10'")
        resolve_history(conn,"2026-11-10")
        assert dict(conn.execute("SELECT * FROM verified_outcomes").fetchone())==original
