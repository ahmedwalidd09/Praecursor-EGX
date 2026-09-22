import sqlite3
import json
import csv
import math
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "database" / "praecursor.db"
REPORTS_DIR = ROOT / "reports"
CHARTS_DIR = REPORTS_DIR / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

def fetch_symbol_history(symbol: str, lookback: int = 70) -> pd.DataFrame:
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
        WHERE ticker = ?
    )
    WHERE rn = 1
    ORDER BY trade_date DESC
    LIMIT ?
    """
    with sqlite3.connect(str(DB_PATH)) as conn:
        df = pd.read_sql(query, conn, params=(symbol, lookback + 100))
    
    if df.empty or len(df) < 15:
        return pd.DataFrame()
    
    # Sort chronologically
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.sort_values("trade_date").reset_index(drop=True)
    
    # Calculate EMAs over full history before slicing
    df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()
    df["vol_ma20"] = df["volume"].rolling(20, min_periods=1).mean()
    
    # Slice to desired display lookback
    display_df = df.iloc[-lookback:].copy().reset_index(drop=True)
    return display_df

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

def parse_target_and_stop(reasons_str: str, current_close: float) -> tuple[float | None, float | None, str, str]:
    """Parse Target and Stop Loss prices and percentage changes from reasons string."""
    import re
    target = None
    stop = None
    target_pct = ""
    stop_pct = ""
    
    m_tgt = re.search(r"Target placed at\s+([\d\.]+)\s+\(\+?([-\d\.]+)%\)", reasons_str)
    if m_tgt:
        target = float(m_tgt.group(1))
        target_pct = f"+{float(m_tgt.group(2)):.1f}%"
    
    m_stop = re.search(r"Stop Loss placed at\s+([\d\.]+)\s+\((-?[\d\.]+)%\)", reasons_str)
    if m_stop:
        stop = float(m_stop.group(1))
        stop_pct = f"{float(m_stop.group(2)):.1f}%"
        
    return target, stop, target_pct, stop_pct

def generate_chart_html(symbol: str, df: pd.DataFrame, meta: dict) -> str:
    """Generate high-contrast, cyberpunk-quant dark-themed candlestick chart HTML."""
    candles = []
    for _, row in df.iterrows():
        candles.append({
            "date": row["trade_date"].strftime("%d %b"),
            "open": round(float(row["open"]), 2),
            "high": round(float(row["high"]), 2),
            "low": round(float(row["low"]), 2),
            "close": round(float(row["close"]), 2),
            "volume": int(row["volume"]),
            "ema20": round(float(row["ema20"]), 2) if not pd.isna(row["ema20"]) else None,
            "ema50": round(float(row["ema50"]), 2) if not pd.isna(row["ema50"]) else None,
            "ema200": round(float(row["ema200"]), 2) if not pd.isna(row["ema200"]) else None,
            "vol_ma20": int(row["vol_ma20"]) if not pd.isna(row["vol_ma20"]) else 0,
        })
    
    company = meta.get("company", symbol)
    close_price = round(float(meta.get("latest_close", candles[-1]["close"])), 2)
    score = f"{float(meta.get('score_percent', 0)):.1f}%"
    label = meta.get("next_day_label", "Breakout Candidate")
    reasons = meta.get("next_day_reasons", "")
    
    target, stop, target_pct, stop_pct = parse_target_and_stop(reasons, close_price)
    
    # Calculate R:R
    rr_str = "N/A"
    if target and stop and target > close_price and stop < close_price:
        gain = target - close_price
        risk = close_price - stop
        if risk > 0:
            rr_str = f"{(gain / risk):.1f} : 1"
            
    # Pattern identification
    pattern_badge = "MOMENTUM SETUP"
    if "NR7" in reasons or "Inside Day" in reasons:
        pattern_badge = "NR7 VOLATILITY COIL"
    elif "Fibonacci" in reasons:
        pattern_badge = "FIBONACCI 61.8% EXPANSION"
    elif "Breakout" in label:
        pattern_badge = "RESISTANCE BREAKOUT"
    elif "VSA" in reasons:
        pattern_badge = "INSTITUTIONAL ABSORPTION"

    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background-color: #07080B;
    color: #F3F4F6;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
    width: 1280px;
    height: 800px;
    overflow: hidden;
    position: relative;
    user-select: none;
  }}

  /* Top Navigation / Header */
  .header {{
    height: 70px;
    padding: 12px 24px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: rgba(13, 15, 22, 0.7);
    backdrop-filter: blur(10px);
  }}
  .header-left {{
    display: flex;
    align-items: center;
    gap: 16px;
  }}
  .symbol {{
    font-size: 26px;
    font-weight: 800;
    letter-spacing: -0.5px;
    color: #FFFFFF;
    font-family: 'JetBrains Mono', monospace, sans-serif;
  }}
  .company {{
    font-size: 14px;
    color: #9CA3AF;
    font-weight: 500;
  }}
  .price-pill {{
    background: #111827;
    border: 1px solid #374151;
    padding: 6px 14px;
    border-radius: 6px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 16px;
    font-weight: 700;
    color: #38BDF8;
  }}
  .badge {{
    padding: 5px 12px;
    border-radius: 5px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    font-family: 'JetBrains Mono', monospace;
  }}
  .badge-setup {{
    background: rgba(16, 185, 129, 0.15);
    color: #10B981;
    border: 1px solid rgba(16, 185, 129, 0.3);
  }}
  .badge-pattern {{
    background: rgba(245, 158, 11, 0.15);
    color: #F59E0B;
    border: 1px solid rgba(245, 158, 11, 0.3);
  }}
  .header-right {{
    display: flex;
    align-items: center;
    gap: 12px;
  }}
  .stat-box {{
    display: flex;
    flex-direction: column;
    align-items: flex-end;
  }}
  .stat-label {{
    font-size: 10px;
    color: #6B7280;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}
  .stat-val {{
    font-size: 15px;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
  }}
  .stat-val.target {{ color: #10B981; }}
  .stat-val.stop {{ color: #EF4444; }}
  .stat-val.rr {{ color: #A855F7; }}

  /* Main Chart Area */
  .chart-container {{
    position: relative;
    width: 1280px;
    height: 730px;
  }}
  canvas {{
    display: block;
  }}

  /* Watermark */
  .watermark {{
    position: absolute;
    bottom: 24px;
    right: 32px;
    font-size: 11px;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.15);
    letter-spacing: 1px;
  }}
</style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <div class="symbol">{symbol}</div>
    <div class="company">{company}</div>
    <div class="price-pill">{close_price:.2f} EGP</div>
    <div class="badge badge-setup">{label}</div>
    <div class="badge badge-pattern">{pattern_badge}</div>
  </div>
  <div class="header-right">
    <div class="stat-box">
      <span class="stat-label">Target</span>
      <span class="stat-val target">{f'{target:.2f} ({target_pct})' if target else 'N/A'}</span>
    </div>
    <div class="stat-box">
      <span class="stat-label">Stop Loss</span>
      <span class="stat-val stop">{f'{stop:.2f} ({stop_pct})' if stop else 'N/A'}</span>
    </div>
    <div class="stat-box">
      <span class="stat-label">Risk/Reward</span>
      <span class="stat-val rr">{rr_str}</span>
    </div>
  </div>
</div>

<div class="chart-container">
  <canvas id="chart" width="1280" height="730"></canvas>
  <div class="watermark">PRAECURSOR-EGX // DAILY INSTITUTIONAL SIGNAL RADAR</div>
</div>

<script>
const data = {json.dumps(candles)};
const target = {json.dumps(target)};
const stop = {json.dumps(stop)};
const closePrice = {close_price};
const targetPct = {json.dumps(target_pct)};
const stopPct = {json.dumps(stop_pct)};

const canvas = document.getElementById('chart');
const ctx = canvas.getContext('2d');

const width = 1280;
const height = 730;
const paddingRight = 90;
const paddingLeft = 20;
const paddingTop = 30;
const volumeHeight = 120;
const priceChartHeight = height - volumeHeight - paddingTop - 40;

// Calculate price bounds
let minPrice = Infinity;
let maxPrice = -Infinity;
data.forEach(d => {{
  if (d.low < minPrice) minPrice = d.low;
  if (d.high > maxPrice) maxPrice = d.high;
  if (d.ema20 && d.ema20 < minPrice) minPrice = d.ema20;
  if (d.ema20 && d.ema20 > maxPrice) maxPrice = d.ema20;
  if (d.ema50 && d.ema50 < minPrice) minPrice = d.ema50;
  if (d.ema50 && d.ema50 > maxPrice) maxPrice = d.ema50;
  if (d.ema200 && d.ema200 < minPrice) minPrice = d.ema200;
  if (d.ema200 && d.ema200 > maxPrice) maxPrice = d.ema200;
}});

if (target && target > maxPrice) maxPrice = target;
if (stop && stop < minPrice) minPrice = stop;

// Add 5% padding to prices
const priceRange = maxPrice - minPrice;
minPrice -= priceRange * 0.04;
maxPrice += priceRange * 0.05;

// Max Volume
let maxVol = 0;
data.forEach(d => {{
  if (d.volume > maxVol) maxVol = d.volume;
}});
maxVol *= 1.25;

// Helper scaling functions
function getY(price) {{
  return paddingTop + priceChartHeight - ((price - minPrice) / (maxPrice - minPrice)) * priceChartHeight;
}}

function getVolY(vol) {{
  const volTop = paddingTop + priceChartHeight + 20;
  return volTop + volumeHeight - (vol / maxVol) * volumeHeight;
}}

const candleCount = data.length;
const chartWidth = width - paddingLeft - paddingRight;
const candleWidth = chartWidth / candleCount;
const barWidth = Math.max(3, candleWidth * 0.72);

// Draw Background Grid
ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
ctx.lineWidth = 1;

// Key level Y positions
const yTarget = target && target > closePrice ? getY(target) : null;
const yStop = stop && stop < closePrice ? getY(stop) : null;
const yEntry = getY(closePrice);

function isNearBadge(y) {{
  if (yTarget !== null && Math.abs(y - yTarget) < 18) return true;
  if (yStop !== null && Math.abs(y - yStop) < 18) return true;
  if (yEntry !== null && Math.abs(y - yEntry) < 16) return true;
  return false;
}}

// Horizontal price grid lines (5 levels)
const gridSteps = 6;
for (let i = 0; i <= gridSteps; i++) {{
  const p = minPrice + (i / gridSteps) * (maxPrice - minPrice);
  const y = getY(p);
  ctx.beginPath();
  ctx.moveTo(paddingLeft, y);
  ctx.lineTo(width - paddingRight, y);
  ctx.stroke();

  // Price text on right axis (only if not colliding with key level badges)
  if (!isNearBadge(y)) {{
    ctx.fillStyle = '#6B7280';
    ctx.font = '11px "JetBrains Mono", monospace';
    ctx.textAlign = 'left';
    ctx.fillText(p.toFixed(2), width - paddingRight + 12, y + 4);
  }}
}}

// Target Corridor (Translucent Shading)
if (yTarget !== null) {{
  const yClose = getY(closePrice);
  ctx.fillStyle = 'rgba(16, 185, 129, 0.06)';
  ctx.fillRect(paddingLeft, yTarget, chartWidth, yClose - yTarget);

  // Target Line
  ctx.strokeStyle = '#10B981';
  ctx.lineWidth = 2;
  ctx.setLineDash([6, 4]);
  ctx.beginPath();
  ctx.moveTo(paddingLeft, yTarget);
  ctx.lineTo(width - paddingRight, yTarget);
  ctx.stroke();
  ctx.setLineDash([]);

  // Target Badge on Right
  ctx.fillStyle = '#10B981';
  if (ctx.roundRect) {{
    ctx.beginPath();
    ctx.roundRect(width - paddingRight + 4, yTarget - 11, 78, 22, 4);
    ctx.fill();
  }} else {{
    ctx.fillRect(width - paddingRight + 4, yTarget - 11, 78, 22);
  }}
  ctx.fillStyle = '#07080B';
  ctx.font = 'bold 10px "JetBrains Mono", monospace';
  ctx.textAlign = 'center';
  ctx.fillText(target.toFixed(2), width - paddingRight + 43, yTarget + 4);
}}

// Stop Loss Corridor (Translucent Shading)
if (yStop !== null) {{
  const yClose = getY(closePrice);
  ctx.fillStyle = 'rgba(239, 68, 68, 0.06)';
  ctx.fillRect(paddingLeft, yClose, chartWidth, yStop - yClose);

  // Stop Line
  ctx.strokeStyle = '#EF4444';
  ctx.lineWidth = 2;
  ctx.setLineDash([6, 4]);
  ctx.beginPath();
  ctx.moveTo(paddingLeft, yStop);
  ctx.lineTo(width - paddingRight, yStop);
  ctx.stroke();
  ctx.setLineDash([]);

  // Stop Badge on Right
  ctx.fillStyle = '#EF4444';
  if (ctx.roundRect) {{
    ctx.beginPath();
    ctx.roundRect(width - paddingRight + 4, yStop - 11, 78, 22, 4);
    ctx.fill();
  }} else {{
    ctx.fillRect(width - paddingRight + 4, yStop - 11, 78, 22);
  }}
  ctx.fillStyle = '#FFFFFF';
  ctx.font = 'bold 10px "JetBrains Mono", monospace';
  ctx.textAlign = 'center';
  ctx.fillText(stop.toFixed(2), width - paddingRight + 43, yStop + 4);
}}

// Current Close Entry Line
ctx.strokeStyle = '#06B6D4';
ctx.lineWidth = 1.5;
ctx.setLineDash([3, 3]);
ctx.beginPath();
ctx.moveTo(paddingLeft, yEntry);
ctx.lineTo(width - paddingRight, yEntry);
ctx.stroke();
ctx.setLineDash([]);

// Entry Badge
ctx.fillStyle = '#06B6D4';
if (ctx.roundRect) {{
  ctx.beginPath();
  ctx.roundRect(width - paddingRight + 4, yEntry - 10, 78, 20, 4);
  ctx.fill();
}} else {{
  ctx.fillRect(width - paddingRight + 4, yEntry - 10, 78, 20);
}}
ctx.fillStyle = '#07080B';
ctx.font = 'bold 10px "JetBrains Mono", monospace';
ctx.textAlign = 'center';
ctx.fillText(closePrice.toFixed(2), width - paddingRight + 43, yEntry + 4);

// Draw EMAs
function drawEMA(key, color, width) {{
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.beginPath();
  let started = false;
  data.forEach((d, i) => {{
    if (d[key] !== null) {{
      const x = paddingLeft + i * candleWidth + candleWidth / 2;
      const y = getY(d[key]);
      if (!started) {{
        ctx.moveTo(x, y);
        started = true;
      }} else {{
        ctx.lineTo(x, y);
      }}
    }}
  }});
  ctx.stroke();
}}

drawEMA('ema200', 'rgba(168, 85, 247, 0.75)', 1.5);
drawEMA('ema50', 'rgba(56, 189, 248, 0.85)', 1.8);
drawEMA('ema20', '#F59E0B', 2.0);

// Draw Candlesticks & Volume
data.forEach((d, i) => {{
  const xCenter = paddingLeft + i * candleWidth + candleWidth / 2;
  const xLeft = xCenter - barWidth / 2;
  const isUp = d.close >= d.open;
  const candleColor = isUp ? '#10B981' : '#EF4444';

  // 1. Candlestick Wick
  ctx.strokeStyle = candleColor;
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  ctx.moveTo(xCenter, getY(d.high));
  ctx.lineTo(xCenter, getY(d.low));
  ctx.stroke();

  // 2. Candlestick Body
  const yOpen = getY(d.open);
  const yClose = getY(d.close);
  const bodyTop = Math.min(yOpen, yClose);
  const bodyHeight = Math.max(2, Math.abs(yClose - yOpen));

  ctx.fillStyle = candleColor;
  ctx.fillRect(xLeft, bodyTop, barWidth, bodyHeight);

  // 3. Volume Bar
  const volTop = getVolY(d.volume);
  const volBottom = paddingTop + priceChartHeight + 20 + volumeHeight;
  ctx.fillStyle = isUp ? 'rgba(16, 185, 129, 0.45)' : 'rgba(239, 68, 68, 0.45)';
  ctx.fillRect(xLeft, volTop, barWidth, volBottom - volTop);

  // Date Labels (Every 8 bars)
  if (i % 8 === 0 || i === candleCount - 1) {{
    ctx.fillStyle = '#6B7280';
    ctx.font = '10px "JetBrains Mono", monospace';
    ctx.textAlign = 'center';
    ctx.fillText(d.date, xCenter, paddingTop + priceChartHeight + 14);
  }}
}});

// 4. Volume 20-MA Line
ctx.strokeStyle = 'rgba(148, 163, 184, 0.7)';
ctx.lineWidth = 1.5;
ctx.beginPath();
let volMaStarted = false;
data.forEach((d, i) => {{
  if (d.vol_ma20 > 0) {{
    const x = paddingLeft + i * candleWidth + candleWidth / 2;
    const y = getVolY(d.vol_ma20);
    if (!volMaStarted) {{
      ctx.moveTo(x, y);
      volMaStarted = true;
    }} else {{
      ctx.lineTo(x, y);
    }}
  }}
}});
ctx.stroke();

// Legend
ctx.font = '11px "JetBrains Mono", monospace';
ctx.textAlign = 'left';

ctx.fillStyle = '#F59E0B';
ctx.fillText('■ EMA20', paddingLeft + 10, paddingTop + 20);

ctx.fillStyle = '#38BDF8';
ctx.fillText('■ EMA50', paddingLeft + 90, paddingTop + 20);

ctx.fillStyle = '#A855F7';
ctx.fillText('■ EMA200', paddingLeft + 170, paddingTop + 20);

ctx.fillStyle = 'rgba(148, 163, 184, 0.8)';
ctx.fillText('■ Vol MA20', paddingLeft + 260, paddingTop + 20);
</script>
</body>
</html>"""
    return html_content

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
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800}, device_scale_factor=2)
        page.goto(html_file.as_uri())
        page.wait_for_timeout(300)  # ensure canvas render
        page.screenshot(path=str(png_path), type="png")
        browser.close()
        
    print(f"Chart saved: {png_path} ({png_path.stat().st_size} bytes)")
    return png_path

