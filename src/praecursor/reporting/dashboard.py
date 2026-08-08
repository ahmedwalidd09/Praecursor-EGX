from html import escape
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
import json
from praecursor.analysis.accuracy_tracker import AccuracyTracker

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DASHBOARD_REPORT = ROOT / "reports" / "dashboard.html"


class ScannerDashboardWriter:
    """Write a static dark HTML dashboard for scanner results."""

    def write(self, result: Any, output_path: Path = DEFAULT_DASHBOARD_REPORT) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self._html(result), encoding="utf-8")
        return output_path

    def _html(self, result: Any) -> str:
        import os
        from datetime import datetime
        try:
            tracker = AccuracyTracker(result.database_path)
            stats = tracker.get_accuracy_stats()
        except Exception as e:
            stats = {"next_day": {"accuracy": 0}, "swing": {"accuracy": 0}, "history": []}
            
        model_path = ROOT / "models" / "xgboost_next_day.json"
        try:
            mtime = os.path.getmtime(model_path)
            model_time_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
        except Exception:
            model_time_str = "Unknown"

        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Praecursor-EGX | Institutional Dashboard</title>
  <style>{self._css()}</style>
</head>
<body>
  <header class="topbar">
    <div>
      <div class="eyebrow">PRAECURSOR-EGX</div>
      <h1>Opportunity Pulse</h1>
    </div>
    <div class="meta">
      <span>Generated {escape(result.generated_at.astimezone(ZoneInfo('Africa/Cairo')).isoformat()[:16].replace('T', ' '))} (Cairo Time)</span>
      <span>{len(result.symbol_results)} Symbols Scanned</span>
      <span>Primary: {escape(result.source_name)}</span>
      <span>Model Updated: {escape(model_time_str)}</span>
    </div>
  </header>
  
  <nav class="tabs">
    <button class="tab-btn active" onclick="switchTab('live-pulse')">Live Pulse</button>
    <button class="tab-btn" onclick="switchTab('history-view')">Accuracy Tracker</button>
  </nav>

  <main>
    <div id="live-pulse" class="tab-content">
      {self._market_cards(result)}

    
    <div class="grid layout">
      <div class="main-content">
          <section class="grid two">
            {self._candidate_panel('Next-Day Candidates', result.next_day_results, 'next')}
          </section>
          
          <section class="panel">
            <div class="panel-title">Score Component Heatmap (Top 10)</div>
            <div class="table-container">
                {self._heatmap_table(result.next_day_results[:10])}
            </div>
          </section>
          
          <section class="panel">
            <div class="panel-title">Overall Opportunity Ranking</div>
            <div class="table-container">
                {self._ranking_table(result.symbol_results)}
            </div>
          </section>
      </div>
      </div>
    </div> <!-- end live-pulse tab -->

    <div id="history-view" class="tab-content" style="display:none;">
      <div class="accuracy-hero">
        <div class="accuracy-card">
          <div class="accuracy-label">30D Accuracy</div>
          <div class="accuracy-value">{stats.get('rolling', dict()).get('30d_accuracy', 0):.1f}%</div>
          <div class="progress-bar-bg">
            <div class="progress-bar-fill" style="width: {stats.get('rolling', dict()).get('30d_accuracy', 0)}%"></div>
          </div>
          <div class="accuracy-hint">7D: {stats.get('rolling', dict()).get('7d_accuracy', 0):.1f}% | All-Time: {stats.get('next_day', dict()).get('accuracy', 0):.1f}%</div>
        </div>
        
        <div class="accuracy-card">
          <div class="accuracy-label">Current Streak</div>
          <div class="accuracy-value streak-value">{stats.get('streak', '0')}</div>
          <div class="accuracy-hint">Consecutive trades without a break</div>
        </div>
        
        <div class="accuracy-card">
          <div class="accuracy-label">Expected Value</div>
          <div class="accuracy-value ev-value">{stats.get('ev', 0.0):+.2f}%</div>
          <div class="accuracy-hint">Average expected return per signal</div>
        </div>
      </div>
      
      <section class="panel">
        <div class="panel-title">Historical Accuracy Trend</div>
        <div style="height: 250px; width: 100%;">
            <canvas id="accuracyChart"></canvas>
        </div>
      </section>
      
      <section class="panel">
        <div class="panel-title">Historical Signal Log</div>
        <div class="table-container">
           <table class="data-table">
            <thead>
              <tr><th>Date</th><th>Symbol</th><th>Signal</th><th>Return</th><th>Verdict</th></tr>
            </thead>
            <tbody>
              {''.join(
                f"<tr><td>{escape(str(r.get('signal_date', ''))[:10])}</td><td><strong>{escape(str(r.get('symbol', '')))}</strong></td>"
                f"<td>{escape(str(r.get('next_day_label', '')))}</td>"
                f"<td style='color: {'#22c55e' if (r.get('next_day_return') or 0) >= 0 else '#ef4444'}'>{(r.get('next_day_return') or 0):+.1f}%</td>"
                f"<td>{self._hit_badge(r.get('next_day_hit'))}</td></tr>"
                for r in stats.get('history', [])
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div> <!-- end history-view tab -->
  </main>

  <div id="tv-modal" class="modal">
    <div class="modal-content">
        <div class="modal-header">
            <span id="tv-modal-title" class="modal-title">Chart</span>
            <span class="close-modal">&times;</span>
        </div>
        <div id="tv-widget-container" style="height: 500px; width: 100%;"></div>
    </div>
  </div>
  
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script>
      const histData = {json.dumps(stats.get('history', []))};
      
      function switchTab(tabId) {{
          document.querySelectorAll('.tab-content').forEach(t => t.style.display = 'none');
          document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
          document.getElementById(tabId).style.display = 'block';
          if (tabId === 'live-pulse') {{
              document.querySelectorAll('.tab-btn')[0].classList.add('active');
          }} else {{
              document.querySelectorAll('.tab-btn')[1].classList.add('active');
          }}
      }}
      
      {self._js()}
  </script>
</body>
</html>"""

    def _hit_badge(self, hit: int | None) -> str:
        if hit is None:
            return "<span class='badge neutral'>PENDING</span>"
        if hit == 1:
            return "<span class='badge good'>HIT</span>"
        return "<span class='badge bad'>MISS</span>"

    def _market_cards(self, result: Any) -> str:
        strong = sum(1 for item in result.symbol_results if item.next_day_score >= 65)
        accepted = sum(1 for item in result.symbol_results if item.consensus_result and item.consensus_result.accepted)
        avg_quality = 0.0
        if result.symbol_results:
            avg_quality = sum(item.data_quality_score for item in result.symbol_results) / len(result.symbol_results)

        cards = [
            ("Next-Day Watch", str(strong), "Follow-through edge"),
            ("Consensus OK", f"{accepted}/{len(result.symbol_results)}", "Verified close"),
            ("Data Quality", f"{avg_quality:.0f}%", "Signal fidelity"),
        ]
        return "<section class='cards'>" + "".join(
            f"<div class='card'><div class='label'>{escape(label)}</div><div class='value'>{escape(value)}</div><div class='hint'>{escape(hint)}</div></div>"
            for label, value, hint in cards
        ) + "</section>"

    def _candidate_panel(self, title: str, results: list[Any], mode: str) -> str:
        cards = []
        for rank, item in enumerate(results[:8], start=1):
            prediction = item.next_day_prediction
            score = item.next_day_score
            label = item.next_day_label
            reasons = item.next_day_reasons_text or ""

            latest_close = float(prediction.latest_close)
            target_price = float(prediction.target_price)
            stop_loss = float(prediction.stop_loss_price)

            # Calculate percentage gain to target and risk to stop
            target_pct = ((target_price - latest_close) / latest_close * 100) if latest_close > 0 and target_price > 0 else 0
            stop_pct = ((latest_close - stop_loss) / latest_close * 100) if latest_close > 0 and stop_loss > 0 else 0

            # AI probability display
            ai_prob = f"{float(score):.1f}%"

            badge_cls = self._badge_class(label)
            cards.append(f"""
            <div class='candidate-card'>
                <div class='cand-header'>
                    <div class='cand-rank'>#{rank}</div>
                    <div class='cand-info'>
                        <div class='cand-symbol'>{escape(item.symbol)}</div>
                        <div class='cand-company'>{escape(item.opportunity_score.company)}</div>
                    </div>
                    <div class='cand-badge-wrap'>
                        <span class='badge {badge_cls}'>{escape(label)}</span>
                    </div>
                </div>
                <div class='cand-metrics'>
                    <div class='cand-metric'>
                        <div class='cand-metric-label'>AI Score</div>
                        <div class='cand-metric-value neon-green'>{ai_prob}</div>
                    </div>
                    <div class='cand-metric'>
                        <div class='cand-metric-label'>Close</div>
                        <div class='cand-metric-value'>{latest_close:.2f}</div>
                    </div>
                    <div class='cand-metric'>
                        <div class='cand-metric-label'>Target</div>
                        <div class='cand-metric-value neon-green'>{target_price:.2f} <span class='pct-tag up'>+{target_pct:.1f}%</span></div>
                    </div>
                    <div class='cand-metric'>
                        <div class='cand-metric-label'>Stop Loss</div>
                        <div class='cand-metric-value neon-red'>{stop_loss:.2f} <span class='pct-tag down'>-{stop_pct:.1f}%</span></div>
                    </div>
                </div>
                <div class='cand-reasons'>
                    <span class='reasons-icon'>&#x1F916;</span>
                    <span class='reasons-text'>
                        {f"The AI model identified this as a candidate because {escape(reasons).replace(', ', ', and ')}." if reasons and "no strong" not in reasons.lower() else "The AI model did not identify strong positive technical catalysts for this symbol today."}
                    </span>
                </div>
            </div>
            """)

        return (
            "<section class='panel candidate-section'>"
            f"<div class='panel-title'>{escape(title)}</div>"
            f"<div class='candidate-grid'>{''.join(cards)}</div>"
            "</section>"
        )

    def _ranking_table(self, results: list[Any]) -> str:
        rows = []
        for rank, item in enumerate(results, start=1):
            consensus = item.consensus_result
            consensus_text = "N/A"
            if consensus:
                consensus_text = f"{consensus.agreeing_source_count}/{consensus.source_count}"
                
            rows.append(
                f"<tr class='clickable-row' data-symbol='{escape(item.symbol)}'>"
                f"<td class='rank'>{rank}</td>"
                f"<td><strong>{escape(item.symbol)}</strong><div class='sub'>{escape(item.opportunity_score.company)}</div></td>"
                f"<td class='score-cell imp'>{item.opportunity_score.score_percent:.0f}</td>"
                f"<td class='score-cell'>{item.final_predictor_score:.0f}</td>"
                f"<td class='score-cell'>{item.next_day_score:.0f}</td>"
                f"<td><span class='badge {self._badge_class(item.next_day_label)}'>{escape(item.next_day_label)}</span></td>"
                f"<td>{escape(consensus_text)}</td>"
                f"</tr>"
            )
        return (
            "<table class='data-table full-table'><thead><tr><th></th><th>Symbol</th><th>Opp</th><th>Final</th><th>Next</th><th>Next Label</th><th>Cons</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )

    def _heatmap_table(self, results: list[Any]) -> str:
        if not results: return ""
        
        # Get all unique component names from the first result
        comp_names = [c.name for c in results[0].opportunity_score.components]
        
        headers = "".join(f"<th>{escape(name)}</th>" for name in comp_names)
        
        rows = []
        for rank, item in enumerate(results, start=1):
            cells = []
            for c in item.opportunity_score.components:
                # Intensity of green based on score vs max_score
                pct = c.score / c.max_score if c.max_score > 0 else 0
                alpha = max(0.05, pct * 0.8) # Min opacity
                color = f"rgba(30, 136, 229, {alpha})" if pct > 0 else "rgba(255, 255, 255, 0.02)"
                val = f"{c.score:.1f}" if c.score % 1 != 0 else f"{c.score:.0f}"
                max_val = f"{c.max_score:.1f}" if c.max_score % 1 != 0 else f"{c.max_score:.0f}"
                cells.append(f"<td style='background: {color}; text-align: center; border: 1px solid rgba(255,255,255,0.05);' title='{escape(c.reason)}'>{val}<span style='color: var(--muted); font-size: 9px;'>/{max_val}</span></td>")
                
            rows.append(
                f"<tr>"
                f"<td class='rank'>#{rank}</td>"
                f"<td><strong>{escape(item.symbol)}</strong></td>"
                f"{''.join(cells)}"
                f"</tr>"
            )
            
        return (
            f"<table class='data-table heatmap-table'><thead><tr><th></th><th>Symbol</th>{headers}</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )


    def _badge_class(self, label: str) -> str:
        lowered = label.lower()
        if "explosion" in lowered or "strong" in lowered or "continuation" in lowered or "confirmed" in lowered or "candidate" in lowered:
            return "good"
        if "watch" in lowered or "reversal" in lowered:
            return "watch"
        if "avoid" in lowered or "low" in lowered:
            return "bad"
        return "neutral"

    def _css(self) -> str:
        return """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root { 
    color-scheme: dark; 
    --bg: #000000; 
    --panel: #080c14; 
    --panel-alt: #0c1220; 
    --line: #1a2038; 
    --text: #c8d0e0; 
    --muted: #5a6580; 
    
    --accent: #1e88e5;
    --accent-glow: rgba(30, 136, 229, 0.25);
    --neon-blue: #42a5f5;
    --neon-red: #ef4444;
    --neon-green: #22c55e;
    --deep-red: #dc2626;
    
    --font-ui: "Inter", -apple-system, sans-serif;
    --font-mono: "JetBrains Mono", "Consolas", "Courier New", monospace;
}

* { box-sizing: border-box; }

body { 
    margin: 0; 
    background: var(--bg); 
    color: var(--text); 
    font-family: var(--font-ui); 
    -webkit-font-smoothing: antialiased;
    line-height: 1.5;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: #1a2038; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #2a3558; }

.topbar { 
    display: flex; 
    justify-content: space-between; 
    align-items: center; 
    padding: 16px 32px; 
    border-bottom: 1px solid var(--line); 
    background: linear-gradient(180deg, rgba(8,12,20,0.98) 0%, rgba(0,0,0,0.95) 100%); 
    backdrop-filter: blur(12px);
    position: sticky; 
    top: 0; 
    z-index: 10;
}

h1 { margin: 0; font-size: 22px; font-weight: 700; letter-spacing: -0.02em; color: #fff; }
.eyebrow { color: var(--accent); font-size: 10px; font-weight: 800; letter-spacing: 0.3em; margin-bottom: 2px; text-transform: uppercase; }

.meta { display: flex; gap: 10px; font-size: 11px; font-family: var(--font-mono); }
.meta span { color: var(--neon-blue); padding: 3px 8px; background: rgba(30, 136, 229, 0.08); border: 1px solid rgba(30, 136, 229, 0.18); border-radius: 4px; font-size: 10px; }

main { padding: 20px 28px; max-width: 1440px; margin: 0 auto; }

/* Grid — full width, no dead sidebar */
.grid.layout { display: block; }

.cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 20px; }
.card { 
    background: var(--panel); 
    border: 1px solid var(--line); 
    border-radius: 10px; 
    padding: 18px 20px; 
    transition: border-color 0.2s, box-shadow 0.2s; 
}
.card:hover { border-color: var(--accent); box-shadow: 0 0 20px var(--accent-glow); }

.label { color: var(--muted); font-size: 10px; text-transform: uppercase; letter-spacing: 0.12em; font-weight: 700; }
.value { font-size: 28px; font-weight: 700; margin: 8px 0 4px; color: var(--neon-blue); font-family: var(--font-mono); }
.hint { color: var(--muted); font-size: 11px; }

.grid.two { display: block; margin-bottom: 20px; }

.panel { 
    background: var(--panel); 
    border: 1px solid var(--line); 
    border-radius: 10px; 
    padding: 20px; 
    margin-bottom: 20px;
}
.panel-title { 
    font-size: 13px; 
    font-weight: 700; 
    text-transform: uppercase; 
    letter-spacing: 0.12em; 
    margin: 0 0 14px; 
    color: #fff; 
    border-bottom: 1px solid var(--line); 
    padding-bottom: 10px; 
    display: flex;
    align-items: center;
    gap: 8px;
}
.panel-title::before { content: ''; display: inline-block; width: 3px; height: 14px; background: var(--accent); border-radius: 2px; }

.table-container { overflow-x: auto; }

.data-table { width: 100%; border-collapse: collapse; font-size: 12px; text-align: left; }
.data-table th { color: var(--muted); font-size: 9px; text-transform: uppercase; letter-spacing: 0.12em; padding: 10px 10px; border-bottom: 1px solid var(--line); font-weight: 700; }
.data-table td { padding: 10px 10px; border-bottom: 1px solid rgba(255,255,255,0.02); vertical-align: middle; }
.data-table tbody tr:hover td { background: rgba(30, 136, 229, 0.04); }

.clickable-row { cursor: pointer; transition: background 0.15s; }
.clickable-row:hover td { background: rgba(30, 136, 229, 0.08) !important; }

.rank { color: var(--muted); font-family: var(--font-mono); font-size: 10px; width: 28px; }
.sub { color: var(--muted); font-size: 10px; margin-top: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 160px; }

.score-cell { font-family: var(--font-mono); font-weight: 600; font-size: 12px; }
.score-cell.imp { color: var(--neon-blue); font-size: 13px; }

.badge { display: inline-block; border-radius: 4px; padding: 3px 7px; font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; }
.badge.good { background: rgba(30, 136, 229, 0.12); color: var(--neon-blue); border: 1px solid rgba(30, 136, 229, 0.25); }
.badge.watch { background: rgba(234, 179, 8, 0.1); color: #eab308; border: 1px solid rgba(234, 179, 8, 0.25); }
.badge.bad { background: rgba(239, 68, 68, 0.1); color: var(--neon-red); border: 1px solid rgba(239, 68, 68, 0.25); }
.badge.neutral { background: rgba(100, 116, 139, 0.12); color: #94a3b8; border: 1px solid rgba(100, 116, 139, 0.25); }

/* Accuracy Tracker */
.accuracy-hero { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }
.accuracy-card { 
    background: var(--panel-alt); 
    border: 1px solid var(--line); 
    border-radius: 10px; 
    padding: 28px; 
    text-align: center; 
}
.accuracy-value { font-size: 2.8rem; font-weight: 700; color: var(--neon-blue); margin: 12px 0; font-family: var(--font-mono); text-shadow: 0 0 24px var(--accent-glow); }
.streak-value { color: #eab308; text-shadow: 0 0 20px rgba(234, 179, 8, 0.3); }
.ev-value { color: var(--neon-green); text-shadow: 0 0 20px rgba(34, 197, 94, 0.3); }
.accuracy-label { font-size: 0.95rem; color: #fff; text-transform: uppercase; letter-spacing: 1.5px; font-weight: 700; }
.accuracy-hint { font-size: 0.8rem; color: var(--muted); margin-top: 6px; font-family: var(--font-mono); }
.progress-bar-bg { background: rgba(255, 255, 255, 0.06); border-radius: 6px; height: 6px; width: 100%; overflow: hidden; margin-top: 14px; }
.progress-bar-fill { background: linear-gradient(90deg, var(--accent), var(--neon-blue)); height: 100%; border-radius: 6px; transition: width 1s ease-in-out; box-shadow: 0 0 8px var(--accent-glow); }

.heatmap-table th { writing-mode: vertical-rl; transform: rotate(180deg); text-align: left; padding: 8px; font-size: 8px; white-space: nowrap; }
.heatmap-table td { padding: 3px; font-family: var(--font-mono); font-size: 10px; }

/* Modal */
.modal { display: none; position: fixed; z-index: 100; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.88); backdrop-filter: blur(6px); }
.modal-content { background-color: var(--panel); margin: 4% auto; border: 1px solid var(--accent); width: 90%; max-width: 1000px; border-radius: 10px; overflow: hidden; box-shadow: 0 0 60px var(--accent-glow); }
.modal-header { padding: 14px 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--line); background: #000; }
.modal-title { color: var(--neon-blue); font-weight: 700; font-size: 15px; letter-spacing: 0.05em; }
.close-modal { color: var(--muted); font-size: 22px; font-weight: bold; cursor: pointer; transition: color 0.2s; }
.close-modal:hover { color: var(--neon-red); }

/* Tabs */
.tabs { display: flex; gap: 0; padding: 0 28px; background: rgba(8, 12, 20, 0.95); border-bottom: 1px solid var(--line); }
.tab-btn { background: none; border: none; color: var(--muted); font-family: var(--font-ui); font-size: 13px; font-weight: 600; padding: 14px 16px; cursor: pointer; border-bottom: 2px solid transparent; transition: all 0.2s; }
.tab-btn:hover { color: #fff; }
.tab-btn.active { color: var(--neon-blue); border-bottom-color: var(--accent); }

/* Candidate Cards */
.candidate-section { overflow: visible; }
.candidate-grid { 
    display: grid; 
    grid-template-columns: repeat(2, 1fr); 
    gap: 14px; 
}
@media (max-width: 900px) { .candidate-grid { grid-template-columns: 1fr; } }

.candidate-card {
    background: var(--panel-alt);
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    transition: transform 0.2s, border-color 0.2s, box-shadow 0.2s;
}
.candidate-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 24px rgba(30, 136, 229, 0.08);
    border-color: rgba(30, 136, 229, 0.3);
}

.cand-header { display: flex; align-items: center; gap: 10px; }
.cand-rank { font-family: var(--font-mono); color: var(--muted); font-size: 11px; font-weight: 700; min-width: 26px; }
.cand-info { flex: 1; min-width: 0; }
.cand-symbol { font-weight: 700; font-size: 14px; color: #fff; letter-spacing: 0.02em; }
.cand-company { color: var(--muted); font-size: 10px; margin-top: 1px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cand-badge-wrap { flex-shrink: 0; }

.cand-metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; padding: 8px 0; border-top: 1px solid rgba(255,255,255,0.03); border-bottom: 1px solid rgba(255,255,255,0.03); }
.cand-metric { text-align: center; }
.cand-metric-label { font-size: 8px; text-transform: uppercase; color: var(--muted); letter-spacing: 0.1em; font-weight: 700; margin-bottom: 3px; }
.cand-metric-value { font-family: var(--font-mono); font-size: 12px; font-weight: 600; }

.neon-green { color: var(--neon-green); }
.neon-red { color: var(--neon-red); }
.neon-blue { color: var(--neon-blue); }

.pct-tag { font-size: 9px; font-weight: 700; padding: 1px 4px; border-radius: 3px; margin-left: 2px; }
.pct-tag.up { background: rgba(34, 197, 94, 0.1); color: var(--neon-green); }
.pct-tag.down { background: rgba(239, 68, 68, 0.1); color: var(--neon-red); }

.cand-reasons {
    font-size: 10px;
    color: var(--muted);
    line-height: 1.5;
    padding: 6px 10px;
    background: rgba(30, 136, 229, 0.03);
    border-radius: 4px;
    border-left: 2px solid var(--accent);
}
.reasons-icon { font-size: 12px; margin-right: 3px; }
        """

    def _js(self) -> str:
        return """
document.addEventListener("DOMContentLoaded", function() {
    
    // Accuracy Chart
    if (histData.length > 0) {
        // Group by signal_date
        const daily = {};
        histData.forEach(r => {
            const date = (r.signal_date || "").substring(0, 10);
            if (!daily[date]) daily[date] = { hits: 0, total: 0 };
            daily[date].total += 1;
            if (r.next_day_hit === 1) daily[date].hits += 1;
        });
        
        const sortedDates = Object.keys(daily).sort();
        const labels = [];
        const data = [];
        
        sortedDates.forEach(d => {
            labels.push(d);
            data.push((daily[d].hits / daily[d].total) * 100);
        });
        
        const ctx = document.getElementById('accuracyChart');
        if (ctx) {
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Daily Accuracy (%)',
                        data: data,
                        borderColor: '#1e88e5',
                        backgroundColor: 'rgba(30, 136, 229, 0.08)',
                        borderWidth: 2,
                        tension: 0.3,
                        fill: true,
                        pointBackgroundColor: '#42a5f5',
                        pointRadius: 3,
                        pointHoverBackgroundColor: '#ef4444',
                        pointHoverRadius: 5
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            min: 0,
                            max: 100,
                            grid: { color: '#1a2038' },
                            ticks: { color: '#5a6580', font: { size: 10 } }
                        },
                        x: {
                            grid: { color: '#1a2038' },
                            ticks: { color: '#5a6580', maxTicksLimit: 10, font: { size: 10 } }
                        }
                    },
                    plugins: {
                        legend: { display: false }
                    }
                }
            });
        }
    }
    
    // TradingView Modal Logic
    const modal = document.getElementById('tv-modal');
    const closeBtn = document.querySelector('.close-modal');
    const container = document.getElementById('tv-widget-container');
    const modalTitle = document.getElementById('tv-modal-title');
    
    const rows = document.querySelectorAll('.clickable-row');
    
    rows.forEach(row => {
        row.addEventListener('click', function() {
            const symbol = this.getAttribute('data-symbol');
            if (!symbol) return;
            
            modalTitle.innerText = `${symbol} - TradingView Advanced Chart`;
            modal.style.display = 'block';
            
            container.innerHTML = ''; // Clear previous
            
            // Inject TV script dynamically
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
                  "backgroundColor": "#0a0a0a",
                  "gridColor": "#222222",
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
        });
    });
    
    closeBtn.onclick = function() {
        modal.style.display = 'none';
        container.innerHTML = '';
    }
    
    window.onclick = function(event) {
        if (event.target == modal) {
            modal.style.display = 'none';
            container.innerHTML = '';
        }
    }
});
        """
