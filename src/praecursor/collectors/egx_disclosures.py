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
    if not isinstance(value, str) or re.fullmatch(r"\$[0-9a-f]+", value.strip(), re.I):
        return ""
    return BeautifulSoup(value, "html.parser").get_text(" ", strip=True)


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


def facts_from_body(body, body_ar=""):
    facts = {}
    arabic = body_ar.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩٬٫", "0123456789,."))
    for field, english, translated in (
        ("net_profit", "Net Profit", "صافي الربح"),
        ("comparative_profit", "Net Comparative Profit", "صافي ربح المقارنة|صافي الربح المقارن"),
    ):
        matches = [m for label, source in ((english, body), (translated, arabic))
                   for m in re.finditer(rf"(?:{label})\s*:\s*(-?(?:\d{{1,3}}(?:,\d{{3}})+|\d+)(?:\.\d+)?)(?![\d,.])", source, re.I)]
        values = {m[1].replace(",", "") for m in matches}
        if len(values) == 1 and len(next(iter(values))) <= 24:
            facts[field] = float(next(iter(values)))
            facts[field + "_evidence"] = matches[0][0]
    currencies = []
    for source, pattern in ((body, r"Currency\s*:\s*(Egyptian Pound|US Dollar|[A-Z]{3}\b)"),
                            (arabic, r"العملة\s*:\s*(جنيه مصر[ىي]|دولار أمريكي|[A-Z]{3}\b)")):
        currencies.extend(re.finditer(pattern, source))
    aliases = {"Egyptian Pound": "EGP", "US Dollar": "USD", "جنيه مصرى": "EGP",
               "جنيه مصري": "EGP", "دولار أمريكي": "USD"}
    codes = {aliases.get(m[1], m[1]) for m in currencies}
    if len(codes) == 1:
        facts.update(currency=codes.pop(), currency_evidence=currencies[0][0])
    periods = []
    scopes = {"المجمعة": "consolidated", "المستقلة": "standalone"}
    for source, pattern in (
        (body, r"F/S\s*\((Consolidated|Standalone)\)\s*Period:\s*From (\d{2}/\d{2}/\d{4}) to (\d{2}/\d{2}/\d{4})"),
        (arabic, r"(?:القوائم المالية|أرقام المقارنة)\s+(المجمعة|المستقلة)\s+عن الفترة:\s*من (\d{2}/\d{2}/\d{4}) إلى (\d{2}/\d{2}/\d{4})"),
    ):
        stated = []
        for m in re.finditer(pattern, source, re.I):
            try:
                start, end = (datetime.strptime(s, "%d/%m/%Y").date().isoformat() for s in m.groups()[1:])
            except ValueError:
                continue
            if start <= end:
                stated.append(dict(scope=scopes.get(m[1], m[1].lower()), start=start, end=end, evidence=m[0]))
        if stated:
            periods.append(stated)
    if periods:
        primary = periods[0]
        for index, item in enumerate(primary):
            if any(index < len(other) and any(other[index][key] != item[key] for key in ("scope", "start", "end"))
                   for other in periods[1:]):
                facts["period_conflict"] = True
                break
        else:
            facts["stated_periods"] = primary
    unit = re.search(r"\b(?:Units?|Amounts in)\s*:\s*(units|thousands|millions|billions)\b", body, re.I)
    if unit:
        facts.update(unit=unit[1].lower(), unit_evidence=unit[0])
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
        isins = set(re.findall(r"\bEG[A-Z0-9]{10}\b", " ".join((str(row.get("isin") or ""), body, body_ar))))
        isin = next(iter(isins)) if len(isins) == 1 else None
        if len(isins) > 1:
            symbol = None
        kind = classify(title + " " + title_ar, group)
        facts = facts_from_body(body, body_ar) if kind == "financial_results" else {}
        facts["issuer_evidence"] = dict(tickers=sorted(matches), isins=sorted(isins))
        content = json.dumps(row, sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha256(content.encode()).hexdigest()
        params = dict(tab="disclosure", newsCode=code, openNewsDetails=1)
        if group == "marketNews":
            params["marketSessionNews"] = "true"
        url = "https://beta.egx.com.eg/en/media-center?" + urlencode(params)
        cursor = conn.execute("INSERT OR IGNORE INTO disclosure_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            f"{group}:{code}", digest, symbol, isin, published.isoformat(), now.isoformat(),
            now.isoformat(), kind, title or body[:200],
            title_ar, body, body_ar, url, json.dumps(facts), content))
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
