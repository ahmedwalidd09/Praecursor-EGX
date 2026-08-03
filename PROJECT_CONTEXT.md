# Praecursor-EGX: Project Context & Architecture

**Welcome to Praecursor-EGX!** If you are a new AI agent reading this, this document contains everything you need to know about the architecture, workflows, and machine learning pipelines of this project.

## Project Overview
Praecursor-EGX is an automated stock screener and machine learning analysis tool specifically designed for the **Egyptian Exchange (EGX)**. It analyzes technical indicators, filters out illiquid penny stocks, evaluates market regime, and predicts next-day breakouts using an XGBoost machine learning model.

**Local Path:** `C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX`

---

## Core Architecture

### 1. Data Collection & Consensus Engine
**Files:** `src/praecursor/workflows/scanner.py`, `src/praecursor/storage/price_cache.py`, `src/praecursor/consensus/engine.py`
- Due to frequent data inaccuracies on TradingView for Egyptian stocks (e.g., returning only 1 bar or bizarre prices), the project uses a **Price Consensus Engine**.
- When `run_scanner.py` is executed, it first hits TradingView. If the data quality is poor, the consensus engine cross-references Mubasher and Investing.com. 
- If 2 out of 3 sources agree, the clean data is written back to the local `praecursor.db` (SQLite).

### 2. Technical Indicators (EGX Optimized)
**Directory:** `src/praecursor/scoring/`
- The system calculates 20 technical indicators, including EGX-specific features:
  - `AverageTurnoverIndicator` (Volume * Close) to filter out fake penny stock liquidity.
  - `LimitUpIndicator` to detect stocks that closed on the 10% or 20% circuit breakers.
- Indicators are aggregated by the `Analyzer` class inside `opportunity_score.py`.

### 3. Market Regime (EGX30)
**File:** `src/praecursor/scoring/regime.py`
- To prevent the scanner from recommending long breakouts during market crashes, it uses a Hidden Markov Model (HMM) to detect the current EGX30 market regime.
- It uses `COMI.CA` (Commercial International Bank) as a high-weight proxy for the EGX30 index.
- If the regime is `Bear`, breakout AI scores are heavily penalized.

### 4. Machine Learning Model (XGBoost)
**Files:** `src/praecursor/scoring/next_day.py`, `tools/retrain_models.py`
- The core prediction engine is an XGBoost model that evaluates the 20 technical features to predict a `next_day_hit` (a successful next-day breakout).
- **Continuous Learning:** The model is retrained locally by running `python tools/retrain_models.py`. This script extracts verified historical data and accuracy outcomes straight from `praecursor.db`, ensuring the model is trained on the exact features it predicts on.

### 5. Accuracy Tracking & Reporting
**Files:** `src/praecursor/analysis/accuracy_tracker.py`, `src/praecursor/cli/dashboard.py`
- **Hit/Miss Logic:** A stock is marked as a `HIT` if it reaches its mathematical target (1.5x ATR) OR achieves a solid intraday gain of ≥2.5% the next day.
- **Dashboard:** A local HTML dashboard is generated at `reports/dashboard.html` and served on `http://127.0.0.1:8000`.

---

## Daily Workflow
1. The user has a `Daily Praecursor Update.bat` on their desktop.
2. It starts the local dashboard server.
3. It runs `python tools/run_scanner.py` (which fetches data, cleans it, scores it, and generates the reports).
4. It runs `python tools/retrain_models.py` to instantly feed the daily hits/misses back into the XGBoost algorithm.
5. It opens the dashboard.

## Next Steps / Directives for AI Agents
If you are tasked with modifying this project:
- **DO NOT** modify the XGBoost dimensions in `next_day.py` without also updating `tools/retrain_models.py`.
- **ALWAYS** test new features by running the retraining script first to ensure dimensions align.
- **PRIORITIZE** accuracy and data integrity over UI cosmetics.
