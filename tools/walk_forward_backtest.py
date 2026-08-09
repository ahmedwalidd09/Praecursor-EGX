"""
Walk-Forward Backtester for Praecursor-EGX (v0.4.0)

Simulates the real daily pipeline historically with NO look-ahead bias:
  For each date D (chronological order):
    - Train on all outcome data BEFORE D
    - Score top-8 candidates on date D using retrained model
    - Record HIT/MISS vs actual outcomes

Outputs: reports/backtest_results.csv + console summary table
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import logging
import csv

import xgboost as xgb
from sklearn.metrics import accuracy_score, roc_auc_score

# Reuse infrastructure from retrain_models.py
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from praecursor.core.price_bar import PriceBar
from praecursor.core.stock import Stock
from praecursor.scoring.opportunity_score import OpportunityScorer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = ROOT / "database" / "praecursor.db"
REPORTS_DIR = ROOT / "reports"

# Must match retrain_models.py exactly (21 features as of v0.4.0)
INDICATOR_TO_FEATURE = {
    "RSI14": "rsi14",
    "RelVolume20": "rel_volume20",
    "MACDHistogram": "macd_histogram",
    "Momentum20": "momentum20",
    "Breakout20": "breakout20",
    "Breakout50": "breakout50",
    "RSIRebound": "rsi_rebound",
    "EMA20Reclaim": "ema20_reclaim",
    "MACDHistogramImprovement": "macd_histogram_improvement",
    "VolumeSpikeFromWeakness": "volume_spike_from_weakness",
    "Momentum5": "momentum5",
    "BBW20": "bbw20",
    "MTF_Trend": "mtf_trend",
    "VPOC_Distance": "vpoc_distance",
    "ADX14": "adx14",
    "ROC10": "roc10",
    "StochRSI": "stoch_rsi",
    "VWAPMom10": "vwap_mom10",
    "AvgTurnover20": "avg_turnover_20",
    "ClosedAtLimitUp": "closed_at_limit_up",
    "ATRPercent14": "atr_pct14",
}
FEATURES = list(INDICATOR_TO_FEATURE.values())
MIN_TRAIN_SAMPLES = 30


def load_all_outcomes(conn) -> pd.DataFrame:
    """Load all labelled outcomes with dates, ordered chronologically."""
    query = """
    SELECT 
        s.run_id, s.symbol, date(s.generated_at) as run_date,
        o.next_day_hit as target, o.next_day_return,
        s.latest_close
    FROM scanner_signals s
    JOIN scanner_signal_outcomes o ON s.run_id = o.run_id AND s.symbol = o.symbol
    WHERE o.next_day_hit IS NOT NULL
    ORDER BY run_date ASC
    """
    return pd.read_sql(query, conn)


def build_stock_from_prices(symbol: str, run_date: str, conn) -> Stock | None:
    """Build a Stock object from source_prices for a given symbol up to run_date."""
    rows = conn.execute("""
        SELECT trade_date, open, high, low, close, volume
        FROM source_prices
        WHERE ticker = ? AND date(trade_date) <= date(?)
        ORDER BY trade_date ASC
        LIMIT 300
    """, (symbol, run_date)).fetchall()

    if len(rows) < 20:
        return None

    history = []
    for r in rows:
        try:
            dt = datetime.strptime(str(r[0])[:10], "%Y-%m-%d")
            bar = PriceBar(
                date=dt,
                open=float(r[1] or 0),
                high=float(r[2] or 0),
                low=float(r[3] or 0),
                close=float(r[4] or 0),
                volume=int(r[5] or 0),
            )
            history.append(bar)
        except (ValueError, TypeError):
            continue

    if len(history) < 20:
        return None

    return Stock(symbol=symbol, company=symbol, history=history)


def extract_features_for_row(symbol: str, run_date: str, conn, scorer: OpportunityScorer) -> list | None:
    """Extract 21 ML features for a single symbol on a given date."""
    stock = build_stock_from_prices(symbol, run_date, conn)
    if stock is None:
        return None
    try:
        opp_score = scorer.score(stock)
        indicator_values = opp_score.indicator_values
        row = []
        for indicator_name in INDICATOR_TO_FEATURE:
            val = indicator_values.get(indicator_name, 0.0)
            if val != val:  # NaN
                val = 0.0
            row.append(val)
        return row
    except Exception as e:
        logger.debug(f"Failed to score {symbol} on {run_date}: {e}")
        return None


def train_model(X_train: np.ndarray, y_train: np.ndarray) -> xgb.XGBClassifier | None:
    """Train a fresh XGBoost model on the given training data."""
    n_pos = int(y_train.sum())
    n_neg = len(y_train) - n_pos
    if n_pos < 3 or n_neg < 3:
        return None

    model = xgb.XGBClassifier(
        n_estimators=100,
        learning_rate=0.05,
        max_depth=4,
        subsample=0.8,
        colsample_bytree=0.8,
        use_label_encoder=False,
        eval_metric='logloss',
        random_state=42,
        scale_pos_weight=n_neg / n_pos,
        verbosity=0,
    )
    model.fit(X_train, y_train)
    return model


def main():
    logger.info("=== Praecursor-EGX Walk-Forward Backtester (v0.4.0) ===")
    logger.info(f"Database: {DB_PATH}")

    if not DB_PATH.exists():
        logger.error("Database not found.")
        return

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        df_all = load_all_outcomes(conn)

    if df_all.empty:
        logger.error("No outcome data found. Run the pipeline for several days first.")
        return

    logger.info(f"Loaded {len(df_all)} total labelled samples across {df_all['run_date'].nunique()} days.")

    unique_dates = sorted(df_all['run_date'].unique())
    scorer = OpportunityScorer()

    results = []
    X_accumulated = []
    y_accumulated = []

    logger.info(f"Running walk-forward simulation over {len(unique_dates)} dates...")
    logger.info(f"Minimum training window: {MIN_TRAIN_SAMPLES} samples before first prediction.")

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        for i, date_str in enumerate(unique_dates):
            day_data = df_all[df_all['run_date'] == date_str]

            # First: accumulate training data from previous days
            if i > 0:
                prev_date = unique_dates[i - 1]
                prev_data = df_all[df_all['run_date'] == prev_date]
                for _, row in prev_data.iterrows():
                    feat = extract_features_for_row(row['symbol'], row['run_date'], conn, scorer)
                    if feat is not None:
                        X_accumulated.append(feat)
                        y_accumulated.append(int(row['target']))

            # Only predict if we have enough training data
            if len(X_accumulated) < MIN_TRAIN_SAMPLES:
                logger.info(f"  {date_str}: Skipping (only {len(X_accumulated)}/{MIN_TRAIN_SAMPLES} training samples)")
                continue

            # Train on all data up to (but not including) today
            X_train = np.array(X_accumulated)
            y_train = np.array(y_accumulated)
            model = train_model(X_train, y_train)
            if model is None:
                logger.info(f"  {date_str}: Skipping (insufficient class balance in training data)")
                continue

            # Predict on today's candidates
            predicted_hits = 0
            actual_hits = 0
            total = 0

            for _, row in day_data.iterrows():
                feat = extract_features_for_row(row['symbol'], row['run_date'], conn, scorer)
                if feat is None:
                    continue
                prob = model.predict_proba([feat])[0][1]
                predicted_positive = prob >= 0.5
                actual_hit = int(row['target'])
                if predicted_positive:
                    predicted_hits += 1
                if actual_hit:
                    actual_hits += 1
                total += 1

            day_accuracy = (actual_hits / total * 100.0) if total > 0 else 0.0
            results.append({
                'date': date_str,
                'total_candidates': total,
                'actual_hits': actual_hits,
                'predicted_hits': predicted_hits,
                'hit_rate_pct': round(day_accuracy, 1),
                'training_samples': len(X_accumulated),
            })
            logger.info(f"  {date_str}: {actual_hits}/{total} hits ({day_accuracy:.0f}%) | trained on {len(X_accumulated)} samples")

    if not results:
        logger.warning("No walk-forward results generated. Need more historical outcome data.")
        return

    # Summary
    df_results = pd.DataFrame(results)
    total_candidates = df_results['total_candidates'].sum()
    total_hits = df_results['actual_hits'].sum()
    overall_accuracy = total_hits / total_candidates * 100.0 if total_candidates > 0 else 0.0

    logger.info("\n" + "=" * 60)
    logger.info("WALK-FORWARD BACKTEST SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Dates simulated:    {len(df_results)}")
    logger.info(f"Total candidates:   {total_candidates}")
    logger.info(f"Total hits:         {total_hits}")
    logger.info(f"Overall accuracy:   {overall_accuracy:.1f}%")
    logger.info(f"Avg hit rate/day:   {df_results['hit_rate_pct'].mean():.1f}%")
    logger.info("=" * 60)

    # Save CSV
    out_path = REPORTS_DIR / "backtest_results.csv"
    df_results.to_csv(out_path, index=False)
    logger.info(f"Results saved to: {out_path}")

    # Print table
    print("\n{:<12} {:>10} {:>8} {:>12} {:>10}".format(
        "Date", "Candidates", "Hits", "Hit Rate %", "Train N"
    ))
    print("-" * 58)
    for _, r in df_results.iterrows():
        print("{:<12} {:>10} {:>8} {:>11.0f}% {:>9}".format(
            r['date'], r['total_candidates'], r['actual_hits'],
            r['hit_rate_pct'], r['training_samples']
        ))
    print("-" * 58)
    print(f"{'OVERALL':<12} {total_candidates:>10} {total_hits:>8} {overall_accuracy:>11.1f}%")


if __name__ == "__main__":
    main()
