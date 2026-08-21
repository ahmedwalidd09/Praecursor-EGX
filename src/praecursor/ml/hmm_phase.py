import sqlite3
import pandas as pd
import numpy as np
import pickle
from pathlib import Path
import logging

try:
    from hmmlearn.hmm import GaussianHMM
    HAS_HMM = True
except ImportError:
    HAS_HMM = False

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "database" / "praecursor.db"
MODELS_DIR = ROOT / "models"
MODEL_PATH = MODELS_DIR / "hmm_model.pkl"

def get_hmm_features_from_prices(prices_df):
    """Calculate daily returns and volume variance."""
    df = prices_df.copy()
    df['return'] = df['close'].pct_change()
    df['vol_var'] = df['volume'].rolling(5).var()
    df = df.dropna()
    if len(df) == 0:
        return np.array([])
    return df[['return', 'vol_var']].values

def get_hmm_features_from_stock(stock):
    closes = [b.close for b in stock.history]
    volumes = [b.volume for b in stock.history]
    df = pd.DataFrame({'close': closes, 'volume': volumes})
    return get_hmm_features_from_prices(df)

def train_hmm():
    if not HAS_HMM:
        logger.warning("hmmlearn not installed, skipping HMM training.")
        return
        
    logger.info("Training HMM...")
    query = "SELECT ticker, trade_date, close, volume FROM source_prices ORDER BY ticker, trade_date"
    try:
        with sqlite3.connect(DB_PATH) as conn:
            df = pd.read_sql(query, conn)
    except Exception as e:
        logger.error(f"Failed to load prices for HMM: {e}")
        return
        
    X_all = []
    lengths = []
    for ticker, group in df.groupby('ticker'):
        group = group.sort_values('trade_date')
        feats = get_hmm_features_from_prices(group)
        if len(feats) > 10:
            # fillna with 0 in case of infinite/NaN variances
            feats = np.nan_to_num(feats)
            X_all.append(feats)
            lengths.append(len(feats))
            
    if not X_all:
        logger.warning("No data for HMM.")
        return
        
    X = np.concatenate(X_all)
    model = GaussianHMM(n_components=3, covariance_type="diag", n_iter=100, random_state=42)
    model.fit(X, lengths)
    
    # Identify the states: Accumulation, Markup, Distribution
    means_ret = model.means_[:, 0]
    means_vol = model.means_[:, 1]
    
    markup_idx = int(np.argmax(means_ret))
    
    other_indices = [i for i in range(3) if i != markup_idx]
    if means_vol[other_indices[0]] > means_vol[other_indices[1]]:
        dist_idx = int(other_indices[0])
        acc_idx = int(other_indices[1])
    else:
        dist_idx = int(other_indices[1])
        acc_idx = int(other_indices[0])
        
    state_map = {
        acc_idx: 'Accumulation',
        markup_idx: 'Markup',
        dist_idx: 'Distribution'
    }
    
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, 'wb') as f:
        pickle.dump({'model': model, 'state_map': state_map}, f)
        
    logger.info(f"Saved HMM model to {MODEL_PATH}")

def predict_hmm_state(stock):
    if not HAS_HMM:
        return 'Unknown'
        
    if not MODEL_PATH.exists():
        return 'Unknown'
        
    try:
        with open(MODEL_PATH, 'rb') as f:
            data = pickle.load(f)
            model = data['model']
            state_map = data['state_map']
            
        feats = get_hmm_features_from_stock(stock)
        if len(feats) == 0:
            return 'Unknown'
            
        feats = np.nan_to_num(feats)
        state = model.predict(feats)[-1]
        return state_map.get(state, 'Unknown')
    except Exception as e:
        logger.error(f"HMM prediction failed: {e}")
        return 'Unknown'
