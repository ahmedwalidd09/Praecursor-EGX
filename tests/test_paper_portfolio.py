from datetime import datetime, date, timedelta, timezone
import json
import sqlite3

import pytest

from praecursor.analysis.paper_portfolio import load_policy, execution_scenario, record_plan, resolve_paper, paper_summary
from praecursor.data.canonical import Candle


def order():
    return dict(reference=100, target=110, stop=95, quantity=100, avg_turnover=1000000)


def candle(**changes):
    values = dict(session="2026-10-05", open=101, high=112, low=99, close=109,
                  volume=100000, source="tradingview", agreeing_sources=1)
    return Candle(**(values | changes))


def test_execution_costs_partial_fills_and_ambiguous_ordering():
    policy = load_policy()
    result = execution_scenario(order(), candle(), policy)
    assert result["status"] == "target" and 0 < result["net_return_pct"] < (110 / 101 - 1) * 100
    assert result["entry"] > 101 and result["exit"] < 110
    assert execution_scenario(order(), candle(open=112), policy)["quantity"] == 0
    partial = execution_scenario(order(), candle(volume=1000), policy)
    assert 0 < partial["quantity"] <= 5 and partial["partial"]
    ambiguous = execution_scenario(order(), candle(low=94), policy)
    assert ambiguous["ambiguous"] and ambiguous["pnl"] < 0 and ambiguous["target_touched"]
    assert execution_scenario(order(), candle(open=50), policy)["pnl"] is None


def database():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript('''CREATE TABLE scanner_signals(run_id,symbol,candidate_rank,feature_session,
        latest_close,next_day_target,next_day_stop_loss,indicator_values_json,data_quality_score);
        CREATE TABLE source_prices(ticker,trade_date,open,high,low,close,volume,source);
        CREATE TABLE instrument_observations(ticker,source,observed_at,currency,source_url);''')
    for i, symbol in enumerate(("ONE", "TWO", "THREE"), 1):
        conn.execute("INSERT INTO instrument_observations VALUES (?,'stockanalysis','2026-10-04T17:00:00+00:00','EGP','https://stockanalysis.com/')",(symbol,))
        conn.execute("INSERT INTO scanner_signals VALUES (1,?,?,?,?,?,?,?,100)",
                     (symbol,i,"2026-10-04",100,110,95,json.dumps({"AvgTurnover20":1000000})))
        for j in range(70):
            day = date(2026, 10, 4) - timedelta(days=69-j)
            close = 90 + j*.1 + (j % 7)*.2
            conn.execute("INSERT INTO source_prices VALUES (?,?,?,?,?,?,?,?)", (symbol,day.isoformat(),close,close+2,close-2,close,100000,"tradingview"))
    return conn


def test_plans_are_prospective_immutable_and_correlation_limited():
    with database() as conn:
        now = datetime(2026,10,4,18,tzinfo=timezone.utc)
        assert record_plan(conn,1,now=now,sectors={"ONE":"Banks","TWO":"Banks","THREE":"Energy"})
        rows = paper_summary(conn)["orders"]
        assert rows[0]["quantity"] > 0 and all(r["quantity"] == 0 for r in rows[1:])
        assert "correlated" in " ".join(rows[1]["reasons"])
        conn.execute("UPDATE scanner_signals SET next_day_target=200")
        assert not record_plan(conn,1,now=now)
        assert paper_summary(conn)["orders"][0]["target"] == 110
    with database() as conn:
        assert not record_plan(conn,1,now=datetime(2026,10,5,12,tzinfo=timezone.utc))
        assert paper_summary(conn)["sessions"] == 0


def test_missing_prices_hold_positions_and_resolution_is_idempotent():
    with database() as conn:
        record_plan(conn,1,now=datetime(2026,10,4,18,tzinfo=timezone.utc))
        resolve_paper(conn,"2026-10-05")
        assert paper_summary(conn)["pending_sessions"] == 1
        conn.execute("INSERT INTO source_prices VALUES ('ONE','2026-10-05',101,112,99,109,100000,'tradingview')")
        resolve_paper(conn,"2026-10-05")
        summary = paper_summary(conn)
        assert summary["trades"] == 1 and summary["equity"] > 100000 and not summary["pending_sessions"]
        conn.execute("UPDATE source_prices SET high=100 WHERE trade_date='2026-10-05'")
        resolve_paper(conn,"2026-10-05")
        assert paper_summary(conn) == summary


def test_policy_rejects_unsafe_limits(tmp_path):
    policy = load_policy()
    policy["max_participation"] = 20
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy))
    with pytest.raises(ValueError, match="fraction"):
        load_policy(path)


def test_foreign_currency_is_never_sized_as_egp():
    from praecursor.collectors.stockanalysis_source import quote_currency
    assert quote_currency('<p>Currency is EGP · Price in USD</p>') == 'USD'
    assert quote_currency('<p>Currency is EGP</p>') == 'EGP'
    assert quote_currency('<script>Currency is EGP</script>') is None
    with database() as conn:
        conn.execute("UPDATE instrument_observations SET currency='USD' WHERE ticker='ONE'")
        record_plan(conn,1,now=datetime(2026,10,4,18,tzinfo=timezone.utc))
        assert paper_summary(conn)["orders"][0]["quantity"] == 0


def test_drawdown_pauses_the_next_session():
    with database() as conn:
        policy=load_policy();policy["max_drawdown"]=.01
        record_plan(conn,1,now=datetime(2026,10,4,18,tzinfo=timezone.utc),policy=policy)
        conn.execute("UPDATE paper_sessions SET state='resolved'")
        conn.execute("UPDATE paper_orders SET outcome_json=? WHERE symbol='ONE'",(json.dumps(dict(quantity=50,pnl=-1500)),))
        conn.execute("UPDATE scanner_signals SET run_id=2,feature_session='2026-10-05'")
        assert record_plan(conn,2,now=datetime(2026,10,5,18,tzinfo=timezone.utc),policy=policy)
        summary=paper_summary(conn)
        assert 'drawdown' in summary["status"] and all(r["quantity"]==0 for r in summary["orders"])
