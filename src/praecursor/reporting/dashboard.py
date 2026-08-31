from html import escape
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DASHBOARD_REPORT = ROOT / "reports" / "dashboard.html"


class ScannerDashboardWriter:
    """Write an institutional-grade dark HTML dashboard for scanner results."""

    def write(self, result: Any, output_path: Path = DEFAULT_DASHBOARD_REPORT) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self._html(result), encoding="utf-8")
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
        next_day = generated_dt.date() + timedelta(days=1)
        while next_day.weekday() in (4, 5):  # Friday, Saturday (EGX weekend)
            next_day += timedelta(days=1)

        # Get Market Regime non-blocking
        regime_name = "Bear Volatile"
        try:
            from praecursor.scoring.regime import _REGIME_CACHE
            if _REGIME_CACHE and isinstance(_REGIME_CACHE, dict):
                regime_name = _REGIME_CACHE.get("regime", "Bear Volatile")
        except Exception:
            pass

        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
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
        <h1>Opportunity Pulse <span class="version-tag">v6.1 QUANT ALPHA</span></h1>
      </div>
    </div>

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
        <span class="pill-label">AI ENSEMBLE:</span>
        <span class="pill-val neon-cyan">XGB + LGBM (Stacked Geometric)</span>
      </div>
      <div class="status-pill">
        <span class="pill-label">LAST RAN AT:</span>
        <span class="pill-val highlight">{escape(generated_dt.strftime('%Y-%m-%d %I:%M %p Cairo'))}</span>
      </div>
    </div>
  </header>

  <main class="app-container">
    <!-- MARKET OVERVIEW METRIC CARDS -->
    {self._market_cards(result, regime_name)}

    <!-- CANDIDATES CONTROLS BAR -->
    <div class="controls-bar">
      <div class="section-heading">
        <div class="heading-glow-bar"></div>
        <h2>NEXT-DAY ALPHA CANDIDATES</h2>
        <span class="count-bubble" id="candidate-count-badge">0</span>
      </div>

      <div class="filter-search-group">
        <div class="search-wrap">
          <svg class="search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
          <input type="text" id="symbol-search" placeholder="Filter symbol or company..." autocomplete="off">
        </div>
        <div class="btn-group">
          <button class="filter-btn active" data-filter="all">ALL</button>
          <button class="filter-btn" data-filter="top">⭐ TOP PICKS</button>
          <button class="filter-btn" data-filter="breakout">BREAKOUTS</button>
          <button class="filter-btn" data-filter="watch">WATCHLIST</button>
          <button class="filter-btn" data-filter="verified">VERIFIED ONLY</button>
        </div>
      </div>
    </div>

    <!-- CANDIDATE CARDS GRID -->
    {self._candidate_panel('Next-Day Candidates', result.next_day_results, 'next')}

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
      <span>•</span>
      <span>HMM REGIME ENGINE + XGBOOST/LIGHTGBM ENSEMBLE + ATR VOLATILITY VA-R</span>
    </div>
  </footer>

  <script>{self._js()}</script>
