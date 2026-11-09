"""Export the same honest dashboard view used by the desktop application."""
import json
from pathlib import Path
from typing import Any
from praecursor.core.sessions import next_session
from praecursor.ml.features import FEATURE_VERSION
from praecursor.reporting.overview import clean, overview
from praecursor.reporting.pages import render_page

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DASHBOARD_REPORT = ROOT / "reports" / "dashboard.html"
TEMPLATE = Path(__file__).parent / "templates" / "home.html"


class ScannerDashboardWriter:
    def write(self, result: Any, output_path: Path = DEFAULT_DASHBOARD_REPORT) -> Path:
        data = overview(result.database_path) if getattr(result, "database_path", None) else overview()
        data["signals"] = []
        for item in result.symbol_results:
            opportunity = item.opportunity_score
            nd = item.next_day_prediction
            sw = item.swing_prediction
            stock = opportunity.stock
            session = stock.history[-1].date.date().isoformat() if stock and stock.history else None
            data["signals"].append(dict(symbol=item.symbol, company=opportunity.company,
                latest_close=opportunity.latest_close, opportunity_score=opportunity.score_percent,
                next_day_score=nd.score, next_day_label=item.next_day_label, next_day_target=nd.target_price,
                candidate_rank=item.candidate_rank, selection_reasons=list(item.selection_reasons), source_status=item.source_status,
                next_day_stop_loss=nd.stop_loss_price, next_day_reasons=nd.reasons_text,
                next_day_probability=nd.probability, model_version=nd.model_version,
                swing_score=sw.score, swing_label=sw.label, swing_target=sw.target_price,
                swing_stop_loss=sw.stop_loss_price, swing_probability=sw.probability,
                swing_model_version=sw.model_version, feature_session=session,
                feature_version=FEATURE_VERSION, legacy=False,
                data_quality_score=item.data_quality_score, consensus_confidence=item.consensus_score))
        data["scan"] = dict(generated_at=result.generated_at.isoformat(), error_count=len(result.errors))
        data["price_session"] = result.end_date.isoformat()
        data["target_session"] = next_session(result.end_date).isoformat()
        data["stale"] = result.end_date.isoformat() != data["expected_session"]
        return self.write_snapshot(data, output_path)

    def write_snapshot(self, data, output_path=DEFAULT_DASHBOARD_REPORT):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(clean(data), ensure_ascii=True, allow_nan=False).replace("<", "\\u003c")
        html = render_page("home.html").replace("<script>",
            '<script id="saved-snapshot" type="application/json">'+payload+'</script><script>', 1)
        output_path.write_text(html, encoding="utf-8")
        return output_path
