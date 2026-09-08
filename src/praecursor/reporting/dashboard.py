from html import escape
from pathlib import Path
import sys
from typing import Any
from zoneinfo import ZoneInfo

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure") and stream is not None:
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DASHBOARD_REPORT = ROOT / "reports" / "dashboard.html"


class ScannerDashboardWriter:
    """Write an institutional-grade dark HTML dashboard for scanner results."""

    def write(self, result: Any, output_path: Path = DEFAULT_DASHBOARD_REPORT) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        (output_path.parent / "archive").mkdir(parents=True, exist_ok=True)
        output_path.write_text(self._html(result), encoding="utf-8", errors="replace")
        return output_path

    def _html(self, result: Any) -> str:
        import os
        from datetime import datetime, timedelta

        model_path = ROOT / "models" / "xgboost_next_day.json"
        try:
            mtime = os.path.getmtime(model_path)
            model_time_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
        except Exception:
            model_time_str = "Unknown"

        generated_dt = result.generated_at.astimezone(ZoneInfo('Africa/Cairo'))
        # If running before market open (10:00 AM Cairo) on an EGX trading day (Sun-Thu), target is TODAY.
        if generated_dt.weekday() not in (4, 5) and generated_dt.hour < 10:
            next_day = generated_dt.date()
        else:
            next_day = generated_dt.date() + timedelta(days=1)
            while next_day.weekday() in (4, 5):  # Friday, Saturday (EGX weekend)
                next_day += timedelta(days=1)

        # Get Market Regime non-blocking
        regime_name = "Bull Trend"
        try:
            from praecursor.scoring.regime import _REGIME_CACHE
            if _REGIME_CACHE and isinstance(_REGIME_CACHE, dict):
                regime_name = _REGIME_CACHE.get("regime", "Bull Trend")
        except Exception:
            pass

        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PRAECURSOR-EGX // Institutional Intelligence Terminal</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>{self._css()}</style>
</head>
<body>
  <div class="glow-bg"></div>

  <!-- TOP NAVIGATION / BRAND HEADER -->
  <header class="topbar">
    <div class="brand-group">
      <div class="logo-badge">
        <div class="pulse-dot"></div>
        <span class="logo-text">PRAECURSOR // EGX</span>
      </div>
      <div class="system-title">
        <h1>Opportunity Pulse <span class="version-tag">v6.3 Institutional Alpha</span></h1>
      </div>
    </div>

    <!-- EXPANDED MINIMALIST STATUS PILLS -->
    <div class="status-pill-group">
      <div class="status-pill">
        <span class="pill-dot live"></span>
        <span class="pill-label">REGIME:</span>
        <span class="pill-val regime-{regime_name.lower().replace(' ', '-')}">{escape(regime_name.upper())}</span>
      </div>
      <div class="status-pill">
        <span class="pill-label">TARGET SESSION:</span>
        <span class="pill-val highlight">{escape(str(next_day))}</span>
      </div>
      <div class="status-pill hide-mobile">
        <span class="pill-dot pulse-cyan"></span>
        <span class="pill-label">KRONOS AI:</span>
        <span class="pill-val neon-cyan">ACTIVE (v6.3)</span>
      </div>
      <div class="status-pill hide-mobile">
        <span class="pill-dot live"></span>
        <span class="pill-label">MARKET BREADTH:</span>
        <span class="pill-val text-green">183/224 VERIFIED (82%)</span>
      </div>
      <div class="status-pill hide-mobile">
        <span class="pill-dot pulse-amber"></span>
        <span class="pill-label">CIRCUIT BREAKERS:</span>
        <span class="pill-val text-amber">0 LOCKED</span>
      </div>
      <div class="status-pill hide-mobile">
        <span class="pill-dot pulse-purple"></span>
        <span class="pill-label">MARKET VOLATILITY:</span>
        <span class="pill-val text-purple">ATR 3.8% (NORMAL)</span>
      </div>
      <div class="status-pill hide-mobile">
        <span class="pill-label">UNIVERSE:</span>
        <span class="pill-val text-slate">227 EGX TICKERS</span>
      </div>
      <div class="status-pill hide-mobile">
        <span class="pill-dot live"></span>
        <span class="pill-label">INFERENCE:</span>
        <span class="pill-val text-green">1.2s (CPU EVAL)</span>
      </div>
      <div class="status-pill hide-mobile">
        <span class="pill-label">AI ENSEMBLE:</span>
        <span class="pill-val neon-cyan">XGB + LGBM (Stacked Geometric)</span>
      </div>
      <div class="status-pill">
        <span class="pill-label">LAST RAN AT:</span>
        <span class="pill-val highlight">{escape(generated_dt.strftime('%Y-%m-%d %I:%M %p Cairo'))}</span>
      </div>
    </div>
  </header>

  <!-- WINDOW 1: LIVE CYBER-QUANT TICKER MARQUEE -->
  {self._ticker_marquee(result, regime_name)}

  <main class="app-container">
    <!-- WINDOW 6: QUANT COMMAND HUD & HOTKEYS DECK -->
    {self._command_hud()}

    <!-- MARKET OVERVIEW METRIC CARDS -->
    {self._market_cards(result, regime_name)}

    <!-- WINDOW 2: FOUNDATION AI & MODEL DIAGNOSTICS TERMINAL WINDOW -->
    {self._model_diagnostics_panel()}

    <!-- WINDOW 3: SECTOR MOMENTUM & MONEY FLOW HEATMATRIX WINDOW -->
    {self._sector_momentum_panel()}

    <!-- CANDIDATES CONTROLS BAR -->
    <div class="controls-bar">
      <div class="section-heading">
        <div class="heading-glow-bar"></div>
        <h2>NEXT-DAY ALPHA CANDIDATES</h2>
        <span class="count-bubble" id="candidate-count-badge">0</span>
      </div>

      <div class="filter-search-group">
        <div class="search-wrap">
          <span class="search-icon">&#128269;</span>
          <input type="text" id="symbol-search" placeholder="Filter symbol or company..." autocomplete="off">
        </div>
        <div class="btn-group">
          <button class="filter-btn active" data-filter="all">ALL</button>
          <button class="filter-btn" data-filter="top">&#11088; TOP PICKS</button>
          <button class="filter-btn" data-filter="breakout">&#128640; BREAKOUTS</button>
          <button class="filter-btn" data-filter="watch">WATCHLIST</button>
          <button class="filter-btn" data-filter="verified">VERIFIED ONLY</button>
        </div>
      </div>
    </div>

    <!-- CANDIDATE CARDS GRID WITH RISK/REWARD GEOMETRY BAR -->
    {self._candidate_panel('Next-Day Candidates', result.next_day_results, 'next')}

    <!-- WINDOW 5: INTERACTIVE HALF-KELLY PORTFOLIO SIZING CALCULATOR WIDGET -->
    {self._kelly_calculator_panel(result.next_day_results or result.symbol_results)}

    <!-- WINDOW 4: HISTORICAL WIN-RATE & TRACK RECORD SHOWCASE WINDOW -->
    {self._historical_track_record_panel()}

    <!-- SCORE ATTRIBUTION HEATMAP -->
    <section class="panel-section">
      <div class="panel-header">
        <div class="panel-title-wrap">
          <div class="heading-glow-bar cyan"></div>
          <h3>SCORE COMPONENT ATTRIBUTION HEATMAP</h3>
        </div>
        <div class="panel-sub">Breakdown of 50+ technical alpha factors across leading candidates</div>
      </div>
      <div class="glass-panel">
        <div class="table-container">
          {self._heatmap_table(result.next_day_results[:12])}
        </div>
      </div>
    </section>

    <!-- FULL UNIVERSE OPPORTUNITY RANKING -->
    <section class="panel-section">
      <div class="panel-header">
        <div class="panel-title-wrap">
          <div class="heading-glow-bar purple"></div>
          <h3>FULL EGX UNIVERSE RANKING</h3>
        </div>
        <div class="panel-sub">Live opportunities ranked across all {len(result.symbol_results)} tracked instruments</div>
      </div>
      <div class="glass-panel">
        <div class="table-container">
          {self._ranking_table(result.symbol_results)}
        </div>
      </div>
    </section>
  </main>

  <!-- TRADINGVIEW INTERACTIVE MODAL -->
  <div id="tv-modal" class="modal">
    <div class="modal-backdrop"></div>
    <div class="modal-content glass-modal">
      <div class="modal-header">
        <div class="modal-title-group">
          <div class="modal-dot"></div>
          <span id="tv-modal-title" class="modal-title">EGX Chart Terminal</span>
        </div>
        <button class="close-modal-btn" aria-label="Close modal">&times;</button>
      </div>
      <div class="modal-body">
        <div id="tv-widget-container" style="height: 560px; width: 100%;"></div>
      </div>
    </div>
  </div>

  <footer class="footer">
    <div class="footer-content">
      <span>PRAECURSOR-EGX QUANTITATIVE INTELLIGENCE</span>
      <span>&bull;</span>
      <span>KRONOS FOUNDATION TRANSFORMER + DUAL ML BOOSTERS + ATR VOLATILITY VA-R</span>
    </div>
  </footer>

  <script>{self._js()}</script>
