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

_EGX30_CACHE = None
_REGIME_CACHE = None

def get_egx30_data(lookback_days=1000) -> pd.DataFrame:
    global _EGX30_CACHE
    if _EGX30_CACHE is None:
        try:
            ticker = yf.Ticker("COMI.CA")
            df = ticker.history(period=f"{lookback_days}d")
            if df.empty:
                logger.warning("Could not fetch EGX30 data from Yahoo.")
                _EGX30_CACHE = df
                return df
            _EGX30_CACHE = df.dropna()
        except Exception as e:
            logger.error(f"Error fetching EGX30: {e}")
            _EGX30_CACHE = pd.DataFrame()
            return _EGX30_CACHE
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
        if len(df) < 20:
            return "Unknown"
            
        # Feature Engineering for HMM
        df["Return"] = np.log(df["Close"] / df["Close"].shift(1))
        df["Volatility"] = df["Return"].rolling(window=10).std()
        df = df.dropna()
        
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
                
            # Sort states by return
            state_profiles.sort(key=lambda x: x["return"])
            
            # Lowest return = Bear
            # Middle return = Sideways
            # Highest return = Bull
            if self.n_components == 3:
                self.regime_labels[state_profiles[0]["state"]] = "Bear Volatile"
                self.regime_labels[state_profiles[1]["state"]] = "Sideways Chop"
                self.regime_labels[state_profiles[2]["state"]] = "Bull Trend"
            
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
        global _REGIME_CACHE
        if _REGIME_CACHE is not None:
            return _REGIME_CACHE
            
        if self.model is None:
            self.train_and_detect()
            
        _REGIME_CACHE = {
            "regime": self.latest_regime,
            "confidence": self.latest_regime_prob
        }
        return _REGIME_CACHE