def generate_top_candidates_charts(top_n: int = 5) -> list[Path]:
    """Generate charts for the top N actionable non-avoid candidates in opportunity_ranking.csv."""
    csv_path = REPORTS_DIR / "opportunity_ranking.csv"
    if not csv_path.exists():
        print("opportunity_ranking.csv not found.")
        return []

    eligible = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            sym = r.get("symbol")
            nd_label = r.get("next_day_label", "")
            if not sym or "Avoid" in nd_label:
                continue
            try:
                nd_score = float(r.get("next_day_score", 0.0) or 0.0)
            except (ValueError, TypeError):
                nd_score = 0.0
            eligible.append((sym, nd_score))

    # Sort actionable candidates by next_day_score descending
    eligible.sort(key=lambda x: x[1], reverse=True)
    symbols = [s[0] for s in eligible[:top_n]]

    if not symbols:
        print("No eligible candidates found for chart generation.")
        return []

    print(f"Generating charts for top {len(symbols)} actionable candidates: {', '.join(symbols)}...")
    generated = []
    
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 800}, device_scale_factor=2)
            
            for sym in symbols:
                try:
                    meta = get_candidate_metadata(sym)
                    df = fetch_symbol_history(sym, lookback=65)
                    if df.empty:
                        print(f"Skipping {sym}: insufficient data.")
                        continue
                    
                    html = generate_chart_html(sym, df, meta)
                    html_file = CHARTS_DIR / f"{sym}_chart.html"
                    with open(html_file, "w", encoding="utf-8") as f:
                        f.write(html)
                        
                    png_path = CHARTS_DIR / f"{sym}_chart.png"
                    page.goto(html_file.as_uri())
                    page.wait_for_timeout(300)
                    page.screenshot(path=str(png_path), type="png")
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
    args = parser.parse_args()

    if args.symbol:
        render_chart_to_png(args.symbol.upper())
    else:
        generate_top_candidates_charts(args.top)