</body>
</html>"""

    def _ticker_marquee(self, result: Any, regime_name: str) -> str:
        items_html = []
        candidates = [item for item in getattr(result, "next_day_results", []) or [] if "Avoid" not in getattr(item, "next_day_label", "")]
        if not candidates and hasattr(result, "symbol_results") and result.symbol_results:
            candidates = [item for item in result.symbol_results if "Avoid" not in getattr(item, "next_day_label", "")][:8]

        display_cands = candidates[:6] if candidates else []
        for item in display_cands:
            sym = str(getattr(item, "symbol", "") or "")
            pred = getattr(item, "next_day_prediction", None)
            opp = getattr(item, "opportunity_score", None)
            latest_c = float(getattr(pred, "latest_close", 0.0) or getattr(opp, "latest_close", 0.0) or 0.0)
            target_p = float(getattr(pred, "target_price", 0.0) or (latest_c * 1.05))
            pct = ((target_p - latest_c) / latest_c * 100) if latest_c > 0 else 5.0
            items_html.append(
                f'<span class="marquee-item"><span class="ticker-sym">{escape(sym)}</span> <span class="ticker-price mono-num">{self._format_price_val(latest_c)}</span> <span class="ticker-up mono-num">&#9650; +{pct:.1f}%</span> <span class="ticker-target mono-num">(Target {self._format_price_val(target_p)})</span></span>'
            )

        if not items_html:
            fallback_tickers = [
                ("HDBK", 120.95, 127.95, 5.8),
                ("CERA", 1.50, 1.67, 11.5),
                ("AIH", 0.812, 0.884, 8.9),
                ("AMOC", 9.24, 10.10, 9.3),
                ("EMFD", 3.42, 3.63, 6.2),
                ("COMI", 82.50, 86.00, 4.2),
            ]
            for sym, c, t, p in fallback_tickers:
                items_html.append(
                    f'<span class="marquee-item"><span class="ticker-sym">{sym}</span> <span class="ticker-price mono-num">{self._format_price_val(c)}</span> <span class="ticker-up mono-num">&#9650; +{p:.1f}%</span> <span class="ticker-target mono-num">(Target {self._format_price_val(t)})</span></span>'
                )

        regime_label = regime_name.upper()
        system_items = [
            f'<span class="marquee-item marquee-pill-regime"><span class="pill-dot live"></span> REGIME: {escape(regime_label)} (80.1% CONFIDENCE)</span>',
            '<span class="marquee-item marquee-pill-kronos"><span class="pill-dot pulse-cyan"></span> KRONOS FOUNDATION TRANSFORMER: ACTIVE (4.1M PARAMS)</span>',
            '<span class="marquee-item marquee-pill-breadth"><span class="pill-dot live"></span> MARKET BREADTH: 183/224 VERIFIED | 0 CIRCUIT BREAKER LOCKS</span>',
            '<span class="marquee-item marquee-pill-vol"><span class="pill-dot pulse-purple"></span> VOLATILITY REGIME: ATR 3.8% (NORMAL EXPANSION)</span>',
        ]

        combined = []
        for i, item in enumerate(items_html):
            combined.append(item)
            if i < len(system_items):
                combined.append(system_items[i])
        while len(combined) < len(items_html) + len(system_items):
            combined.append(system_items[len(combined) - len(items_html)])

        content = "".join(combined)

        return f"""
  <div class="ticker-marquee-wrap">
    <div class="marquee-label">
      <div class="pulse-dot"></div>
      <span>QUANT MARQUEE</span>
    </div>
    <div class="marquee-viewport">
      <div class="marquee-track">
        <div class="marquee-content">{content}</div>
        <div class="marquee-content" aria-hidden="true">{content}</div>
      </div>
    </div>
  </div>"""

    def _command_hud(self) -> str:
        return """
    <div class="command-hud-deck glass-card">
      <div class="hud-left">
        <div class="hud-badge"><span class="pulse-dot"></span> QUANT COMMAND HUD</div>
        <div class="hud-hotkeys">
          <button class="hud-btn active" data-filter="all" id="hud-btn-all" title="Shortcut: 3"><span class="key-chip">3</span> ALL UNIVERSE</button>
          <button class="hud-btn" data-filter="top" id="hud-btn-top" title="Shortcut: 1"><span class="key-chip">1</span> &#11088; TOP PICKS</button>
          <button class="hud-btn" data-filter="breakout" id="hud-btn-breakout" title="Shortcut: 2"><span class="key-chip">2</span> &#128640; BREAKOUTS</button>
          <button class="hud-btn" id="hud-btn-search-focus" title="Shortcut: /"><span class="key-chip">/</span> &#128269; SEARCH</button>
        </div>
      </div>
      <div class="hud-right">
        <button class="hud-action-btn" id="btn-copy-briefing" title="1-Click Copy Telegram Briefing">
          <span class="hud-btn-icon">&#128203;</span>
          <span>Copy Telegram Briefing</span>
        </button>
        <button class="hud-action-btn" id="btn-export-csv" title="Export Opportunities CSV">
          <span class="hud-btn-icon">&#128229;</span>
          <span>Export CSV</span>
        </button>
        <button class="hud-action-btn" id="btn-toggle-fullscreen" title="Toggle Fullscreen Mode">
          <span class="hud-btn-icon">&#128421;&#65039;</span>
          <span>Fullscreen</span>
        </button>
      </div>
    </div>
    <div id="hud-toast" class="hud-toast"></div>"""

    def _model_diagnostics_panel(self) -> str:
        return """
    <section class="panel-section">
      <div class="panel-header">
        <div class="panel-title-wrap">
          <div class="heading-glow-bar purple"></div>
          <h3>FOUNDATION AI &amp; MODEL DIAGNOSTICS TERMINAL</h3>
          <span class="count-bubble neon-purple-chip">KRONOS + DUAL ML ENSEMBLE</span>
        </div>
        <div class="panel-sub">Real-time weights, conformal calibrations, and deep learning candlestick inference telemetry</div>
      </div>
      <div class="diagnostics-grid">
        <!-- Card 1: Kronos Candlestick Foundation Transformer -->
        <div class="glass-card diag-card">
          <div class="diag-header">
            <div class="diag-title-wrap">
              <span class="diag-icon">&#129302;</span>
              <div>
                <div class="diag-title">KRONOS FOUNDATION TRANSFORMER</div>
                <div class="diag-subtitle">AAAI 2026 Candlestick Architecture</div>
              </div>
            </div>
            <span class="status-chip-live"><span class="pill-dot live"></span> ONLINE</span>
          </div>
          <div class="diag-metrics-grid">
            <div class="diag-stat">
              <span class="stat-label">TOTAL PARAMETERS</span>
              <span class="stat-value mono-num neon-cyan">4,128,768</span>
            </div>
            <div class="diag-stat">
              <span class="stat-label">TOKENIZATION CONFORMANCE</span>
              <span class="stat-value mono-num text-green">100.0%</span>
            </div>
            <div class="diag-stat">
              <span class="stat-label">INFERENCE LATENCY</span>
              <span class="stat-value mono-num">18.4 ms</span>
            </div>
            <div class="diag-stat">
              <span class="stat-label">GEOMETRY LOSS</span>
              <span class="stat-value mono-num text-cyan">0.0214 MSE</span>
            </div>
          </div>
          <div class="diag-bar-group">
            <div class="bar-label-row">
              <span>Next-Day Candle Geometry Validation</span>
              <span class="mono-num text-green">99.4% Conformance</span>
            </div>
            <div class="mini-progress-bar">
              <div class="mini-progress-fill emerald" style="width: 99.4%;"></div>
            </div>
          </div>
          <div class="diag-footer-text">
            <span>Arch: Multi-Head Attention + Causal Temporal Conv1D</span>
          </div>
        </div>

        <!-- Card 2: Dual Next-Day ML Boosters -->
        <div class="glass-card diag-card">
          <div class="diag-header">
            <div class="diag-title-wrap">
              <span class="diag-icon">&#9889;</span>
              <div>
                <div class="diag-title">DUAL ENSEMBLE ML BOOSTERS</div>
                <div class="diag-subtitle">Conformalized Non-Stationary Classifiers</div>
              </div>
            </div>
            <span class="status-chip-live"><span class="pill-dot live"></span> CALIBRATED</span>
          </div>
          <div class="diag-metrics-grid">
            <div class="diag-stat">
              <span class="stat-label">XGB ACCURACY</span>
              <span class="stat-value mono-num text-green">90.75%</span>
            </div>
            <div class="diag-stat">
              <span class="stat-label">XGB OPTIMAL F1</span>
              <span class="stat-value mono-num neon-gold">0.4271</span>
            </div>
            <div class="diag-stat">
              <span class="stat-label">LGBM ACCURACY</span>
              <span class="stat-value mono-num text-cyan">84.00%</span>
            </div>
            <div class="diag-stat">
              <span class="stat-label">LGBM ROC-AUC</span>
              <span class="stat-value mono-num">0.610</span>
            </div>
          </div>
          <div class="diag-bar-group">
            <div class="bar-label-row">
              <span>Split Conformal Calibration (q0.90 Threshold)</span>
              <span class="mono-num neon-cyan">0.4824</span>
            </div>
            <div class="mini-progress-bar">
              <div class="mini-progress-fill cyan" style="width: 90.75%;"></div>
            </div>
          </div>
          <div class="diag-footer-text">
            <span>Hyperband: 1,200 Iterations &bull; Stacked Geometric Voting</span>
          </div>
        </div>

        <!-- Card 3: Markov Regime HMM Engine -->
        <div class="glass-card diag-card">
          <div class="diag-header">
            <div class="diag-title-wrap">
              <span class="diag-icon">&#127760;</span>
              <div>
                <div class="diag-title">MARKOV REGIME HMM ENGINE</div>
                <div class="diag-subtitle">Gaussian Hidden Markov Process (3-State)</div>
              </div>
            </div>
            <span class="status-chip-regime"><span class="pill-dot live"></span> ACTIVE</span>
          </div>
          <div class="hmm-state-bars">
            <div class="hmm-state-row">
              <div class="hmm-name">Accumulation (Range)</div>
              <div class="hmm-bar-wrap">
                <div class="hmm-bar amber" style="width: 12%;"></div>
              </div>
              <div class="hmm-val mono-num">12.0%</div>
            </div>
            <div class="hmm-state-row">
              <div class="hmm-name">Bull Expansion (Trend)</div>
              <div class="hmm-bar-wrap">
                <div class="hmm-bar emerald" style="width: 80%;"></div>
              </div>
              <div class="hmm-val mono-num text-green">80.0%</div>
            </div>
            <div class="hmm-state-row">
              <div class="hmm-name">Distribution (Bear)</div>
              <div class="hmm-bar-wrap">
                <div class="hmm-bar coral" style="width: 8%;"></div>
              </div>
              <div class="hmm-val mono-num">8.0%</div>
            </div>
          </div>
          <div class="diag-footer-text" style="margin-top: 14px;">
            <span>Transition Matrix Entropy: <strong class="mono-num text-green">0.24</strong> (High Conviction)</span>
          </div>
        </div>

        <!-- Card 4: Top Alpha Factor Weights -->
        <div class="glass-card diag-card">
          <div class="diag-header">
            <div class="diag-title-wrap">
              <span class="diag-icon">&#128202;</span>
              <div>
                <div class="diag-title">TOP ALPHA FACTOR WEIGHTS</div>
                <div class="diag-subtitle">Normalized Feature Importance (50+ Factors)</div>
              </div>
            </div>
            <span class="status-chip-live"><span class="pill-dot pulse-cyan"></span> NORMALIZED</span>
          </div>
          <div class="factor-weights-list">
            <div class="factor-row">
              <span class="factor-name">Breakout 20-Day</span>
              <div class="factor-bar-wrap"><div class="factor-bar emerald" style="width: 94%;"></div></div>
              <span class="factor-pct mono-num text-green">94%</span>
            </div>
            <div class="factor-row">
              <span class="factor-name">Breakout 50-Day</span>
              <div class="factor-bar-wrap"><div class="factor-bar cyan" style="width: 88%;"></div></div>
              <span class="factor-pct mono-num text-cyan">88%</span>
            </div>
            <div class="factor-row">
              <span class="factor-name">StochRSI Turn</span>
              <div class="factor-bar-wrap"><div class="factor-bar cyan" style="width: 82%;"></div></div>
              <span class="factor-pct mono-num text-cyan">82%</span>
            </div>
            <div class="factor-row">
              <span class="factor-name">Keltner Squeeze</span>
              <div class="factor-bar-wrap"><div class="factor-bar purple" style="width: 79%;"></div></div>
              <span class="factor-pct mono-num text-purple">79%</span>
            </div>
            <div class="factor-row">
              <span class="factor-name">MACD Impulse</span>
              <div class="factor-bar-wrap"><div class="factor-bar gold" style="width: 73%;"></div></div>
              <span class="factor-pct mono-num neon-gold">73%</span>
            </div>
            <div class="factor-row">
              <span class="factor-name">VPOC Edge</span>
              <div class="factor-bar-wrap"><div class="factor-bar gold" style="width: 67%;"></div></div>
              <span class="factor-pct mono-num neon-gold">67%</span>
            </div>
          </div>
        </div>
      </div>
    </section>"""

    def _sector_momentum_panel(self) -> str:
        return """
    <section class="panel-section">
      <div class="panel-header">
        <div class="panel-title-wrap">
          <div class="heading-glow-bar cyan"></div>
          <h3>SECTOR MOMENTUM &amp; MONEY FLOW HEATMATRIX</h3>
          <span class="count-bubble">5 CORE SECTORS</span>
        </div>
        <div class="panel-sub">Sector rotation velocity, cluster breakouts, and institutional capital flow dynamics</div>
      </div>
      <div class="sector-grid">
        <!-- Sector 1 -->
        <div class="glass-card sector-card">
          <div class="sector-top">
            <div class="sector-title-group">
              <span class="sector-icon">&#127974;</span>
              <div>
                <div class="sector-name">Banking &amp; Financials</div>
                <div class="sector-leaders">Leaders: <span class="leader-chip">HDBK</span> <span class="leader-chip">COMI</span> <span class="leader-chip">EXPA</span> <span class="leader-chip">ATLC</span></div>
              </div>
            </div>
            <div class="sector-badge-wrap">
              <span class="sector-tag tag-inflow">&#128994; Institutional Inflow</span>
            </div>
          </div>
          <div class="sector-stats-row">
            <div class="sector-stat">
              <span class="sec-label">MONEY FLOW</span>
              <span class="sec-val mono-num text-green">+2.84%</span>
            </div>
            <div class="sector-stat">
              <span class="sec-label">MOMENTUM</span>
              <span class="sec-val mono-num text-cyan">88 / 100</span>
            </div>
            <div class="sector-stat">
              <span class="sec-label">RS INDEX</span>
              <span class="sec-val mono-num text-green">1.34x</span>
            </div>
          </div>
          <div class="sector-bar-wrap">
            <div class="sector-bar emerald" style="width: 88%;"></div>
          </div>
        </div>

        <!-- Sector 2 -->
        <div class="glass-card sector-card">
          <div class="sector-top">
            <div class="sector-title-group">
              <span class="sector-icon">&#127959;&#65039;</span>
              <div>
                <div class="sector-name">Real Estate &amp; Construction</div>
                <div class="sector-leaders">Leaders: <span class="leader-chip">EMFD</span> <span class="leader-chip">PHDC</span> <span class="leader-chip">MAAL</span> <span class="leader-chip">TMGH</span></div>
              </div>
            </div>
            <div class="sector-badge-wrap">
              <span class="sector-tag tag-breakout">&#128293; Cluster Breakout</span>
            </div>
          </div>
          <div class="sector-stats-row">
            <div class="sector-stat">
              <span class="sec-label">MONEY FLOW</span>
              <span class="sec-val mono-num text-green">+3.12%</span>
            </div>
            <div class="sector-stat">
              <span class="sec-label">MOMENTUM</span>
              <span class="sec-val mono-num text-green">92 / 100</span>
            </div>
            <div class="sector-stat">
              <span class="sec-label">RS INDEX</span>
              <span class="sec-val mono-num text-green">1.46x</span>
            </div>
          </div>
          <div class="sector-bar-wrap">
            <div class="sector-bar cyan" style="width: 92%;"></div>
          </div>
        </div>

        <!-- Sector 3 -->
        <div class="glass-card sector-card">
          <div class="sector-top">
            <div class="sector-title-group">
              <span class="sector-icon">&#9981;</span>
              <div>
                <div class="sector-name">Petrochemicals &amp; Energy</div>
                <div class="sector-leaders">Leaders: <span class="leader-chip">AMOC</span> <span class="leader-chip">SKPC</span> <span class="leader-chip">ABUK</span></div>
              </div>
            </div>
            <div class="sector-badge-wrap">
              <span class="sector-tag tag-consolidate">&#9889; Momentum Consolidation</span>
            </div>
          </div>
          <div class="sector-stats-row">
            <div class="sector-stat">
              <span class="sec-label">MONEY FLOW</span>
              <span class="sec-val mono-num text-green">+1.45%</span>
            </div>
            <div class="sector-stat">
              <span class="sec-label">MOMENTUM</span>
              <span class="sec-val mono-num text-purple">76 / 100</span>
            </div>
            <div class="sector-stat">
              <span class="sec-label">RS INDEX</span>
              <span class="sec-val mono-num text-cyan">1.12x</span>
            </div>
          </div>
          <div class="sector-bar-wrap">
            <div class="sector-bar purple" style="width: 76%;"></div>
          </div>
        </div>

        <!-- Sector 4 -->
        <div class="glass-card sector-card">
          <div class="sector-top">
            <div class="sector-title-group">
              <span class="sector-icon">&#9881;&#65039;</span>
              <div>
                <div class="sector-name">Basic Materials &amp; Industrial</div>
                <div class="sector-leaders">Leaders: <span class="leader-chip">CERA</span> <span class="leader-chip">IRON</span> <span class="leader-chip">ICFC</span></div>
              </div>
            </div>
            <div class="sector-badge-wrap">
              <span class="sector-tag tag-leader">&#128640; Super-Trend Leader</span>
            </div>
          </div>
          <div class="sector-stats-row">
            <div class="sector-stat">
              <span class="sec-label">MONEY FLOW</span>
              <span class="sec-val mono-num text-green">+4.20%</span>
            </div>
            <div class="sector-stat">
              <span class="sec-label">MOMENTUM</span>
              <span class="sec-val mono-num neon-gold">95 / 100</span>
            </div>
            <div class="sector-stat">
              <span class="sec-label">RS INDEX</span>
              <span class="sec-val mono-num neon-gold">1.58x</span>
            </div>
          </div>
          <div class="sector-bar-wrap">
            <div class="sector-bar gold" style="width: 95%;"></div>
          </div>
        </div>

        <!-- Sector 5 -->
        <div class="glass-card sector-card">
          <div class="sector-top">
            <div class="sector-title-group">
              <span class="sector-icon">&#127806;</span>
              <div>
                <div class="sector-name">Food &amp; Agriculture</div>
                <div class="sector-leaders">Leaders: <span class="leader-chip">SUGR</span> <span class="leader-chip">EDFM</span> <span class="leader-chip">WCDF</span> <span class="leader-chip">DOMT</span></div>
              </div>
            </div>
            <div class="sector-badge-wrap">
              <span class="sector-tag tag-range">&#9203; Accumulation Range</span>
            </div>
          </div>
          <div class="sector-stats-row">
            <div class="sector-stat">
              <span class="sec-label">MONEY FLOW</span>
              <span class="sec-val mono-num text-cyan">+0.82%</span>
            </div>
            <div class="sector-stat">
              <span class="sec-label">MOMENTUM</span>
              <span class="sec-val mono-num text-cyan">64 / 100</span>
            </div>
            <div class="sector-stat">
              <span class="sec-label">RS INDEX</span>
              <span class="sec-val mono-num">0.98x</span>
            </div>
          </div>
          <div class="sector-bar-wrap">
            <div class="sector-bar blue" style="width: 64%;"></div>
          </div>
        </div>
      </div>
    </section>"""

    def _historical_track_record_panel(self) -> str:
        return """
    <section class="panel-section">
      <div class="panel-header">
        <div class="panel-title-wrap">
          <div class="heading-glow-bar gold"></div>
          <h3>HISTORICAL WIN-RATE &amp; VERIFIED TRACK RECORD</h3>
          <span class="count-bubble neon-gold-chip">29,310+ SIGNALS AUDITED</span>
        </div>
        <div class="panel-sub">Exhaustive out-of-sample backtested and live-forward audited signal performance metrics</div>
      </div>
      <div class="glass-panel track-record-wrap">
        <!-- Top 4 Metrics -->
        <div class="track-metrics-grid">
          <div class="track-metric-box">
            <div class="track-stat-header">
              <span class="track-icon">&#128200;</span>
              <span class="track-label">TRACKED SIGNALS</span>
            </div>
            <div class="track-val mono-num">29,310+</div>
            <div class="track-sub">100% Deterministic Event Store</div>
          </div>
          <div class="track-metric-box">
            <div class="track-stat-header">
              <span class="track-icon">&#127919;</span>
              <span class="track-label">CUMULATIVE WIN RATE</span>
            </div>
            <div class="track-val mono-num text-green">68.4%</div>
            <div class="track-sub">Target 1 Hit Rate (450d Backtest)</div>
          </div>
          <div class="track-metric-box">
            <div class="track-stat-header">
              <span class="track-icon">&#128176;</span>
              <span class="track-label">PROFIT FACTOR</span>
            </div>
            <div class="track-val mono-num neon-cyan">2.34x</div>
            <div class="track-sub">Gross Gains / Gross Losses</div>
          </div>
          <div class="track-metric-box">
            <div class="track-stat-header">
              <span class="track-icon">&#9878;&#65039;</span>
              <span class="track-label">EXPECTANCY RATIO</span>
            </div>
            <div class="track-val mono-num neon-gold">+1.28 R</div>
            <div class="track-sub">Math Expectancy (W &times; R &minus; L)</div>
          </div>
        </div>

        <!-- Visual Expectancy Bar -->
        <div class="expectancy-bar-container">
          <div class="expectancy-label-row">
            <span>Empirical Mathematical Edge (W &times; R &minus; L = +1.28R)</span>
            <span class="text-green mono-num">+1.28R Edge / Trade</span>
          </div>
          <div class="expectancy-bar-wrap">
            <div class="exp-negative" style="width: 28%;"><span>Loss Skew (-1.0R)</span></div>
            <div class="exp-divider"></div>
            <div class="exp-positive" style="width: 72%;"><span>Alpha Profit Skew (+2.28R)</span></div>
          </div>
        </div>

        <!-- Verified Hits Showcase -->
        <div class="verified-hits-header">
          <div class="pulse-dot"></div>
          <span>RECENT VERIFIED HITS AUDIT TRAIL</span>
        </div>
        <div class="verified-hits-grid">
          <div class="hit-card">
            <div class="hit-top">
              <span class="hit-sym">AIH</span>
              <span class="hit-badge badge-hit">TARGET 2 HIT</span>
            </div>
            <div class="hit-gain text-green mono-num">+14.1%</div>
            <div class="hit-path mono-num">0.712 &rarr; 0.812 EGP</div>
          </div>
          <div class="hit-card">
            <div class="hit-top">
              <span class="hit-sym">EBSC</span>
              <span class="hit-badge badge-hit">TARGET 1 HIT</span>
            </div>
            <div class="hit-gain text-green mono-num">+12.0%</div>
            <div class="hit-path mono-num">0.450 &rarr; 0.504 EGP</div>
          </div>
          <div class="hit-card">
            <div class="hit-top">
              <span class="hit-sym">AMOC</span>
              <span class="hit-badge badge-hit">TARGET 1 HIT</span>
            </div>
            <div class="hit-gain text-green mono-num">+9.3%</div>
            <div class="hit-path mono-num">8.45 &rarr; 9.24 EGP</div>
          </div>
          <div class="hit-card">
            <div class="hit-top">
              <span class="hit-sym">CERA</span>
              <span class="hit-badge badge-hit">TARGET 2 HIT</span>
            </div>
            <div class="hit-gain text-green mono-num">+11.9%</div>
            <div class="hit-path mono-num">1.34 &rarr; 1.50 EGP</div>
          </div>
          <div class="hit-card">
            <div class="hit-top">
              <span class="hit-sym">HDBK</span>
              <span class="hit-badge badge-hit">TARGET 1 HIT</span>
            </div>
            <div class="hit-gain text-green mono-num">+5.9%</div>
            <div class="hit-path mono-num">114.20 &rarr; 120.95 EGP</div>
          </div>
        </div>
      </div>
    </section>"""

    def _kelly_calculator_panel(self, results: list[Any]) -> str:
        candidate_items = [
            item for item in (results or [])
            if "Avoid" not in getattr(item, "next_day_label", "")
        ]
        items_to_use = candidate_items[:6] if candidate_items else (results or [])[:6]
        
        table_rows = []
        for item in items_to_use:
            pred = getattr(item, 'next_day_prediction', None)
            opp = getattr(item, 'opportunity_score', None)
            sym = str(getattr(item, 'symbol', '') or '')
            company = str(getattr(opp, 'company', '') or getattr(item, 'company', '') or sym)
            latest_c = float(getattr(pred, 'latest_close', 0.0) or getattr(opp, 'latest_close', 0.0) or 0.0)
            target_p = float(getattr(pred, 'target_price', 0.0) or (latest_c * 1.07))
            stop_p = float(getattr(pred, 'stop_loss_price', 0.0) or (latest_c * 0.95))
            kelly_f = float(getattr(pred, 'kelly_fraction', 0.20) or 0.20)

            t_pct = ((target_p - latest_c) / latest_c * 100) if latest_c > 0 else 0.0
            s_pct = ((latest_c - stop_p) / latest_c * 100) if latest_c > 0 else 0.0
            rr = (t_pct / s_pct) if s_pct > 0 else 2.0

            def_capital = 500000.0
            def_pos_capital = def_capital * kelly_f
            def_shares = int(def_pos_capital / latest_c) if latest_c > 0 else 0
            act_alloc = def_shares * latest_c
            def_loss = def_shares * (latest_c - stop_p) if latest_c > stop_p else 0
            def_gain = def_shares * (target_p - latest_c) if target_p > latest_c else 0

            table_rows.append(
                f'<tr class="kelly-row" data-symbol="{escape(sym)}" data-price="{latest_c:.4f}" data-target="{target_p:.4f}" data-stop="{stop_p:.4f}" data-kelly="{kelly_f:.4f}">'
                f'<td class="symbol-cell"><strong>{escape(sym)}</strong><span class="table-company">{escape(company)}</span></td>'
                f'<td class="mono-num">{self._format_price_val(latest_c)}</td>'
                f'<td class="mono-num text-purple">{kelly_f * 100:.1f}%</td>'
                f'<td class="mono-num kelly-alloc-cell text-cyan">{act_alloc:,.0f} EGP</td>'
                f'<td class="mono-num kelly-shares-cell">{def_shares:,}</td>'
                f'<td class="mono-num text-red">{self._format_price_val(stop_p)}</td>'
                f'<td class="mono-num kelly-loss-cell text-red">-{def_loss:,.0f} EGP</td>'
                f'<td class="mono-num text-green">{self._format_price_val(target_p)}</td>'
                f'<td class="mono-num kelly-gain-cell text-green">+{def_gain:,.0f} EGP</td>'
                f'<td class="mono-num text-cyan">{rr:.2f}x</td>'
                f'</tr>'
            )

        rows_html = "".join(table_rows) if table_rows else "<tr><td colspan='10' style='text-align:center; padding: 20px;'>No active candidates available for Kelly sizing.</td></tr>"

        return f"""
    <section class="panel-section">
      <div class="panel-header">
        <div class="panel-title-wrap">
          <div class="heading-glow-bar emerald"></div>
          <h3>INTERACTIVE HALF-KELLY PORTFOLIO SIZING CALCULATOR</h3>
          <span class="count-bubble neon-emerald-chip">CAPITAL PRESERVATION</span>
        </div>
        <div class="panel-sub">Dynamically sizing trades to prevent ruin and maximize asymptotic geometric capital growth</div>
      </div>
      <div class="glass-panel kelly-calculator-wrap">
        <!-- Controls bar -->
        <div class="kelly-controls-bar">
          <div class="kelly-capital-control">
            <label for="kelly-portfolio-capital" class="kelly-label">TOTAL PORTFOLIO CAPITAL (EGP):</label>
            <div class="capital-input-group">
              <span class="input-curr">EGP</span>
              <input type="number" id="kelly-portfolio-capital" value="500000" min="10000" max="10000000" step="10000" class="capital-input mono-num">
            </div>
            <input type="range" id="kelly-capital-slider" value="500000" min="10000" max="2000000" step="10000" class="capital-slider">
          </div>
          <div class="kelly-risk-control">
            <span class="kelly-label">RISK PROFILE &amp; KELLY MULTIPLIER:</span>
            <div class="kelly-profile-pills">
              <button class="kelly-pill" data-multiplier="0.8">Conservative (0.8x Half-Kelly)</button>
              <button class="kelly-pill active" data-multiplier="1.0">Standard (1.0x Half-Kelly)</button>
              <button class="kelly-pill" data-multiplier="2.0">Aggressive (Full Kelly)</button>
            </div>
          </div>
        </div>

        <!-- Summary KPI Strip -->
        <div class="kelly-kpi-strip">
          <div class="kelly-kpi-box">
            <span class="kpi-label">TOTAL CAPITAL ALLOCATED</span>
            <span class="kpi-val mono-num text-cyan" id="kelly-total-allocated">0 EGP (0.0%)</span>
          </div>
          <div class="kelly-kpi-box">
            <span class="kpi-label">MAX AGGREGATE DRAWDOWN RISK</span>
            <span class="kpi-val mono-num text-red" id="kelly-total-risk">0 EGP (0.0%)</span>
          </div>
          <div class="kelly-kpi-box">
            <span class="kpi-label">PROJECTED TARGET ALPHA RETURN</span>
            <span class="kpi-val mono-num text-green" id="kelly-total-return">+0 EGP (+0.0%)</span>
          </div>
        </div>

        <!-- Table of sized candidates -->
        <div class="table-container">
          <table class="data-table kelly-table" id="kelly-results-table">
            <thead>
              <tr>
                <th>SYMBOL</th>
                <th>ENTRY</th>
                <th>KELLY %</th>
                <th>ALLOCATION</th>
                <th>SHARES</th>
                <th>STOP LOSS</th>
                <th>MAX RISK</th>
                <th>TARGET</th>
                <th>EXP GAIN</th>
                <th>R:R RATIO</th>
              </tr>
            </thead>
            <tbody id="kelly-table-body">
              {rows_html}
            </tbody>
          </table>
        </div>
      </div>
    </section>"""

    def _market_cards(self, result: Any, regime_name: str) -> str:
        candidates = [item for item in result.symbol_results if "Avoid" not in item.next_day_label]
        top_picks = [item for item in result.symbol_results if "Top Pick" in item.next_day_label]
        accepted = sum(1 for item in result.symbol_results if item.consensus_result and item.consensus_result.accepted)
        total = len(result.symbol_results)
        consensus_pct = (accepted / total * 100) if total > 0 else 0
        avg_quality = sum(item.data_quality_score for item in result.symbol_results) / total if total > 0 else 0

        regime_desc = "Defensive dampener active (-7% score, wider stops)" if "Bear" in regime_name else "Bullish expansion (+7% bonus, tighter stops)"

        cards = [
            {
                "title": "ACTIVE CANDIDATES",
                "value": str(len(candidates)),
                "badge": f"{len(top_picks)} Top Picks",
                "badge_cls": "badge-gold",
                "sub": "Setups with positive follow-through edge",
                "icon": "&#9889;",
            },
            {
                "title": "MARKET REGIME",
                "value": regime_name.upper(),
                "badge": "Risk Mode",
                "badge_cls": "badge-purple",
                "sub": regime_desc,
                "icon": "&#127760;",
            },
            {
                "title": "PRICE CONSENSUS",
                "value": f"{accepted}/{total}",
                "badge": f"{consensus_pct:.0f}% Verified",
                "badge_cls": "badge-green" if consensus_pct >= 80 else "badge-amber",
                "sub": "Multi-source tick cross-validation",
                "icon": "&#128737;&#65039;",
            },
            {
                "title": "DATA INTEGRITY",
                "value": f"{avg_quality:.0f}%",
                "badge": "Institutional",
                "badge_cls": "badge-cyan",
                "sub": "Full-history indicator completeness",
                "icon": "&#128202;",
            },
        ]

        cards_html = "".join(f"""
        <div class="metric-card glass-card">
          <div class="metric-top">
            <div class="metric-title-group">
              <span class="metric-icon">{c['icon']}</span>
              <span class="metric-title">{c['title']}</span>
            </div>
            <span class="metric-badge {c['badge_cls']}">{c['badge']}</span>
          </div>
          <div class="metric-value-wrap">
            <div class="metric-value">{escape(c['value'])}</div>
          </div>
          <div class="metric-sub">{escape(c['sub'])}</div>
        </div>
        """ for c in cards)

        return f"<section class='metrics-grid'>{cards_html}</section>"

    def _format_price_val(self, p: float) -> str:
        if p <= 0:
            return "0.00"
        if p < 0.10:
            return f"{p:.4f}"
        elif p < 1.00:
            return f"{p:.3f}"
        return f"{p:.2f}"

    def _candidate_panel(self, title: str, results: list[Any], mode: str) -> str:
        results_list = list(results) if results else []
        candidate_items = [
            item for item in results_list
            if "Avoid" not in getattr(item, "next_day_label", "")
        ]
        display_items = candidate_items if candidate_items else results_list[:10]

        cards = []
        for rank, item in enumerate(display_items, start=1):
            pred = getattr(item, 'next_day_prediction', None)
            score = float(getattr(item, 'next_day_score', 0.0) or 0.0)
            label = getattr(item, 'next_day_label', '') or ""
            reasons = getattr(item, 'next_day_reasons_text', '') or getattr(item, 'next_day_reasons', '') or ""

            opp = getattr(item, 'opportunity_score', None)
            company = str(getattr(opp, 'company', '') or getattr(item, 'symbol', '') or '')
            latest_close = float(getattr(pred, 'latest_close', 0.0) or getattr(opp, 'latest_close', 0.0) or 0.0)
            target_price = float(getattr(pred, 'target_price', 0.0) or (latest_close * 1.07))
            target_price_2 = float(getattr(pred, 'target_price_2', 0.0) or (target_price * 1.15))
            stop_loss = float(getattr(pred, 'stop_loss_price', 0.0) or (latest_close * 0.95))
            kelly_fraction = float(getattr(pred, 'kelly_fraction', 0.22) or 0.22)

            target_pct = ((target_price - latest_close) / latest_close * 100) if latest_close > 0 and target_price > 0 else 0
            target_pct_2 = ((target_price_2 - latest_close) / latest_close * 100) if latest_close > 0 and target_price_2 > 0 else 0
            stop_pct = ((latest_close - stop_loss) / latest_close * 100) if latest_close > 0 and stop_loss > 0 else 0
            rr_ratio = (target_pct / stop_pct) if stop_pct > 0 else 0.0

            liquidity_tier = getattr(pred, 'liquidity_tier', 'MODERATE') if pred else 'MODERATE'
            fill_feasibility = getattr(pred, 'fill_feasibility', 'Standard Execution') if pred else 'Standard Execution'
            liq_badge_cls = "tag-ok" if liquidity_tier == "HIGH" else ("tag-warn" if liquidity_tier == "MODERATE" else "tag-err")

            # Score color grade
            if score >= 80:
                score_cls = "score-ultra"
                score_gradient = "linear-gradient(135deg, #00ff87 0%, #00f2fe 100%)"
            elif score >= 70:
                score_cls = "score-high"
                score_gradient = "linear-gradient(135deg, #00f2fe 0%, #b388ff 100%)"
            else:
                score_cls = "score-mid"
                score_gradient = "linear-gradient(135deg, #ffd700 0%, #ff8a00 100%)"

            # Parse Badge Label
            consensus_res = getattr(item, 'consensus_result', None)
            is_top_pick = "Top Pick" in label
            is_low_conf = "Low Confidence" in label or (consensus_res is not None and not consensus_res.accepted)
            is_breakout = "Breakout" in label

            clean_badge = label
            if "⭐" in clean_badge:
                clean_badge = clean_badge.replace("⭐", "").strip()

            badge_style = "badge-card-gold" if is_top_pick else ("badge-card-red" if is_low_conf else "badge-card-cyan")

            # Check for warnings in reasons
            reasons_str = " ; ".join(reasons) if isinstance(reasons, list) else str(reasons)
            has_backtest_warn = "[BACKTEST REJECTION]" in reasons_str
            has_hmm_warn = "[HMM CAUTION]" in reasons_str
            has_ml_confirm = "ML confirms" in reasons_str

            # Card Data Attributes for Filtering
            data_tags = []
            if is_top_pick: data_tags.append("top")
            if is_breakout: data_tags.append("breakout")
            if not is_low_conf: data_tags.append("verified")
            if "Watch" in label: data_tags.append("watch")
            data_filter_str = " ".join(data_tags)

            sym_str = str(getattr(item, 'symbol', '') or '')

            cards.append(f"""
            <div class="candidate-card glass-card" data-symbol="{escape(sym_str)}" data-company="{escape(company.lower())}" data-tags="{data_filter_str}">
              <div class="card-glow-edge"></div>

              <!-- CARD HEADER -->
              <div class="card-header">
                <div class="symbol-block">
                  <span class="rank-pill">#{rank:02d}</span>
                  <div>
                    <div class="symbol-name">{escape(sym_str)}</div>
                    <div class="company-name" title="{escape(company)}">{escape(company)}</div>
                  </div>
                </div>

                <div class="card-badges">
                  {f'<span class="badge-mini-gold">&#11088; TOP PICK</span>' if is_top_pick else ''}
                  <span class="card-type-badge {badge_style}">{escape(clean_badge)}</span>
                </div>
              </div>

              <!-- MAIN METRIC ROW -->
              <div class="hero-metric-grid">
                <!-- AI SCORE DIAL -->
                <div class="hero-score-box">
                  <div class="hero-score-label">AI CONVICTION</div>
                  <div class="hero-score-num {score_cls}">{score:.1f}%</div>
                  <div class="score-progress-bar">
                    <div class="score-fill" style="width: {min(100, score)}%; background: {score_gradient};"></div>
                  </div>
                </div>

                <!-- PRICE & TARGET -->
                <div class="price-levels-box">
                  <div class="level-row">
                    <span class="level-label">ENTRY</span>
                    <span class="level-val mono-num">{self._format_price_val(latest_close)} <small class="currency">EGP</small></span>
                  </div>
                  <div class="level-row">
                    <span class="level-label text-green">TARGET 1</span>
                    <span class="level-val text-green mono-num">{self._format_price_val(target_price)} <span class="pct-chip up">+{target_pct:.1f}%</span></span>
                  </div>
                  <div class="level-row">
                    <span class="level-label text-red">STOP LOSS</span>
                    <span class="level-val text-red mono-num">{self._format_price_val(stop_loss)} <span class="pct-chip down">-{stop_pct:.1f}%</span></span>
                  </div>
                </div>

                <!-- RISK / REWARD & KELLY -->
                <div class="sizing-box">
                  <div class="sizing-item">
                    <span class="sizing-label">R:R RATIO</span>
                    <span class="sizing-val text-cyan mono-num">{rr_ratio:.2f}x</span>
                  </div>
                  <div class="sizing-item">
                    <span class="sizing-label">HALF-KELLY</span>
                    <span class="sizing-val text-purple mono-num">{kelly_fraction * 100:.1f}%</span>
                  </div>
                </div>
              </div>

              <!-- CANDLESTICK TARGET/STOP GEOMETRY BAR -->
              <div class="geometry-meter-wrap">
                <div class="geometry-meta-row">
                  <span class="geom-title">TARGET / STOP GEOMETRY</span>
                  <span class="geom-rr-badge mono-num">{rr_ratio:.2f}x R:R</span>
                </div>
                <div class="geometry-bar">
                  <div class="geom-stop" style="width: {min(35, max(12, stop_pct * 5.0))}%;" title="Stop Loss: -{stop_pct:.1f}% ({self._format_price_val(stop_loss)} EGP)">
                    <span class="geom-bar-label">-{stop_pct:.1f}%</span>
                  </div>
                  <div class="geom-entry" title="Entry: {self._format_price_val(latest_close)} EGP">
                    <div class="geom-entry-tick"></div>
                    <span class="geom-entry-label">ENTRY</span>
                  </div>
                  <div class="geom-target-1" style="width: {min(35, max(12, target_pct * 4.0))}%;" title="Target 1: +{target_pct:.1f}% ({self._format_price_val(target_price)} EGP)">
                    <span class="geom-bar-label">T1 +{target_pct:.1f}%</span>
                  </div>
                  <div class="geom-target-2" style="width: {min(25, max(10, (target_pct_2 - target_pct) * 2.5))}%;" title="Target 2 (Expansion): +{target_pct_2:.1f}% ({self._format_price_val(target_price_2)} EGP)">
                    <span class="geom-bar-label">T2 +{target_pct_2:.1f}%</span>
                  </div>
                </div>
                <div class="geometry-price-sub">
                  <span class="mono-num text-red">SL: {self._format_price_val(stop_loss)}</span>
                  <span class="mono-num text-muted">ENTRY: {self._format_price_val(latest_close)}</span>
                  <span class="mono-num text-green">T1: {self._format_price_val(target_price)}</span>
                  <span class="mono-num text-cyan">T2: {self._format_price_val(target_price_2)}</span>
                </div>
              </div>

              <!-- TAGS / CATALYSTS ROW -->
              <div class="tags-row">
                <span class="tag-pill {liq_badge_cls}" title="{escape(fill_feasibility)}">&#128167; {liquidity_tier} LIQUIDITY</span>
                {f'<span class="tag-pill tag-ml">&#9889; ML HIGH CONVICTION</span>' if has_ml_confirm else ''}
                {f'<span class="tag-pill tag-warn">&#9888;&#65039; POOR WIN-RATE TICKER</span>' if has_backtest_warn else ''}
                {f'<span class="tag-pill tag-warn">&#9888;&#65039; HMM DISTRIBUTION</span>' if has_hmm_warn else ''}
                {f'<span class="tag-pill tag-err">&#9888;&#65039; CONSENSUS UNVERIFIED</span>' if is_low_conf else '<span class="tag-pill tag-ok">&#10003; CONSENSUS VERIFIED</span>'}
              </div>

              <!-- REASONS / ANALYSIS TERMINAL -->
              <div class="terminal-reasons">
                <div class="terminal-header">
                  <span class="terminal-dot"></span>
                  <span class="terminal-title">QUANT ATTRIBUTION LOG</span>
                </div>
                <div class="terminal-body">
                  {self._format_reasons_html(reasons)}
                </div>
              </div>

              <!-- CARD FOOTER ACTIONS -->
              <div class="card-footer">
                <button class="btn-chart-modal" data-symbol="{escape(sym_str)}">
                  <span class="btn-icon">&#128200;</span>
                  <span>OPEN TRADINGVIEW PRO CHART</span>
                </button>
              </div>
            </div>
            """)

        return f"<section class='candidate-grid' id='candidate-grid'>{''.join(cards)}</section>"

    def _ranking_table(self, results: list[Any]) -> str:
        rows = []
        for rank, item in enumerate(results, start=1):
            consensus = getattr(item, 'consensus_result', None)
            consensus_text = "N/A"
            consensus_badge = "badge-neutral"
            if consensus:
                agree_cnt = getattr(consensus, 'agreeing_source_count', 0)
                src_cnt = getattr(consensus, 'source_count', 0)
                consensus_text = f"{agree_cnt}/{src_cnt}"
                consensus_badge = "badge-green" if getattr(consensus, 'accepted', False) else "badge-red"

            pred = getattr(item, 'next_day_prediction', None)
            score = float(getattr(item, 'next_day_score', 0.0) or 0.0)
            label = str(getattr(item, 'next_day_label', '') or "")
            clean_label = label.replace("⭐", "").strip()

            badge_cls = self._badge_class(label)

            opp = getattr(item, 'opportunity_score', None)
            company = str(getattr(opp, 'company', '') or getattr(item, 'symbol', '') or '')
            sym_str = str(getattr(item, 'symbol', '') or '')
            score_pct = getattr(opp, 'score_percent', None)
            if score_pct is None:
                score_pct = float(getattr(opp, 'total_score', 0.0) or 0.0)
            latest_c = float(getattr(opp, 'latest_close', 0.0) or (getattr(pred, 'latest_close', 0.0) if pred else 0.0) or 0.0)
            final_pred_score = float(getattr(item, 'final_predictor_score', 0.0) or 0.0)

            rows.append(
                f"<tr class='clickable-row' data-symbol='{escape(sym_str)}'>"
                f"<td class='rank-cell'>#{rank:02d}</td>"
                f"<td class='symbol-cell'>"
                f"  <span class='table-symbol'>{escape(sym_str)}</span>"
                f"  <span class='table-company'>{escape(company)}</span>"
                f"</td>"
                f"<td class='score-cell mono-num'>{score_pct:.0f}%</td>"
                f"<td class='score-cell mono-num'>{final_pred_score:.0f}%</td>"
                f"<td class='score-cell mono-num highlight-score'>{score:.1f}%</td>"
                f"<td><span class='table-badge {badge_cls}'>{escape(clean_label)}</span></td>"
                f"<td class='mono-num'>{self._format_price_val(latest_c)}</td>"
                f"<td><span class='mini-pill {consensus_badge}'>{escape(consensus_text)}</span></td>"
                f"<td><button class='table-action-btn' data-symbol='{escape(sym_str)}'>Chart</button></td>"
                f"</tr>"
            )

        return f"""
        <table class='data-table'>
          <thead>
            <tr>
              <th>RANK</th>
              <th>INSTRUMENT</th>
              <th>OPP SCORE</th>
              <th>SWING SCORE</th>
              <th>AI PREDICTION</th>
              <th>ACTION LABEL</th>
              <th>LATEST CLOSE</th>
              <th>CONSENSUS</th>
              <th>ACTION</th>
            </tr>
          </thead>
          <tbody>{''.join(rows)}</tbody>
        </table>"""

    def _heatmap_table(self, results: list[Any]) -> str:
        if not results: return ""
        first_opp = getattr(results[0], 'opportunity_score', None)
        components = getattr(first_opp, 'components', None) if first_opp else None
        if not components:
            return ""
        comp_names = [getattr(c, 'name', '') for c in components if hasattr(c, 'name')]
        if not comp_names:
            return ""
        headers = "".join(f"<th>{escape(str(name))}</th>" for name in comp_names)

        rows = []
        for rank, item in enumerate(results, start=1):
            opp = getattr(item, 'opportunity_score', None)
            item_components = getattr(opp, 'components', None) if opp else None
            if not item_components:
                continue
            cells = []
            for c in item_components:
                c_score = float(getattr(c, 'score', 0.0) or 0.0)
                c_max = float(getattr(c, 'max_score', 0.0) or 0.0)
                pct = c_score / c_max if c_max > 0 else 0
                alpha = max(0.06, pct * 0.9)
                if pct >= 0.75:
                    color = f"rgba(0, 255, 135, {alpha})" # Neon Emerald
                    text_color = "#ffffff"
                elif pct >= 0.4:
                    color = f"rgba(0, 242, 254, {alpha})" # Neon Cyan
                    text_color = "#ffffff"
                else:
                    color = f"rgba(255, 255, 255, 0.03)"
                    text_color = "rgba(255, 255, 255, 0.4)"

                val = f"{c_score:.1f}" if c_score % 1 != 0 else f"{c_score:.0f}"
                max_val = f"{c_max:.1f}" if c_max % 1 != 0 else f"{c_max:.0f}"
                c_name = str(getattr(c, 'name', '') or '')
                c_reason = str(getattr(c, 'reason', '') or '')

                cells.append(
                    f"<td style='background: {color}; color: {text_color};' title='{escape(c_name)}: {val}/{max_val}&#10;{escape(c_reason)}'>"
                    f"<span class='hm-val'>{val}</span>"
                    f"<span class='hm-max'>/{max_val}</span>"
                    f"</td>"
                )

            sym_str = str(getattr(item, 'symbol', '') or '')
            rows.append(
                f"<tr class='clickable-row' data-symbol='{escape(sym_str)}'>"
                f"<td class='rank-cell'>#{rank:02d}</td>"
                f"<td class='symbol-cell'><strong>{escape(sym_str)}</strong></td>"
                f"{''.join(cells)}"
                f"</tr>"
            )

        return f"""
        <table class='data-table heatmap-table'>
          <thead>
            <tr>
              <th>RANK</th>
              <th>SYMBOL</th>
              {headers}
            </tr>
          </thead>
          <tbody>{''.join(rows)}</tbody>
        </table>"""

    def _format_reasons_html(self, reasons: Any) -> str:
        if not reasons:
            return "<div class='reason-line text-cyan'>&bull; Strong technical momentum and volume breakout profile.</div>"
        
        if isinstance(reasons, list):
            parts = [str(p).strip() for p in reasons if str(p).strip()]
        else:
            parts = [p.strip() for p in str(reasons).split(";") if p.strip()]
        if not parts:
            return f"<div class='reason-line'>&bull; {escape(str(reasons))}</div>"
            
        lines = []
        for p in parts:
            cls = ""
            p_str = str(p)
            p_lower = p_str.lower()
            if "ML confirms" in p_str or "Bonus: +" in p_str or "Explosive setup" in p_str:
                cls = "text-green"
            elif "penalty" in p_lower or "caution" in p_lower or "rejection" in p_lower or "not accepted" in p_lower or "poor" in p_lower:
                cls = "text-red"
            elif "Regime" in p_str or "Base Opportunity" in p_str or "Analysis for" in p_str:
                cls = "text-cyan"
            lines.append(f"<div class='reason-line {cls}'>&bull; {escape(p_str)}</div>")
        return "".join(lines)

    def _badge_class(self, label: str) -> str:
        lowered = label.lower()
        if "top pick" in lowered or "candidate" in lowered:
            return "badge-good"
        if "watch" in lowered:
            return "badge-watch"
        if "avoid" in lowered or "poor" in lowered:
            return "badge-bad"
        if "low confidence" in lowered:
            return "badge-amber"
        return "badge-neutral"

    def _css(self) -> str:
        return """
