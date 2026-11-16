"""Build a bounded news link index from official notices and publisher RSS."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import xml.etree.ElementTree as ET

from praecursor.collectors.egx_disclosures import SOURCE, ingest_records, parse_homepage, text_only

RELEASE = "https://github.com/ahmedwalidd09/Praecursor-EGX/releases/download/news-latest/news.json"
SOURCES = {
    "egx": ("Egyptian Exchange", SOURCE),
    "macro": ("Arab Finance · Macroeconomy", "https://www.arabfinance.com/en/rss/rssbycat/1"),
    "banking": ("Arab Finance · Finance and banking", "https://www.arabfinance.com/en/rss/rssbycat/2"),
}
EGX_CATEGORIES = {
    "trading_resumption": "Trading notices", "trading_suspension": "Trading notices",
    "capital_action": "Capital actions", "dividend": "Dividends",
    "treasury_shares": "Capital actions", "ownership": "Ownership",
    "financial_results": "Financial results", "other": "Exchange notices",
}
RSS_CATEGORIES = {"macro": "Macroeconomy", "banking": "Finance and banking"}
MAX_ITEMS = 300
MAX_SNAPSHOT = 1_000_000
RETENTION = timedelta(days=30)
STALE_AFTER = timedelta(hours=14)


class SourceRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old, new = urlsplit(req.full_url), urlsplit(newurl)
        allowed = new.scheme == "https" and new.netloc == old.netloc
        if req.full_url == RELEASE:
            allowed |= new.scheme == "https" and new.netloc == "release-assets.githubusercontent.com"
        if not allowed:
            raise ValueError("Unexpected news source redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, limit=5_000_000):
    request = Request(url, headers={"User-Agent": "Praecursor-EGX news index"})
    with build_opener(SourceRedirects()).open(request, timeout=15) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("News response exceeded size limit")
    return data


def timestamp(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        try:
            result = datetime.fromisoformat(value)
        except ValueError:
            result = parsedate_to_datetime(value)
        return result.astimezone(timezone.utc) if result.tzinfo is not None else None
    except (ValueError, OverflowError, TypeError):
        return None


def iso(value):
    return value.isoformat() if value else None


def official_items(data, now):
    with closing(sqlite3.connect(":memory:")) as db:
        db.row_factory = sqlite3.Row
        ingest_records(db, parse_homepage(data), now)
        rows = db.execute("""SELECT event_id,title,title_ar,source_url,event_type,symbol,published_at
            FROM disclosure_events ORDER BY event_id LIKE 'financialStatements:%', event_id""").fetchall()

    def match_key(row):
        return tuple(row[key] for key in ("published_at", "symbol", "title", "title_ar"))

    statement_links = {
        (match_key(row), int(row["event_id"].split(":")[1])): row["source_url"]
        for row in rows if row["event_id"].startswith("financialStatements:") and row["symbol"]
    }
    seen = set()
    for row in rows:
        key = row["source_url"]
        if key in seen or not row["title"]:
            continue
        seen.add(key)
        group, code = row["event_id"].split(":")
        kind = row["event_type"]
        if re.search(r"\bfinancial (?:results|statements)\b|القوائم المالية", row["title"] + " " + row["title_ar"], re.I):
            kind = "financial_results"
        aliases = []
        # Paired EGX listings have adjacent references and identical bilingual titles,
        # ticker and timestamp. Prefer the disclosure that links to the attachments.
        if group == "disclosureNews" and kind == "financial_results":
            alias = statement_links.get((match_key(row), int(code) - 1))
            if alias:
                seen.add(alias)
                aliases.append(alias)
        yield dict(source="egx", title=row["title"][:360], title_ar=row["title_ar"][:360],
                   url=key, category=EGX_CATEGORIES[kind], symbols=[row["symbol"]] if row["symbol"] else [],
                   published_at=row["published_at"], source_updated_at=None, aliases=aliases)


def rss_items(data, source, now, *, personal=False):
    # These endpoints use UTF-8 RSS; reject declarations before parsing.
    xml = data.decode("utf-8-sig")
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)", xml, re.I):
        raise ValueError("Unexpected feed declaration")
    feed = ET.fromstring(xml)
    channel = feed.find("channel")
    if feed.tag != "rss" or channel is None:
        raise ValueError("Expected RSS channel")
    for item in channel.findall("item"):
        link = urlsplit(item.findtext("link", ""))
        if link.scheme not in ("http", "https") or link.netloc not in ("arabfinance.com", "www.arabfinance.com"):
            continue
        if not re.fullmatch(r"/en/news/newdetails/\d+", link.path, re.I):
            continue
        published = timestamp(item.findtext("pubDate"))
        updated = timestamp(item.findtext("{http://www.w3.org/2005/Atom}updated"))
        if any(date and date > now for date in (published, updated)):
            continue
        headline = text_only(item.findtext("title", ""))
        if not headline:
            continue
        # Public index stores derived topics and links. Publisher headlines stay local.
        topic = RSS_CATEGORIES[source]
        for label, pattern in (
            ("Central bank", r"\b(?:cbe|central bank)\b"),
            ("Inflation", r"\binflation\b"),
            ("Exchange rates", r"\bexchange rate|\bus dollar\b"),
            ("Earnings", r"\b(?:earnings|profit|losses)\b"),
            ("Investment", r"\binvest(?:ment|or|s)\b"),
            ("Public finances", r"\b(?:budget|fiscal|treasury bills)\b"),
        ):
            if re.search(pattern, headline, re.I):
                topic = label
                break
        yield dict(source=source, title=headline[:360] if personal else topic, title_ar="",
                   url="https://www.arabfinance.com" + link.path.lower(),
                   category=RSS_CATEGORIES[source], symbols=[],
                   published_at=iso(published), source_updated_at=iso(updated))


def read_source(source, now, *, personal=False):
    data = fetch(SOURCES[source][1])
    items = list(official_items(data, now) if source == "egx" else rss_items(data, source, now, personal=personal))
    if not items:
        raise ValueError("No usable news links")
    return items


def collect(previous, now, loader=read_source):
    stamp = iso(now)
    items = {item["url"]: item for item in previous.get("items", [])}
    health = {}
    with ThreadPoolExecutor(max_workers=len(SOURCES)) as pool:
        requests = {source: pool.submit(loader, source, now) for source in SOURCES}
        for source, (label, _) in SOURCES.items():
            last_success = previous.get("sources", {}).get(source, {}).get("last_success_at")
            try:
                new = requests[source].result()
            except (OSError, ValueError, ET.ParseError, UnicodeError) as exc:
                health[source] = dict(label=label, status="unavailable", last_success_at=last_success,
                                      count=0, error=type(exc).__name__)
                continue
            health[source] = dict(label=label, status="ok", last_success_at=stamp, count=len(new))
            for item in new:
                old = items.get(item["url"], {})
                prior_aliases = [items.pop(url, {}) for url in item.pop("aliases", [])]
                item["first_seen_at"] = min(
                    previous_item.get("first_seen_at", stamp) for previous_item in (old, *prior_aliases)
                )
                # Keep one canonical copy when the publisher puts an item in both feeds.
                if old.get("last_seen_at") == stamp:
                    continue
                item["last_seen_at"] = stamp
                item["revised_at"] = old.get("revised_at")
                if old and any(old.get(key) != item[key] for key in ("title", "title_ar", "source_updated_at")):
                    item["revised_at"] = stamp
                items[item["url"]] = item

    def source_date(item):
        return item["published_at"] or item["source_updated_at"]

    recent = [item for item in items.values()
              if timestamp(source_date(item) or item["first_seen_at"]) >= now - RETENTION]
    recent.sort(key=lambda item: (source_date(item) or "", item["first_seen_at"], item["url"]), reverse=True)
    return dict(version=1, generated_at=stamp, sources=health, items=recent[:MAX_ITEMS])


def load_snapshot(data):
    if len(data) > MAX_SNAPSHOT:
        raise ValueError("News snapshot exceeded size limit")
    state = json.loads(data)
    if not isinstance(state, dict) or state.get("version") != 1 or not timestamp(state.get("generated_at")):
        raise ValueError("Invalid news snapshot")
    items, sources = state.get("items"), state.get("sources")
    if not isinstance(items, list) or len(items) > MAX_ITEMS or not isinstance(sources, dict):
        raise ValueError("Invalid news snapshot")
    if set(sources) != set(SOURCES) or any(
        not isinstance(source, dict) or source.get("status") not in ("ok", "unavailable")
        or not isinstance(source.get("label"), str)
        for source in sources.values()
    ):
        raise ValueError("Invalid news source status")
    fields = ("source", "title", "title_ar", "url", "category")
    dates = ("published_at", "source_updated_at", "revised_at")
    for item in items:
        if (not isinstance(item, dict) or any(not isinstance(item.get(key), str) for key in fields)
                or item["source"] not in SOURCES or not timestamp(item.get("first_seen_at"))
                or not timestamp(item.get("last_seen_at")) or any(key not in item or
                    (item[key] is not None and not timestamp(item[key])) for key in dates)
                or not isinstance(item.get("symbols"), list)
                or not all(isinstance(symbol, str) for symbol in item["symbols"])):
            raise ValueError("Invalid news item")
        link = urlsplit(item["url"])
        expected_host = "beta.egx.com.eg" if item["source"] == "egx" else "www.arabfinance.com"
        if link.scheme != "https" or link.netloc != expected_host:
            raise ValueError("Unexpected news link")
    return state


def write_snapshot(path, state):
    path = Path(path)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as file:
        temporary = Path(file.name)
        try:
            json.dump(state, file, ensure_ascii=False, separators=(",", ":"))
            file.close()
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
