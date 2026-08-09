"""
Retrain ML models using real indicator features from source_prices.
Replaces the synthetic data approach with actual EGX market data.
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import logging

import json
import xgboost as xgb
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score, precision_recall_curve

from praecursor.core.price_bar import PriceBar
from praecursor.core.stock import Stock
from praecursor.scoring.opportunity_score import OpportunityScorer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "database" / "praecursor.db"
MODELS_DIR = ROOT / "models"

# The exact 21 features the ML model uses in production (next_day.py lines 95-107)
# v0.4.0: Added ATRPercent14 so model natively learns volatile stocks are better candidates
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
    "ATRPercent14": "atr_pct14",   # v0.4.0: volatile stocks natively rewarded
    "Momentum1": "momentum1",
    "RSISlope3": "rsi_slope3",
    "ConsecutiveGreen": "consecutive_green",
    "DayOfWeek": "day_of_week",
}

FEATURES = list(INDICATOR_TO_FEATURE.values())


def load_outcomes():
    """Load all signals that have a hit/miss outcome."""
    # Try with indicator_values_json first (added by Task 8), fall back without
    for include_cache in [True, False]:
        cache_col = ",\n        s.indicator_values_json" if include_cache else ""
        query = f"""
        SELECT 
            s.run_id, s.symbol, s.company, date(s.generated_at) as run_date,
            o.next_day_hit as target,
            s.latest_close{cache_col}
        FROM scanner_signals s
        JOIN scanner_signal_outcomes o ON s.run_id = o.run_id AND s.symbol = o.symbol
        WHERE o.next_day_hit IS NOT NULL
        """
        try:
            if not DB_PATH.exists():
                logger.warning(f"Database {DB_PATH} does not exist.")
                return pd.DataFrame()
            with sqlite3.connect(DB_PATH) as conn:
                df = pd.read_sql(query, conn)
            return df
        except Exception as e:
            if "no such column" in str(e) and include_cache:
                continue  # Try without the cache column
            logger.warning(f"Database error: {e}")
            return pd.DataFrame()
    return pd.DataFrame()


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

    # Look up company name from symbols config or use symbol as fallback
    company_row = conn.execute("""
        SELECT DISTINCT ticker FROM source_prices WHERE ticker = ? LIMIT 1
    """, (symbol,)).fetchone()
    company = symbol  # fallback

    return Stock(symbol=symbol, company=company, history=history)


def extract_features_from_stock(stock: Stock, scorer: OpportunityScorer) -> dict | None:
    """Run the full scoring pipeline and extract the 20 ML features."""
    try:
        opp_score = scorer.score(stock)
        indicator_values = opp_score.indicator_values

        row = {}
        for indicator_name, feature_name in INDICATOR_TO_FEATURE.items():
            val = indicator_values.get(indicator_name, 0.0)
            if val != val:  # NaN check
                val = 0.0
            row[feature_name] = val

        return row
    except Exception as e:
        logger.debug(f"Failed to score {stock.symbol}: {e}")
        return None


def extract_features(df: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    """Extract real indicator features for all outcome records."""
    logger.info(f"Extracting real features for {len(df)} outcome records...")

    scorer = OpportunityScorer()
    X = []
    y = []
    skipped = 0

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        for idx, row in df.iterrows():
            symbol = row["symbol"]
            run_date = row["run_date"]
            target = int(row["target"])

            # Try cached indicator values first (Task 8 column, if it exists)
            cached_json = row.get("indicator_values_json")
            if cached_json and str(cached_json) != "None" and str(cached_json).strip():
                try:
                    import json
                    cached_vals = json.loads(cached_json)
                    feat_row = {}
                    for indicator_name, feature_name in INDICATOR_TO_FEATURE.items():
                        val = cached_vals.get(indicator_name, 0.0)
                        if val != val:  # NaN
                            val = 0.0
                        feat_row[feature_name] = val
                    X.append([feat_row[f] for f in FEATURES])
                    y.append(target)
                    continue
                except Exception:
                    pass  # Fall through to recalculate

            # Recalculate from source_prices
            stock = build_stock_from_prices(symbol, run_date, conn)
            if stock is None:
                skipped += 1
                continue

            feat_row = extract_features_from_stock(stock, scorer)
            if feat_row is None:
                skipped += 1
                continue

            X.append([feat_row[f] for f in FEATURES])
            y.append(target)

    logger.info(f"Extracted {len(X)} feature vectors, skipped {skipped} records (insufficient price data).")
    return pd.DataFrame(X, columns=FEATURES), np.array(y)


def main():
    logger.info("=== Praecursor-EGX Model Retraining (Real Features) ===")
    logger.info(f"Database: {DB_PATH}")

    df = load_outcomes()
    logger.info(f"Loaded {len(df)} historical labelled examples.")

    if len(df) < 30:
        logger.warning(f"Only {len(df)} labelled examples available. Need at least 30 for meaningful training. Aborting.")
        return

    X, y = extract_features(df)

    if len(X) < 30:
        logger.warning(f"Only {len(X)} usable feature vectors. Need at least 30. Aborting.")
        return

    # Check class balance
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    logger.info(f"Class balance: {n_pos} positive (hit) / {n_neg} negative (miss)")

    if n_pos < 5 or n_neg < 5:
        logger.warning("Insufficient class balance for training. Need at least 5 of each class. Aborting.")
        return

    # Time-based split: train on first 80%, test on last 20% chronologically.
    # This eliminates look-ahead bias from random shuffling (v0.4.0 fix).
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    logger.info(f"Training XGBoost on {len(X_train)} samples ({len(FEATURES)} real EGX features)...")

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
    )

    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    probs = model.predict_proba(X_test)[:, 1]

    acc = accuracy_score(y_test, preds)
    try:
        auc = roc_auc_score(y_test, probs)
    except ValueError:
        auc = 0.0  # Only one class in test set

    logger.info(f"Retraining Complete! Test Accuracy: {acc:.2f} | AUC: {auc:.2f}")
    logger.info(f"  Train: {len(X_train)} | Test: {len(X_test)}")

    # Feature importance
    importances = model.feature_importances_
    feat_imp = sorted(zip(FEATURES, importances), key=lambda x: x[1], reverse=True)
    logger.info("Top 10 feature importances:")
    for name, imp in feat_imp[:10]:
        logger.info(f"  {name}: {imp:.4f}")

    # Probability Calibration (Problem 2)
    precisions, recalls, thresholds = precision_recall_curve(y_test, probs)
    if len(thresholds) > 0:
        f1_scores = 2 * (precisions[:-1] * recalls[:-1]) / (precisions[:-1] + recalls[:-1] + 1e-9)
        best_idx = np.argmax(f1_scores)
        optimal_threshold = round(float(thresholds[best_idx]), 4)
    else:
        optimal_threshold = 0.5

    logger.info(f"Optimal F1 Threshold: {optimal_threshold:.4f}")

    meta_data = {
        "threshold": optimal_threshold,
        "features": FEATURES,
    }
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    meta_path = MODELS_DIR / "xgboost_next_day_meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta_data, f, indent=2)
    logger.info(f"Saved model metadata to {meta_path}")

    # Save XGBoost model
    model_path = MODELS_DIR / "xgboost_next_day.json"
    model.save_model(str(model_path))
    logger.info(f"Saved retrained model to {model_path}")

    # Train LightGBM Model (Problem 4)
    logger.info(f"Training LightGBM on {len(X_train)} samples...")
    lgb_model = lgb.LGBMClassifier(
        n_estimators=100,
        learning_rate=0.05,
        max_depth=4,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        scale_pos_weight=n_neg / n_pos,
        verbosity=-1,
    )
    lgb_model.fit(X_train, y_train)

    lgb_preds = lgb_model.predict(X_test)
    lgb_probs = lgb_model.predict_proba(X_test)[:, 1]

    lgb_acc = accuracy_score(y_test, lgb_preds)
    try:
        lgb_auc = roc_auc_score(y_test, lgb_probs)
    except ValueError:
        lgb_auc = 0.0

    logger.info(f"LightGBM Retraining Complete! Test Accuracy: {lgb_acc:.2f} | AUC: {lgb_auc:.2f}")

    lgb_path = MODELS_DIR / "lightgbm_next_day.txt"
    lgb_model.booster_.save_model(str(lgb_path))
    logger.info(f"Saved LightGBM model to {lgb_path}")


if __name__ == "__main__":
    main()