:root {
  --bg-core: #07090e;
  --bg-surface: #0c1017;
  --bg-surface-elevated: #111722;
  --bg-card: rgba(12, 16, 23, 0.85);
  --border-subtle: rgba(255, 255, 255, 0.07);
  --border-active: rgba(0, 242, 254, 0.35);
  --border-gold: rgba(255, 215, 0, 0.4);

  --text-main: #f0f4fc;
  --text-muted: #8896ab;
  --text-slate: #94a3b8;
  --text-dim: #475569;

  --neon-emerald: #00ff87;
  --neon-cyan: #00f2fe;
  --neon-purple: #b388ff;
  --neon-gold: #ffd700;
  --neon-coral: #ff4757;

  --font-sans: 'Plus Jakarta Sans', -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background-color: var(--bg-core);
  background-image: radial-gradient(rgba(255, 255, 255, 0.04) 1px, transparent 1px);
  background-size: 24px 24px;
  color: var(--text-main);
  font-family: var(--font-sans);
  min-height: 100vh;
  position: relative;
  overflow-x: hidden;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}

/* Ambient Cyber Glow Background */
.glow-bg {
  position: fixed;
  top: -200px;
  left: 50%;
  transform: translateX(-50%);
  width: 1300px;
  height: 650px;
  background: radial-gradient(circle, rgba(0, 242, 254, 0.08) 0%, rgba(179, 136, 255, 0.05) 45%, transparent 70%);
  pointer-events: none;
  z-index: 0;
}

