"""Read the official public homepage's latest disclosures, preserving first-seen times.

The homepage is a partial feed, not a complete exchange archive or live halt feed.
"""
from datetime import datetime, timezone
import hashlib
import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
from praecursor.core.sessions import CAIRO

SOURCE = "https://beta.egx.com.eg/en"
GROUPS = ("disclosureNews", "listingNews", "memberNews", "financialStatements", "marketNews")
SCHEMA = """
CREATE TABLE IF NOT EXISTS disclosure_events (
 event_id TEXT NOT NULL, content_hash TEXT NOT NULL, symbol TEXT, isin TEXT,
 published_at TEXT NOT NULL, first_seen_at TEXT NOT NULL, known_at TEXT NOT NULL,
 event_type TEXT NOT NULL, title TEXT NOT NULL, title_ar TEXT NOT NULL,
 body TEXT NOT NULL, body_ar TEXT NOT NULL, source_url TEXT NOT NULL,
 facts_json TEXT NOT NULL, raw_json TEXT NOT NULL, PRIMARY KEY(event_id,content_hash));
CREATE TABLE IF NOT EXISTS feed_health (
 feed TEXT PRIMARY KEY, checked_at TEXT NOT NULL, last_success_at TEXT,
 status TEXT NOT NULL, message TEXT NOT NULL, record_count INTEGER NOT NULL);
"""


def text_only(value):
    return BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True)


def parse_homepage(html):
    chunks = []
    for script in BeautifulSoup(html, "html.parser").find_all("script"):
        text = (script.string or "").strip()
        prefix = "self.__next_f.push("
        if text.startswith(prefix):
            try:
                payload = json.loads(text[len(prefix):].rstrip(";")[:-1])
                if len(payload) > 1 and payload[0] == 1 and isinstance(payload[1], str):
                    chunks.append(payload[1])
            except (ValueError, TypeError, IndexError):
                continue
    data = "".join(chunks)
    records = []
    for group in GROUPS:
        for match in re.finditer('"' + group + r'":\s*\[', data):
            rows, _ = json.JSONDecoder().raw_decode(data[match.end()-1:])
            if not isinstance(rows, list):
                raise ValueError("Unexpected EGX disclosure payload")
            records.extend((group, row) for row in rows if isinstance(row, dict))
    if not records:
        raise ValueError("Official homepage returned no readable disclosure records")
    return records


def classify(title, group):
    lowered = title.lower()
    for kind, terms in (
        ("trading_resumption", ("resume of trading", "resumption", "اعادة التعامل", "إعادة التعامل")),
        ("trading_suspension", ("suspension", "suspend", "ايقاف", "إيقاف")),
        ("capital_action", ("capital increase", "stock split", "rights issue", "زيادة رأس", "زيادة راس", "تجزئة")),
        ("dividend", ("dividend", "coupon", "كوبون", "توزيع أرباح", "توزيع ارباح")),
        ("treasury_shares", ("treasury", "اسهم خزينة", "أسهم خزينة")),
        ("ownership", ("ownership", "shareholding", "ملكية", "مساهم")),
        ("financial_results", ("financial results", "results", "نتائج أعمال", "نتائج اعمال")),
    ):
        if any(term in lowered for term in terms):
            return kind
    return "financial_results" if group == "financialStatements" else "other"


def facts_from_body(body):
    facts = {}
    for field, pattern in (
        ("net_profit", r"Net Profit\s*:\s*([-\d,]+(?:\.\d+)?)"),
        ("comparative_profit", r"Net Comparative Profit\s*:\s*([-\d,]+(?:\.\d+)?)"),
    ):
        match = re.search(pattern, body, re.I)
        if match:
            facts[field] = float(match.group(1).replace(",", ""))
            facts[field + "_evidence"] = match.group(0)
    currency = re.search(r"Currency\s*:\s*([A-Z]{3})\b", body)
    if currency:
        facts["currency"] = currency.group(1)
    # No growth/materiality score without verified comparable periods and consolidation basis.
    return facts


