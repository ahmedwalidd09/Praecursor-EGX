import re

with open("src/praecursor/scoring/regime.py", "r") as f:
    content = f.read()

# Replace global vars
global_vars_pattern = re.compile(r"_EGX30_CACHE = None\n_REGIME_CACHE = None", re.MULTILINE)
new_global_vars = """import time

_EGX30_CACHE = None
_EGX30_CACHE_TIME = 0

_REGIME_CACHE = None
_REGIME_CACHE_TIME = 0
_REGIME_CACHE_TTL = 14400  # 4 hours in seconds"""
content = global_vars_pattern.sub(new_global_vars, content)

# Replace get_egx30_data
get_egx30_data_pattern = re.compile(r"def get_egx30_data\(lookback_days=1000\) -> pd\.DataFrame:.*?return _EGX30_CACHE", re.DOTALL)
new_get_egx30_data = """def get_egx30_data(lookback_days=1000) -> pd.DataFrame:
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
        _EGX30_CACHE = df.dropna()
        _EGX30_CACHE_TIME = time.time()
    except Exception as e:
        logger.error(f"Error fetching EGX30: {e}")
        _EGX30_CACHE = pd.DataFrame()
        _EGX30_CACHE_TIME = time.time()
    return _EGX30_CACHE"""
content = get_egx30_data_pattern.sub(new_get_egx30_data, content)

# Replace get_latest_regime
get_latest_regime_pattern = re.compile(r"def get_latest_regime\(self\) -> dict:.*?return _REGIME_CACHE", re.DOTALL)
new_get_latest_regime = """def get_latest_regime(self) -> dict:
        global _REGIME_CACHE, _REGIME_CACHE_TIME
        if _REGIME_CACHE is not None and (time.time() - _REGIME_CACHE_TIME) < _REGIME_CACHE_TTL:
            return _REGIME_CACHE
            
        self.train_and_detect()
            
        _REGIME_CACHE = {
            "regime": self.latest_regime,
            "confidence": self.latest_regime_prob
        }
        _REGIME_CACHE_TIME = time.time()
        return _REGIME_CACHE"""
content = get_latest_regime_pattern.sub(new_get_latest_regime, content)

with open("src/praecursor/scoring/regime.py", "w") as f:
    f.write(content)
