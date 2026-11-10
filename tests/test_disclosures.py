from datetime import datetime, timedelta, timezone
import json
import sqlite3
from praecursor.collectors.egx_disclosures import parse_homepage, ingest_records, collect, disclosure_summary


def fixture():
    row = dict(code=123,dateStamp="2026-11-09T17:30:00",heading="Example (COMI.CA) Results",
               headingArabic="نتائج أعمال",content="Net Profit: 1,200<br>Net Comparative Profit: 900<br>Currency: EGP",isin="EGS000000001")
    flight = '1:["$","$L1",null,' + json.dumps(dict(disclosureNews=[row]),ensure_ascii=False) + ']'
    return '<script>self.__next_f.push(' + json.dumps([1,flight],ensure_ascii=False) + ')</script>'


def test_official_records_preserve_known_time_and_revisions():
    conn=sqlite3.connect(":memory:");conn.row_factory=sqlite3.Row
    now=datetime(2026,11,10,7,tzinfo=timezone.utc)
    rows=parse_homepage(fixture())
    assert ingest_records(conn,rows,now)==1
    assert ingest_records(conn,rows,now+timedelta(hours=1))==0
    event=disclosure_summary(conn)["events"][0]
    assert event["symbol"]=="COMI" and event["known_at"]==now.isoformat()
    assert event["published_at"] < event["known_at"]
    assert event["facts"]["net_profit"]==1200 and event["facts"]["currency"]=="EGP"
    rows[0][1]["content"]="Net Profit: 1,300"
    assert ingest_records(conn,rows,now+timedelta(hours=2))==1
    assert conn.execute("SELECT count(*) FROM disclosure_events").fetchone()[0]==2
    assert disclosure_summary(conn)["events"][0]["facts"]["net_profit"]==1300


def test_failed_or_empty_feed_never_erases_prior_events():
    conn=sqlite3.connect(":memory:");conn.row_factory=sqlite3.Row
    now=datetime(2026,11,10,7,tzinfo=timezone.utc)
    assert collect(conn,lambda:fixture(),now)["status"]=="partial"
    assert collect(conn,lambda:"Request rejected",now+timedelta(hours=1))["status"]=="unavailable"
    summary=disclosure_summary(conn)
    assert len(summary["events"])==1 and summary["last_success_at"]==now.isoformat()


def test_ambiguous_symbols_are_not_guessed_and_future_items_are_ignored():
    conn=sqlite3.connect(":memory:")
    rows=parse_homepage(fixture())
    rows[0][1]["heading"]="COMI.CA and HRHO.CA transaction"
    assert ingest_records(conn,rows,datetime(2026,11,8,tzinfo=timezone.utc))==0
    assert ingest_records(conn,rows,datetime(2026,11,10,tzinfo=timezone.utc))==1
    assert conn.execute("SELECT symbol FROM disclosure_events").fetchone()[0] is None
