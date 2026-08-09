# Detailed Analysis Report: Requirement R3 & Test Suite Mocking Audit

**Agent:** explorer_audit_3  
**Date:** 2026-08-07  
**Project:** Praecursor-EGX  

---

## 1. Executive Summary

This audit evaluated **Requirement R3: Low Credit Usage & Test Suite Mocking** for the Praecursor-EGX autonomous scanner pipeline.

### Key Audit Findings:
1. **Zero LLM Credit Consumption:** The Praecursor-EGX codebase contains **no external calls to cloud LLMs (Gemini, OpenAI, Anthropic, etc.)**. All machine learning scoring is powered by **local offline models** (`XGBoost`, `LightGBM`, and `PyTorch LSTM`) executing on CPU from local files in `models/`.
2. **100% Test Suite Mocking Compliance:** All unit, integration, and end-to-end tests (including `tests/e2e/test_r1_scheduling.py` and `tests/e2e/test_r3_historical_archive.py`) use synthetic datasets, `FakeMarketDataSource`, in-memory HTML fixtures, or isolated SQLite test databases (`temp_db_path`). **Zero live network or credit-burning API calls are executed during test runs.**
3. **Price Data Caching Architecture:** The pipeline features a SQLite caching layer (`PriceCache` & `SignalHistoryStore` in `data/praecursor.db`). Primary market data (`TradingViewSource`) and consensus data (`MubasherSource`, `StockAnalysisSource`) load and update cached price bars, preventing redundant downloads across daily runs.

---

## 2. LLM & ML Model Usage Audit

### 2.1 Examination of LLM APIs
* **Search Query:** `gemini`, `openai`, `anthropic`, `genai`, `gpt`, `api_key`
* **Result:** **No external LLM API dependencies** exist in `pyproject.toml` or source code.
* **Explanation:** References to "Gemini/ML models" in project prompts refer to ML prediction scoring logic. The pipeline relies on local machine learning classification models rather than remote LLMs.

### 2.2 Local Machine Learning Model Inference
* **Models Utilized:**
  * `models/xgboost_next_day.json`: XGBoost classifier predicting 1-day breakout follow-through based on 20 technical/EGX features.
  * `models/xgboost_swing.json`: XGBoost classifier predicting 10–20 bar swing continuation.
  * `models/lightgbm_next_day.txt` / `models/lightgbm_swing.txt`: Optional ensemble boosters (loaded via `lightgbm` if available).
  * `models/lstm_swing.pt`: Optional PyTorch deep learning sequence model.
* **Inference Mechanism:**
  * Model files are loaded directly into memory from disk (`Path(__file__).resolve().parents[3] / "models"`).
  * Feature vectors are built from `OpportunityScore.indicator_values` and evaluated in-memory via `model.predict_proba(df)`.
* **Cost & Credit Impact:** **$0.00 cost / 0 API credits consumed**.

---

## 3. Market Data Collection & Caching Strategy Audit

### 3.1 Data Collectors
| Collector | Module Path | Mechanism | External Network Call? |
|---|---|---|---|
| **TradingViewSource** | `src/praecursor/collectors/tradingview_source.py` | `tvDatafeed` library | Yes (during live scan runs) |
| **MubasherSource** | `src/praecursor/collectors/mubasher_source.py` | Web scraping via `urllib` HTTP | Yes (during live scan runs) |
| **StockAnalysisSource** | `src/praecursor/collectors/stockanalysis_source.py` | HTTP quote fetcher | Yes (during live scan runs) |
| **YahooFinanceSource** | `src/praecursor/collectors/yahoo_finance_source.py` | HTTP chart fetcher | Yes (during live scan runs) |
| **FakeMarketDataSource** | `src/praecursor/collectors/fake_market_data_source.py` | In-memory synthetic generator | No (100% Mocked) |

### 3.2 Caching Mechanism (`PriceCache`)
* **File:** `src/praecursor/storage/price_cache.py`
* **Database:** SQLite at `data/praecursor.db` or `database/praecursor.db`.
* **Behavior:**
  * `DataManager.fetch_history()` queries `PriceCache` first for cached daily price bars within the date range.
  * Only missing date ranges are requested from live sources.
  * `PriceCache.override_consensus_prices()` updates local cached prices if multi-source consensus corrects primary source errors.

