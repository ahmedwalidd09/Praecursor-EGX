"""Enhanced ML training pipeline with:
- Expanded feature set (ADX, ROC, StochRSI, VWAP Momentum)
- LightGBM ensemble alongside XGBoost
- SHAP value feature pruning
- Probability calibration (Platt Scaling / Isotonic Regression)
- Model metadata tracking
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit, train_test_split
from sklearn.calibration import CalibratedClassifierCV

ROOT = Path(__file__).resolve().parents[3]
MODELS_DIR = ROOT / "models"

# Expanded feature set with the 4 new indicators
FEATURES = [
    "rsi14",
    "rel_volume20",
    "macd_histogram",
    "momentum20",
    "breakout20",
    "breakout50",
    "rsi_rebound",
    "ema20_reclaim",
    "macd_histogram_improvement",
    "volume_spike_from_weakness",
    "momentum5",
    "bbw20",
    "mtf_trend",
    "vpoc_distance",
    # New features
    "adx14",
    "roc10",
    "stoch_rsi",
    "vwap_mom10",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, default=str(ROOT / "reports" / "backtest_signals.csv"))
    parser.add_argument("--no-ensemble", action="store_true", help="Skip LightGBM ensemble")
    parser.add_argument("--no-shap", action="store_true", help="Skip SHAP feature pruning")
    parser.add_argument("--no-calibration", action="store_true", help="Skip probability calibration")
    args = parser.parse_args()

    print(f"Loading dataset from {args.data}...")
    df = pd.read_csv(args.data)

    # Use all available features, gracefully handle missing new columns
    available_features = [f for f in FEATURES if f in df.columns]
    missing_features = [f for f in FEATURES if f not in df.columns]
    
    if missing_features:
        print(f"  -> Missing features (will use zeros): {missing_features}")
        for f in missing_features:
            df[f] = 0.0

    for col in FEATURES:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # --- Next-Day Model ---
    df["return_1_bars"] = pd.to_numeric(df["return_1_bars"], errors="coerce")
    valid_next_day = df.dropna(subset=["return_1_bars"])
    y_next = (valid_next_day["return_1_bars"] > 0).astype(int)
    X_next = valid_next_day[FEATURES].fillna(0)

    print(f"\n{'='*60}")
    print(f"Training Next-Day Model on {len(X_next)} samples...")
    print(f"Features: {len(FEATURES)}")
    train_and_save(
        X_next, y_next, "xgboost_next_day.json",
        enable_ensemble=not args.no_ensemble,
        enable_shap=not args.no_shap,
        enable_calibration=not args.no_calibration,
        model_type="next_day",
    )

    # --- Swing Model ---
    df["return_20_bars"] = pd.to_numeric(df["return_20_bars"], errors="coerce")
    valid_swing = df.dropna(subset=["return_20_bars"])
    y_swing = (valid_swing["return_20_bars"] > 0).astype(int)
    X_swing = valid_swing[FEATURES].fillna(0)

    print(f"\n{'='*60}")
    print(f"Training Swing Model on {len(X_swing)} samples...")
    train_and_save(
        X_swing, y_swing, "xgboost_swing.json",
        enable_ensemble=not args.no_ensemble,
        enable_shap=not args.no_shap,
        enable_calibration=not args.no_calibration,
        model_type="swing",
    )


def train_and_save(
    X: pd.DataFrame,
    y: pd.Series,
    filename: str,
    enable_ensemble: bool = True,
    enable_shap: bool = True,
    enable_calibration: bool = True,
    model_type: str = "next_day",
):
    # Class imbalance handling
    pos_count = y.sum()
    neg_count = len(y) - pos_count
    scale_weight = neg_count / pos_count if pos_count > 0 else 1.0
    print(f"  -> Class balance: {pos_count} positive / {neg_count} negative (scale_pos_weight={scale_weight:.2f})")

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # ============================
    # 1. XGBoost with Hyperparameter Tuning
    # ============================
    model = xgb.XGBClassifier(
        random_state=42,
        eval_metric="logloss",
        scale_pos_weight=scale_weight,
    )

    param_grid = {
        'n_estimators': [100, 200, 300, 500],
        'learning_rate': [0.01, 0.03, 0.05, 0.1],
        'max_depth': [3, 4, 5, 6, 7],
        'subsample': [0.7, 0.8, 0.9],
        'colsample_bytree': [0.6, 0.7, 0.8, 0.9],
        'min_child_weight': [1, 3, 5],
        'gamma': [0, 0.1, 0.2],
    }

    print(f"  -> Tuning XGBoost Hyperparameters...")
    search = RandomizedSearchCV(
        model,
        param_distributions=param_grid,
        n_iter=25,
        scoring='roc_auc',
        cv=TimeSeriesSplit(n_splits=5),
        random_state=42,
        n_jobs=-1,
        verbose=0,
    )

    search.fit(X_train, y_train)
    best_xgb = search.best_estimator_
    print(f"  -> Best XGBoost params: {search.best_params_}")

    xgb_probs = best_xgb.predict_proba(X_test)[:, 1]
    xgb_auc = roc_auc_score(y_test, xgb_probs)
    print(f"  -> XGBoost ROC AUC: {xgb_auc:.4f}")

    # ============================
    # 2. SHAP Feature Pruning
    # ============================
    features_used = list(X.columns)
    if enable_shap:
        try:
            import shap
            print(f"  -> Running SHAP analysis...")
            explainer = shap.TreeExplainer(best_xgb)
            shap_values = explainer.shap_values(X_test)
            
            mean_abs_shap = np.abs(shap_values).mean(axis=0)
            feature_importance = dict(zip(X.columns, mean_abs_shap))
            
            # Sort by importance
            sorted_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
            print(f"  -> SHAP Feature Importance:")
            for fname, fval in sorted_features:
                print(f"     {fname}: {fval:.4f}")
            
            # Prune features with < 1% of max importance (noise)
            max_importance = sorted_features[0][1] if sorted_features else 1.0
            threshold = max_importance * 0.01
            pruned = [f for f, v in sorted_features if v >= threshold]
            dropped = [f for f, v in sorted_features if v < threshold]
            
            if dropped:
                print(f"  -> SHAP pruning dropped: {dropped}")
                features_used = pruned
                
                # Retrain with pruned features
                X_train_pruned = X_train[pruned]
                X_test_pruned = X_test[pruned]
                
                search_pruned = RandomizedSearchCV(
                    xgb.XGBClassifier(random_state=42, eval_metric="logloss", scale_pos_weight=scale_weight),
                    param_distributions=param_grid,
                    n_iter=15,
                    scoring='roc_auc',
                    cv=TimeSeriesSplit(n_splits=5),
                    random_state=42,
                    n_jobs=-1,
                    verbose=0,
                )
                search_pruned.fit(X_train_pruned, y_train)
                best_xgb_pruned = search_pruned.best_estimator_
                
                pruned_probs = best_xgb_pruned.predict_proba(X_test_pruned)[:, 1]
                pruned_auc = roc_auc_score(y_test, pruned_probs)
                print(f"  -> Pruned XGBoost AUC: {pruned_auc:.4f} (was {xgb_auc:.4f})")
                
                # Only use pruned model if it's not significantly worse
                if pruned_auc >= xgb_auc - 0.005:
                    best_xgb = best_xgb_pruned
                    xgb_probs = pruned_probs
                    xgb_auc = pruned_auc
                    print(f"  -> Using pruned model (AUC improved or within tolerance)")
                else:
                    features_used = list(X.columns)
                    print(f"  -> Keeping full feature set (pruned AUC too low)")
            else:
                print(f"  -> No features pruned (all are significant)")
        except ImportError:
            print(f"  -> SHAP not installed, skipping feature pruning")

    # ============================
    # 3. LightGBM Ensemble
    # ============================
    ensemble_probs = xgb_probs
    if enable_ensemble:
        try:
            import lightgbm as lgb
            print(f"  -> Training LightGBM ensemble member...")
            
            lgb_model = lgb.LGBMClassifier(
                n_estimators=200,
                learning_rate=0.05,
                max_depth=5,
                subsample=0.8,
                colsample_bytree=0.8,
                scale_pos_weight=scale_weight,
                random_state=42,
                verbose=-1,
            )
            
            X_train_ens = X_train[features_used] if features_used != list(X.columns) else X_train
            X_test_ens = X_test[features_used] if features_used != list(X.columns) else X_test
            
            lgb_model.fit(X_train_ens, y_train)
            lgb_probs = lgb_model.predict_proba(X_test_ens)[:, 1]
            lgb_auc = roc_auc_score(y_test, lgb_probs)
            print(f"  -> LightGBM ROC AUC: {lgb_auc:.4f}")
            
            # Average ensemble
            ensemble_probs = 0.6 * xgb_probs + 0.4 * lgb_probs
            ensemble_auc = roc_auc_score(y_test, ensemble_probs)
            print(f"  -> Ensemble ROC AUC: {ensemble_auc:.4f}")
            
            # Save LightGBM model
            lgb_path = MODELS_DIR / f"lightgbm_{model_type}.txt"
            lgb_model.booster_.save_model(str(lgb_path))
            print(f"  -> Saved LightGBM model to {lgb_path}")
            
        except ImportError:
            print(f"  -> LightGBM not installed, skipping ensemble")

    # ============================
    # 4. Probability Calibration
    # ============================
    if enable_calibration:
        print(f"  -> Calibrating probabilities (isotonic regression)...")
        try:
            calibrated_model = CalibratedClassifierCV(best_xgb, method='isotonic', cv=3)
            X_train_cal = X_train[features_used] if features_used != list(X.columns) else X_train
            X_test_cal = X_test[features_used] if features_used != list(X.columns) else X_test
            calibrated_model.fit(X_train_cal, y_train)
            
            cal_probs = calibrated_model.predict_proba(X_test_cal)[:, 1]
            cal_auc = roc_auc_score(y_test, cal_probs)
            print(f"  -> Calibrated ROC AUC: {cal_auc:.4f}")
            
            # Save calibration info
            cal_metadata = {
                "calibration_method": "isotonic",
                "calibrated_auc": float(cal_auc),
                "uncalibrated_auc": float(xgb_auc),
            }
        except Exception as e:
            print(f"  -> Calibration failed: {e}")
            cal_metadata = {"calibration_method": "none"}
    else:
        cal_metadata = {"calibration_method": "none"}

    # ============================
    # 5. Final Evaluation
    # ============================
    final_preds = (ensemble_probs >= 0.5).astype(int)
    final_acc = accuracy_score(y_test, final_preds)
    final_auc = roc_auc_score(y_test, ensemble_probs)
    
    print(f"\n  {'='*50}")
    print(f"  FINAL RESULTS ({model_type})")
    print(f"  {'='*50}")
    print(f"  Accuracy: {final_acc:.4f}")
    print(f"  ROC AUC:  {final_auc:.4f}")
    print(f"  Features: {len(features_used)}")
    print(classification_report(y_test, final_preds, zero_division=0))

    # Save XGBoost model
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = MODELS_DIR / filename
    best_xgb.save_model(str(out_path))
    print(f"  -> Saved XGBoost model to {out_path}")

    # Save model metadata
    metadata = {
        "model_type": model_type,
        "features_used": features_used,
        "sample_count": len(X),
        "train_count": len(X_train),
        "test_count": len(X_test),
        "best_params": search.best_params_,
        "xgb_auc": float(xgb_auc),
        "final_auc": float(final_auc),
        "final_accuracy": float(final_acc),
        "scale_pos_weight": float(scale_weight),
        "class_balance": {"positive": int(pos_count), "negative": int(neg_count)},
        **cal_metadata,
    }
    
    metadata_path = MODELS_DIR / f"metadata_{model_type}.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2, default=str)
    print(f"  -> Saved model metadata to {metadata_path}")


if __name__ == "__main__":
    main()