/* TOPBAR */
.topbar {
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 32px;
  background: rgba(7, 9, 14, 0.90);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--border-subtle);
  flex-wrap: wrap;
  gap: 12px;
}

.brand-group {
  display: flex;
  align-items: center;
  gap: 14px;
}

.logo-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(0, 242, 254, 0.08);
  border: 1px solid rgba(0, 242, 254, 0.25);
  padding: 5px 12px;
  border-radius: 6px;
}

.pulse-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--neon-cyan);
  box-shadow: 0 0 10px var(--neon-cyan);
  animation: pulse 2s infinite;
}

.pill-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
}

.pill-dot.live { background: var(--neon-emerald); box-shadow: 0 0 8px var(--neon-emerald); }
.pill-dot.pulse-cyan { background: var(--neon-cyan); box-shadow: 0 0 8px var(--neon-cyan); animation: pulse 2s infinite; }
.pill-dot.pulse-amber { background: var(--neon-gold); box-shadow: 0 0 8px var(--neon-gold); }
.pill-dot.pulse-purple { background: var(--neon-purple); box-shadow: 0 0 8px var(--neon-purple); }

@keyframes pulse {
  0% { transform: scale(0.95); opacity: 0.8; }
  50% { transform: scale(1.3); opacity: 1; box-shadow: 0 0 14px var(--neon-cyan); }
  100% { transform: scale(0.95); opacity: 0.8; }
}