</body>
</html>"""

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
                "icon": "⚡",
            },
            {
                "title": "MARKET REGIME",
                "value": regime_name.upper(),
                "badge": "Risk Mode",
                "badge_cls": "badge-purple",
                "sub": regime_desc,
                "icon": "🌐",
            },
            {
                "title": "PRICE CONSENSUS",
                "value": f"{accepted}/{total}",
                "badge": f"{consensus_pct:.0f}% Verified",
                "badge_cls": "badge-green" if consensus_pct >= 80 else "badge-amber",
                "sub": "Multi-source tick cross-validation",
                "icon": "🛡️",
            },
            {
                "title": "DATA INTEGRITY",
                "value": f"{avg_quality:.0f}%",
                "badge": "Institutional",
                "badge_cls": "badge-cyan",
                "sub": "Full-history indicator completeness",
                "icon": "📊",
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

    def _candidate_panel(self, title: str, results: list[Any], mode: str) -> str:
        candidate_items = [
            item for item in results
            if "Avoid" not in item.next_day_label
        ]
        display_items = candidate_items if candidate_items else results[:10]

        cards = []
        for rank, item in enumerate(display_items, start=1):
            pred = item.next_day_prediction
            score = float(item.next_day_score)
            label = item.next_day_label
            reasons = item.next_day_reasons_text or ""

            latest_close = float(pred.latest_close)
            target_price = float(pred.target_price)
            target_price_2 = float(getattr(pred, 'target_price_2', 0.0) or (target_price * 1.15))
            stop_loss = float(pred.stop_loss_price)

            target_pct = ((target_price - latest_close) / latest_close * 100) if latest_close > 0 and target_price > 0 else 0
            target_pct_2 = ((target_price_2 - latest_close) / latest_close * 100) if latest_close > 0 and target_price_2 > 0 else 0
            stop_pct = ((latest_close - stop_loss) / latest_close * 100) if latest_close > 0 and stop_loss > 0 else 0
            rr_ratio = (target_pct / stop_pct) if stop_pct > 0 else 0.0

            liquidity_tier = getattr(pred, 'liquidity_tier', 'MODERATE')
            fill_feasibility = getattr(pred, 'fill_feasibility', 'Standard Execution')
            liq_badge_cls = "tag-ok" if liquidity_tier == "HIGH" else ("tag-warn" if liquidity_tier == "MODERATE" else "tag-err")

            # Score color grade
            if score >= 80:
                score_cls = "score-ultra"
                score_gradient = "linear-gradient(135deg, #00F5A0 0%, #00D2FF 100%)"
            elif score >= 70:
                score_cls = "score-high"
                score_gradient = "linear-gradient(135deg, #00D2FF 0%, #7928CA 100%)"
            else:
                score_cls = "score-mid"
                score_gradient = "linear-gradient(135deg, #FFB800 0%, #FF8A00 100%)"

            # Parse Badge Label
            is_top_pick = "Top Pick" in label
            is_low_conf = "Low Confidence" in label or (item.consensus_result and not item.consensus_result.accepted)
            is_breakout = "Breakout" in label

            # Clean up badge text for presentation
            clean_badge = label
            if "⭐" in clean_badge:
                clean_badge = clean_badge.replace("⭐", "").strip()

            badge_style = "badge-card-gold" if is_top_pick else ("badge-card-red" if is_low_conf else "badge-card-cyan")

            # Check for warnings in reasons
            has_backtest_warn = "[BACKTEST REJECTION]" in reasons
            has_hmm_warn = "[HMM CAUTION]" in reasons
            has_ml_confirm = "ML confirms" in reasons

            # Card Data Attributes for Filtering
            data_tags = []
            if is_top_pick: data_tags.append("top")
            if is_breakout: data_tags.append("breakout")
            if not is_low_conf: data_tags.append("verified")
            if "Watch" in label: data_tags.append("watch")
            data_filter_str = " ".join(data_tags)

            cards.append(f"""
            <div class="candidate-card glass-card" data-symbol="{escape(item.symbol)}" data-company="{escape(item.opportunity_score.company.lower())}" data-tags="{data_filter_str}">
              <div class="card-glow-edge"></div>

              <!-- CARD HEADER -->
              <div class="card-header">
                <div class="symbol-block">
                  <span class="rank-pill">#{rank:02d}</span>
                  <div>
                    <div class="symbol-name">{escape(item.symbol)}</div>
                    <div class="company-name" title="{escape(item.opportunity_score.company)}">{escape(item.opportunity_score.company)}</div>
                  </div>
                </div>

                <div class="card-badges">
                  {f'<span class="badge-mini-gold">⭐ TOP PICK</span>' if is_top_pick else ''}
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
                    <span class="level-val mono-num">{latest_close:.2f} <small class="currency">EGP</small></span>
                  </div>
                  <div class="level-row">
                    <span class="level-label text-green">TARGET</span>
                    <span class="level-val text-green mono-num">{target_price:.2f} <span class="pct-chip up">+{target_pct:.1f}%</span></span>
                  </div>
                  <div class="level-row">
                    <span class="level-label text-red">STOP LOSS</span>
                    <span class="level-val text-red mono-num">{stop_loss:.2f} <span class="pct-chip down">-{stop_pct:.1f}%</span></span>
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
                    <span class="sizing-val text-purple mono-num">{pred.kelly_fraction * 100:.1f}%</span>
                  </div>
                </div>
              </div>

              <!-- RISK / REWARD VISUAL METER -->
              <div class="rr-meter-wrap">
                <div class="rr-bar">
                  <div class="rr-stop" style="width: {min(45, max(15, stop_pct * 8.0))}%;"></div>
                  <div class="rr-anchor"></div>
                  <div class="rr-target" style="width: {min(50, max(20, target_pct * 6.0))}%;"></div>
                </div>
                <div class="rr-labels">
                  <span class="rr-sub-label text-red">Stop: -{stop_pct:.1f}%</span>
                  <span class="rr-sub-label text-green">Target: +{target_pct:.1f}%</span>
                </div>
              </div>

              <!-- TAGS / CATALYSTS ROW -->
              <div class="tags-row">
                <span class="tag-pill {liq_badge_cls}" title="{escape(fill_feasibility)}">💧 {liquidity_tier} LIQUIDITY</span>
                {f'<span class="tag-pill tag-ml">⚡ ML HIGH CONVICTION</span>' if has_ml_confirm else ''}
                {f'<span class="tag-pill tag-warn">⚠️ POOR WIN-RATE TICKER</span>' if has_backtest_warn else ''}
                {f'<span class="tag-pill tag-warn">⚠️ HMM DISTRIBUTION</span>' if has_hmm_warn else ''}
                {f'<span class="tag-pill tag-err">⚠️ CONSENSUS UNVERIFIED</span>' if is_low_conf else '<span class="tag-pill tag-ok">✓ CONSENSUS VERIFIED</span>'}
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
                <button class="btn-chart-modal" data-symbol="{escape(item.symbol)}">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>
                  OPEN TRADINGVIEW PRO CHART
                </button>
              </div>
            </div>
            """)

        return f"<section class='candidate-grid' id='candidate-grid'>{''.join(cards)}</section>"

    def _ranking_table(self, results: list[Any]) -> str:
        rows = []
        for rank, item in enumerate(results, start=1):
            consensus = item.consensus_result
            consensus_text = "N/A"
            consensus_badge = "badge-neutral"
            if consensus:
                consensus_text = f"{consensus.agreeing_source_count}/{consensus.source_count}"
                consensus_badge = "badge-green" if consensus.accepted else "badge-red"

            pred = item.next_day_prediction
            score = item.next_day_score
            label = item.next_day_label
            clean_label = label.replace("⭐", "").strip()

            badge_cls = self._badge_class(label)

            rows.append(
                f"<tr class='clickable-row' data-symbol='{escape(item.symbol)}'>"
                f"<td class='rank-cell'>#{rank:02d}</td>"
                f"<td class='symbol-cell'>"
                f"  <span class='table-symbol'>{escape(item.symbol)}</span>"
                f"  <span class='table-company'>{escape(item.opportunity_score.company)}</span>"
                f"</td>"
                f"<td class='score-cell mono-num'>{item.opportunity_score.score_percent:.0f}%</td>"
                f"<td class='score-cell mono-num'>{item.final_predictor_score:.0f}%</td>"
                f"<td class='score-cell mono-num highlight-score'>{score:.1f}%</td>"
                f"<td><span class='table-badge {badge_cls}'>{escape(clean_label)}</span></td>"
                f"<td class='mono-num'>{item.opportunity_score.latest_close:.2f}</td>"
                f"<td><span class='mini-pill {consensus_badge}'>{escape(consensus_text)}</span></td>"
                f"<td><button class='table-action-btn' data-symbol='{escape(item.symbol)}'>Chart</button></td>"
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
        comp_names = [c.name for c in results[0].opportunity_score.components]
        headers = "".join(f"<th>{escape(name)}</th>" for name in comp_names)

        rows = []
        for rank, item in enumerate(results, start=1):
            cells = []
            for c in item.opportunity_score.components:
                pct = c.score / c.max_score if c.max_score > 0 else 0
                alpha = max(0.06, pct * 0.9)
                if pct >= 0.75:
                    color = f"rgba(0, 245, 160, {alpha})" # Neon Emerald
                    text_color = "#ffffff"
                elif pct >= 0.4:
                    color = f"rgba(0, 210, 255, {alpha})" # Neon Cyan
                    text_color = "#ffffff"
                else:
                    color = f"rgba(255, 255, 255, 0.03)"
                    text_color = "rgba(255, 255, 255, 0.4)"

                val = f"{c.score:.1f}" if c.score % 1 != 0 else f"{c.score:.0f}"
                max_val = f"{c.max_score:.1f}" if c.max_score % 1 != 0 else f"{c.max_score:.0f}"

                cells.append(
                    f"<td style='background: {color}; color: {text_color};' title='{escape(c.name)}: {val}/{max_val}&#10;{escape(c.reason)}'>"
                    f"<span class='hm-val'>{val}</span>"
                    f"<span class='hm-max'>/{max_val}</span>"
                    f"</td>"
                )

            rows.append(
                f"<tr class='clickable-row' data-symbol='{escape(item.symbol)}'>"
                f"<td class='rank-cell'>#{rank:02d}</td>"
                f"<td class='symbol-cell'><strong>{escape(item.symbol)}</strong></td>"
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

    def _format_reasons_html(self, reasons: str) -> str:
        if not reasons:
            return "<div class='reason-line text-cyan'>• Strong technical momentum and volume breakout profile.</div>"
        
        parts = [p.strip() for p in reasons.split(";") if p.strip()]
        if not parts:
            return f"<div class='reason-line'>• {escape(reasons)}</div>"
            
        lines = []
        for p in parts:
            cls = ""
            if "ML confirms" in p or "Bonus: +" in p or "Explosive setup" in p:
                cls = "text-green"
            elif "penalty" in p.lower() or "caution" in p.lower() or "rejection" in p.lower() or "not accepted" in p.lower() or "poor" in p.lower():
                cls = "text-red"
            elif "Regime" in p or "Base Opportunity" in p or "Analysis for" in p:
                cls = "text-cyan"
            lines.append(f"<div class='reason-line {cls}'>• {escape(p)}</div>")
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
  --bg-surface: #0d111a;
  --bg-surface-elevated: #131926;
  --bg-card: rgba(15, 22, 36, 0.75);
  --border-subtle: rgba(255, 255, 255, 0.08);
  --border-active: rgba(0, 210, 255, 0.35);
  --border-gold: rgba(255, 184, 0, 0.4);

  --text-main: #f0f4fc;
  --text-muted: #7e8b9f;
  --text-dim: #4d576a;

  --neon-emerald: #00f5a0;
  --neon-cyan: #00d2ff;
  --neon-purple: #9d4edd;
  --neon-gold: #ffb800;
  --neon-coral: #ff3366;

  --font-sans: 'Plus Jakarta Sans', -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background-color: var(--bg-core);
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
  width: 1200px;
  height: 600px;
  background: radial-gradient(circle, rgba(0, 210, 255, 0.07) 0%, rgba(157, 78, 221, 0.04) 50%, transparent 70%);
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
  padding: 16px 36px;
  background: rgba(7, 9, 14, 0.85);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--border-subtle);
}

.brand-group {
  display: flex;
  align-items: center;
  gap: 16px;
}

.logo-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(0, 210, 255, 0.08);
  border: 1px solid rgba(0, 210, 255, 0.25);
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
  font-size: 18px;
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
  color: var(--text-muted);
}

.status-pill-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.status-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  font-family: var(--font-mono);
  font-size: 11px;
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

.regime-bear-volatile { color: var(--neon-coral); text-shadow: 0 0 8px rgba(255, 51, 102, 0.4); }
.regime-bull-trend { color: var(--neon-emerald); text-shadow: 0 0 8px rgba(0, 245, 160, 0.4); }

/* CONTAINER */
.app-container {
  max-width: 1440px;
  margin: 0 auto;
  padding: 28px 36px;
  position: relative;
  z-index: 1;
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
  backdrop-filter: blur(12px);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  padding: 20px;
  position: relative;
  transition: all 0.25s ease;
}

.glass-card:hover {
  border-color: var(--border-active);
  box-shadow: 0 8px 32px rgba(0, 210, 255, 0.06);
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

.badge-gold { background: rgba(255, 184, 0, 0.12); color: var(--neon-gold); border: 1px solid rgba(255, 184, 0, 0.3); }
.badge-purple { background: rgba(157, 78, 221, 0.12); color: var(--neon-purple); border: 1px solid rgba(157, 78, 221, 0.3); }
.badge-green { background: rgba(0, 245, 160, 0.12); color: var(--neon-emerald); border: 1px solid rgba(0, 245, 160, 0.3); }
.badge-cyan { background: rgba(0, 210, 255, 0.12); color: var(--neon-cyan); border: 1px solid rgba(0, 210, 255, 0.3); }
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
  background: rgba(0, 210, 255, 0.12);
  color: var(--neon-cyan);
  border: 1px solid rgba(0, 210, 255, 0.3);
  padding: 1px 7px;
  border-radius: 10px;
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
  box-shadow: 0 0 12px rgba(0, 210, 255, 0.15);
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
  background: rgba(0, 210, 255, 0.15);
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
  border-color: rgba(0, 210, 255, 0.4);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.6), 0 0 24px rgba(0, 210, 255, 0.08);
}

.card-glow-edge {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, rgba(0, 210, 255, 0.6), transparent);
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
  background: rgba(0, 210, 255, 0.08);
  border: 1px solid rgba(0, 210, 255, 0.2);
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
  background: rgba(255, 184, 0, 0.15);
  border: 1px solid rgba(255, 184, 0, 0.35);
  padding: 2px 6px;
  border-radius: 4px;
  box-shadow: 0 0 8px rgba(255, 184, 0, 0.2);
}

.card-type-badge {
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 3px 8px;
  border-radius: 4px;
}

.badge-card-gold { background: rgba(255, 184, 0, 0.1); color: var(--neon-gold); border: 1px solid rgba(255, 184, 0, 0.25); }
.badge-card-cyan { background: rgba(0, 210, 255, 0.1); color: var(--neon-cyan); border: 1px solid rgba(0, 210, 255, 0.25); }
.badge-card-red { background: rgba(255, 51, 102, 0.1); color: var(--neon-coral); border: 1px solid rgba(255, 51, 102, 0.25); }

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

.score-ultra { color: var(--neon-emerald); text-shadow: 0 0 14px rgba(0, 245, 160, 0.4); }
.score-high { color: var(--neon-cyan); text-shadow: 0 0 14px rgba(0, 210, 255, 0.4); }
.score-mid { color: var(--neon-gold); text-shadow: 0 0 14px rgba(255, 184, 0, 0.4); }

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

.pct-chip.up { background: rgba(0, 245, 160, 0.15); color: var(--neon-emerald); }
.pct-chip.up-cyan { background: rgba(0, 210, 255, 0.15); color: var(--neon-cyan); }
.pct-chip.down { background: rgba(255, 51, 102, 0.15); color: var(--neon-coral); }

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
.mono-num { font-family: var(--font-mono); }

/* RISK REWARD VISUAL BAR */
.rr-meter-wrap {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.rr-bar {
  height: 6px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 3px;
  display: flex;
  align-items: center;
  position: relative;
  overflow: hidden;
}

.rr-stop {
  height: 100%;
  background: linear-gradient(90deg, var(--neon-coral), rgba(255, 51, 102, 0.3));
}

.rr-anchor {
  width: 2px;
  height: 100%;
  background: #ffffff;
  z-index: 2;
}

.rr-target {
  height: 100%;
  background: linear-gradient(90deg, rgba(0, 245, 160, 0.3), var(--neon-emerald));
}

.rr-target-runner {
  height: 100%;
  background: linear-gradient(90deg, rgba(0, 210, 255, 0.4), var(--neon-cyan));
}

.rr-labels {
  display: flex;
  justify-content: space-between;
  font-size: 9px;
  font-family: var(--font-mono);
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

.tag-ml { background: rgba(0, 245, 160, 0.08); color: var(--neon-emerald); border: 1px solid rgba(0, 245, 160, 0.25); }
.tag-warn { background: rgba(255, 184, 0, 0.08); color: var(--neon-gold); border: 1px solid rgba(255, 184, 0, 0.25); }
.tag-err { background: rgba(255, 51, 102, 0.08); color: var(--neon-coral); border: 1px solid rgba(255, 51, 102, 0.25); }
.tag-ok { background: rgba(0, 210, 255, 0.08); color: var(--neon-cyan); border: 1px solid rgba(0, 210, 255, 0.25); }

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
  background: rgba(0, 210, 255, 0.06);
  border: 1px solid rgba(0, 210, 255, 0.2);
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
  background: rgba(0, 210, 255, 0.16);
  border-color: var(--neon-cyan);
  box-shadow: 0 0 16px rgba(0, 210, 255, 0.2);
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
  background: rgba(0, 210, 255, 0.04) !important;
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

.badge-good { background: rgba(0, 245, 160, 0.1); color: var(--neon-emerald); border: 1px solid rgba(0, 245, 160, 0.25); }
.badge-watch { background: rgba(255, 184, 0, 0.1); color: var(--neon-gold); border: 1px solid rgba(255, 184, 0, 0.25); }
.badge-bad { background: rgba(255, 51, 102, 0.1); color: var(--neon-coral); border: 1px solid rgba(255, 51, 102, 0.25); }
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
  border: 1px solid rgba(0, 210, 255, 0.35);
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 20px 80px rgba(0, 0, 0, 0.8), 0 0 40px rgba(0, 210, 255, 0.15);
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
  padding: 24px 36px;
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

@media (max-width: 1024px) {
  .metrics-grid { grid-template-columns: repeat(2, 1fr); }
  .candidate-grid { grid-template-columns: 1fr; }
  .topbar { padding: 14px 20px; }
  .app-container { padding: 20px; }
  .hide-mobile { display: none; }
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

    if (searchInput) {
        searchInput.addEventListener('input', function(e) {
            searchQuery = e.target.value.toLowerCase().trim();
            updateGrid();
        });
    }

    filterBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            filterBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            currentFilter = this.getAttribute('data-filter');
            updateGrid();
        });
    });

    updateGrid();

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
                "backgroundColor": "#0d111a",
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

    // Trigger on card button click
    document.querySelectorAll('.btn-chart-modal').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const symbol = this.getAttribute('data-symbol');
            openChart(symbol);
        });
    });

    // Trigger on table row or action button click
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
        if (e.key === 'Escape' && modal.classList.contains('active')) {
            closeModal();
        }
    });
});
"""
