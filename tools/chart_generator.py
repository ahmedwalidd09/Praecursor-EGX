import sqlite3
import json
import csv
import math
import sys
from pathlib import Path
from datetime import date
from html import escape
import re
from string import Template
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "database" / "praecursor.db"
REPORTS_DIR = ROOT / "reports"
CHARTS_DIR = REPORTS_DIR / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

def fetch_symbol_history(symbol: str, lookback: int = 70, through: str | None = None) -> pd.DataFrame:
    """Fetch recent daily OHLCV bars for a symbol from SQLite database."""
    query = """
    SELECT trade_date, open, high, low, close, volume
    FROM (
        SELECT trade_date, open, high, low, close, volume,
               ROW_NUMBER() OVER (
                   PARTITION BY trade_date 
                   ORDER BY CASE source WHEN 'tradingview' THEN 1 WHEN 'stockanalysis' THEN 2 ELSE 3 END, 
                            collected_at DESC
               ) as rn
        FROM source_prices
        WHERE ticker = ? AND date(trade_date) <= ?
    )
    WHERE rn = 1
    ORDER BY trade_date DESC
    LIMIT ?
    """
    with sqlite3.connect(str(DB_PATH)) as conn:
        df = pd.read_sql(query, conn, params=(symbol, through or "9999-12-31", lookback))
    
    if df.empty or len(df) < 15:
        return pd.DataFrame()
    
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df.sort_values("trade_date").reset_index(drop=True)

def get_candidate_metadata(symbol: str) -> dict:
    """Read candidate ranking, labels, target and stop from opportunity_ranking.csv."""
    csv_path = REPORTS_DIR / "opportunity_ranking.csv"
    if not csv_path.exists():
        return {}
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if r.get("symbol") == symbol:
                return r
    return {}

def price_value(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value > 0 else None


def saved_level(meta, field, prose_label):
    if field in meta:
        return price_value(meta[field])
    match = re.search(rf"{prose_label} placed at ([0-9.]+)", meta.get("next_day_reasons") or "")
    return price_value(match.group(1)) if match else None


def generate_chart_html(symbol: str, df: pd.DataFrame, meta: dict) -> str:
    """Render the saved setup with full-precision daily price geometry."""
    bars = [dict(date=row.trade_date.strftime("%d %b"), open=float(row.open),
                 high=float(row.high), low=float(row.low), close=float(row.close),
                 volume=float(row.volume))
            for row in df.itertuples()]
    reference = price_value(meta.get("latest_close")) or price_value(bars[-1]["close"])
    target = saved_level(meta, "next_day_target", "Target")
    stop = saved_level(meta, "next_day_stop_loss", "Stop Loss")
    levels = [reference, target, stop]
    precision = 4 if any(value is not None and value < 1 for value in levels) else 3

    def display_price(value):
        return f"{value:,.{precision}f}" if value is not None else "—"

    reward_risk = ""
    if target and stop and reference and 0 < stop < reference < target:
        reward_risk = f"Reward / risk {(target - reference) / (reference - stop):.2f}×"

    rank = meta.get("candidate_rank")
    rank = f"Candidate {int(rank):02d}" if rank else "Daily chart"
    feature = meta.get("feature_session") or df["trade_date"].iloc[-1].date().isoformat()
    target_session = meta.get("target_session")
    close_date = date.fromisoformat(feature).strftime("%d %b %Y")
    session = f"Briefing <strong>{date.fromisoformat(target_session):%d %b %Y}</strong>" if target_session else ""

    reasons = meta.get("selection_reasons") or ""
    if isinstance(reasons, str):
        reasons = json.loads(reasons) if reasons.startswith("[") else reasons.split("; ")
    selected = [reason for reason in reasons if reason and not reason.startswith("Target/stop reward-to-risk")][:2]
    selected.extend((meta.get("adaptive_levels") or [])[:1])
    evidence = "".join(f"<p>{escape(reason)}</p>" for reason in selected)
    if evidence:
        evidence = '<section class="evidence"><span class="kicker">Selection evidence</span>' + evidence + "</section>"

    template = Template(Path(__file__).with_name("candidate_chart.html").read_text(encoding="utf-8"))
    return template.substitute(
        symbol=escape(symbol), company=escape(meta.get("company") or symbol), rank=rank,
        session=session, close_date=close_date, reference=display_price(reference),
        target=display_price(target), stop=display_price(stop), reward_risk=reward_risk,
        evidence=evidence, chart_data=json.dumps(dict(bars=bars, levels=levels), allow_nan=False),
    )


def capture_chart(page, html_file: Path, png_path: Path):
    page.goto(html_file.as_uri())
    page.locator('canvas[data-rendered="true"]').wait_for(timeout=5000)
    page.screenshot(path=str(png_path), type="png", full_page=True)


def render_chart_to_png(symbol: str, output_path: Path | None = None) -> Path | None:
    """Generate and capture a high-res PNG chart for a given symbol."""
    meta = get_candidate_metadata(symbol)
    if not meta:
        print(f"Warning: Metadata for {symbol} not found in opportunity_ranking.csv.")
        
    df = fetch_symbol_history(symbol, lookback=65)
    if df.empty:
        print(f"Error: Could not retrieve price history for {symbol}.")
        return None
        
    html = generate_chart_html(symbol, df, meta)
    
    html_file = CHARTS_DIR / f"{symbol}_chart.html"
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html)
        
    png_path = output_path or (CHARTS_DIR / f"{symbol}_chart.png")
    
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 600, "height": 740}, device_scale_factor=2)
            capture_chart(page, html_file, png_path)
            browser.close()
            
        print(f"Chart saved: {png_path} ({png_path.stat().st_size} bytes)")
        return png_path
    except Exception as e:
        print(f"Error rendering chart with Playwright for {symbol}: {e}")
        return None

