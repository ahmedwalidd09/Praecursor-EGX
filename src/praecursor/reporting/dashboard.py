from html import escape
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DASHBOARD_REPORT = ROOT / "reports" / "dashboard.html"


class ScannerDashboardWriter:
    """Write a static dark HTML dashboard for scanner results."""

    def write(self, result: Any, output_path: Path = DEFAULT_DASHBOARD_REPORT) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self._html(result), encoding="utf-8")
        return output_path

    def _html(self, result: Any) -> str:
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Praecursor-EGX Dashboard</title>
  <style>{self._css()}</style>
</head>
<body>
  <header class="topbar">
    <div>
      <div class="eyebrow">PRAECURSOR-EGX</div>
      <h1>Opportunity Pulse</h1>
    </div>
    <div class="meta">
      <span>Generated {escape(result.generated_at.isoformat())}</span>
      <span>{len(result.symbol_results)} symbols</span>
      <span>Primary {escape(result.source_name)}</span>
    </div>
  </header>
  <main>
    {self._market_cards(result)}
    <section class="grid two">
      {self._candidate_panel('Next-Day Candidates', result.next_day_results, 'next')}
      {self._candidate_panel('Swing Candidates', result.swing_results, 'swing')}
    </section>
    <section class="panel">
      <div class="panel-title">Overall Opportunity Ranking</div>
      {self._ranking_table(result.symbol_results)}
    </section>
  </main>
</body>
</html>"""

    def _market_cards(self, result: Any) -> str:
        strong = sum(1 for item in result.symbol_results if item.next_day_score >= 65)
        swing = sum(1 for item in result.symbol_results if item.swing_score >= 60)
        accepted = sum(1 for item in result.symbol_results if item.consensus_result and item.consensus_result.accepted)
        avg_quality = 0.0
        if result.symbol_results:
            avg_quality = sum(item.data_quality_score for item in result.symbol_results) / len(result.symbol_results)

        cards = [
            ("Next-Day Watch", str(strong), "setups with immediate follow-through potential"),
            ("Swing Watch", str(swing), "setups with multi-session potential"),
            ("Consensus OK", f"{accepted}/{len(result.symbol_results)}", "latest close accepted"),
            ("Avg Data Quality", f"{avg_quality:.0f}%", "warning-rate quality score"),
        ]
        return "<section class='cards'>" + "".join(
            f"<div class='card'><div class='label'>{escape(label)}</div><div class='value'>{escape(value)}</div><div class='hint'>{escape(hint)}</div></div>"
            for label, value, hint in cards
        ) + "</section>"

    def _candidate_panel(self, title: str, results: list[Any], mode: str) -> str:
        rows = []
        for rank, item in enumerate(results[:8], start=1):
            score = item.next_day_score if mode == "next" else item.swing_score
            label = item.next_day_label if mode == "next" else item.swing_label
            rows.append(
                f"<tr>"
                f"<td class='rank'>#{rank}</td>"
                f"<td><strong>{escape(item.symbol)}</strong><div class='sub'>{escape(item.opportunity_score.company)}</div></td>"
                f"<td>{score:.0f}</td>"
                f"<td><span class='badge {self._badge_class(label)}'>{escape(label)}</span></td>"
                f"</tr>"
            )
        return (
            "<section class='panel'>"
            f"<div class='panel-title'>{escape(title)}</div>"
            "<table><thead><tr><th></th><th>Symbol</th><th>Score</th><th>Label</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></section>"
        )

    def _ranking_table(self, results: list[Any]) -> str:
        rows = []
        for rank, item in enumerate(results, start=1):
            consensus = item.consensus_result
            consensus_text = "N/A"
            if consensus:
                consensus_text = f"{consensus.agreeing_source_count}/{consensus.source_count} · {consensus.confidence_label}"
            rows.append(
                f"<tr>"
                f"<td class='rank'>#{rank}</td>"
                f"<td><strong>{escape(item.symbol)}</strong><div class='sub'>{escape(item.opportunity_score.company)}</div></td>"
                f"<td>{item.opportunity_score.score_percent:.0f}</td>"
                f"<td>{item.final_predictor_score:.0f}</td>"
                f"<td>{item.next_day_score:.0f}</td>"
                f"<td>{item.swing_score:.0f}</td>"
                f"<td><span class='badge {self._badge_class(item.next_day_label)}'>{escape(item.next_day_label)}</span></td>"
                f"<td><span class='badge {self._badge_class(item.swing_label)}'>{escape(item.swing_label)}</span></td>"
                f"<td>{escape(consensus_text)}</td>"
                f"<td>{item.data_quality_score:.0f}%</td>"
                f"</tr>"
            )
        return (
            "<table><thead><tr><th></th><th>Symbol</th><th>Opp</th><th>Final</th><th>Next</th><th>Swing</th><th>Next Label</th><th>Swing Label</th><th>Consensus</th><th>Quality</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )

    def _badge_class(self, label: str) -> str:
        lowered = label.lower()
        if "explosion" in lowered or "strong" in lowered or "continuation" in lowered:
            return "good"
        if "watch" in lowered or "reversal" in lowered:
            return "watch"
        if "avoid" in lowered or "low" in lowered:
            return "bad"
        return "neutral"

    def _css(self) -> str:
        return """
