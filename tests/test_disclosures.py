from datetime import datetime, timedelta, timezone
import json
import sqlite3
from praecursor.collectors.egx_disclosures import parse_homepage, ingest_records, collect, disclosure_summary
from praecursor.collectors.egx_disclosures import facts_from_body, text_only


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


def test_official_template_leaves_units_unknown_and_rejects_conflicts():
    body = ("Currency: Egyptian Pound F/S (Consolidated) Period: From 01/07/2026 to 30/09/2026 "
            "Net profit: 42,638,754 F/S (Consolidated) Period: From 01/07/2025 to 30/09/2025 "
            "Net Comparative profit: 111,275,045")
    arabic = "العملة: جنيه مصرى صافي الربح: ٤٢٬٦٣٨٬٧٥٤"
    facts = facts_from_body(body, arabic)
    assert facts["net_profit"] == 42638754 and facts["currency"] == "EGP"
    assert facts["stated_periods"][1]["start"] == "2025-07-01"
    assert "unit" not in facts
    assert "net_profit" not in facts_from_body(body, arabic.replace("٤٢", "٤٣"))
    arabic_period = "القوائم المالية المجمعة عن الفترة: من ٠١/٠٧/٢٠٢٦ إلى ٣٠/٠٩/٢٠٢٦"
    assert facts_from_body("", arabic_period)["stated_periods"][0]["scope"] == "consolidated"
    assert facts_from_body(body, arabic_period.replace("المجمعة", "المستقلة"))["period_conflict"]
    assert text_only("$33") == ""


def test_study_freezes_pre_scan_revision_and_controls(tmp_path, monkeypatch):
    from praecursor.analysis import disclosure_study as study
    from praecursor.analysis.data_quality import SCHEMA
    from praecursor.analysis.verified_history import SCHEMA as OUTCOMES

    stamp = datetime(2026,11,10,18,tzinfo=timezone.utc)
    with sqlite3.connect(tmp_path / "study.db") as conn:
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA + OUTCOMES + """CREATE TABLE scanner_signals(
            run_id, symbol, feature_session, generated_at, opportunity_score);""")
        body = ("ISIN Code: EGS000000001 F/S (Consolidated) Period: From 01/07/2026 to 30/09/2026 "
                "Currency: Egyptian Pound")
        event = dict(code=1,dateStamp="2026-11-10T16:30:00+00:00",
                     heading="Bank (COMI.CA) Financial Results",content=body)
        ingest_records(conn,[("disclosureNews",event),("financialStatements",dict(event, code=2))],
                       stamp-timedelta(minutes=30))
        ingest_records(conn,[("disclosureNews",dict(event, heading="Other (RAYA.CA) Financial Results"))],
                       stamp+timedelta(minutes=1))
        conn.execute("INSERT INTO feed_health VALUES ('egx_disclosures',?,?,'partial','',2)",
                     ((stamp-timedelta(minutes=20)).isoformat(),)*2)
        for symbol in ("COMI", "CANA", "RAYA"):
            conn.execute("INSERT INTO scanner_signals VALUES (1,?,'2026-11-10',?,70)", (symbol,stamp.isoformat()))
            conn.execute("INSERT INTO instrument_observations VALUES (?,'provider',?,'EGP','https://example.com')",
                         (symbol,(stamp-timedelta(minutes=30)).isoformat()))
        monkeypatch.setattr(study,"eligible_features",lambda row: {"avg_turnover_20":500_000})
        study.record_disclosure_study(conn,1,stamp+timedelta(minutes=2))
        payload = conn.execute("SELECT snapshot FROM disclosure_study_sessions").fetchone()[0]
        snapshot = json.loads(payload)
        assert snapshot["observed_events"] == 1
        assert snapshot["pair"]["event_symbol"] == "COMI" and snapshot["pair"]["control_symbol"] == "CANA"
        assert study.disclosure_study_summary(conn)["unresolved"] == 1
        for symbol, gain in (("COMI", 2), ("CANA", 0)):
            conn.execute("""INSERT INTO verified_outcomes
                (run_id,symbol,signal_date,resolved_session,label_version,next_day_net_return,next_day_status)
                VALUES (1,?,'2026-11-10','2026-11-11',?,?,?)""",
                (symbol,study.LABEL_VERSION,gain,"target" if gain else "unfilled"))
        report = study.disclosure_study_summary(conn)
        assert report["resolved"] == 1 and report["mean_excess_pct"] == 2
        assert report["stressed_excess_pct"] == 1.5 and report["interval_95"] is None
        study.record_disclosure_study(conn,1,stamp+timedelta(minutes=5))
        assert conn.execute("SELECT snapshot FROM disclosure_study_sessions").fetchone()[0] == payload
        later = stamp + timedelta(days=1)
        conn.execute("INSERT INTO scanner_signals VALUES (2,'COMI','2026-11-11',?,70)", (later.isoformat(),))
        study.record_disclosure_study(conn,2,later+timedelta(minutes=2))
        assert study.disclosure_study_summary(conn)["coverage"]["feed_unavailable_or_stale"] == 1