def generate_top_candidates_charts(top_n: int = 5, session: str | None = None) -> list[Path]:
    """Generate charts for the dated shortlist or the current ranking CSV."""
    if session:
        from contextlib import closing
        from praecursor.notifications.owner_briefing import original_shortlist
        from praecursor.analysis.adaptive_levels import adaptive_notes
        with closing(sqlite3.connect(str(DB_PATH))) as conn:
            picks = original_shortlist(conn, session)
            notes = adaptive_notes(conn, picks[0]["run_id"]) if picks else {}
        for pick in picks:
            pick["adaptive_levels"] = notes.get(pick["symbol"], [])
        return generate_candidate_charts({r["symbol"]: r for r in picks[:top_n]}, session)
    csv_path = REPORTS_DIR / "opportunity_ranking.csv"
    if not csv_path.exists():
        print("opportunity_ranking.csv not found.")
        return []

    with open(csv_path, "r", encoding="utf-8") as f:
        eligible = [r for r in csv.DictReader(f) if r.get("symbol") and r.get("candidate_rank")]
    eligible.sort(key=lambda r: int(r["candidate_rank"]))
    return generate_candidate_charts({r["symbol"]: r for r in eligible[:top_n]})


def generate_candidate_charts(candidates: dict, session: str | None = None) -> list[Path]:
    if not candidates:
        print("No eligible candidates found for chart generation.")
        return []

    print(f"Generating charts for {len(candidates)} candidates: {', '.join(candidates)}...")
    generated = []
    
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 600, "height": 740}, device_scale_factor=2)
            
            for sym, meta in candidates.items():
                try:
                    df = fetch_symbol_history(sym, lookback=65, through=meta.get("feature_session") if session else None)
                    if df.empty:
                        print(f"Skipping {sym}: insufficient data.")
                        continue
                    if session and df["trade_date"].iloc[-1].date().isoformat() != meta.get("feature_session"):
                        print(f"Skipping {sym}: chart data do not reach the saved price session.")
                        continue
                    
                    html = generate_chart_html(sym, df, meta)
                    stem = f"{session}_{sym}_chart" if session else f"{sym}_chart"
                    html_file = CHARTS_DIR / f"{stem}.html"
                    with open(html_file, "w", encoding="utf-8") as f:
                        f.write(html)
                        
                    png_path = CHARTS_DIR / f"{stem}.png"
                    capture_chart(page, html_file, png_path)
                    print(f"[OK] Generated chart: {png_path.name} ({png_path.stat().st_size} bytes)")
                    generated.append(png_path)
                except Exception as e:
                    print(f"Error generating chart for {sym}: {e}")
                    
            browser.close()
    except Exception as pw_err:
        print(f"Warning: Playwright chart generation encountered an error: {pw_err}")
        
    return generated


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate high-resolution dark mode candlestick chart PNGs.")
    parser.add_argument("--symbol", type=str, help="Single EGX ticker symbol to chart (e.g. SDTI)")
    parser.add_argument("--top", type=int, default=5, help="Generate charts for top N candidates (default: 5)")
    parser.add_argument("--session", help="Use the original shortlist saved for this session")
    args = parser.parse_args()

    if args.symbol:
        render_chart_to_png(args.symbol.upper())
    else:
        charts = generate_top_candidates_charts(args.top, args.session)
        if args.session and not charts:
            sys.exit(1)
