"""Resolve stored signals without changing legacy outcome evidence."""
from collections import defaultdict
from datetime import date, datetime
import json
from praecursor.analysis.outcomes import LABEL_VERSION, evaluate_path
from praecursor.data.canonical import select_candle
from praecursor.core.sessions import completed_session, next_session, CAIRO

SCHEMA = """
CREATE TABLE IF NOT EXISTS verified_outcomes (
 run_id INTEGER NOT NULL, symbol TEXT NOT NULL, signal_date TEXT NOT NULL,
 next_day_label TEXT, next_day_hit INTEGER, next_day_return REAL, next_day_max_return REAL,
 next_day_trade_hit INTEGER, next_day_net_return REAL, next_day_status TEXT,
 resolved_session TEXT, swing_label TEXT, swing_hit INTEGER, swing_trade_hit INTEGER,
 swing_net_return REAL, swing_status TEXT, swing_resolved_session TEXT,
 label_version TEXT NOT NULL DEFAULT '3', cost_bps REAL NOT NULL DEFAULT 25, PRIMARY KEY(run_id,symbol)
);
CREATE TABLE IF NOT EXISTS corporate_actions (
 symbol TEXT NOT NULL, effective_session TEXT NOT NULL, price_factor REAL NOT NULL,
 source_url TEXT NOT NULL, verified INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(symbol,effective_session)
);
"""


def resolve_history(conn, as_of_date=None):
    conn.executescript(SCHEMA)
    cutoff = min(date.fromisoformat(as_of_date) if as_of_date else completed_session(), completed_session()).isoformat()
    source_rows = conn.execute("SELECT * FROM source_prices WHERE date(trade_date)<=? ORDER BY trade_date,source", (cutoff,)).fetchall()
    groups = defaultdict(list)
    session_symbols = defaultdict(set)
    for r in source_rows:
        session = str(r["trade_date"])[:10]
        groups[(r["ticker"], session)].append(r)
        if r["source"] != "mubasher" and r["volume"] > 0:
            session_symbols[session].add(r["ticker"])
    # Infer historical exchange sessions from broad market observations; never skip
    # a missing ticker candle just because another ticker traded on the next day.
    universe_size = len({key[0] for key in groups})
    minimum = min(10, max(1, universe_size // 3))
    sessions = sorted(d for d, symbols in session_symbols.items() if len(symbols) >= minimum)
    observed_sessions = set(sessions)
    candles = {key: select_candle(rows) for key, rows in groups.items()}
    actions = {(r["symbol"], r["effective_session"]): r["price_factor"] for r in conn.execute(
        "SELECT * FROM corporate_actions WHERE verified=1 AND price_factor>0 AND source_url<>''")}
    count = 0
    for sig in conn.execute("SELECT * FROM scanner_signals ORDER BY generated_at,run_id"):
        sig = dict(sig)
        # New signals store the feature session explicitly. Legacy anchoring is
        # only accepted when its recorded close matches the dated canonical bar.
        from praecursor.analysis.accuracy_tracker import _parse_signal_date
        generated = _parse_signal_date(sig["generated_at"]).isoformat()
        if generated > cutoff:
            continue
        published_session = sig.get("feature_session")
        ref = published_session
        if not ref:
            stamp = datetime.fromisoformat(str(sig["generated_at"]).replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=CAIRO)
            feature_cutoff = completed_session(stamp).isoformat()
            prior = [d for d in sessions if d <= feature_cutoff and candles.get((sig["symbol"], d))]
            if not prior:
                continue
            ref = prior[-1]
            bar = candles[(sig["symbol"], ref)]
            if not sig["latest_close"] or abs(bar.close / sig["latest_close"] - 1) > .01:
                continue
        if published_session:
            # An exchange-wide data gap cannot shift a published next-open entry.
            entry = next_session(date.fromisoformat(ref)).isoformat()
            future = [entry] + [d for d in sessions if d > entry][:19] if entry <= cutoff else []
        else:
            future = [d for d in sessions if d > ref][:20]
        path = [candles.get((sig["symbol"], d)) if d in observed_sessions else None for d in future]
        # Split factors come only from explicit verified events, never price-ratio guesses.
        # Convert all future bars back to the signal's price basis.
        from dataclasses import replace
        factor = 1.0
        adjusted = []
        for d, bar in zip(future, path):
            factor *= actions.get((sig["symbol"], d), 1.0)
            adjusted.append(replace(bar, open=bar.open/factor, high=bar.high/factor,
                                    low=bar.low/factor, close=bar.close/factor) if bar else None)
        reference = float(sig["latest_close"] or 0)
        target = float(sig["next_day_target"] or 0)
        stop = float(sig.get("next_day_stop_loss") or 0)
        nd = evaluate_path(adjusted, reference, target, stop, 1)
        swing_target = float(sig.get("swing_target") or 0)
        # Old signals without a published swing target are not retrospectively relabelled.
        sw = evaluate_path(adjusted, reference, swing_target, float(sig.get("swing_stop_loss") or 0), 20)
        previous = conn.execute("SELECT * FROM verified_outcomes WHERE run_id=? AND symbol=?",
                                (sig["run_id"], sig["symbol"])).fetchone()
        # Freeze resolved observations under this protocol; vendor revisions remain in the price journal.
        terminal = {"target", "stop", "horizon_exit", "unfilled", "ambiguous_barrier_order"}
        from praecursor.analysis.outcomes import Outcome
        if previous and previous["label_version"] == LABEL_VERSION:
            for horizon in ("next_day", "swing"):
                if previous[horizon+"_status"] not in terminal:
                    continue
                frozen = Outcome(previous[horizon+"_status"], target_hit=previous[horizon+"_hit"],
                    trade_hit=previous[horizon+"_trade_hit"], net_return_pct=previous[horizon+"_net_return"],
                    resolved_session=previous["resolved_session" if horizon=="next_day" else "swing_resolved_session"],
                    close_return_pct=previous["next_day_return"] if horizon=="next_day" else None,
                    max_return_pct=previous["next_day_max_return"] if horizon=="next_day" else None)
                if horizon == "next_day":
                    nd = frozen
                else:
                    sw = frozen
        conn.execute("""INSERT OR REPLACE INTO verified_outcomes VALUES
            (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            sig["run_id"], sig["symbol"], ref, sig["next_day_label"], nd.target_hit,
            nd.close_return_pct, nd.max_return_pct, nd.trade_hit, nd.net_return_pct, nd.status,
            nd.resolved_session, sig["swing_label"], sw.target_hit, sw.trade_hit,
            sw.net_return_pct, sw.status, sw.resolved_session, LABEL_VERSION, 25.0))
        if nd.target_hit is not None and (previous is None or previous["next_day_hit"] is None):
            count += 1
    conn.commit()
    return count
