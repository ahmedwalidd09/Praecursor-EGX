"""Dated reference checks and conservative, machine-readable data review queues."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sqlite3
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from praecursor.core.sessions import completed_session
from praecursor.data.canonical import select_candle
from praecursor.data.symbol_mapper import SymbolMapper

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = """
CREATE TABLE IF NOT EXISTS reference_checks (
 symbol TEXT PRIMARY KEY, checked_at TEXT, status TEXT, source_url TEXT);
CREATE TABLE IF NOT EXISTS quality_audits (
 checked_at TEXT PRIMARY KEY, session TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS instrument_observations (
 ticker TEXT, source TEXT, observed_at TEXT, currency TEXT, source_url TEXT,
 PRIMARY KEY(ticker,source,observed_at));
"""


def currency_evidence(conn, symbol, now):
    rows = conn.execute("""SELECT source,currency,observed_at FROM instrument_observations
        WHERE ticker=? AND datetime(observed_at)<=datetime(?) AND datetime(observed_at)>=datetime(?)
        ORDER BY datetime(observed_at) DESC""",
        (symbol, now.isoformat(), (now-timedelta(days=7)).isoformat())).fetchall()
    latest = {}
    for row in rows:
        latest.setdefault(row[0], row[1])
    currencies = set(latest.values())
    return next(iter(currencies)) if len(currencies) == 1 else "conflicting" if currencies else None


def _download(url):
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; Praecursor-EGX/0.1)"})
    with urlopen(request, timeout=10) as response:
        content = response.read(2_000_001)
    if len(content) > 2_000_000:
        raise ValueError("Reference page exceeds limit")
    return content.decode("utf-8")


def refresh_quote_currencies(conn, symbols, now=None, download=None, symbol_mapper=None):
    """Refresh only missing/stale candidate references, independently of OHLCV success."""
    from praecursor.collectors.stockanalysis_source import quote_currency
    conn.executescript(SCHEMA)
    now = now or datetime.now(timezone.utc)
    mapper = symbol_mapper or SymbolMapper.from_csv()
    results = {}
    for symbol in sorted(set(symbols)):
        if not re.fullmatch(r"[A-Z][A-Z0-9-]{0,12}", symbol):
            raise ValueError("Invalid EGX symbol")
        currency = currency_evidence(conn, symbol, now)
        if currency and currency != "conflicting":
            results[symbol] = "fresh"
            continue
        try:
            provider_symbol = mapper.get_stockanalysis_symbol(symbol).strip().upper()
        except KeyError:
            results[symbol] = "unmapped"
            continue
        if not re.fullmatch(r"[A-Z][A-Z0-9-]{0,12}", provider_symbol):
            raise ValueError("Invalid StockAnalysis symbol mapping")
        url = f"https://stockanalysis.com/quote/egx/{provider_symbol}/"
        try:
            currency = quote_currency((download or _download)(url), provider_symbol)
            if not currency:
                status = "unverified_reference"
            else:
                conn.execute("INSERT OR IGNORE INTO instrument_observations VALUES (?,?,?,?,?)",
                             (symbol, "stockanalysis", now.isoformat(), currency, url))
                status = "observed"
        except HTTPError as exc:
            status = f"http_{exc.code}"
        except Exception:
            status = "unavailable"  # Failed references never become assumed EGP.
        conn.execute("INSERT OR REPLACE INTO reference_checks VALUES (?,?,?,?)",
                     (symbol, now.isoformat(), status, url))
        results[symbol] = status
    conn.commit()
    return results


def audit_data(conn, now=None, symbols=None):
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    now = now or datetime.now(timezone.utc)
    session = completed_session(now).isoformat()
    if symbols is None:
        mapper = SymbolMapper.from_csv(ROOT / "config/symbols.csv")
        enabled_symbols = set(mapper.get_symbols())
        configured = {symbol: symbol in enabled_symbols for symbol in mapper.get_symbols(include_disabled=True)}
    else:
        configured = dict.fromkeys(symbols, True)
    groups = defaultdict(list)
    for row in conn.execute("SELECT * FROM source_prices WHERE date(trade_date)=?", (session,)):
        groups[row["ticker"]].append(row)
    provider_dates = defaultdict(dict)
    reference_checks = {r["symbol"]: dict(r) for r in conn.execute("SELECT * FROM reference_checks")}
    for ticker, source, last in conn.execute("""SELECT ticker,source,max(date(trade_date))
        FROM source_prices WHERE date(trade_date)<=? GROUP BY ticker,source""", (session,)):
        provider_dates[ticker][source] = last
    records = []
    for symbol, enabled in sorted(configured.items()):
        candle = select_candle(groups[symbol]) if groups[symbol] else None
        sources = provider_dates[symbol]
        valid = {item.source: item for row in groups[symbol] if (item := select_candle([row]))}
        display = valid.get("stockanalysis")
        primary = valid.get("tradingview")
        # Audit-only comparison to the published two-decimal history display.
        # Keep canonical selection and its verification gates unchanged.
        prices = ("open", "high", "low", "close")
        display_compatible = bool(display and primary and display.volume == primary.volume
            and all(abs(getattr(display, field) * 100 - round(getattr(display, field) * 100)) < 1e-7
                    and abs(getattr(display, field) - getattr(primary, field)) <= .0050000001
                    for field in prices))
        evidence = ("complete" if candle else "display_compatible_conflict" if display_compatible and len(valid) == 2
                    else "source_conflict" if len(valid) > 1 else
                    "invalid_or_no_trades" if groups[symbol] else "no_current_observation")
        records.append(dict(symbol=symbol, enabled=enabled, last_price_session=max(sources.values(), default=None),
            price_status="current" if candle else "conflicting_or_invalid" if groups[symbol] else "stale_or_missing",
            price_evidence=evidence, canonical_source=candle.source if candle else None, source_sessions=sources,
            agreeing_sources=candle.agreeing_sources if candle else 0,
            reference_check=reference_checks.get(symbol),
            quote_currency=currency_evidence(conn, symbol, now)))
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    reviews = []
    if "disclosure_events" in tables:
        for row in conn.execute("""SELECT * FROM (
                SELECT *,ROW_NUMBER() OVER(PARTITION BY event_id ORDER BY known_at DESC,content_hash DESC) AS revision
                FROM disclosure_events WHERE datetime(known_at)>=datetime(?) AND datetime(known_at)<=datetime(?))
            WHERE revision=1 ORDER BY known_at DESC,event_id""",
            ((now-timedelta(days=14)).isoformat(), now.isoformat())):
            notice = " ".join(row[field] or "" for field in ("title", "title_ar", "body", "body_ar"))
            calendar = bool(re.search(r"\bholidays?\b|إجازة|عطلة|اجازة", notice, re.I))
            if row["event_type"] in ("capital_action", "trading_suspension") or calendar:
                reviews.append(dict(event_id=row["event_id"], symbol=row["symbol"],
                    kind="calendar_notice" if calendar else row["event_type"], source_url=row["source_url"],
                    known_at=row["known_at"], title=row["title"], title_ar=row["title_ar"],
                    status="Effective date/factor not automatically verified"))
    fresh = sum(r["price_status"] == "current" for r in records)
    report = dict(checked_at=now.isoformat(), expected_session=session, configured_symbols=len(records),
        current_symbols=fresh, coverage_pct=100*fresh/len(records) if records else 0,
        enabled_symbols=sum(configured.values()),
        current_enabled_symbols=sum(r["enabled"] and r["price_status"] == "current" for r in records),
        stale_or_missing=[r["symbol"] for r in records if r["price_status"] == "stale_or_missing"],
        conflicting_or_invalid=[r["symbol"] for r in records if r["price_status"] == "conflicting_or_invalid"],
        unknown_or_conflicting_currency=[r["symbol"] for r in records if r["quote_currency"] in (None,"conflicting")],
        single_source_symbols=[r["symbol"] for r in records if r["agreeing_sources"] == 1],
        market_wide_data_gap=fresh < max(1, len(records)*.5), review_queue=reviews, symbols=records,
        calendar_status="Configured closures plus weekday schedule; incomplete official coverage. A market-wide gap is not inferred to be a holiday.",
        action_status="Unverified notices are flagged; price adjustment factors are never guessed.")
    conn.execute("INSERT OR IGNORE INTO quality_audits VALUES (?,?,?)", (now.isoformat(),session,json.dumps(report)))
    conn.commit()
    return report
