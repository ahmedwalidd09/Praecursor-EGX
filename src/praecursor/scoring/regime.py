import yfinance as yf
import pandas as pd
import numpy as np
import logging
from pathlib import Path

try:
    from hmmlearn.hmm import GaussianHMM
    HAS_HMM = True
except ImportError:
    HAS_HMM = False

logger = logging.getLogger(__name__)

import time

_EGX30_CACHE = None
_EGX30_CACHE_TIME = 0

_REGIME_CACHE = None
_REGIME_CACHE_TIME = 0
_REGIME_CACHE_TTL = 14400  # 4 hours in seconds

def get_egx30_data(lookback_days=1000) -> pd.DataFrame:
    global _EGX30_CACHE, _EGX30_CACHE_TIME
    if _EGX30_CACHE is not None and (time.time() - _EGX30_CACHE_TIME) < _REGIME_CACHE_TTL:
        return _EGX30_CACHE
    try:
        ticker = yf.Ticker("COMI.CA")
        df = ticker.history(period=f"{lookback_days}d")
        if df.empty:
            logger.warning("Could not fetch EGX30 data from Yahoo.")
            _EGX30_CACHE = df
            _EGX30_CACHE_TIME = time.time()
            return df
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        _EGX30_CACHE = df.dropna()
        _EGX30_CACHE_TIME = time.time()
    except Exception as e:
        logger.error(f"Error fetching EGX30: {e}")
        _EGX30_CACHE = pd.DataFrame()
        _EGX30_CACHE_TIME = time.time()
    return _EGX30_CACHE

class MarketRegimeModel:
    def __init__(self, n_components=3, lookback_days=1000):
        self.n_components = n_components
        self.lookback_days = lookback_days
        self.model = None
        self.regime_labels = {}
        self.latest_regime = "Unknown"
        self.latest_regime_prob = 0.0
        
    def fetch_data(self) -> pd.DataFrame:
        return get_egx30_data(self.lookback_days)

    def train_and_detect(self) -> str:
        if not HAS_HMM:
            logger.warning("hmmlearn not installed. Cannot detect market regime.")
            return "Unknown"
            
        df = self.fetch_data()
        if "Close" not in df.columns or len(df) < 20:
            return "Unknown"
            
        # Feature Engineering for HMM
        df = df[df["Close"] > 0].copy()
        if len(df) < 20:
            return "Unknown"
        df["Return"] = np.log(df["Close"] / df["Close"].shift(1))
        df["Volatility"] = df["Return"].rolling(window=10).std()
        df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=["Return", "Volatility"])
        
        if len(df) < 50:
            return "Unknown"
            
        features = df[["Return", "Volatility"]].values
        
        try:
            self.model = GaussianHMM(
                n_components=self.n_components, 
                covariance_type="full", 
                n_iter=100, 
                random_state=42
            )
            self.model.fit(features)
            
            hidden_states = self.model.predict(features)
            
            # Map hidden states to Bull/Bear/Sideways based on mean return and volatility
            means = self.model.means_
            state_profiles = []
            for i in range(self.n_components):
                state_profiles.append({
                    "state": i,
                    "return": means[i][0],
                    "volatility": means[i][1]
                })
                
            volatilities = [p["volatility"] for p in state_profiles]
            median_vol = np.median(volatilities)
            
            for p in state_profiles:
                ret = p["return"]
                vol = p["volatility"]
                high_vol = vol > median_vol
                
                if abs(ret) < 0.0002:
                    label = "Sideways Chop"
                elif ret < 0:
                    label = "Bear Volatile" if high_vol else "Bear Trend"
                else:
                    label = "Bull Volatile" if high_vol else "Bull Trend"
                    
                self.regime_labels[p["state"]] = label
            
            latest_state = hidden_states[-1]
            self.latest_regime = self.regime_labels.get(latest_state, "Unknown")
            
            # Calculate probability of current state
            probs = self.model.predict_proba(features)
            self.latest_regime_prob = probs[-1][latest_state] * 100.0
            
            logger.info(f"Market Regime Detected: {self.latest_regime} ({self.latest_regime_prob:.1f}% confidence)")
            return self.latest_regime
            
        except Exception as e:
            logger.error(f"HMM Training failed: {e}")
            return "Unknown"

    def get_latest_regime(self) -> dict:
        global _REGIME_CACHE, _REGIME_CACHE_TIME
        if _REGIME_CACHE is not None and (time.time() - _REGIME_CACHE_TIME) < _REGIME_CACHE_TTL:
            return _REGIME_CACHE
            
        self.train_and_detect()
            
        _REGIME_CACHE = {
            "regime": self.latest_regime,
            "confidence": self.latest_regime_prob
        }
        _REGIME_CACHE_TIME = time.time()
        return _REGIME_CACHE

    def get_historical_regime(self, date_str: str) -> dict:
        """Label a historical date as Bull or Bear based on EGX30 close vs MA200."""
        df = self.fetch_data()
        if len(df) == 0 or "Close" not in df.columns:
            return {"regime": "Unknown", "score": 0.5}
            
        df = df[df["Close"] > 0].copy()
        df["MA200"] = df["Close"].rolling(200).mean()
        try:
            dt = pd.to_datetime(date_str)
            # Ensure index and dt are both tz-naive for robust comparison
            if hasattr(df.index, 'tz_localize') and df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            if hasattr(dt, 'tz_localize') and dt.tzinfo is not None:
                dt = dt.tz_localize(None)
                
            sub_df = df[df.index <= dt]
            if len(sub_df) == 0:
                return {"regime": "Unknown", "score": 0.5}
                
            row = sub_df.iloc[-1]
            if pd.isna(row["MA200"]):
                return {"regime": "Unknown", "score": 0.5}
                
            is_bull = row["Close"] > row["MA200"]
            return {
                "regime": "Bull" if is_bull else "Bear",
                "score": 1.0 if is_bull else 0.0
            }
        except Exception as e:
            logger.error(f"Error getting historical regime: {e}")
            return {"regime": "Unknown", "score": 0.5}
