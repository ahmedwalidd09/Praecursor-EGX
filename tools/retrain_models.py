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
import shutil
import xgboost as xgb
import lightgbm as lgb
from sklearn.metrics import accuracy_score, roc_auc_score, precision_recall_curve

from praecursor.core.price_bar import PriceBar
from praecursor.core.stock import Stock
from praecursor.scoring.opportunity_score import OpportunityScorer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "database" / "praecursor.db"
MODELS_DIR = ROOT / "models"

# ML Features — ONLY features present in indicator_values_json cache.
# Features NOT in cache were trained as 0.0 but had real values at inference,
# causing training/inference skew and anti-predictive AUC. Removed:
#   KalmanTrend, RSI14_ZScore, Momentum20_ZScore, LiquidityVacuumScore,
#   Distance_To_ATH, New_ATH_Made_Today, ATR_Expansion_Ratio, ATR_Exploding,
#   Squeeze_Fired, Squeeze_Building, Full_Confirmation, Partial_Confirmation,
#   Very_Near, Near_High, Momentum1, ConsecutiveGreen, DayOfWeek
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


def load_outcomes():
    """Load all signals that have a hit/miss outcome, with cached indicators."""
    query = """
    SELECT 
        s.run_id, s.symbol, s.company, date(s.generated_at) as run_date,
        o.next_day_hit as target,
        s.latest_close,
        s.indicator_values_json,
        s.opportunity_score as opp_score_pct
    FROM scanner_signals s
    JOIN scanner_signal_outcomes o ON s.run_id = o.run_id AND s.symbol = o.symbol
    WHERE o.next_day_hit IS NOT NULL
    ORDER BY date(s.generated_at) ASC
    """
    try:
        if not DB_PATH.exists():
            logger.warning(f"Database {DB_PATH} does not exist.")
            return pd.DataFrame()
        with sqlite3.connect(DB_PATH) as conn:
            df = pd.read_sql(query, conn)
        
        # Verify and enforce chronological sorting to prevent look-ahead bias
        df['run_date'] = pd.to_datetime(df['run_date'])
        if not df['run_date'].is_monotonic_increasing:
            logger.info("Data not perfectly sorted by date. Enforcing sort.")
            df = df.sort_values('run_date').reset_index(drop=True)
            
        return df
    except Exception as e:
        logger.warning(f"Database error: {e}")
        return pd.DataFrame()


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

    company = symbol  # fallback
    return Stock(symbol=symbol, company=company, history=history)


def extract_features_from_stock(stock: Stock, scorer: OpportunityScorer) -> dict | None:
    """Run the full scoring pipeline and extract the ML features."""
    try:
        opp_score = scorer.score(stock)
        
        flat_values = {}
        for k, v in opp_score.indicator_values.items():
            if isinstance(v, dict):
                for sub_k, sub_v in v.items():
                    flat_values[sub_k] = sub_v
            else:
                flat_values[k] = v

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
            
        flat_values["Momentum1"] = momentum1
        flat_values["ConsecutiveGreen"] = float(consecutive_green)
        flat_values["DayOfWeek"] = day_of_week

        row = {}
        for indicator_name, feature_name in INDICATOR_TO_FEATURE.items():
            val = flat_values.get(indicator_name, 0.0)
            if val != val:  # NaN check
                val = 0.0
            row[feature_name] = val

        return row
    except Exception as e:
        logger.debug(f"Failed to score {stock.symbol}: {e}")
        return None


