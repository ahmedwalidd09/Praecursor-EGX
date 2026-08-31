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

# Must match retrain_models.py exactly (31 features)
INDICATOR_TO_FEATURE = {
    # --- Core indicators (all verified in cache 100/100) ---
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
    # --- v2: Features verified in cache ---
    "OpportunityScorePct": "opp_score_pct",
    "NearCloseHigh250Percent": "near_high250_pct",
    "CMF20": "cmf20",
    "MFI14": "mfi14",
    "RS_vs_EGX30_50": "rs_vs_index",
    "VolumeConfirmedBreakout": "vol_confirmed_breakout",
    "WilliamsR14": "williams_r14",
    "KCSqueeze20": "kc_squeeze20",
    "Ichimoku_Score": "ichimoku_score",
    "ElderRay_Score": "elder_ray_score",
    # --- v6.1 Next-Day Alpha Features ---
    "ClosingAggression": "closing_aggression",
    "NR7_Compression": "nr7_compression",
    "VSA_Absorption": "vsa_absorption",
    "SectorSpillover": "sector_spillover",
}
FEATURES = list(INDICATOR_TO_FEATURE.values())
MIN_TRAIN_SAMPLES = 30


def load_all_outcomes(conn) -> pd.DataFrame:
    """Load all labelled outcomes with dates, ordered chronologically."""
    query = """
    SELECT 
        s.run_id, s.symbol, date(s.generated_at) as run_date,
        o.next_day_hit as target, o.next_day_return,
        s.latest_close, s.indicator_values_json, s.opportunity_score as opp_score_pct
    FROM scanner_signals s
    JOIN scanner_signal_outcomes o ON s.run_id = o.run_id AND s.symbol = o.symbol
    WHERE o.next_day_hit IS NOT NULL AND s.indicator_values_json IS NOT NULL
    ORDER BY run_date ASC
    """
    return pd.read_sql(query, conn)


def build_stock_from_prices(symbol: str, run_date: str, conn) -> Stock | None:
    """Build a Stock object from source_prices for a given symbol up to run_date."""
    # Ensure run_date is extended to end of day to include time-stamped rows
    run_date_end = run_date + " 23:59:59" if len(run_date) <= 10 else run_date
    
    rows = conn.execute("""
        SELECT trade_date, open, high, low, close, volume
        FROM source_prices
        WHERE ticker = ? AND trade_date <= ?
        ORDER BY trade_date ASC
        LIMIT 300
    """, (symbol, run_date_end)).fetchall()

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


