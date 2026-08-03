import pandas as pd
import numpy as np
import lightgbm as lgb
from pathlib import Path
from praecursor.storage.price_cache import PriceCache
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def train_mae_model():
    base_dir = Path(__file__).resolve().parents[3]
    csv_path = base_dir / "reports" / "backtest_signals.csv"
    
    if not csv_path.exists():
        logger.error(f"Cannot find {csv_path}. Run a backtest first.")
        return
        
    df = pd.read_csv(csv_path)
    
    # We only care about positive swing setups where we actually need a stop loss
    df = df[df["swing_score"] >= 50.0].copy()
    if df.empty:
        logger.error("No valid swing signals found for training.")
        return
        
    logger.info(f"Loaded {len(df)} positive swing signals for MAE calculation.")
    
    db_path = base_dir / "database" / "praecursor.db"
    cache = PriceCache(db_path=str(db_path))
    
    maes = []
    
    for _, row in df.iterrows():
        symbol = row["symbol"]
        entry_date = pd.to_datetime(row["signal_date"]).date()
        entry_close = row["entry_close"]
        
        try:
            # Get 40 days of history after the signal date to ensure we capture 20 trading days
            end_date = entry_date + pd.Timedelta(days=40)
            bars = cache.load(symbol, "yahoo_finance", entry_date, end_date)
            
            # Find the index of the entry date
            entry_idx = -1
            for i, b in enumerate(bars):
                if b.date.date() == entry_date:
                    entry_idx = i
                    break
                    
            if entry_idx == -1 or entry_idx + 1 >= len(bars):
                maes.append(np.nan)
                continue
                
            # Next 20 trading days
            future_bars = bars[entry_idx + 1 : entry_idx + 21]
            if not future_bars:
                maes.append(np.nan)
                continue
                
            min_low = min(b.low for b in future_bars)
            mae_pct = ((entry_close - min_low) / entry_close) * 100.0
            
            # MAE is typically a positive number representing the percentage drop
            # Example: entry 100, min low 95 -> mae = 5%
            maes.append(mae_pct)
        except Exception as e:
            maes.append(np.nan)
            
    df["mae_pct"] = maes
    df = df.dropna(subset=["mae_pct"])
    
    logger.info(f"Calculated MAE for {len(df)} signals.")
    
    features = [
        "rsi14", "rel_volume20", "macd_histogram", "momentum20", "breakout20", "breakout50",
        "rsi_rebound", "ema20_reclaim", "macd_histogram_improvement", "volume_spike_from_weakness", "momentum5", "bbw20",
        "mtf_trend", "vpoc_distance", "adx14", "roc10", "stoch_rsi", "vwap_mom10"
    ]
    
    # Filter features that exist in the dataframe
    actual_features = [f for f in features if f in df.columns]
    
    X = df[actual_features]
    y = df["mae_pct"]
    
    logger.info(f"Training LightGBM Regressor with {len(actual_features)} features on {len(X)} samples.")
    
    model = lgb.LGBMRegressor(
        n_estimators=150,
        learning_rate=0.05,
        max_depth=5,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42
    )
    
    model.fit(X, y)
    
    model_path = base_dir / "models" / "lightgbm_mae.txt"
    model_path.parent.mkdir(exist_ok=True)
    model.booster_.save_model(str(model_path))
    
    logger.info(f"MAE Regressor saved to {model_path}")
    
    # Calculate Mean Absolute Error of our MAE predictions
    preds = model.predict(X)
    error = np.mean(np.abs(y - preds))
    logger.info(f"Training Error (Mean Absolute Error): {error:.2f}%")

if __name__ == "__main__":
    train_mae_model()