def extract_features(df: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray, list]:
    """Extract features using cached indicator_values_json. Skips uncached rows for speed."""
    logger.info(f"Extracting features for {len(df)} outcome records...")

    X = []
    y = []
    run_dates = []
    cached_used = 0
    skipped_no_cache = 0

    for idx, row in df.iterrows():
        symbol = row["symbol"]
        run_date = row["run_date"]
        target = int(row["target"])
        cached_json = row.get("indicator_values_json", None)
        opp_score = float(row.get("opp_score_pct", 0.0) or 0.0)

        if not cached_json or str(cached_json) == "nan" or str(cached_json) == "None":
            skipped_no_cache += 1
            continue

        # --- FAST PATH: use cached indicator values ---
        try:
            cached_data = json.loads(cached_json)
        except (json.JSONDecodeError, TypeError):
            skipped_no_cache += 1
            continue

        cached_data["OpportunityScorePct"] = opp_score

        feat_vec = []
        for indicator_name, feature_name in INDICATOR_TO_FEATURE.items():
            val = cached_data.get(indicator_name, 0.0)
            if val is None or (isinstance(val, float) and val != val):
                val = 0.0
            if isinstance(val, dict):
                val = val.get("VPOC_Distance_Pct", 0.0) if "VPOC_Distance_Pct" in val else 0.0
            feat_vec.append(float(val))
        X.append(feat_vec)
        y.append(target)
        run_dates.append(run_date)
        cached_used += 1

    logger.info(f"Feature extraction complete: {cached_used} cached, {skipped_no_cache} skipped (no cache).")
    return pd.DataFrame(X, columns=FEATURES), np.array(y), run_dates


