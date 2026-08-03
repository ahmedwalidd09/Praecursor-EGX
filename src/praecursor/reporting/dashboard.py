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
        # Extract swing candidates for the simulator
        sim_data = []
        for item in result.swing_results[:20]:
            if item.swing_prediction.position_size > 0:
                sim_data.append({
                    "symbol": item.symbol,
                    "company": item.opportunity_score.company,
                    "score": float(item.swing_score),
                    "weight": float(item.swing_prediction.position_size),
                    "maxRisk": float(item.swing_prediction.max_risk),
                    "entry": float(item.swing_prediction.latest_close),
                    "stop": float(item.swing_prediction.stop_loss_price)
                })

        try:
            tracker = AccuracyTracker(result.database_path)
            stats = tracker.get_accuracy_stats()
        except Exception as e:
            stats = {"next_day": {"accuracy": 0}, "swing": {"accuracy": 0}, "history": []}

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
            {self._candidate_panel('Swing Candidates', result.swing_results, 'swing')}
          </section>
          
          <section class="panel">
            <div class="panel-title">Overall Opportunity Ranking</div>
            <div class="table-container">
                {self._ranking_table(result.symbol_results)}
            </div>
          </section>
      </div>
      <div class="sidebar">
          {self._capital_scenario_simulator()}
      </div>
    </div>
    </div> <!-- end live-pulse tab -->

    <div id="history-view" class="tab-content" style="display:none;">
      <div class="accuracy-hero">
        <div class="accuracy-card">
          <div class="accuracy-label">Next-Day Accuracy (30D)</div>
          <div class="accuracy-value">{stats['next_day']['accuracy']:.1f}%</div>
          <div class="progress-bar-bg">
            <div class="progress-bar-fill" style="width: {stats['next_day']['accuracy']}%"></div>
          </div>
          <div class="accuracy-hint">{stats['next_day']['hits']} Hits out of {stats['next_day']['total']} Signals</div>
        </div>
      </div>
      
      <section class="panel">
        <div class="panel-title">Historical Signal Log</div>
        <div class="table-container">
           <table class="data-table">
            <thead>
              <tr><th>Date</th><th>Symbol</th><th>Signal</th><th>Return</th><th>Verdict</th></tr>
            </thead>
            <tbody>
              {''.join(
                f"<tr><td>{r['signal_date'][:10]}</td><td><strong>{r['symbol']}</strong></td>"
                f"<td>{r['next_day_label']}</td>"
                f"<td style='color: {'#00ff88' if (r.get('next_day_return') or 0) >= 0 else '#ff4444'}'>{(r.get('next_day_return') or 0):+.1f}%</td>"
                f"<td>{self._hit_badge(r['next_day_hit'])}</td></tr>"
                for r in stats['history']
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
  
  <script>
      const simData = {json.dumps(sim_data)};
      
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
        swing = sum(1 for item in result.symbol_results if item.swing_score >= 60)
        accepted = sum(1 for item in result.symbol_results if item.consensus_result and item.consensus_result.accepted)
        avg_quality = 0.0
        if result.symbol_results:
            avg_quality = sum(item.data_quality_score for item in result.symbol_results) / len(result.symbol_results)

        cards = [
            ("Next-Day Watch", str(strong), "Follow-through edge"),
            ("Swing Watch", str(swing), "Multi-session edge"),
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
            if mode == "next":
                prediction = item.next_day_prediction
                score = item.next_day_score
                label = item.next_day_label
                reasons = item.next_day_reasons_text
            else:
                prediction = item.swing_prediction
                score = item.swing_score
                label = item.swing_label
                reasons = item.swing_reasons_text

            latest_close = float(prediction.latest_close)
            target_price = float(prediction.target_price)
            stop_loss = float(prediction.stop_loss_price)

            # Calculate percentage gain to target and risk to stop
            target_pct = ((target_price - latest_close) / latest_close * 100) if latest_close > 0 and target_price > 0 else 0
            stop_pct = ((latest_close - stop_loss) / latest_close * 100) if latest_close > 0 and stop_loss > 0 else 0

            # AI probability display
            ai_prob = f"{float(score):.1f}%"

            # Extra swing info
            alloc_html = ""
            if mode == "swing" and hasattr(item, "swing_prediction") and item.swing_prediction.position_size > 0:
                pos = float(item.swing_prediction.position_size)
                risk = float(item.swing_prediction.max_risk)
                dyn_tag = " <span class='ml-stop'>[ML]</span>" if item.swing_prediction.dynamic_stop else ""
                alloc_html = f"""<div class='cand-row alloc-row'>
                    <span>Kelly Alloc: <b class='neon-blue'>{pos:.1f}%</b></span>
                    <span>Max Risk: <b class='imp-amber'>{risk:.1f}%</b>{dyn_tag}</span>
                </div>"""

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
                {alloc_html}
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
                
            dyn_stop = ""
            if hasattr(item, "swing_prediction") and item.swing_prediction.dynamic_stop:
                dyn_stop = "<span class='ml-stop' title='ML Predicted MAE Stop'>[ML]</span>"
                
            rows.append(
                f"<tr class='clickable-row' data-symbol='{escape(item.symbol)}'>"
                f"<td class='rank'>#{rank}</td>"
                f"<td><strong>{escape(item.symbol)}</strong><div class='sub'>{escape(item.opportunity_score.company)}</div></td>"
                f"<td class='score-cell imp'>{item.opportunity_score.score_percent:.0f}</td>"
                f"<td class='score-cell'>{item.final_predictor_score:.0f}</td>"
                f"<td class='score-cell'>{item.next_day_score:.0f}</td>"
                f"<td class='score-cell'>{item.swing_score:.0f}</td>"
                f"<td><span class='badge {self._badge_class(item.next_day_label)}'>{escape(item.next_day_label)}</span></td>"
                f"<td><span class='badge {self._badge_class(item.swing_label)}'>{escape(item.swing_label)}</span></td>"
                f"<td>{item.swing_prediction.stop_loss_price:.2f} {dyn_stop}</td>"
                f"<td>{item.swing_prediction.position_size:.1f}%</td>"
                f"<td>{escape(consensus_text)}</td>"
                f"</tr>"
            )
        return (
            "<table class='data-table full-table'><thead><tr><th></th><th>Symbol</th><th>Opp</th><th>Final</th><th>Next</th><th>Swing</th><th>Next Label</th><th>Swing Label</th><th>Stop Loss</th><th>Alloc%</th><th>Cons</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )
        
    def _capital_scenario_simulator(self) -> str:
        return """
        <section class="panel simulator-panel">
            <div class="panel-title">Capital Scenario Simulator</div>
            <div class="sim-desc">Distribute capital across ML-verified swing setups based on Volatility-Scaled Fractional Kelly sizing.</div>
            
            <div class="input-group">
                <label>Total Capital (EGP)</label>
                <input type="number" id="sim-capital" value="100000" min="1000" step="1000">
            </div>
            
            <div class="input-group">
                <label>Max Risk Per Trade (%)</label>
                <input type="number" id="sim-risk" value="2.0" min="0.5" max="10" step="0.5">
            </div>
            
            <button id="sim-run" class="btn">Run Allocation Matrix</button>
            
            <div id="sim-results" class="sim-results" style="display:none;">
                <div class="sim-summary">
                    <div>Allocated: <span id="sim-alloc-val" class="imp"></span></div>
                    <div>Risk Exposure: <span id="sim-risk-val" class="imp-amber"></span></div>
                </div>
                <div class="sim-table-wrap">
                    <table class="data-table sim-table" id="sim-table">
                        <thead><tr><th>Sym</th><th>Shares</th><th>Value</th></tr></thead>
                        <tbody></tbody>
                    </table>
                </div>
            </div>
        </section>
        """

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
:root { 
    color-scheme: dark; 
    --bg: #000000; 
    --panel: #0a0a0a; 
    --line: #222222; 
    --text: #e0e0e0; 
    --muted: #6b6b6b; 
    
    --orange: #ff9900;
    --neon-blue: #00e5ff;
    --neon-green: #00ff41;
    --neon-red: #ff3333;
    
    --font-ui: "Inter", -apple-system, sans-serif;
    --font-mono: "Consolas", "Courier New", monospace;
}

* { box-sizing: border-box; }

body { 
    margin: 0; 
    background: var(--bg); 
    color: var(--text); 
    font-family: var(--font-ui); 
    -webkit-font-smoothing: antialiased;
}

/* Scrollbar */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: #333; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #555; }

.topbar { 
    display: flex; 
    justify-content: space-between; 
    align-items: center; 
    padding: 20px 32px; 
    border-bottom: 1px solid var(--orange); 
    background: rgba(0, 0, 0, 0.85); 
    backdrop-filter: blur(8px);
    position: sticky; 
    top: 0; 
    z-index: 10;
}

h1 { margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.02em; color: #fff; }
.eyebrow { color: var(--orange); font-size: 11px; font-weight: 800; letter-spacing: 0.25em; margin-bottom: 4px; text-transform: uppercase; }

.meta { display: flex; gap: 12px; font-size: 12px; font-family: var(--font-mono); }
.meta span { color: var(--neon-blue); padding: 4px 8px; background: rgba(0, 229, 255, 0.1); border: 1px solid rgba(0, 229, 255, 0.2); border-radius: 4px; }

main { padding: 24px 32px; max-width: 1600px; margin: 0 auto; }

/* Grid Layout */
.grid.layout { display: grid; grid-template-columns: 1fr 340px; gap: 24px; align-items: start; }
@media (max-width: 1200px) { .grid.layout { grid-template-columns: 1fr; } }

.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 20px; transition: border-color 0.2s; }
.card:hover { border-color: rgba(255, 153, 0, 0.5); }

.label { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 600; }
.value { font-size: 32px; font-weight: 700; margin: 12px 0; color: var(--neon-green); font-family: var(--font-mono); }
.hint { color: var(--muted); font-size: 12px; }

.grid.two { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }
@media (max-width: 900px) { .grid.two { grid-template-columns: 1fr; } }

.panel { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 20px; }
.panel-title { font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; margin: 0 0 16px; color: #fff; border-bottom: 1px solid var(--line); padding-bottom: 12px; }

.table-container { overflow-x: auto; }

.data-table { width: 100%; border-collapse: collapse; font-size: 13px; text-align: left; }
.data-table th { color: var(--muted); font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; padding: 12px 10px; border-bottom: 1px solid var(--line); font-weight: 600; }
.data-table td { padding: 12px 10px; border-bottom: 1px solid rgba(255,255,255,0.03); vertical-align: middle; }

.clickable-row { cursor: pointer; transition: background 0.15s; }
.clickable-row:hover td { background: rgba(255, 153, 0, 0.08); }

.rank { color: var(--muted); font-family: var(--font-mono); font-size: 11px; width: 30px; }
.sub { color: var(--muted); font-size: 11px; margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 150px; }
.sub.alloc { color: var(--neon-blue); }

.score-cell { font-family: var(--font-mono); font-weight: 600; }
.score-cell.imp { color: var(--orange); font-size: 14px; }

.ml-stop { color: var(--orange); font-size: 10px; font-weight: bold; border: 1px solid var(--orange); padding: 1px 3px; border-radius: 3px; }

.badge { display: inline-block; border-radius: 4px; padding: 4px 8px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; }
.badge.good { background: rgba(0, 255, 65, 0.1); color: var(--neon-green); border: 1px solid rgba(0, 255, 65, 0.3); }
.badge.watch { background: rgba(255, 153, 0, 0.1); color: var(--orange); border: 1px solid rgba(255, 153, 0, 0.3); }
.badge.bad { background: rgba(255, 51, 51, 0.1); color: var(--neon-red); border: 1px solid rgba(255, 51, 51, 0.3); }
.badge.neutral { background: rgba(0, 229, 255, 0.1); color: var(--neon-blue); border: 1px solid rgba(0, 229, 255, 0.3); }

/* Accuracy Tracker */
.accuracy-hero { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 32px; }
.accuracy-card { background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; padding: 32px; text-align: center; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2); }
.accuracy-value { font-size: 3.5rem; font-weight: 700; color: var(--neon-blue); margin: 16px 0; font-family: var(--font-mono); text-shadow: 0 0 20px rgba(0, 229, 255, 0.3); }
.accuracy-label { font-size: 1.2rem; color: #fff; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; }
.accuracy-hint { font-size: 0.9rem; color: rgba(255, 255, 255, 0.5); margin-top: 8px; font-family: var(--font-mono); }
.progress-bar-bg { background: rgba(255, 255, 255, 0.1); border-radius: 8px; height: 8px; width: 100%; overflow: hidden; margin-top: 16px; }
.progress-bar-fill { background: var(--neon-blue); height: 100%; border-radius: 8px; transition: width 1s ease-in-out; box-shadow: 0 0 10px var(--neon-blue); }
.accuracy-card.swing .accuracy-value { color: var(--neon-green); text-shadow: 0 0 20px rgba(0, 255, 65, 0.3); }
.accuracy-card.swing .progress-bar-fill { background: var(--neon-green); box-shadow: 0 0 10px var(--neon-green); }

/* Simulator */
.simulator-panel { border-color: rgba(0, 229, 255, 0.3); box-shadow: 0 0 20px rgba(0, 229, 255, 0.05); }
.sim-desc { font-size: 12px; color: var(--muted); margin-bottom: 20px; line-height: 1.5; }
.input-group { margin-bottom: 16px; }
.input-group label { display: block; font-size: 11px; text-transform: uppercase; color: var(--neon-blue); margin-bottom: 6px; font-weight: 600; }
.input-group input { width: 100%; background: #000; border: 1px solid var(--line); color: #fff; padding: 10px; font-family: var(--font-mono); border-radius: 4px; outline: none; }
.input-group input:focus { border-color: var(--neon-blue); }

.btn { width: 100%; background: rgba(0, 229, 255, 0.15); color: var(--neon-blue); border: 1px solid var(--neon-blue); padding: 12px; border-radius: 4px; font-family: var(--font-ui); font-weight: 600; text-transform: uppercase; font-size: 12px; cursor: pointer; transition: all 0.2s; letter-spacing: 0.05em; }
.btn:hover { background: var(--neon-blue); color: #000; }

.sim-results { margin-top: 24px; padding-top: 20px; border-top: 1px dashed var(--line); }
.sim-summary { display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 16px; font-family: var(--font-mono); }
.imp-amber { color: var(--orange); font-weight: bold; }
.sim-table-wrap { max-height: 300px; overflow-y: auto; border: 1px solid var(--line); border-radius: 4px; }
.sim-table th { position: sticky; top: 0; background: #000; }
.sim-table td { font-family: var(--font-mono); font-size: 12px; }

/* Modal */
.modal { display: none; position: fixed; z-index: 100; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.85); backdrop-filter: blur(5px); }
.modal-content { background-color: #0a0a0a; margin: 5% auto; border: 1px solid var(--orange); width: 90%; max-width: 1000px; border-radius: 8px; overflow: hidden; box-shadow: 0 0 40px rgba(255, 153, 0, 0.15); }
.modal-header { padding: 16px 24px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--line); background: #000; }
.modal-title { color: var(--orange); font-weight: 700; font-size: 16px; letter-spacing: 0.05em; }
.close-modal { color: var(--muted); font-size: 24px; font-weight: bold; cursor: pointer; transition: color 0.2s; }
.close-modal:hover { color: #fff; }

/* Tabs */
.tabs { display: flex; gap: 16px; padding: 0 32px; background: rgba(0, 0, 0, 0.85); border-bottom: 1px solid var(--line); }
.tab-btn { background: none; border: none; color: var(--muted); font-family: var(--font-ui); font-size: 14px; font-weight: 600; padding: 16px 8px; cursor: pointer; border-bottom: 2px solid transparent; transition: all 0.2s; }
.tab-btn:hover { color: #fff; }
.tab-btn.active { color: var(--orange); border-bottom-color: var(--orange); }

/* Enhanced Candidate Cards */
.candidate-section { overflow: visible; }
.candidate-grid { display: flex; flex-direction: column; gap: 12px; }

.candidate-card {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
    transition: transform 0.2s, box-shadow 0.2s;
}
.candidate-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
    border-color: rgba(255, 255, 255, 0.2);
}

.cand-header { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.cand-rank { font-family: var(--font-mono); color: var(--muted); font-size: 12px; font-weight: 700; min-width: 28px; }
.cand-info { flex: 1; min-width: 0; }
.cand-symbol { font-weight: 700; font-size: 15px; color: #fff; letter-spacing: 0.02em; }
.cand-company { color: var(--muted); font-size: 11px; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cand-badge-wrap { flex-shrink: 0; }

.cand-metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; padding: 10px 0; border-top: 1px solid rgba(255,255,255,0.04); border-bottom: 1px solid rgba(255,255,255,0.04); }
.cand-metric { text-align: center; }
.cand-metric-label { font-size: 9px; text-transform: uppercase; color: var(--muted); letter-spacing: 0.08em; font-weight: 600; margin-bottom: 4px; }
.cand-metric-value { font-family: var(--font-mono); font-size: 13px; font-weight: 600; }

.neon-green { color: var(--neon-green); }
.neon-red { color: var(--neon-red); }
.neon-blue { color: var(--neon-blue); }

.pct-tag { font-size: 10px; font-weight: 700; padding: 2px 5px; border-radius: 3px; margin-left: 2px; }
.pct-tag.up { background: rgba(0, 255, 65, 0.12); color: var(--neon-green); }
.pct-tag.down { background: rgba(255, 51, 51, 0.12); color: var(--neon-red); }

.cand-row.alloc-row { display: flex; justify-content: space-between; padding: 8px 0; font-size: 11px; color: var(--muted); border-bottom: 1px solid rgba(255,255,255,0.04); }

.cand-reasons {
    margin-top: 10px;
    font-size: 11px;
    color: var(--muted);
    line-height: 1.6;
    padding: 8px 10px;
    background: rgba(255, 153, 0, 0.04);
    border-radius: 4px;
    border-left: 2px solid var(--orange);
}
.reasons-icon { font-size: 13px; margin-right: 4px; }
        """

    def _js(self) -> str:
        return """
document.addEventListener("DOMContentLoaded", function() {
    
    // Capital Scenario Simulator Logic
    const runBtn = document.getElementById('sim-run');
    if (runBtn) {
        runBtn.addEventListener('click', function() {
            const capital = parseFloat(document.getElementById('sim-capital').value);
            const riskLimit = parseFloat(document.getElementById('sim-risk').value);
            
            if (isNaN(capital) || capital <= 0) return;
            
            let totalAllocated = 0;
            let totalRisk = 0;
            const tbody = document.querySelector('#sim-table tbody');
            tbody.innerHTML = '';
            
            // Sort by score
            simData.sort((a, b) => b.score - a.score);
            
            let remainingCap = capital;
            
            for (const item of simData) {
                // Apply dynamic risk cap
                const itemRisk = item.maxRisk;
                
                // If the stock's natural risk is above our global risk limit, we must downsize it
                let finalWeight = item.weight;
                if (itemRisk > riskLimit) {
                    const reductionRatio = riskLimit / itemRisk;
                    finalWeight = item.weight * reductionRatio;
                }
                
                // Convert weight to EGP
                let allocEGP = capital * (finalWeight / 100);
                
                // Cap by remaining capital
                if (allocEGP > remainingCap) {
                    allocEGP = remainingCap;
                }
                
                if (allocEGP < 1000) continue; // Minimum 1000 EGP ticket
                
                const shares = Math.floor(allocEGP / item.entry);
                const actualAlloc = shares * item.entry;
                
                if (shares <= 0) continue;
                
                remainingCap -= actualAlloc;
                totalAllocated += actualAlloc;
                
                // Calculate EGP Risk
                const riskPerShare = item.entry - item.stop;
                const actualRiskEGP = shares * riskPerShare;
                totalRisk += actualRiskEGP;
                
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><strong>${item.symbol}</strong></td>
                    <td>${shares.toLocaleString()}</td>
                    <td>£${actualAlloc.toLocaleString(undefined, {maximumFractionDigits:0})}</td>
                `;
                tbody.appendChild(tr);
                
                if (remainingCap <= 1000) break;
            }
            
            const allocPct = (totalAllocated / capital) * 100;
            const riskPct = (totalRisk / capital) * 100;
            
            document.getElementById('sim-alloc-val').innerText = `£${totalAllocated.toLocaleString(undefined, {maximumFractionDigits:0})} (${allocPct.toFixed(1)}%)`;
            document.getElementById('sim-risk-val').innerText = `£${totalRisk.toLocaleString(undefined, {maximumFractionDigits:0})} (${riskPct.toFixed(2)}%)`;
            document.getElementById('sim-results').style.display = 'block';
        });
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