def ingest_records(conn, records, now=None):
    conn.executescript(SCHEMA)
    now = now or datetime.now(timezone.utc)
    count = 0
    for group, row in records:
        try:
            code = int(row["code"])
            published = datetime.fromisoformat(row["dateStamp"].replace("Z", "+00:00"))
            if published.tzinfo is None:
                published = published.replace(tzinfo=CAIRO)
            published = published.astimezone(timezone.utc)
        except (KeyError, ValueError, TypeError):
            continue
        if published > now or code <= 0:
            continue
        title, title_ar = text_only(row.get("heading")), text_only(row.get("headingArabic"))
        body, body_ar = text_only(row.get("content")), text_only(row.get("contentArabic"))
        if not (title or title_ar or body or body_ar):
            continue
        matches = set(re.findall(r"\b([A-Z][A-Z0-9-]{1,12})\.CA\b", " ".join((title, title_ar, body, body_ar))))
        symbol = next(iter(matches)) if len(matches) == 1 else None
        content = json.dumps(row, sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha256(content.encode()).hexdigest()
        params = dict(tab="disclosure", newsCode=code, openNewsDetails=1)
        if group == "marketNews":
            params["marketSessionNews"] = "true"
        url = "https://beta.egx.com.eg/en/media-center?" + urlencode(params)
        cursor = conn.execute("INSERT OR IGNORE INTO disclosure_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            f"{group}:{code}", digest, symbol, row.get("isin"), published.isoformat(), now.isoformat(),
            max(now, published).isoformat(), classify(title + " " + title_ar, group), title or body[:200],
            title_ar, body, body_ar, url, json.dumps(facts_from_body(body)), content))
        count += cursor.rowcount
    conn.commit()
    return count


def collect(conn, fetch=None, now=None):
    conn.executescript(SCHEMA)
    now = now or datetime.now(timezone.utc)
    stamp = now.isoformat()
    previous = conn.execute("SELECT last_success_at FROM feed_health WHERE feed='egx_disclosures'").fetchone()
    last_success = previous[0] if previous else None
    try:
        if fetch is None:
            request = Request(SOURCE, headers={"User-Agent": "Praecursor-EGX public disclosure research"})
            with urlopen(request, timeout=30) as response:
                html = response.read(5_000_001)
                if len(html) > 5_000_000:
                    raise ValueError("Disclosure page exceeded size limit")
        else:
            html = fetch()
        records = parse_homepage(html)
        added = ingest_records(conn, records, now)
        status, message, last_success = "partial", "Official homepage snapshot; archive completeness and live trading status are not guaranteed", stamp
    except Exception as exc:
        added, status, message = 0, "unavailable", f"Official disclosure collection failed ({type(exc).__name__}); prior records retained"
    conn.execute("INSERT OR REPLACE INTO feed_health VALUES ('egx_disclosures',?,?,?,?,?)", (stamp, last_success, status, message, added))
    conn.commit()
    return dict(status=status, message=message, added=added, checked_at=stamp)


def disclosure_summary(conn, limit=30):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "disclosure_events" not in tables:
        return dict(status="Not collected", events=[], message="Awaiting an official disclosure snapshot")
    health = conn.execute("SELECT * FROM feed_health WHERE feed='egx_disclosures'").fetchone()
    rows = conn.execute("""SELECT * FROM (SELECT *,ROW_NUMBER() OVER(PARTITION BY event_id ORDER BY known_at DESC) AS revision
        FROM disclosure_events) WHERE revision=1 ORDER BY published_at DESC LIMIT ?""", (limit,)).fetchall()
    events = []
    for row in rows:
        item = dict(row)
        for field in ("raw_json", "body", "body_ar", "content_hash", "revision"):
            item.pop(field, None)
        item["facts"] = json.loads(item.pop("facts_json"))
        events.append(item)
    return dict(dict(health) if health else {}, events=events)
