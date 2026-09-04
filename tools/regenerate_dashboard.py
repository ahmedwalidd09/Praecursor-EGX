import os
import sys
import logging
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure") and stream is not None:
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

Path("reports/archive").mkdir(parents=True, exist_ok=True)

from praecursor.core.settings import ScannerSettings
from praecursor.storage.signal_history import SignalHistoryStore
from praecursor.storage.price_cache import PriceCache
from praecursor.reporting.dashboard import ScannerDashboardWriter
from praecursor.workflows.scanner import ScannerRunResult
from praecursor.scoring.next_day import NextDayPrediction
from dataclasses import dataclass
@dataclass
class MockSymbolScanResult:
    symbol: str
    company: str
    latest_close: float
    opportunity_score: any
    final_predictor_score: float
    predictor_label: str
    data_quality_score: float
    next_day_score: float
    next_day_label: str
    consensus_result: any
    previous_rank: int
    rank_change: int
    next_day_prediction: any = None
    data_quality_label: str = 'high'
    warnings: list = None
    
    @property
    def warning_count(self): return 0

    @property
    def next_day_reasons_text(self):
        return self.next_day_prediction.reasons_text if self.next_day_prediction else "Historical scan result"

from praecursor.scoring.opportunity_score import OpportunityScore
from praecursor.consensus.price_consensus import PriceConsensusResult
from datetime import datetime, timezone
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    try:
        logger.info("Instantly regenerating dashboard from the latest database scan...")
        
        settings = ScannerSettings.from_json()
        store = SignalHistoryStore()
        
        latest_run = None
        rows = []
        import contextlib
        try:
            with contextlib.closing(store._connect()) as conn:
                conn.row_factory = __import__('sqlite3').Row
                latest_run = conn.execute(
                    "SELECT * FROM scanner_runs WHERE id IN (SELECT run_id FROM scanner_signals) ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if latest_run:
                    run_id = latest_run["id"]
                    rows = conn.execute("SELECT * FROM scanner_signals WHERE run_id = ? ORDER BY rank ASC", (run_id,)).fetchall()
        except Exception as db_err:
            logger.warning(f"Database query failed or tables missing: {db_err}")

        if not latest_run:
            logger.warning("No historical runs found in database. Generating fallback empty dashboard.")
            today = datetime.now(timezone.utc).date()
            now = datetime.now(timezone.utc)
            fallback_run_result = ScannerRunResult(
                start_date=today,
                end_date=today,
                generated_at=now,
                source_name="offline",
                consensus_source_names=[],
                database_path=PriceCache().path,
                report_path=None,
                next_day_report_path=None,
                markdown_report_path=None,
                dashboard_report_path=None,
                archive_report_path=None,
                archive_markdown_report_path=None,
                history_run_id=None,
                symbols=[],
                symbol_results=[],
                errors={}
            )
            writer = ScannerDashboardWriter()
            writer.write(fallback_run_result)
            logger.info("Fallback dashboard HTML generated successfully.")
            return 0
            
        gen_at_str = latest_run["generated_at"]
        if isinstance(gen_at_str, str):
            generated_at = datetime.fromisoformat(gen_at_str.replace('Z', '+00:00'))
        else:
            generated_at = datetime.now(timezone.utc)
            
        source_name = latest_run["source_name"] if latest_run["source_name"] else "offline"
        symbols_raw = latest_run["symbols"]
        symbols = json.loads(symbols_raw) if symbols_raw else []
        run_id = latest_run["id"]
        
        symbol_results = []
        for r in rows:
            row = dict(r)
            sym = row.get("symbol", "UNKNOWN")
            comp = row.get("company", sym)
            latest_c = row.get("latest_close", 0.0) or 0.0
            opp_s = row.get("opportunity_score", 0.0) or 0.0
            
            ind_json = row.get("indicator_values_json")
            ind_values = {}
            if ind_json:
                try:
                    ind_values = json.loads(ind_json)
                except Exception:
                    ind_values = {}

            opp_score = OpportunityScore(
                symbol=sym,
                company=comp,
                total_score=opp_s,
                max_score=100,
                indicator_values=ind_values,
                latest_close=latest_c
            )
            
            consensus = None
            consensus_conf = row.get("consensus_confidence", 0.0) or 0.0
            if consensus_conf > 0:
                consensus = PriceConsensusResult(
                    symbol=sym,
                    trade_date=generated_at.date(),
                    consensus_close=latest_c,
                    source_count=3,
                    agreeing_source_count=3,
                    target_source_count=3,
                    tolerance_percent=0.01,
                    minimum_agreeing_sources=2,
                    accepted=True,
                    agreements=[],
                    warnings=[]
                )
                
            target_p = row.get("next_day_target", 0.0) or (latest_c * 1.05)
            stop_p = row.get("swing_stop_loss", 0.0) or (latest_c * 0.95)
            if target_p <= 0: target_p = latest_c * 1.05
            if stop_p <= 0: stop_p = latest_c * 0.95

            k_fraction = 0.0
            nd_s = row.get("next_day_score", 0.0) or 0.0
            w_p = max(0.40, min(0.50 + max(0.0, nd_s - 50.0) * 0.005, 0.62))
            t_pct = (target_p - latest_c) / latest_c if latest_c > 0 else 0.0
            s_pct = (latest_c - stop_p) / latest_c if latest_c > 0 else 0.0
            if t_pct > 0 and s_pct > 0:
                b = t_pct / s_pct
                k_fraction = max(0.0, min((w_p - ((1.0 - w_p) / b)) * 0.5, 0.25))

            try:
                from praecursor.scoring.next_day import calculate_next_day_prediction
                next_day_pred = calculate_next_day_prediction(
                    opportunity_score=opp_score,
                    consensus_accepted=consensus.accepted if consensus else False,
                    data_quality_score=row.get("data_quality_score", 100.0) or 100.0,
                )
            except Exception as e:
                import traceback
                print(f"FAILED calculate_next_day_prediction for {sym}: {e}")
                traceback.print_exc()
                next_day_pred = NextDayPrediction(
                    score=nd_s,
                    label=row.get("next_day_label", "") or "",
                    reasons=[f"Score: {nd_s:.1f}% based on technical indicators"],
                    latest_close=latest_c,
                    target_price=target_p,
                    stop_loss_price=stop_p,
                    kelly_fraction=k_fraction,
                )
            
            result = MockSymbolScanResult(
                symbol=sym,
                company=comp,
                latest_close=latest_c,
                opportunity_score=opp_score,
                final_predictor_score=row.get("final_predictor_score", 0.0) or 0.0,
                predictor_label=row.get("predictor_label", "") or "",
                data_quality_score=row.get("data_quality_score", 100.0) or 100.0,
                next_day_score=row.get("next_day_score", 0.0) or 0.0,
                next_day_label=row.get("next_day_label", "") or "",
                consensus_result=consensus,
                previous_rank=row.get("previous_rank"),
                rank_change=row.get("rank_change"),
                next_day_prediction=next_day_pred
            )
            symbol_results.append(result)
            
        run_result = ScannerRunResult(
            start_date=generated_at.date(),
            end_date=generated_at.date(),
            generated_at=generated_at,
            source_name=source_name,
            consensus_source_names=[],
            database_path=PriceCache().path,
            report_path=None,
            next_day_report_path=None,
            markdown_report_path=None,
            dashboard_report_path=None,
            archive_report_path=None,
            archive_markdown_report_path=None,
            history_run_id=run_id,
            symbols=symbols,
            symbol_results=symbol_results,
            errors={}
        )
        
        writer = ScannerDashboardWriter()
        writer.write(run_result)
        logger.info("Dashboard instantly regenerated from history!")

        if not os.getenv("PRAECURSOR_PIPELINE_RUNNING"):
            try:
                from praecursor.notifications.telegram import dispatch_telegram_scan_briefing
                dispatch_telegram_scan_briefing(run_result, top_n=5, verbose=True)
            except Exception as tg_err:
                logger.debug(f"Telegram dispatch skipped in regenerate_dashboard: {tg_err}")

        return 0
    except Exception as e:
        logger.error(f"Error regenerating dashboard: {e}. Generating fallback dashboard HTML.", exc_info=True)
        try:
            today = datetime.now(timezone.utc).date()
            now = datetime.now(timezone.utc)
            fallback_run_result = ScannerRunResult(
                start_date=today,
                end_date=today,
                generated_at=now,
                source_name="offline",
                consensus_source_names=[],
                database_path=PriceCache().path,
                report_path=None,
                next_day_report_path=None,
                markdown_report_path=None,
                dashboard_report_path=None,
                archive_report_path=None,
                archive_markdown_report_path=None,
                history_run_id=None,
                symbols=[],
                symbol_results=[],
                errors={}
            )
            writer = ScannerDashboardWriter()
            writer.write(fallback_run_result)
            logger.info("Fallback dashboard written following exception.")
        except Exception as fb_err:
            logger.error(f"Failed to write fallback dashboard: {fb_err}")
        return 0

if __name__ == "__main__":
    sys.exit(main())