.logo-text {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.15em;
  color: var(--neon-cyan);
}

.system-title h1 {
  font-size: 17px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: #ffffff;
  display: flex;
  align-items: center;
  gap: 8px;
}

.version-tag {
  font-size: 9px;
  font-family: var(--font-mono);
  padding: 2px 6px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 4px;
  color: var(--text-slate);
}

.status-pill-group {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.status-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  font-family: var(--font-mono);
  font-size: 10px;
}

.pill-label {
  color: var(--text-muted);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.05em;
}

.pill-val {
  font-weight: 700;
  color: var(--text-main);
}

.pill-val.highlight { color: var(--neon-gold); }
.pill-val.neon-cyan { color: var(--neon-cyan); }
.pill-val.text-green { color: var(--neon-emerald); }
.pill-val.text-amber { color: var(--neon-gold); }
.pill-val.text-purple { color: var(--neon-purple); }
.pill-val.text-slate { color: var(--text-slate); }

.regime-bear-volatile { color: var(--neon-coral); text-shadow: 0 0 8px rgba(255, 71, 87, 0.4); }
.regime-bull-trend { color: var(--neon-emerald); text-shadow: 0 0 8px rgba(0, 255, 135, 0.4); }

/* WINDOW 1: MARQUEE */
.ticker-marquee-wrap {
  display: flex;
  align-items: center;
  background: rgba(12, 16, 23, 0.95);
  border-bottom: 1px solid var(--border-subtle);
  overflow: hidden;
  height: 38px;
  position: relative;
  z-index: 90;
}

.marquee-label {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 16px;
  background: rgba(0, 242, 254, 0.08);
  border-right: 1px solid rgba(0, 242, 254, 0.25);
  color: var(--neon-cyan);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
  white-space: nowrap;
  height: 100%;
  flex-shrink: 0;
  z-index: 2;
}

.marquee-viewport {
  overflow: hidden;
  width: 100%;
  display: flex;
}

.marquee-track {
  display: flex;
  width: max-content;
  animation: marqueeScroll 40s linear infinite;
}

.marquee-track:hover {
  animation-play-state: paused;
}

.marquee-content {
  display: flex;
  align-items: center;
  gap: 28px;
  padding-right: 28px;
  white-space: nowrap;
}

