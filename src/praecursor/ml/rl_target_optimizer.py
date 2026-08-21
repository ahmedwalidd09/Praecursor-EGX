import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pandas as pd
import sqlite3
from pathlib import Path
import logging

try:
    from stable_baselines3 import PPO
    HAS_SB3 = True
except ImportError:
    HAS_SB3 = False

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "database" / "praecursor.db"
MODELS_DIR = ROOT / "models"

class EGXTradingEnv(gym.Env):
    """
    Custom Environment that follows gym interface.
    Optimizes dynamic target and stop loss multipliers based on stock features.
    """
    metadata = {"render_modes": ["human"]}

    def __init__(self, data: pd.DataFrame):
        super(EGXTradingEnv, self).__init__()
        self.data = data.reset_index(drop=True)
        self.current_step = 0
        self.max_steps = len(self.data) - 1

        # Observations: next_day_score, atr_pct14, VWAPDivergence15m, EODAccumulation, bull_prob, bear_prob, regime_score
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(7,), dtype=np.float32
        )

        # Actions: target_multiplier [1.0, 5.0], stop_multiplier [0.5, 3.0]
        # Box requires scaled space typically [-1, 1], so we map it later.
        self.action_space = spaces.Box(
            low=np.array([1.0, 0.5]), high=np.array([5.0, 3.0]), dtype=np.float32
        )

    def _get_obs(self):
        row = self.data.iloc[self.current_step]
        return np.array([
            row["next_day_score"],
            row["atr_pct14"],
            row["vwap_divergence"],
            row["eod_accumulation"],
            row["bull_prob"],
            row["bear_prob"],
            row["regime_score"]
        ], dtype=np.float32)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        return self._get_obs(), {}

    def step(self, action):
        if self.current_step > self.max_steps:
            return self._get_obs(), 0, True, False, {}

        row = self.data.iloc[self.current_step]
        
        target_mult = action[0]
        stop_mult = action[1]

        # Reward formulation based on scanner_signal_outcomes
        # If it hit the target in historical data, reward scaled by target_mult
        hit = row["next_day_hit"]
        # Simplified reward: if historical outcome was a hit, higher target gets higher reward (up to a point)
        # Assuming higher target carries more risk
        
        if hit == 1:
            reward = target_mult - (stop_mult * 0.5)
        else:
            reward = -stop_mult
            
        self.current_step += 1
        done = self.current_step >= self.max_steps
        truncated = False
        
        return self._get_obs(), reward, done, truncated, {}


def train_rl_optimizer():
    if not HAS_SB3:
        logger.error("stable-baselines3 is not installed.")
        return

    query = """
    SELECT 
        o.next_day_hit,
        s.latest_close,
        s.indicator_values_json
    FROM scanner_signals s
    JOIN scanner_signal_outcomes o ON s.run_id = o.run_id AND s.symbol = o.symbol
    WHERE o.next_day_hit IS NOT NULL
    """
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            df = pd.read_sql(query, conn)
    except Exception as e:
        logger.error(f"Failed to load database: {e}")
        return
        
    if df.empty:
        logger.warning("No outcome data available for RL training.")
        return

    # Extract features
    features_list = []
    import json
    for _, row in df.iterrows():
        try:
            vals = json.loads(row["indicator_values_json"]) if row["indicator_values_json"] else {}
            features_list.append({
                "next_day_score": 50.0, # Placeholder since we don't recalculate the full score here
                "atr_pct14": vals.get("ATRPercent14", 0.0) or 0.0,
                "vwap_divergence": vals.get("VWAPDivergence15m", 0.0) or 0.0,
                "eod_accumulation": vals.get("EODAccumulation", 0.0) or 0.0,
                "bull_prob": 0.5,
                "bear_prob": 0.5,
                "regime_score": 1.0,
                "next_day_hit": row["next_day_hit"]
            })
        except Exception:
            continue
            
    if not features_list:
        logger.warning("No valid features for RL.")
        return

    data = pd.DataFrame(features_list)
    env = EGXTradingEnv(data)

    logger.info("Training PPO RL Target Optimizer...")
    model = PPO("MlpPolicy", env, verbose=0, n_steps=1024, learning_rate=3e-4)
    model.learn(total_timesteps=10000)
    
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODELS_DIR / "rl_target_agent.zip"
    model.save(str(model_path))
    logger.info(f"Saved RL agent to {model_path}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    train_rl_optimizer()