---

## 4. Test Suite Mocking & Isolation Verification

### 4.1 Verification Matrix of Test Files

| Test File | Focus Area | Mocking Strategy | Live Network Calls? | Live Credits Used? |
|---|---|---|---|---|
| `tests/e2e/test_r1_scheduling.py` | Task Scheduler & 5 PM execution | Uses `schtasks` CLI commands & `mock_fetch_offline` NetworkError mock | No | 0 |
| `tests/e2e/test_r3_historical_archive.py` | History Archive & 16 baseline records | Isolated SQLite DB fixture (`temp_db_path`) populated in-memory | No | 0 |
| `tests/e2e/test_r2_target_verification.py` | Intraday high vs target verification | In-memory SQLite DB builder (`create_test_db_for_target_eval`) | No | 0 |
| `tests/e2e/test_r4_data_consensus.py` | Consensus Engine outlier resolution | In-memory `SourcePrice` dataclass instances | No | 0 |
| `tests/e2e/test_tier3_combinations.py` | Pairwise integration tests | Synthetic SQLite DB records & in-memory `SourcePrice` | No | 0 |
| `tests/e2e/test_tier4_scenarios.py` | Multi-day pipeline end-to-end scenarios | In-memory SQLite DB lifecycle simulations | No | 0 |
| `tests/test_scanner_workflow.py` | Scanner workflow & rank changes | `FakeMarketDataSource` + temporary SQLite DB | No | 0 |
| `tests/test_accuracy_tracker.py` | Accuracy Tracker target evaluations | Temporary SQLite DB & synthetic signal tables | No | 0 |
| `tests/test_mubasher_source.py` | Mubasher HTML parsing | Hardcoded inline HTML string fixture | No | 0 |
| `tests/test_consensus.py` | Multi-source price aggregation | In-memory `SourcePrice` lists | No | 0 |
| `tests/test_telegram.py` | Telegram message formatting | `FakeMarketDataSource` + `TelegramReportFormatter` | No | 0 |
| `tests/test_scheduled_task.py` | Runner pipeline script & stages | `unittest.mock.patch` for `run_stage` subprocesses | No | 0 |
| `tests/test_next_day.py` | Next-day prediction scoring | In-memory `OpportunityScore` objects | No | 0 |
| `tests/test_swing.py` | Swing prediction scoring | In-memory `OpportunityScore` objects | No | 0 |
| `tests/test_scoring.py` | Indicator & score calculations | Synthetic `Stock` / `PriceBar` data | No | 0 |
| `tests/test_indicators.py` | Technical indicators | Synthetic pandas / numpy series | No | 0 |
| `tests/test_backtesting.py` | Historical engine simulation | In-memory backtest datasets | No | 0 |

### 4.2 Test Execution Details & Command Recommendations
* E2E tests (`test_r1_scheduling.py` & `test_r3_historical_archive.py`) execute cleanly via `python -m pytest tests/e2e/`.
* When running pytest across all unit tests, execute `python -m pytest tests/` or set `PYTHONPATH=.` so unit tests can import `tests/helpers.py`.
* Avoid bare `pytest` from project root without target path parameters to prevent pytest from attempting to collect root-level non-test files like `scratch_test.py` or `test_results.txt`.

---

## 5. Recommendations for Optimization & Bulletproofing

1. **Explicit Pytest Network Blocking Fixture (Optional Hardening):**
   Add an `autouse` socket-disabling fixture in `tests/conftest.py` (e.g. using `monkeypatch` or `socket.socket`) to guarantee that any future tests added by developers will automatically fail if they attempt outbound HTTP socket connections.
2. **5 PM Automated Run Data Caching:**
   Ensure `run_autonomous_pipeline.py` passes appropriate lookback parameters so `DataManager` maximizes hit rate against `PriceCache`, minimizing redundant live HTTP web-scraping requests to TradingView/Mubasher.
3. **Model Retraining Optimization (`tools/retrain_models.py`):**
   When `retrain_models.py` runs during Stage 2 of the 5 PM automated pipeline, it trains XGBoost on local SQLite data and saves the updated JSON model locally without making any external API calls.

---