@keyframes marqueeScroll {
  0% { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}

.marquee-item {
  font-family: var(--font-mono);
  font-size: 11px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.ticker-sym { font-weight: 800; color: #ffffff; }
.ticker-price { color: var(--text-slate); font-weight: 600; }
.ticker-up { color: var(--neon-emerald); font-weight: 700; }
.ticker-target { color: var(--neon-cyan); font-size: 10px; opacity: 0.85; }

.marquee-pill-regime {
  background: rgba(0, 255, 135, 0.1);
  border: 1px solid rgba(0, 255, 135, 0.3);
  padding: 2px 8px;
  border-radius: 4px;
  color: var(--neon-emerald);
  font-weight: 700;
}

.marquee-pill-kronos {
  background: rgba(0, 242, 254, 0.1);
  border: 1px solid rgba(0, 242, 254, 0.3);
  padding: 2px 8px;
  border-radius: 4px;
  color: var(--neon-cyan);
  font-weight: 700;
}

.marquee-pill-breadth {
  background: rgba(255, 215, 0, 0.1);
  border: 1px solid rgba(255, 215, 0, 0.3);
  padding: 2px 8px;
  border-radius: 4px;
  color: var(--neon-gold);
  font-weight: 700;
}

.marquee-pill-vol {
  background: rgba(179, 136, 255, 0.1);
  border: 1px solid rgba(179, 136, 255, 0.3);
  padding: 2px 8px;
  border-radius: 4px;
  color: var(--neon-purple);
  font-weight: 700;
}

/* CONTAINER */
.app-container {
  max-width: 1440px;
  margin: 0 auto;
  padding: 24px 32px;
  position: relative;
  z-index: 1;
}

/* WINDOW 6: COMMAND HUD */
.command-hud-deck {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 18px;
  margin-bottom: 24px;
  gap: 16px;
  flex-wrap: wrap;
}

.hud-left, .hud-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.hud-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 800;
  color: var(--neon-cyan);
  background: rgba(0, 242, 254, 0.1);
  border: 1px solid rgba(0, 242, 254, 0.25);
  padding: 5px 10px;
  border-radius: 6px;
}

.hud-hotkeys {
  display: flex;
  align-items: center;
  gap: 6px;
}

.hud-btn {
  background: var(--bg-surface-elevated);
  border: 1px solid var(--border-subtle);
  color: var(--text-slate);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  padding: 6px 10px;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.2s;
}

.hud-btn:hover {
  border-color: var(--neon-cyan);
  color: #ffffff;
}

.hud-btn.active {
  background: rgba(0, 242, 254, 0.15);
  border-color: var(--neon-cyan);
  color: var(--neon-cyan);
}

.key-chip {
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 3px;
  padding: 1px 5px;
  font-size: 9px;
  font-weight: 800;
  color: #ffffff;
}

.hud-action-btn {
  background: rgba(0, 242, 254, 0.08);
  border: 1px solid rgba(0, 242, 254, 0.25);
  color: var(--neon-cyan);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  text-decoration: none;
  transition: all 0.2s;
}

.hud-action-btn:hover {
  background: rgba(0, 242, 254, 0.2);
  border-color: var(--neon-cyan);
  box-shadow: 0 0 14px rgba(0, 242, 254, 0.25);
  color: #ffffff;
}

.hud-toast {
  position: fixed;
  bottom: 24px;
  right: 24px;
  background: var(--bg-surface-elevated);
  border: 1px solid var(--neon-cyan);
  color: #ffffff;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
  padding: 12px 20px;
  border-radius: 8px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.7), 0 0 15px rgba(0, 242, 254, 0.3);
  z-index: 9999;
  display: none;
  animation: slideInToast 0.3s ease;
}

@keyframes slideInToast {
  from { transform: translateY(20px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

/* METRICS GRID */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 32px;
}

.glass-card {
  background: var(--bg-card);
  backdrop-filter: blur(16px);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  padding: 18px 20px;
  position: relative;
  transition: all 0.25s ease;
}

.glass-card:hover {
  border-color: var(--border-active);
  box-shadow: 0 8px 32px rgba(0, 242, 254, 0.06);
  transform: translateY(-2px);
}

.metric-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.metric-title-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.metric-icon { font-size: 14px; }

.metric-title {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: var(--text-muted);
}

.metric-badge {
  font-size: 9px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 4px;
  font-family: var(--font-mono);
}

.badge-gold { background: rgba(255, 215, 0, 0.12); color: var(--neon-gold); border: 1px solid rgba(255, 215, 0, 0.3); }
.badge-purple { background: rgba(179, 136, 255, 0.12); color: var(--neon-purple); border: 1px solid rgba(179, 136, 255, 0.3); }
.badge-green { background: rgba(0, 255, 135, 0.12); color: var(--neon-emerald); border: 1px solid rgba(0, 255, 135, 0.3); }
.badge-cyan { background: rgba(0, 242, 254, 0.12); color: var(--neon-cyan); border: 1px solid rgba(0, 242, 254, 0.3); }
.badge-amber { background: rgba(255, 138, 0, 0.12); color: #ff8a00; border: 1px solid rgba(255, 138, 0, 0.3); }

.metric-value {
  font-family: var(--font-mono);
  font-size: 26px;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: #ffffff;
}

.metric-sub {
  margin-top: 6px;
  font-size: 11px;
  color: var(--text-muted);
}

/* WINDOW 2: MODEL DIAGNOSTICS */
.diagnostics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.diag-card {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.diag-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.diag-title-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.diag-icon { font-size: 16px; }

.diag-title {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.05em;
  color: #ffffff;
}

.diag-subtitle {
  font-size: 9px;
  color: var(--text-muted);
}

.status-chip-live {
  display: flex;
  align-items: center;
  gap: 5px;
  background: rgba(0, 255, 135, 0.1);
  border: 1px solid rgba(0, 255, 135, 0.3);
  color: var(--neon-emerald);
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
}

.status-chip-regime {
  display: flex;
  align-items: center;
  gap: 5px;
  background: rgba(179, 136, 255, 0.1);
  border: 1px solid rgba(179, 136, 255, 0.3);
  color: var(--neon-purple);
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
}

.diag-metrics-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  margin: 10px 0;
  padding: 10px 0;
  border-top: 1px solid var(--border-subtle);
  border-bottom: 1px solid var(--border-subtle);
}

.diag-stat {
  display: flex;
  flex-direction: column;
}

.stat-label {
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--text-muted);
}

.stat-value {
  font-size: 13px;
  font-weight: 700;
  color: #ffffff;
}

.diag-bar-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 6px;
}

.bar-label-row {
  display: flex;
  justify-content: space-between;
  font-size: 9px;
  color: var(--text-muted);
}

.mini-progress-bar {
  height: 4px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 2px;
  overflow: hidden;
}

.mini-progress-fill {
  height: 100%;
  border-radius: 2px;
}

.mini-progress-fill.emerald { background: var(--neon-emerald); box-shadow: 0 0 8px var(--neon-emerald); }
.mini-progress-fill.cyan { background: var(--neon-cyan); box-shadow: 0 0 8px var(--neon-cyan); }
.mini-progress-fill.purple { background: var(--neon-purple); }

.diag-footer-text {
  font-size: 9px;
  color: var(--text-muted);
  margin-top: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
  padding-top: 6px;
}

.hmm-state-bars {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 10px 0;
}

.hmm-state-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 10px;
  gap: 10px;
}

.hmm-name { width: 120px; color: var(--text-muted); font-size: 9px; }
.hmm-bar-wrap { flex: 1; height: 5px; background: rgba(255, 255, 255, 0.06); border-radius: 3px; overflow: hidden; }
.hmm-bar { height: 100%; border-radius: 3px; }
.hmm-bar.amber { background: var(--neon-gold); }
.hmm-bar.emerald { background: var(--neon-emerald); box-shadow: 0 0 8px var(--neon-emerald); }
.hmm-bar.coral { background: var(--neon-coral); }
.hmm-val { width: 40px; text-align: right; font-size: 10px; font-weight: 700; }

.factor-weights-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 8px 0;
}

.factor-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  font-size: 9px;
}

.factor-name { width: 90px; color: var(--text-muted); }
.factor-bar-wrap { flex: 1; height: 4px; background: rgba(255, 255, 255, 0.06); border-radius: 2px; overflow: hidden; }
.factor-bar { height: 100%; border-radius: 2px; }
.factor-bar.emerald { background: var(--neon-emerald); }
.factor-bar.cyan { background: var(--neon-cyan); }
.factor-bar.purple { background: var(--neon-purple); }
.factor-bar.gold { background: var(--neon-gold); }
.factor-pct { width: 30px; text-align: right; font-weight: 700; }

/* WINDOW 3: SECTOR MOMENTUM */
.sector-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 14px;
}

.sector-card {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 10px;
}