def main():
    logger.info("=== Praecursor-EGX Model Retraining (Real Features) ===")
    logger.info(f"Database: {DB_PATH}")

    df = load_outcomes()
    logger.info(f"Loaded {len(df)} historical labelled examples.")

    if len(df) < 30:
        logger.warning(f"Only {len(df)} labelled examples available. Need at least 30 for meaningful training. Aborting.")
        return

    X, y, run_dates = extract_features(df)

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

    # Temporal split: train on first 80%, test on last 20% chronologically to prevent look-ahead bias.
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    logger.info(f"Training XGBoost on {len(X_train)} samples ({len(FEATURES)} features)...")
    xgb_model = xgb.XGBClassifier(
        n_estimators=500,
        learning_rate=0.03,
        max_depth=5,
        min_child_weight=5,
        gamma=0.1,
        subsample=0.8,
        colsample_bytree=0.7,
        reg_alpha=0.1,
        reg_lambda=1.0,
        scale_pos_weight=n_neg / n_pos if n_pos > 0 else 1.0,
        use_label_encoder=False,
        eval_metric='logloss',
        random_state=42,
        early_stopping_rounds=30,
    )
    xgb_model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    probs = xgb_model.predict_proba(X_test)[:, 1]
    preds = (probs > 0.5).astype(int)
    acc = accuracy_score(y_test, preds)
    try:
        auc = roc_auc_score(y_test, probs)
    except ValueError:
        auc = 0.0

    logger.info(f"XGBoost Retraining Complete! Test Accuracy: {acc:.2f} | AUC: {auc:.2f}")

    # Feature importance
    importances = xgb_model.feature_importances_
    xgb_feat_imp = sorted(zip(FEATURES, importances), key=lambda x: x[1], reverse=True)
    logger.info("\n=== XGBoost Feature Importances ===")
    xgb_imp_dict = {}
    for name, imp in xgb_feat_imp:
        logger.info(f"  {name}: {imp:.4f}")
        xgb_imp_dict[name] = float(imp)
        
    xgb_prune = [name for name, imp in xgb_feat_imp if imp < 0.01]
    if xgb_prune:
        logger.warning(f"Features with <1% importance (XGBoost candidates for pruning): {', '.join(xgb_prune)}")

    precisions, recalls, thresholds = precision_recall_curve(y_test, probs)
    if len(thresholds) > 0:
        f1_scores = 2 * (precisions[:-1] * recalls[:-1]) / (precisions[:-1] + recalls[:-1] + 1e-9)
        best_idx = np.argmax(f1_scores)
        optimal_threshold = round(float(thresholds[best_idx]), 4)
    else:
        optimal_threshold = 0.5

    logger.info(f"Optimal F1 Threshold: {optimal_threshold:.4f}")

    logger.info("Computing Conformal Prediction Bounds...")
    cal_scores = []
    for i in range(len(y_test)):
        if y_test[i] == 1:
            cal_scores.append(1.0 - probs[i])
        else:
            cal_scores.append(probs[i])
            
    cal_scores = np.array(cal_scores)
    alpha = 0.1
    n_cal = len(cal_scores)
    q_level = np.ceil((n_cal + 1) * (1 - alpha)) / n_cal if n_cal > 0 else 0.5
    if q_level > 1.0:
        q_level = 1.0
    q_hat = float(np.quantile(cal_scores, q_level)) if n_cal > 0 else 0.5
    logger.info(f"Conformal Calibration q_hat (90%): {q_hat:.4f}")

    meta_data = {
        "training_date": datetime.now().isoformat(),
        "n_samples_train": len(X_train),
        "n_samples_test": len(X_test),
        "test_accuracy": round(acc, 4),
        "threshold": optimal_threshold,
        "features": FEATURES,
        "conformal_q_hat": q_hat,
    }
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR = MODELS_DIR / "archive"
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    meta_path = MODELS_DIR / "xgboost_next_day_meta.json"
    xgb_path = MODELS_DIR / "xgboost_next_day.json"
    lgb_path = MODELS_DIR / "lightgbm_next_day.txt"

    prev_acc = None
    if meta_path.exists():
        try:
            with open(meta_path, "r") as f:
                old_meta = json.load(f)
                prev_acc = old_meta.get("test_accuracy")
        except Exception as e:
            logger.warning(f"Could not read old metadata: {e}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if xgb_path.exists():
        shutil.copy2(xgb_path, ARCHIVE_DIR / f"xgboost_next_day_{ts}.json")
    if meta_path.exists():
        shutil.copy2(meta_path, ARCHIVE_DIR / f"xgboost_next_day_meta_{ts}.json")
    if lgb_path.exists():
        shutil.copy2(lgb_path, ARCHIVE_DIR / f"lightgbm_next_day_{ts}.txt")

    if prev_acc is not None:
        if acc < prev_acc:
            logger.warning(f"[MODEL UPGRADE] New XGBoost test accuracy: {acc*100:.2f}% vs previous: {prev_acc*100:.2f}% (WORSE)")
        else:
            logger.info(f"[MODEL UPGRADE] New XGBoost test accuracy: {acc*100:.2f}% vs previous: {prev_acc*100:.2f}% (IMPROVED)")
    else:
        logger.info(f"[MODEL UPGRADE] New XGBoost test accuracy: {acc*100:.2f}%")

    with open(meta_path, "w") as f:
        json.dump(meta_data, f, indent=2)

    xgb_model.save_model(str(xgb_path))
    logger.info(f"Saved XGBoost model to {xgb_path}")

    logger.info(f"Training LightGBM on {len(X_train)} samples...")
    lgb_model = lgb.LGBMClassifier(
        n_estimators=100,
        learning_rate=0.05,
        max_depth=4,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        scale_pos_weight=n_neg / n_pos if n_pos > 0 else 1.0,
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

    lgb_model.booster_.save_model(str(lgb_path))
    logger.info(f"Saved LightGBM model to {lgb_path}")

    # LightGBM Feature importance
    lgb_importances = lgb_model.feature_importances_
    total_lgb_imp = sum(lgb_importances)
    if total_lgb_imp > 0:
        lgb_importances = [x / total_lgb_imp for x in lgb_importances]
    lgb_feat_imp = sorted(zip(FEATURES, lgb_importances), key=lambda x: x[1], reverse=True)
    
    logger.info("\n=== LightGBM Feature Importances ===")
    lgb_imp_dict = {}
    for name, imp in lgb_feat_imp:
        logger.info(f"  {name}: {imp:.4f}")
        lgb_imp_dict[name] = float(imp)
        
    lgb_prune = [name for name, imp in lgb_feat_imp if imp < 0.01]
    if lgb_prune:
        logger.warning(f"Features with <1% importance (LightGBM candidates for pruning): {', '.join(lgb_prune)}")

    feat_imp_data = {
        "xgboost": xgb_imp_dict,
        "lightgbm": lgb_imp_dict
    }
    with open(MODELS_DIR / "feature_importance.json", "w") as f:
        json.dump(feat_imp_data, f, indent=2)
    logger.info("Saved feature importance data to models/feature_importance.json")

if __name__ == "__main__":
    main()