import json
def extract_features_for_row(row, conn, scorer: OpportunityScorer) -> list | None:
    """Extract ML features for a single symbol on a given date (fast cache or slow recompute)."""
    symbol = row['symbol']
    run_date = row['run_date']
    cached_json = row.get("indicator_values_json", None)
    opp_score = float(row.get("opp_score_pct", 0.0) or 0.0)

    if cached_json and str(cached_json) != "nan" and str(cached_json) != "None":
        try:
            cached_data = json.loads(cached_json)
        except (json.JSONDecodeError, TypeError):
            cached_data = {}

        cached_data["OpportunityScorePct"] = opp_score

        feat_vec = []
        for indicator_name in INDICATOR_TO_FEATURE:
            val = cached_data.get(indicator_name, 0.0)
            if val is None or (isinstance(val, float) and val != val):
                val = 0.0
            if isinstance(val, dict):
                val = val.get("VPOC_Distance_Pct", 0.0) if "VPOC_Distance_Pct" in val else 0.0
            feat_vec.append(float(val))
        return feat_vec

    # Slow fallback
    stock = build_stock_from_prices(symbol, run_date, conn)
    if stock is None:
        return None
    try:
        opp_score_obj = scorer.score(stock)
        indicator_values = opp_score_obj.indicator_values
        indicator_values["OpportunityScorePct"] = opp_score
        
        # Ghost Features
        momentum1 = 0.0
        consecutive_green = 0
        day_of_week = 0.0
        
        if stock is not None and hasattr(stock, "history") and len(stock.history) >= 4:
            history = stock.history
            close = history[-1].close
            prev_close = history[-2].close
            if prev_close > 0:
                momentum1 = (close - prev_close) / prev_close * 100.0
                
            count = 0
            for bar in reversed(history):
                if bar.close > bar.open:
                    count += 1
                else:
                    break
            consecutive_green = count
            day_of_week = float(history[-1].date.weekday())
            
        indicator_values["Momentum1"] = momentum1
        indicator_values["ConsecutiveGreen"] = float(consecutive_green)
        indicator_values["DayOfWeek"] = day_of_week

        feat_vec = []
        for indicator_name in INDICATOR_TO_FEATURE:
            val = indicator_values.get(indicator_name, 0.0)
            if val != val or val is None:  # NaN
                val = 0.0
            if isinstance(val, dict):
                val = val.get("VPOC_Distance_Pct", 0.0) if "VPOC_Distance_Pct" in val else 0.0
            feat_vec.append(float(val))
        return feat_vec
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

    excluded_signals_count = 0

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        for i, date_str in enumerate(unique_dates):
            day_data = df_all[df_all['run_date'] == date_str]

            # First: accumulate training data from previous days
            if i > 0:
                prev_date = unique_dates[i - 1]
                prev_data = df_all[df_all['run_date'] == prev_date]
                for _, row in prev_data.iterrows():
                    next_ret = row.get('next_day_return')
                    if next_ret is not None and not np.isnan(next_ret) and abs(float(next_ret)) > 0.40:
                        continue
                    feat = extract_features_for_row(row, conn, scorer)
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
                next_ret = row.get('next_day_return')
                if next_ret is not None and not np.isnan(next_ret) and abs(float(next_ret)) > 0.40:
                    excluded_signals_count += 1
                    logger.warning(f"Excluded {row['symbol']} on {date_str} due to suspected corporate action (gap {float(next_ret):.1%})")
                    continue

                feat = extract_features_for_row(row, conn, scorer)
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
    if excluded_signals_count > 0:
        logger.info(f"Excluded {excluded_signals_count} signals due to suspected corporate actions (splits/dividends)")
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

    # --- STATISTICAL SIGNIFICANCE ---
    import math
    scanner_k = total_top8_hits
    scanner_n = total_top8_num
    p_scanner = scanner_k / scanner_n if scanner_n > 0 else 0.0

    baseline_k = total_hits
    baseline_n = total_candidates
    p_baseline = baseline_k / baseline_n if baseline_n > 0 else 0.0

    if scanner_n > 0 and baseline_n > 0:
        p0 = p_baseline
        if p0 > 0 and p0 < 1:
            var = p0 * (1 - p0) / scanner_n
            z = (p_scanner - p0) / math.sqrt(var) if var > 0 else 0
            try:
                from scipy.stats import norm
                p_val = norm.sf(z) if z > 0 else norm.sf(-z)
            except ImportError:
                p_val = 0.5 * math.erfc(abs(z) / math.sqrt(2))
        else:
            p_val = 1.0
            z = 0.0

        z_ci = 1.96
        denominator = 1 + z_ci**2 / scanner_n
        center_prob = p_scanner + z_ci**2 / (2 * scanner_n)
        ci_term = z_ci * math.sqrt((p_scanner * (1 - p_scanner) + z_ci**2 / (4 * scanner_n)) / scanner_n)
        ci_lower = (center_prob - ci_term) / denominator
        ci_upper = (center_prob + ci_term) / denominator

        if p_scanner > 0 and p0 > 0:
            h = 2 * (math.asin(math.sqrt(p_scanner)) - math.asin(math.sqrt(p0)))
        else:
            h = 0.0

        expected_hit = scanner_n * p0
        expected_miss = scanner_n * (1 - p0)
        actual_miss = scanner_n - scanner_k
        if expected_hit > 0 and expected_miss > 0:
            chi2 = ((scanner_k - expected_hit)**2 / expected_hit) + ((actual_miss - expected_miss)**2 / expected_miss)
        else:
            chi2 = 0.0

        stars = ""
        if p_val < 0.001: stars = "***"
        elif p_val < 0.01: stars = "**"
        elif p_val < 0.05: stars = "*"

        print("\n=== STATISTICAL SIGNIFICANCE ===")
        print(f"Scanner Hit Rate: {p_scanner*100:.1f}% (N={scanner_n})")
        print(f"Baseline Hit Rate: {p_baseline*100:.1f}% (N={baseline_n})")
        print(f"p-value (binomial): {p_val:.5g} {stars}".strip())
        print(f"95% CI: [{ci_lower*100:.1f}%, {ci_upper*100:.1f}%]")
        
        abs_h = abs(h)
        if abs_h >= 0.8: effect_desc = "large"
        elif abs_h >= 0.5: effect_desc = "medium"
        elif abs_h >= 0.2: effect_desc = "small-medium"
        elif abs_h >= 0.1: effect_desc = "small"
        else: effect_desc = "trivial"
        
        print(f"Effect Size (Cohen's h): {h:.2f} ({effect_desc})")
        print(f"Chi-Squared: {chi2:.2f}")

        if p_val < 0.01:
            print("Verdict: STATISTICALLY SIGNIFICANT at p < 0.01")
        elif p_val < 0.05:
            print("Verdict: STATISTICALLY SIGNIFICANT at p < 0.05")
        else:
            print("Verdict: NOT STATISTICALLY SIGNIFICANT")


if __name__ == "__main__":
    main()