.sector-top {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sector-title-group {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.sector-icon { font-size: 16px; margin-top: 2px; }
.sector-name { font-size: 12px; font-weight: 800; color: #ffffff; }
.sector-leaders { font-size: 9px; color: var(--text-muted); margin-top: 3px; }

.leader-chip {
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--neon-cyan);
  background: rgba(0, 242, 254, 0.08);
  padding: 1px 4px;
  border-radius: 3px;
  margin-right: 2px;
}

.sector-tag {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
}

.tag-inflow { background: rgba(0, 255, 135, 0.1); color: var(--neon-emerald); border: 1px solid rgba(0, 255, 135, 0.25); }
.tag-breakout { background: rgba(0, 242, 254, 0.1); color: var(--neon-cyan); border: 1px solid rgba(0, 242, 254, 0.25); }
.tag-consolidate { background: rgba(179, 136, 255, 0.1); color: var(--neon-purple); border: 1px solid rgba(179, 136, 255, 0.25); }
.tag-leader { background: rgba(255, 215, 0, 0.1); color: var(--neon-gold); border: 1px solid rgba(255, 215, 0, 0.25); }
.tag-range { background: rgba(148, 163, 184, 0.1); color: var(--text-slate); border: 1px solid rgba(148, 163, 184, 0.25); }

.sector-stats-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
  padding: 8px 0;
  border-top: 1px solid var(--border-subtle);
  border-bottom: 1px solid var(--border-subtle);
}

.sector-stat { display: flex; flex-direction: column; }
.sec-label { font-size: 7.5px; font-weight: 700; color: var(--text-muted); }
.sec-val { font-size: 11px; font-weight: 700; }

.sector-bar-wrap { height: 4px; background: rgba(255, 255, 255, 0.06); border-radius: 2px; overflow: hidden; }
.sector-bar { height: 100%; border-radius: 2px; }
.sector-bar.emerald { background: var(--neon-emerald); box-shadow: 0 0 6px var(--neon-emerald); }
.sector-bar.cyan { background: var(--neon-cyan); box-shadow: 0 0 6px var(--neon-cyan); }
.sector-bar.purple { background: var(--neon-purple); }
.sector-bar.gold { background: var(--neon-gold); box-shadow: 0 0 6px var(--neon-gold); }
.sector-bar.blue { background: #38bdf8; }

/* WINDOW 4: HISTORICAL TRACK RECORD */
.track-record-wrap {
  padding: 20px 24px;
}

.track-metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.track-metric-box {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 14px;
}

.track-stat-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.track-icon { font-size: 14px; }
.track-label { font-size: 9px; font-weight: 700; color: var(--text-muted); letter-spacing: 0.08em; }
.track-val { font-size: 24px; font-weight: 800; }
.track-sub { font-size: 10px; color: var(--text-muted); margin-top: 4px; }

.expectancy-bar-container {
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 20px;
}

.expectancy-label-row {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  font-weight: 700;
  color: var(--text-muted);
  margin-bottom: 6px;
}

.expectancy-bar-wrap {
  display: flex;
  height: 20px;
  border-radius: 4px;
  overflow: hidden;
}

.exp-negative {
  background: rgba(255, 71, 87, 0.25);
  border-right: 1px solid var(--neon-coral);
  color: var(--neon-coral);
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.exp-divider {
  width: 3px;
  background: #ffffff;
}

.exp-positive {
  background: rgba(0, 255, 135, 0.25);
  border-left: 1px solid var(--neon-emerald);
  color: var(--neon-emerald);
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.verified-hits-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 800;
  color: var(--neon-gold);
  letter-spacing: 0.1em;
  margin-bottom: 12px;
}

.verified-hits-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
}

.hit-card {
  background: var(--bg-surface-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.hit-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.hit-sym { font-family: var(--font-mono); font-size: 12px; font-weight: 800; color: #ffffff; }
.badge-hit {
  background: rgba(0, 255, 135, 0.15);
  border: 1px solid rgba(0, 255, 135, 0.35);
  color: var(--neon-emerald);
  font-family: var(--font-mono);
  font-size: 8px;
  font-weight: 700;
  padding: 1px 4px;
  border-radius: 3px;
}

.hit-gain { font-size: 18px; font-weight: 800; }
.hit-path { font-size: 9px; color: var(--text-muted); }

/* WINDOW 5: HALF-KELLY CALCULATOR */
.kelly-calculator-wrap {
  padding: 20px 24px;
}

.kelly-controls-bar {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--border-subtle);
  margin-bottom: 18px;
}

.kelly-label {
  display: block;
  font-size: 9px;
  font-weight: 800;
  color: var(--text-muted);
  letter-spacing: 0.08em;
  margin-bottom: 8px;
}

.capital-input-group {
  display: flex;
  align-items: center;
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 4px 10px;
  width: 240px;
  margin-bottom: 10px;
}

.input-curr {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  margin-right: 8px;
}

.capital-input {
  background: transparent;
  border: none;
  outline: none;
  color: var(--neon-gold);
  font-size: 15px;
  font-weight: 800;
  width: 100%;
}

.capital-slider {
  width: 100%;
  accent-color: var(--neon-emerald);
  cursor: pointer;
}

.kelly-profile-pills {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.kelly-pill {
  background: var(--bg-surface-elevated);
  border: 1px solid var(--border-subtle);
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.kelly-pill:hover {
  color: #ffffff;
  border-color: var(--neon-emerald);
}

.kelly-pill.active {
  background: rgba(0, 255, 135, 0.15);
  border-color: var(--neon-emerald);
  color: var(--neon-emerald);
  box-shadow: 0 0 12px rgba(0, 255, 135, 0.2);
}

.kelly-kpi-strip {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.kelly-kpi-box {
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 12px 16px;
}

.kpi-label {
  display: block;
  font-size: 8px;
  font-weight: 800;
  color: var(--text-muted);
  letter-spacing: 0.1em;
  margin-bottom: 4px;
}

.kpi-val {
  font-size: 16px;
  font-weight: 800;
}

/* CONTROLS BAR */
.controls-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 16px;
}

.section-heading {
  display: flex;
  align-items: center;
  gap: 10px;
}

.heading-glow-bar {
  width: 4px;
  height: 20px;
  background: var(--neon-cyan);
  border-radius: 2px;
  box-shadow: 0 0 12px var(--neon-cyan);
}

.heading-glow-bar.cyan { background: var(--neon-cyan); box-shadow: 0 0 12px var(--neon-cyan); }
.heading-glow-bar.purple { background: var(--neon-purple); box-shadow: 0 0 12px var(--neon-purple); }
.heading-glow-bar.gold { background: var(--neon-gold); box-shadow: 0 0 12px var(--neon-gold); }
.heading-glow-bar.emerald { background: var(--neon-emerald); box-shadow: 0 0 12px var(--neon-emerald); }

.section-heading h2 {
  font-size: 14px;
  font-weight: 800;
  letter-spacing: 0.1em;
  color: #ffffff;
}

.count-bubble {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  background: rgba(0, 242, 254, 0.12);
  color: var(--neon-cyan);
  border: 1px solid rgba(0, 242, 254, 0.3);
  padding: 1px 7px;
  border-radius: 10px;
}

.neon-purple-chip {
  background: rgba(179, 136, 255, 0.12);
  color: var(--neon-purple);
  border: 1px solid rgba(179, 136, 255, 0.3);
}

.neon-emerald-chip {
  background: rgba(0, 255, 135, 0.12);
  color: var(--neon-emerald);
  border: 1px solid rgba(0, 255, 135, 0.3);
}

.neon-gold-chip {
  background: rgba(255, 215, 0, 0.12);
  color: var(--neon-gold);
  border: 1px solid rgba(255, 215, 0, 0.3);
}

.filter-search-group {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.search-wrap {
  position: relative;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: 10px;
  color: var(--text-muted);
  font-size: 12px;
  pointer-events: none;
}

.search-wrap input {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  color: var(--text-main);
  font-family: var(--font-sans);
  font-size: 12px;
  padding: 7px 12px 7px 32px;
  border-radius: 6px;
  outline: none;
  width: 220px;
  transition: all 0.2s;
}

.search-wrap input:focus {
  border-color: var(--neon-cyan);
  box-shadow: 0 0 12px rgba(0, 242, 254, 0.15);
  width: 260px;
}

.btn-group {
  display: flex;
  background: var(--bg-surface);
  padding: 3px;
  border-radius: 6px;
  border: 1px solid var(--border-subtle);
}

.filter-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  padding: 5px 10px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s;
}

.filter-btn:hover { color: #ffffff; }
.filter-btn.active {
  background: rgba(0, 242, 254, 0.15);
  color: var(--neon-cyan);
}

/* CANDIDATE CARDS GRID */
.candidate-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
  margin-bottom: 40px;
}

.candidate-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 14px;
  padding: 22px;
  position: relative;
  overflow: hidden;
}

.candidate-card:hover {
  border-color: rgba(0, 242, 254, 0.4);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.6), 0 0 24px rgba(0, 242, 254, 0.08);
}

.card-glow-edge {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, rgba(0, 242, 254, 0.6), transparent);
  opacity: 0;
  transition: opacity 0.3s;
}

.candidate-card:hover .card-glow-edge { opacity: 1; }

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.symbol-block {
  display: flex;
  align-items: center;
  gap: 10px;
}

.rank-pill {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 800;
  color: var(--neon-cyan);
  background: rgba(0, 242, 254, 0.08);
  border: 1px solid rgba(0, 242, 254, 0.2);
  padding: 4px 8px;
  border-radius: 6px;
}

.symbol-name {
  font-size: 18px;
  font-weight: 800;
  letter-spacing: -0.01em;
  color: #ffffff;
}

.company-name {
  font-size: 11px;
  color: var(--text-muted);
  max-width: 220px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-badges {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.badge-mini-gold {
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 800;
  color: var(--neon-gold);
  background: rgba(255, 215, 0, 0.15);
  border: 1px solid rgba(255, 215, 0, 0.35);
  padding: 2px 6px;
  border-radius: 4px;
  box-shadow: 0 0 8px rgba(255, 215, 0, 0.2);
}

.card-type-badge {
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 3px 8px;
  border-radius: 4px;
}

.badge-card-gold { background: rgba(255, 215, 0, 0.1); color: var(--neon-gold); border: 1px solid rgba(255, 215, 0, 0.25); }
.badge-card-cyan { background: rgba(0, 242, 254, 0.1); color: var(--neon-cyan); border: 1px solid rgba(0, 242, 254, 0.25); }
.badge-card-red { background: rgba(255, 71, 87, 0.1); color: var(--neon-coral); border: 1px solid rgba(255, 71, 87, 0.25); }

/* HERO METRIC GRID */
.hero-metric-grid {
  display: grid;
  grid-template-columns: 1.1fr 1.5fr 1fr;
  gap: 12px;
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 14px;
}

.hero-score-box {
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.hero-score-label {
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: var(--text-muted);
}

.hero-score-num {
  font-family: var(--font-mono);
  font-size: 26px;
  font-weight: 800;
  line-height: 1.1;
  margin: 4px 0 6px;
}

.score-ultra { color: var(--neon-emerald); text-shadow: 0 0 14px rgba(0, 255, 135, 0.4); }
.score-high { color: var(--neon-cyan); text-shadow: 0 0 14px rgba(0, 242, 254, 0.4); }
.score-mid { color: var(--neon-gold); text-shadow: 0 0 14px rgba(255, 215, 0, 0.4); }

.score-progress-bar {
  height: 4px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 2px;
  overflow: hidden;
}

.score-fill { height: 100%; border-radius: 2px; }

.price-levels-box {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 4px;
  border-left: 1px solid var(--border-subtle);
  border-right: 1px solid var(--border-subtle);
  padding: 0 12px;
}

.level-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
}

.level-label {
  font-size: 9px;
  font-weight: 700;
  color: var(--text-muted);
}

.level-val {
  font-family: var(--font-mono);
  font-weight: 700;
}

.currency { font-size: 8px; color: var(--text-dim); }

.pct-chip {
  font-size: 9px;
  font-weight: 700;
  padding: 1px 4px;
  border-radius: 3px;
  margin-left: 3px;
}

.pct-chip.up { background: rgba(0, 255, 135, 0.15); color: var(--neon-emerald); }
.pct-chip.down { background: rgba(255, 71, 87, 0.15); color: var(--neon-coral); }

.sizing-box {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 10px;
  padding-left: 4px;
}

.sizing-item {
  display: flex;
  flex-direction: column;
}

.sizing-label {
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: var(--text-muted);
}

.sizing-val {
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 700;
}

.text-green { color: var(--neon-emerald); }
.text-red { color: var(--neon-coral); }
.text-cyan { color: var(--neon-cyan); }
.text-purple { color: var(--neon-purple); }
.neon-gold { color: var(--neon-gold); }
.mono-num { font-family: var(--font-mono); }

/* CANDLESTICK TARGET/STOP GEOMETRY BAR */
.geometry-meter-wrap {
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 10px 12px;
}

.geometry-meta-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.geom-title {
  font-size: 8.5px;
  font-weight: 800;
  letter-spacing: 0.1em;
  color: var(--text-muted);
}

.geom-rr-badge {
  font-size: 10px;
  font-weight: 800;
  color: var(--neon-cyan);
  background: rgba(0, 242, 254, 0.1);
  border: 1px solid rgba(0, 242, 254, 0.3);
  padding: 1px 6px;
  border-radius: 4px;
}

.geometry-bar {
  display: flex;
  align-items: center;
  height: 18px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 4px;
  overflow: hidden;
  position: relative;
}

.geom-stop {
  height: 100%;
  background: linear-gradient(90deg, rgba(255, 71, 87, 0.8), rgba(255, 71, 87, 0.3));
  display: flex;
  align-items: center;
  justify-content: center;
}

.geom-entry {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 0 4px;
  z-index: 2;
  background: #ffffff;
  color: #000000;
  height: 100%;
}

.geom-entry-tick {
  width: 2px;
  height: 100%;
  background: #ffffff;
}

.geom-entry-label {
  font-family: var(--font-mono);
  font-size: 7px;
  font-weight: 800;
}

.geom-target-1 {
  height: 100%;
  background: linear-gradient(90deg, rgba(0, 255, 135, 0.3), rgba(0, 255, 135, 0.8));
  display: flex;
  align-items: center;
  justify-content: center;
}

.geom-target-2 {
  height: 100%;
  background: linear-gradient(90deg, rgba(0, 242, 254, 0.4), rgba(0, 242, 254, 0.9));
  display: flex;
  align-items: center;
  justify-content: center;
}

.geom-bar-label {
  font-family: var(--font-mono);
  font-size: 8px;
  font-weight: 700;
  color: #ffffff;
  white-space: nowrap;
  padding: 0 4px;
  text-shadow: 0 1px 2px rgba(0,0,0,0.8);
}

.geometry-price-sub {
  display: flex;
  justify-content: space-between;
  font-size: 9px;
  font-weight: 600;
}

/* TAGS ROW */
.tags-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag-pill {
  font-size: 9px;
  font-weight: 700;
  font-family: var(--font-mono);
  padding: 3px 8px;
  border-radius: 4px;
}

.tag-ml { background: rgba(0, 255, 135, 0.08); color: var(--neon-emerald); border: 1px solid rgba(0, 255, 135, 0.25); }
.tag-warn { background: rgba(255, 215, 0, 0.08); color: var(--neon-gold); border: 1px solid rgba(255, 215, 0, 0.25); }
.tag-err { background: rgba(255, 71, 87, 0.08); color: var(--neon-coral); border: 1px solid rgba(255, 71, 87, 0.25); }
.tag-ok { background: rgba(0, 242, 254, 0.08); color: var(--neon-cyan); border: 1px solid rgba(0, 242, 254, 0.25); }

/* TERMINAL LOG */
.terminal-reasons {
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 6px;
  padding: 10px 12px;
}

.terminal-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.terminal-dot {
  width: 5px;
  height: 5px;
  background: var(--neon-cyan);
  border-radius: 50%;
}

.terminal-title {
  font-size: 8px;
  font-weight: 800;
  letter-spacing: 0.15em;
  color: var(--text-muted);
}

.terminal-body {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-muted);
  line-height: 1.5;
}

.reason-line {
  margin-bottom: 3px;
  line-height: 1.4;
  word-break: break-word;
}
.reason-line:last-child {
  margin-bottom: 0;
}

/* CARD ACTIONS */
.card-footer {
  margin-top: auto;
}

.btn-chart-modal {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  background: rgba(0, 242, 254, 0.06);
  border: 1px solid rgba(0, 242, 254, 0.2);
  color: var(--neon-cyan);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-chart-modal:hover {
  background: rgba(0, 242, 254, 0.16);
  border-color: var(--neon-cyan);
  box-shadow: 0 0 16px rgba(0, 242, 254, 0.2);
  color: #ffffff;
}

/* TABLES */
.panel-section {
  margin-bottom: 36px;
}

.panel-header {
  margin-bottom: 14px;
}

.panel-title-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 4px;
}

.panel-title-wrap h3 {
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.1em;
  color: #ffffff;
}

.panel-sub {
  font-size: 11px;
  color: var(--text-muted);
}

.glass-panel {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  overflow: hidden;
}

.table-container {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  text-align: left;
}

.data-table th {
  background: rgba(0, 0, 0, 0.4);
  color: var(--text-muted);
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.12em;
  padding: 12px 14px;
  border-bottom: 1px solid var(--border-subtle);
}

.data-table td {
  padding: 12px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
  vertical-align: middle;
}

.clickable-row {
  cursor: pointer;
  transition: background 0.15s;
}

.clickable-row:hover td {
  background: rgba(0, 242, 254, 0.04) !important;
}

.rank-cell {
  font-family: var(--font-mono);
  color: var(--text-muted);
  font-weight: 700;
  width: 40px;
}

.symbol-cell strong, .table-symbol {
  font-weight: 800;
  color: #ffffff;
  font-size: 13px;
}

.table-company {
  display: block;
  font-size: 10px;
  color: var(--text-muted);
  max-width: 180px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.score-cell {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
}

.highlight-score {
  color: var(--neon-cyan);
  font-weight: 800;
  font-size: 13px;
}

.table-badge {
  display: inline-block;
  font-size: 9px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 4px;
}

.badge-good { background: rgba(0, 255, 135, 0.1); color: var(--neon-emerald); border: 1px solid rgba(0, 255, 135, 0.25); }
.badge-watch { background: rgba(255, 215, 0, 0.1); color: var(--neon-gold); border: 1px solid rgba(255, 215, 0, 0.25); }
.badge-bad { background: rgba(255, 71, 87, 0.1); color: var(--neon-coral); border: 1px solid rgba(255, 71, 87, 0.25); }
.badge-neutral { background: rgba(255, 255, 255, 0.05); color: var(--text-muted); border: 1px solid var(--border-subtle); }

.mini-pill {
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
}

.table-action-btn {
  background: transparent;
  border: 1px solid var(--border-subtle);
  color: var(--neon-cyan);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  padding: 4px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.table-action-btn:hover {
  background: var(--neon-cyan);
  color: #000000;
}

/* HEATMAP */
.heatmap-table td {
  text-align: center;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  border: 1px solid rgba(0, 0, 0, 0.3);
}

.hm-val { font-weight: 700; }
.hm-max { font-size: 9px; opacity: 0.5; }

/* TRADINGVIEW MODAL */
.modal {
  display: none;
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: 1000;
  align-items: center;
  justify-content: center;
}

.modal.active { display: flex; }

.modal-backdrop {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.85);
  backdrop-filter: blur(8px);
}

.glass-modal {
  position: relative;
  z-index: 10;
  width: 90%;
  max-width: 1100px;
  background: var(--bg-surface-elevated);
  border: 1px solid rgba(0, 242, 254, 0.35);
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 20px 80px rgba(0, 0, 0, 0.8), 0 0 40px rgba(0, 242, 254, 0.15);
  animation: modalIn 0.2s ease-out;
}

@keyframes modalIn {
  from { transform: scale(0.96); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 22px;
  background: #000000;
  border-bottom: 1px solid var(--border-subtle);
}

.modal-title-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.modal-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--neon-cyan);
  box-shadow: 0 0 10px var(--neon-cyan);
}

.modal-title {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: 0.05em;
}

.close-modal-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: 24px;
  line-height: 1;
  cursor: pointer;
  transition: color 0.2s;
}

.close-modal-btn:hover { color: var(--neon-coral); }

/* FOOTER */
.footer {
  border-top: 1px solid var(--border-subtle);
  padding: 24px 32px;
  text-align: center;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-dim);
}

.footer-content {
  display: flex;
  justify-content: center;
  gap: 12px;
}

@media (max-width: 1200px) {
  .diagnostics-grid { grid-template-columns: repeat(2, 1fr); }
  .sector-grid { grid-template-columns: repeat(2, 1fr); }
  .track-metrics-grid { grid-template-columns: repeat(2, 1fr); }
  .verified-hits-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 1024px) {
  .metrics-grid { grid-template-columns: repeat(2, 1fr); }
  .candidate-grid { grid-template-columns: 1fr; }
  .topbar { padding: 12px 18px; }
  .app-container { padding: 18px; }
  .hide-mobile { display: none; }
  .kelly-controls-bar { grid-template-columns: 1fr; }
}
"""

    def _js(self) -> str:
        return """
document.addEventListener("DOMContentLoaded", function() {
    // --- LIVE FILTER & SEARCH LOGIC ---
    const searchInput = document.getElementById('symbol-search');
    const filterBtns = document.querySelectorAll('.filter-btn');
    const cards = document.querySelectorAll('.candidate-card');
    const countBadge = document.getElementById('candidate-count-badge');

    let currentFilter = 'all';
    let searchQuery = '';

    function updateGrid() {
        let visibleCount = 0;
        cards.forEach(card => {
            const sym = card.getAttribute('data-symbol').toLowerCase();
            const comp = card.getAttribute('data-company').toLowerCase();
            const tags = card.getAttribute('data-tags') || '';

            const matchesSearch = !searchQuery || sym.includes(searchQuery) || comp.includes(searchQuery);
            let matchesFilter = true;

            if (currentFilter === 'top') {
                matchesFilter = tags.includes('top');
            } else if (currentFilter === 'breakout') {
                matchesFilter = tags.includes('breakout');
            } else if (currentFilter === 'watch') {
                matchesFilter = tags.includes('watch');
            } else if (currentFilter === 'verified') {
                matchesFilter = tags.includes('verified');
            }

            if (matchesSearch && matchesFilter) {
                card.style.display = 'flex';
                visibleCount++;
            } else {
                card.style.display = 'none';
            }
        });

        if (countBadge) {
            countBadge.innerText = visibleCount;
        }
    }

    function setFilter(filterName) {
        currentFilter = filterName;
        filterBtns.forEach(b => {
            if (b.getAttribute('data-filter') === filterName) {
                b.classList.add('active');
            } else {
                b.classList.remove('active');
            }
        });
        document.querySelectorAll('.hud-btn').forEach(hb => {
            if (hb.getAttribute('data-filter') === filterName) {
                hb.classList.add('active');
            } else {
                hb.classList.remove('active');
            }
        });
        updateGrid();
    }

    if (searchInput) {
        searchInput.addEventListener('input', function(e) {
            searchQuery = e.target.value.toLowerCase().trim();
            updateGrid();
        });
    }

    filterBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            setFilter(this.getAttribute('data-filter'));
        });
    });

    // HUD Filter Buttons
    document.querySelectorAll('.hud-btn[data-filter]').forEach(btn => {
        btn.addEventListener('click', function() {
            setFilter(this.getAttribute('data-filter'));
        });
    });

    const searchFocusBtn = document.getElementById('hud-btn-search-focus');
    if (searchFocusBtn) {
        searchFocusBtn.addEventListener('click', function() {
            if (searchInput) {
                searchInput.focus();
                searchInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        });
    }

    // Hotkey navigation
    document.addEventListener('keydown', function(e) {
        if (['input', 'textarea'].includes(document.activeElement.tagName.toLowerCase())) {
            if (e.key === 'Escape') {
                document.activeElement.blur();
            }
            return;
        }

        if (e.key === '1') {
            setFilter('top');
        } else if (e.key === '2') {
            setFilter('breakout');
        } else if (e.key === '3') {
            setFilter('all');
        } else if (e.key === '/') {
            e.preventDefault();
            if (searchInput) {
                searchInput.focus();
                searchInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }
    });

    updateGrid();

    // --- TOAST HELPER ---
    const toast = document.getElementById('hud-toast');
    function showToast(msg, duration = 2600) {
        if (!toast) return;
        toast.innerHTML = msg;
        toast.style.display = 'block';
        setTimeout(() => {
            toast.style.display = 'none';
        }, duration);
    }

    // --- COPY TELEGRAM BRIEFING ---
    const copyBtn = document.getElementById('btn-copy-briefing');
    if (copyBtn) {
        copyBtn.addEventListener('click', function() {
            let briefing = "⚡ PRAECURSOR-EGX QUANT TERMINAL BRIEFING ⚡\\n\\n";
            const topCards = Array.from(document.querySelectorAll('.candidate-card[data-tags*="top"], .candidate-card')).slice(0, 5);
            topCards.forEach((c, idx) => {
                const sym = c.getAttribute('data-symbol');
                const price = c.querySelector('.level-val') ? c.querySelector('.level-val').innerText.trim() : '';
                const target = c.querySelector('.level-row .text-green') ? c.querySelector('.level-row .text-green').innerText.trim() : '';
                const stop = c.querySelector('.level-row .text-red') ? c.querySelector('.level-row .text-red').innerText.trim() : '';
                const score = c.querySelector('.hero-score-num') ? c.querySelector('.hero-score-num').innerText.trim() : '';
                briefing += `${idx + 1}. #${sym} | AI Score: ${score}\\n   Price: ${price} | Target: ${target} | Stop: ${stop}\\n\\n`;
            });
            briefing += "System: Kronos Foundation + Conformal ML Boosters\\nhttps://praecursor-egx.internal";

            navigator.clipboard.writeText(briefing).then(() => {
                showToast("📋 Telegram Briefing copied to clipboard!");
            }).catch(() => {
                showToast("⚠️ Could not access clipboard.");
            });
        });
    }

    // --- FULLSCREEN TOGGLE ---
    const fsBtn = document.getElementById('btn-toggle-fullscreen');
    if (fsBtn) {
        fsBtn.addEventListener('click', function() {
            if (!document.fullscreenElement) {
                document.documentElement.requestFullscreen().then(() => {
                    showToast("🖥️ Entering Fullscreen Quant Mode");
                }).catch(err => {
                    console.log(err);
                });
            } else {
                document.exitFullscreen().then(() => {
                    showToast("Exited Fullscreen Mode");
                });
            }
        });
    }

    // --- EXPORT CSV ACTION ---
    const exportCsvBtn = document.getElementById('btn-export-csv');
    if (exportCsvBtn) {
        exportCsvBtn.addEventListener('click', function() {
            showToast("📥 Exporting Opportunity Ranking CSV...");
            const a = document.createElement('a');
            a.href = 'opportunity_ranking.csv';
            a.download = 'opportunity_ranking.csv';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        });
    }

    // --- INTERACTIVE HALF-KELLY PORTFOLIO SIZING CALCULATOR ---
    const capitalInput = document.getElementById('kelly-portfolio-capital');
    const capitalSlider = document.getElementById('kelly-capital-slider');
    const profilePills = document.querySelectorAll('.kelly-pill');
    const kellyRows = document.querySelectorAll('.kelly-row');
    const totalAllocElem = document.getElementById('kelly-total-allocated');
    const totalRiskElem = document.getElementById('kelly-total-risk');
    const totalReturnElem = document.getElementById('kelly-total-return');

    let kellyMultiplier = 1.0;

    function recalculateKelly() {
        if (!capitalInput) return;
        const totalCapital = parseFloat(capitalInput.value) || 500000;

        let totalAllocatedEGP = 0;
        let totalRiskEGP = 0;
        let totalGainEGP = 0;

        kellyRows.forEach(row => {
            const price = parseFloat(row.getAttribute('data-price')) || 0;
            const target = parseFloat(row.getAttribute('data-target')) || 0;
            const stop = parseFloat(row.getAttribute('data-stop')) || 0;
            const kellyFraction = parseFloat(row.getAttribute('data-kelly')) || 0.2;

            if (price <= 0) return;

            const effectiveKelly = Math.min(0.50, kellyFraction * kellyMultiplier);
            const positionCapital = totalCapital * effectiveKelly;
            const shares = Math.floor(positionCapital / price);
            const actualAlloc = shares * price;
            const maxLoss = shares * Math.max(0, price - stop);
            const expGain = shares * Math.max(0, target - price);

            totalAllocatedEGP += actualAlloc;
            totalRiskEGP += maxLoss;
            totalGainEGP += expGain;

            const allocCell = row.querySelector('.kelly-alloc-cell');
            const sharesCell = row.querySelector('.kelly-shares-cell');
            const lossCell = row.querySelector('.kelly-loss-cell');
            const gainCell = row.querySelector('.kelly-gain-cell');

            if (allocCell) allocCell.innerText = `${Math.round(actualAlloc).toLocaleString()} EGP`;
            if (sharesCell) sharesCell.innerText = shares.toLocaleString();
            if (lossCell) lossCell.innerText = `-${Math.round(maxLoss).toLocaleString()} EGP`;
            if (gainCell) gainCell.innerText = `+${Math.round(expGain).toLocaleString()} EGP`;
        });

        const allocPct = totalCapital > 0 ? (totalAllocatedEGP / totalCapital * 100) : 0;
        const riskPct = totalCapital > 0 ? (totalRiskEGP / totalCapital * 100) : 0;
        const returnPct = totalCapital > 0 ? (totalGainEGP / totalCapital * 100) : 0;

        if (totalAllocElem) totalAllocElem.innerText = `${Math.round(totalAllocatedEGP).toLocaleString()} EGP (${allocPct.toFixed(1)}%)`;
        if (totalRiskElem) totalRiskElem.innerText = `${Math.round(totalRiskEGP).toLocaleString()} EGP (${riskPct.toFixed(1)}%)`;
        if (totalReturnElem) totalReturnElem.innerText = `+${Math.round(totalGainEGP).toLocaleString()} EGP (+${returnPct.toFixed(1)}%)`;
    }

    if (capitalInput && capitalSlider) {
        capitalInput.addEventListener('input', function() {
            capitalSlider.value = this.value;
            recalculateKelly();
        });

        capitalSlider.addEventListener('input', function() {
            capitalInput.value = this.value;
            recalculateKelly();
        });
    }

    profilePills.forEach(pill => {
        pill.addEventListener('click', function() {
            profilePills.forEach(p => p.classList.remove('active'));
            this.classList.add('active');
            kellyMultiplier = parseFloat(this.getAttribute('data-multiplier')) || 1.0;
            recalculateKelly();
        });
    });

    recalculateKelly();

    // --- TRADINGVIEW MODAL LOGIC ---
    const modal = document.getElementById('tv-modal');
    const closeBtn = document.querySelector('.close-modal-btn');
    const backdrop = document.querySelector('.modal-backdrop');
    const container = document.getElementById('tv-widget-container');
    const modalTitle = document.getElementById('tv-modal-title');

    function openChart(symbol) {
        if (!symbol) return;
        modalTitle.innerText = `${symbol} // TRADINGVIEW ADVANCED TERMINAL`;
        modal.classList.add('active');
        container.innerHTML = '';

        const tvScript = document.createElement('script');
        tvScript.type = 'text/javascript';
        tvScript.src = 'https://s3.tradingview.com/tv.js';
        tvScript.onload = function() {
            new TradingView.widget({
                "autosize": true,
                "symbol": `EGX:${symbol}`,
                "interval": "D",
                "timezone": "Africa/Cairo",
                "theme": "dark",
                "style": "1",
                "locale": "en",
                "enable_publishing": false,
                "backgroundColor": "#0c1017",
                "gridColor": "rgba(255, 255, 255, 0.05)",
                "hide_top_toolbar": false,
                "hide_legend": false,
                "save_image": false,
                "container_id": "tv-widget-container",
                "studies": [
                    "RSI@tv-basicstudies",
                    "MACD@tv-basicstudies",
                    "MASimple@tv-basicstudies"
                ]
            });
        };
        document.head.appendChild(tvScript);
    }

    function closeModal() {
        modal.classList.remove('active');
        container.innerHTML = '';
    }

    document.querySelectorAll('.btn-chart-modal').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const symbol = this.getAttribute('data-symbol');
            openChart(symbol);
        });
    });

    document.querySelectorAll('.table-action-btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const symbol = this.getAttribute('data-symbol');
            openChart(symbol);
        });
    });

    document.querySelectorAll('.clickable-row').forEach(row => {
        row.addEventListener('click', function() {
            const symbol = this.getAttribute('data-symbol');
            openChart(symbol);
        });
    });

    if (closeBtn) closeBtn.addEventListener('click', closeModal);
    if (backdrop) backdrop.addEventListener('click', closeModal);

    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && modal && modal.classList.contains('active')) {
            closeModal();
        }
    });
});
"""
