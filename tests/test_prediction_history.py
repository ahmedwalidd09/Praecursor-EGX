import sqlite3
import pytest
from praecursor.reporting.prediction_history import prediction_history


def history_db():
    conn=sqlite3.connect(":memory:");conn.row_factory=sqlite3.Row
    conn.executescript("""CREATE TABLE scanner_signals(id,run_id,symbol,company,generated_at,
      latest_close,next_day_target,feature_session,candidate_rank,next_day_label);
      CREATE TABLE verified_outcomes(run_id,symbol,signal_date,resolved_session,
      next_day_hit,next_day_return,next_day_max_return,next_day_status);""")
    return conn


def add(conn, run, symbol, hit=None, close=None, high=None, status=None, resolved=None, scan=1):
    conn.execute("INSERT INTO scanner_signals VALUES (?,?,?,?,?,?,?,?,?,?)",
                 (run,scan,symbol,symbol+" Company",f"2026-11-05T{16+run:02}:00:00Z",100,105,"2026-11-05",run,""))
    if status:
        conn.execute("INSERT INTO verified_outcomes VALUES (?,?,?,?,?,?,?,?)",
                     (scan,symbol,"2026-11-05",resolved,hit,close,high,status))


def test_history_hit_miss_and_actual_prices_use_saved_outcomes():
    with history_db() as conn:
        add(conn,1,"HIT",1,-2,6,"ambiguous_barrier_order","2026-11-08")
        add(conn,2,"MISS",0,0,4,"horizon_exit","2026-11-08")
        rows={r["symbol"]:r for r in prediction_history(conn)}
    assert rows["HIT"]["status"]=="hit"  # Target touch is distinct from trade profit.
    assert rows["HIT"]["actual_high"]==pytest.approx(106)
    assert rows["HIT"]["actual_close"]==pytest.approx(98)
    assert rows["MISS"]["status"]=="miss"
    assert rows["MISS"]["actual_close"]==100
    assert rows["MISS"]["close_change_pct"]==0
    assert all(r["session"]=="2026-11-08" for r in rows.values())


def test_pending_and_conflicting_data_never_become_misses():
    with history_db() as conn:
        add(conn,1,"NEW")
        add(conn,2,"CONFLICT",status="missing_or_conflicting_candle")
        rows={r["symbol"]:r for r in prediction_history(conn)}
    assert rows["NEW"]["status"]=="pending"
    assert rows["CONFLICT"]["status"]=="unverified"
    assert rows["NEW"]["session"]=="2026-11-08" and not rows["NEW"]["session_confirmed"]
    assert all(r["actual_high"] is None and r["actual_close"] is None for r in rows.values())


def test_reruns_keep_first_prediction_and_confirmed_session_overrides_calendar_guess():
    with history_db() as conn:
        add(conn,1,"TEST",0,-2,1,"horizon_exit","2026-11-09")
        add(conn,2,"TEST",1,7,8,"target","2026-11-09",scan=2)
        rows=prediction_history(conn)
    assert len(rows)==1 and rows[0]["status"]=="miss"
    assert rows[0]["session"]=="2026-11-09"


def test_only_saved_top_five_candidates_are_displayed():
    with history_db() as conn:
        for rank in range(1,8):
            add(conn,rank,f"PICK{rank}")
        conn.execute("UPDATE scanner_signals SET candidate_rank=NULL,next_day_label='Top Pick #2 (Candidate)' WHERE symbol='PICK2'")
        conn.execute("UPDATE scanner_signals SET candidate_rank=NULL WHERE symbol='PICK3'")
        rows=prediction_history(conn)
    assert [r["candidate_rank"] for r in rows]==[1,2,4,5]
    assert [r["symbol"] for r in rows]==["PICK1","PICK2","PICK4","PICK5"]


def test_pending_history_without_outcome_table_and_empty_database():
    with history_db() as conn:
        add(conn,1,"NEW")
        conn.execute("DROP TABLE verified_outcomes")
        assert prediction_history(conn)[0]["status"]=="pending"
        conn.execute("DROP TABLE scanner_signals")
        assert prediction_history(conn)==[]
