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
    "Momentum1": "momentum1",
    "RSISlope3": "rsi_slope3",
    "ConsecutiveGreen": "consecutive_green",
    "DayOfWeek": "day_of_week",
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
            day_candidates = []

            for _, row in day_data.iterrows():
                feat = extract_features_for_row(row['symbol'], row['run_date'], conn, scorer)
                if feat is None:
                    continue
                prob = float(model.predict_proba([feat])[0][1])
                actual_hit = int(row['target'])
                day_candidates.append((row['symbol'], prob, actual_hit))

            if not day_candidates:
                continue

            # Sort by prob descending
            day_candidates.sort(key=lambda x: x[1], reverse=True)

            # Take top 8
            top8 = day_candidates[:8]
            top8_hits = sum(1 for c in top8 if c[2] == 1)
            top8_total = len(top8)
            top8_hit_rate_pct = (top8_hits / top8_total * 100.0) if top8_total > 0 else 0.0

            # All candidates
            total_candidates = len(day_candidates)
            actual_hits = sum(1 for c in day_candidates if c[2] == 1)
            hit_rate_pct = (actual_hits / total_candidates * 100.0) if total_candidates > 0 else 0.0

            results.append({
                'date': date_str,
                'top8_hits': top8_hits,
                'top8_total': top8_total,
                'top8_hit_rate_pct': round(top8_hit_rate_pct, 1),
                'total_candidates': total_candidates,
                'actual_hits': actual_hits,
                'hit_rate_pct': round(hit_rate_pct, 1),
                'training_samples': len(X_accumulated),
            })
            logger.info(
                f"  {date_str}: Top-8 {top8_hits}/{top8_total} hits ({top8_hit_rate_pct:.0f}%) | "
                f"All {actual_hits}/{total_candidates} ({hit_rate_pct:.0f}%) | trained on {len(X_accumulated)} samples"
            )

    if not results:
        logger.warning("No walk-forward results generated. Need more historical outcome data.")
        return

    # Summary
    df_results = pd.DataFrame(results)
    total_top8_hits = int(df_results['top8_hits'].sum())
    total_top8_num = int(df_results['top8_total'].sum())
    top8_overall_accuracy = (total_top8_hits / total_top8_num * 100.0) if total_top8_num > 0 else 0.0

    total_candidates = int(df_results['total_candidates'].sum())
    total_hits = int(df_results['actual_hits'].sum())
    overall_accuracy = (total_hits / total_candidates * 100.0) if total_candidates > 0 else 0.0

    logger.info("\n" + "=" * 60)
    logger.info("WALK-FORWARD BACKTEST SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Dates simulated:       {len(df_results)}")
    logger.info(f"Top-8 Total Hits:      {total_top8_hits}/{total_top8_num}")
    logger.info(f"Top-8 Overall Accuracy:{top8_overall_accuracy:.1f}%")
    logger.info(f"Top-8 Avg Hit Rate/day:{df_results['top8_hit_rate_pct'].mean():.1f}%")
    logger.info(f"All-Candidates Hits:   {total_hits}/{total_candidates}")
    logger.info(f"All-Candidates Acc:    {overall_accuracy:.1f}%")
    logger.info("=" * 60)

    # Save CSV
    out_path = REPORTS_DIR / "backtest_results.csv"
    df_results.to_csv(out_path, index=False)
    logger.info(f"Results saved to: {out_path}")

    # Print table
    print("\n{:<12} {:>12} {:>12} {:>15} {:>10}".format(
        "Date", "Top-8 Hits", "Top-8 Rate", "All Candidates", "Train N"
    ))
    print("-" * 65)
    for _, r in df_results.iterrows():
        top8_str = f"{r['top8_hits']}/{r['top8_total']}"
        all_str = f"{r['actual_hits']}/{r['total_candidates']}"
        print("{:<12} {:>12} {:>11.0f}% {:>15} {:>10}".format(
            r['date'], top8_str, r['top8_hit_rate_pct'],
            all_str, r['training_samples']
        ))
    print("-" * 65)
    top8_tot_str = f"{total_top8_hits}/{total_top8_num}"
    all_tot_str = f"{total_hits}/{total_candidates}"
    print("{:<12} {:>12} {:>11.1f}% {:>15}".format(
        "OVERALL", top8_tot_str, top8_overall_accuracy, all_tot_str
    ))


if __name__ == "__main__":
    main()
