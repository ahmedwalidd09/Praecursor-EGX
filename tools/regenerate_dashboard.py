import sys
import logging
from praecursor.core.settings import ScannerSettings
from praecursor.storage.signal_history import SignalHistoryStore
from praecursor.storage.price_cache import PriceCache
from praecursor.reporting.dashboard import ScannerDashboardWriter
from praecursor.workflows.scanner import ScannerRunResult
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
    swing_score: float
    swing_label: str
    consensus_result: any
    previous_rank: int
    rank_change: int
    next_day_prediction: any = None
    swing_prediction: any = None
    data_quality_label: str = 'high'
    warnings: list = None
    
    @property
    def warning_count(self): return 0

    @property
    def next_day_reasons_text(self):
        return self.next_day_prediction.reasons_text if self.next_day_prediction else "Historical scan result"

    @property
    def swing_reasons_text(self):
        return self.swing_prediction.reasons_text if self.swing_prediction else "Historical scan result"

from praecursor.scoring.opportunity_score import OpportunityScore
from praecursor.consensus.price_consensus import PriceConsensusResult
from datetime import datetime, timezone
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    logger.info("Instantly regenerating dashboard from the latest database scan...")
    
    settings = ScannerSettings.from_json()
    store = SignalHistoryStore()
    
    # 1. Fetch latest run metadata
    with store._connect() as conn:
        conn.row_factory = __import__('sqlite3').Row
        latest_run = conn.execute("SELECT * FROM scanner_runs WHERE id IN (SELECT run_id FROM scanner_signals) ORDER BY id DESC LIMIT 1").fetchone()
        
        if not latest_run:
            logger.error("No historical runs found in database.")
            return 1
            
        run_id = latest_run["id"]
        generated_at = datetime.fromisoformat(latest_run["generated_at"])
        source_name = latest_run["source_name"]
        symbols = json.loads(latest_run["symbols"])
        
        # 2. Fetch all signals for this run
        rows = conn.execute("SELECT * FROM scanner_signals WHERE run_id = ? ORDER BY rank ASC", (run_id,)).fetchall()
        
    symbol_results = []
    
    for r in rows:
        row = dict(r)
        # Reconstruct minimal OpportunityScore
        opp_score = OpportunityScore(
            symbol=row["symbol"],
            company=row["company"],
            total_score=row["opportunity_score"],
            max_score=100,
            indicator_values={},
            latest_close=row["latest_close"]
        )
        
        # Reconstruct minimal Consensus Result
        consensus = None
        if row["consensus_confidence"] > 0:
            consensus = PriceConsensusResult(
                symbol=row["symbol"],
                trade_date=generated_at.date(),
                consensus_close=row["latest_close"],
                source_count=3,
                agreeing_source_count=3,
                target_source_count=3,
                tolerance_percent=0.01,
                minimum_agreeing_sources=2,
                accepted=True,
                agreements=[],
                warnings=[]
            )
            
        # Mock SwingPrediction (needs max_risk, position_size, stop_loss_price, latest_close)
        from praecursor.scoring.swing import SwingPrediction
        swing_pred = SwingPrediction(
            score=row.get("swing_score", 0.0),
            label=row.get("swing_label", ""),
            reasons=[],
            target_price=0.0,
            stop_loss_price=row.get("swing_stop_loss", 0.0),
            position_size=10.0 if "Swing" in row.get("swing_label", "") and "Avoid" not in row.get("swing_label", "") else 0.0,
            max_risk=2.0,
            latest_close=row["latest_close"],
            dynamic_stop=True
        )

        from praecursor.scoring.next_day import NextDayPrediction
        next_day_pred = NextDayPrediction(
            score=row.get("next_day_score", 0.0),
            label=row.get("next_day_label", ""),
            reasons=[],
            latest_close=row["latest_close"],
            target_price=row["latest_close"] * 1.05,
            stop_loss_price=row["latest_close"] * 0.95
        )
        
        result = MockSymbolScanResult(
            symbol=row["symbol"],
            company=row["company"],
            latest_close=row["latest_close"],
            opportunity_score=opp_score,
            final_predictor_score=row["final_predictor_score"],
            predictor_label=row["predictor_label"],
            data_quality_score=row["data_quality_score"],
            next_day_score=row.get("next_day_score", 0.0),
            next_day_label=row.get("next_day_label", " "),
            swing_score=row.get("swing_score", 0.0),
            swing_label=row.get("swing_label", " "),
            consensus_result=consensus,
            previous_rank=row["previous_rank"],
            rank_change=row["rank_change"],
            swing_prediction=swing_pred,
            next_day_prediction=next_day_pred
        )
        
        
        symbol_results.append(result)
        
    # Reconstruct ScannerRunResult
    run_result = ScannerRunResult(
        start_date=generated_at.date(),
        end_date=generated_at.date(),
        generated_at=generated_at,
        source_name=source_name,
        consensus_source_names=[],
        database_path=PriceCache().path,
        report_path=None,
        next_day_report_path=None,
        swing_report_path=None,
        markdown_report_path=None,
        dashboard_report_path=None,
        archive_report_path=None,
        archive_markdown_report_path=None,
        history_run_id=run_id,
        symbols=symbols,
        symbol_results=symbol_results,
        errors={}
    )
    
    # 3. Regenerate HTML
    writer = ScannerDashboardWriter()
    writer.write(run_result)
    
    logger.info("Dashboard instantly regenerated from history!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
