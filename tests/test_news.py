from datetime import datetime, timedelta, timezone
import json

from fastapi.testclient import TestClient
import pytest

from praecursor.collectors import news
from praecursor.reporting import news as view

NOW = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)
RSS = b"""<?xml version="1.0" encoding="utf-8"?>
<rss xmlns:atom="http://www.w3.org/2005/Atom" version="2.0"><channel>
<item><title>Central bank publishes statement &amp; market update</title>
<link>http://arabfinance.com/en/news/newdetails/49711?utm_source=rss</link>
<atom:updated>2026-11-16T09:00:00+02:00</atom:updated></item>
<item><title>Invalid link</title><link>https://arabfinance.com@localhost/en/news/newdetails/9</link></item>
<item><title>Future date</title><link>https://arabfinance.com/en/news/newdetails/49712</link>
<pubDate>Tue, 17 Nov 2026 00:00:00 GMT</pubDate></item>
</channel></rss>"""


def only_rss(name, now):
    if name == "egx":
        raise TimeoutError
    return list(news.rss_items(RSS, name, now))


def test_cloud_index_deduplicates_retains_and_tracks_revisions():
    state = news.collect({}, NOW, loader=only_rss)
    assert len(state["items"]) == 1
    item = state["items"][0]
    assert item["source"] == "macro"
    assert item["url"] == "https://www.arabfinance.com/en/news/newdetails/49711"
    assert item["title"] == "Central bank"
    assert item["published_at"] is None
    assert item["source_updated_at"] == "2026-11-16T07:00:00+00:00"

    def outage(source, now):
        raise TimeoutError

    later = NOW + timedelta(hours=6)
    fallback = news.collect(state, later, loader=outage)
    assert fallback["items"] == [item]
    assert fallback["sources"]["macro"]["status"] == "unavailable"
    assert fallback["sources"]["macro"]["last_success_at"] == NOW.isoformat()

    def revised(source, now):
        return list(news.rss_items(RSS.replace(b"Central bank", b"Inflation"), source, now)) if source == "macro" else []

    revised_state = news.collect(fallback, later, loader=revised)
    assert revised_state["items"][0]["title"] == "Inflation"
    assert revised_state["items"][0]["first_seen_at"] == NOW.isoformat()
    assert revised_state["items"][0]["revised_at"] == later.isoformat()


def test_official_news_uses_disclosure_identity_and_cairo_time(monkeypatch):
    row = {"code": 14, "dateStamp": "2026-11-16T08:00:00", "heading": "ABC.ABC COMI.CA Dividend",
           "headingArabic": "إفصاح", "content": "<b>Details</b>"}
    monkeypatch.setattr(news, "parse_homepage", lambda data: [
        ("financialStatements", row), ("disclosureNews", row),
    ])
    item, = news.official_items(b"", NOW)
    assert item["symbols"] == ["COMI"]
    assert item["title_ar"] == "إفصاح"
    assert item["category"] == "Dividends"
    assert item["published_at"] == "2026-11-16T06:00:00+00:00"
    assert "newsCode=14" in item["url"]



def test_egx_crossposts_consolidate_without_merging_distinct_scopes(monkeypatch):
    row = dict(code=20, dateStamp="2026-11-16T08:00:00",
               heading="Example (COMI.CA) Reports its Financial Results (Consolidated)",
               headingArabic="شركة مساهمة (COMI.CA)")
    statement = dict(row, code=19)
    standalone = dict(row, code=18, heading=row["heading"].replace("Consolidated", "Standalone"))
    records = [("financialStatements", statement)]
    monkeypatch.setattr(news, "parse_homepage", lambda data: records)

    def loader(source, now):
        return list(news.official_items(b"", now)) if source == "egx" else []

    previous = news.collect({}, NOW, loader=loader)
    records += [("disclosureNews", row), ("financialStatements", standalone)]
    refreshed = news.collect(previous, NOW + timedelta(hours=1), loader=loader)
    assert {item["title"] for item in refreshed["items"]} == {row["heading"], standalone["heading"]}
    primary = next(item for item in refreshed["items"] if item["title"] == row["heading"])
    assert primary["category"] == "Financial results"
    assert "newsCode=20" in primary["url"]
    assert primary["first_seen_at"] == NOW.isoformat()
    assert all("aliases" not in item for item in refreshed["items"])


def test_rejects_untrusted_index_links_and_feed_declarations():
    state = news.collect({}, NOW, loader=only_rss)
    state["items"][0]["url"] = "https://www.arabfinance.com@localhost/article"
    with pytest.raises(ValueError, match="Unexpected news link"):
        news.load_snapshot(json.dumps(state).encode())
    with pytest.raises(ValueError, match="Unexpected feed declaration"):
        list(news.rss_items(b"<!DOCTYPE rss><rss><channel/></rss>", "macro", NOW))


def test_dashboard_serves_cached_state_and_keeps_personal_headlines_local(monkeypatch, tmp_path):
    from praecursor.cli import dashboard

    class FrozenClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW

    monkeypatch.setattr(view, "datetime", FrozenClock)
    state = news.collect({}, NOW, loader=only_rss)
    cache = tmp_path / "news.json"
    news.write_snapshot(cache, state)

    def offline(*args):
        raise TimeoutError

    def personal(source, now, *, personal):
        return list(news.rss_items(RSS, source, now, personal=personal))

    monkeypatch.setattr(view, "fetch", offline)
    monkeypatch.setattr(view, "read_source", personal)
    monkeypatch.setattr(dashboard, "news_feed", view.NewsFeed(cache))
    client = TestClient(dashboard.app)
    monkeypatch.setattr(dashboard, "is_machine_whitelisted", lambda: False)
    assert client.get("/api/news").status_code == 403

    monkeypatch.setattr(dashboard, "is_machine_whitelisted", lambda: True)
    assert 'href="/dashboard/news">News</a>' in client.get("/dashboard").text
    assert "Market news" in client.get("/dashboard/news").text
    response = client.get("/api/news")
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["status"] == "cached"
    assert response.json()["items"][0]["title"].startswith("Central bank publishes")
    assert news.load_snapshot(cache.read_bytes())["items"][0]["title"] == "Central bank"