:root { color-scheme: dark; --bg:#05070a; --panel:#0c1118; --panel2:#111827; --line:#1f2a37; --text:#e5edf5; --muted:#7c8da5; --blue:#2f80ed; --green:#17c964; --red:#ff4d4f; --amber:#f5a524; }
* { box-sizing: border-box; }
body { margin:0; background: radial-gradient(circle at top left, #101827 0, #05070a 38%, #030406 100%); color:var(--text); font-family: Inter, Segoe UI, Arial, sans-serif; }
.topbar { display:flex; justify-content:space-between; gap:24px; align-items:center; padding:24px 28px; border-bottom:1px solid var(--line); background:rgba(3,4,6,.8); position:sticky; top:0; backdrop-filter: blur(12px); }
h1 { margin:0; font-size:28px; letter-spacing:.04em; }
.eyebrow { color:var(--green); font-size:12px; letter-spacing:.2em; margin-bottom:6px; }
.meta { display:flex; gap:10px; flex-wrap:wrap; justify-content:flex-end; color:var(--muted); font-size:12px; }
.meta span { border:1px solid var(--line); border-radius:999px; padding:7px 10px; background:#080c12; }
main { padding:22px; max-width:1500px; margin:0 auto; }
.cards { display:grid; grid-template-columns: repeat(4, minmax(160px,1fr)); gap:14px; margin-bottom:18px; }
.card, .panel { background: linear-gradient(180deg, rgba(17,24,39,.95), rgba(8,12,18,.95)); border:1px solid var(--line); border-radius:16px; box-shadow: 0 12px 40px rgba(0,0,0,.25); }
.card { padding:16px; }
.label { color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.08em; }
.value { font-size:28px; font-weight:800; margin:8px 0; color:var(--green); }
.hint { color:var(--muted); font-size:12px; }
.grid.two { display:grid; grid-template-columns:1fr 1fr; gap:18px; margin-bottom:18px; }
.panel { padding:16px; overflow:hidden; }
.panel-title { font-weight:800; margin:0 0 14px; letter-spacing:.04em; }
table { width:100%; border-collapse:collapse; font-size:13px; }
th { color:var(--muted); text-align:left; font-size:11px; text-transform:uppercase; letter-spacing:.08em; border-bottom:1px solid var(--line); padding:10px 8px; }
td { border-bottom:1px solid rgba(31,42,55,.7); padding:10px 8px; vertical-align:middle; }
tr:hover td { background:rgba(47,128,237,.06); }
.rank { color:var(--muted); width:46px; }
.sub { color:var(--muted); font-size:11px; margin-top:3px; }
.badge { display:inline-block; border-radius:999px; padding:5px 9px; font-size:11px; font-weight:700; white-space:nowrap; }
.badge.good { background:rgba(23,201,100,.12); color:var(--green); border:1px solid rgba(23,201,100,.35); }
.badge.watch { background:rgba(245,165,36,.12); color:var(--amber); border:1px solid rgba(245,165,36,.35); }
.badge.bad { background:rgba(255,77,79,.12); color:var(--red); border:1px solid rgba(255,77,79,.35); }
.badge.neutral { background:rgba(47,128,237,.12); color:var(--blue); border:1px solid rgba(47,128,237,.35); }
@media (max-width: 900px) { .cards, .grid.two { grid-template-columns:1fr; } .topbar { display:block; } .meta { justify-content:flex-start; margin-top:12px; } }
"""
