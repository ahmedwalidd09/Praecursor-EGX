# Praecursor-EGX Deep CodeGraph & Symbol Map

## 1. Feature Map (ML & Scorer)

The ML ensemble (`models/xgboost_next_day.json` and `models/lightgbm_next_day.txt`) consumes 34 synchronized features:

| Indicator Key | Feature Name | Description |
| :--- | :--- | :--- |
| `RSI14` | `rsi14` | 14-period Relative Strength Index |
| `RelVolume20` | `rel_volume20` | Current volume / 20-day SMA volume |
| `MACDHistogram` | `macd_histogram` | MACD - Signal line difference |
| `Momentum20` | `momentum20` | 20-day rate of change (%) |
| `Breakout20` | `breakout20` | 1.0 if close broke 20-day high |
| `Breakout50` | `breakout50` | 1.0 if close broke 50-day high |
| `RSIRebound` | `rsi_rebound` | RSI crossed above 30 from oversold |
| `EMA20Reclaim` | `ema20_reclaim` | Close crossed above 20 EMA |
| `MACDHistogramImprovement` | `macd_histogram_improvement` | Positive slope in histogram |
| `VolumeSpikeFromWeakness` | `volume_spike_from_weakness` | Volume spike on green bar after selloff |
| `Momentum5` | `momentum5` | 5-day rate of change (%) |
| `BBW20` | `bbw20` | Bollinger Band width (volatility compression) |
| `MTF_Trend` | `mtf_trend` | Multi-timeframe trend score |
| `VPOC_Distance` | `vpoc_distance` | Distance to Volume Point of Control |
| `ADX14` | `adx14` | Average Directional Index (trend strength) |
| `ROC10` | `roc10` | 10-day Rate of Change |
| `StochRSI` | `stoch_rsi` | Stochastic RSI (0-100) |
| `VWAPMom10` | `vwap_mom10` | VWAP 10-bar momentum |
| `AvgTurnover20` | `avg_turnover_20` | 20-day average cash turnover (EGP) |
| `ClosedAtLimitUp` | `closed_at_limit_up` | 1.0 if closed at +10% or +20% circuit breaker |
| `ATRPercent14` | `atr_pct14` | 14-period ATR / Close (%) |
| `OpportunityScorePct` | `opp_score_pct` | Total base opportunity score (0-100) |
| `NearCloseHigh250Percent` | `near_high250_pct` | Closeness to 52-week closing high |
| `CMF20` | `cmf20` | Chaikin Money Flow (20-period) |
| `MFI14` | `mfi14` | Money Flow Index (14-period) |
| `RS_vs_EGX30_50` | `rs_vs_index` | Relative Strength vs EGX30 benchmark |
| `VolumeConfirmedBreakout` | `vol_confirmed_breakout` | Breakout + RelVolume > 1.5x |
| `WilliamsR14` | `williams_r14` | Williams %R momentum |
| `KCSqueeze20` | `kc_squeeze20` | Bollinger Bands inside Keltner Channel |
| `Ichimoku_Score` | `ichimoku_score` | Tenkan/Kijun/Cloud alignment score |
| `ElderRay_Score` | `elder_ray_score` | Bull/Bear power score |
| `ClosingAggression` | `closing_aggression` | Close location relative to daily range (0-100) |
| `NR7_Compression` | `nr7_compression` | 100 if Narrowest Range of 7 days |
| `VSA_Absorption` | `vsa_absorption` | Volume Spread Analysis absorption score |
| `SectorSpillover` | `sector_spillover` | Sector peer strength correlation |

---

## 2. Notification Pipeline Call Sequence

1. `tools/run_autonomous_pipeline.py` executes Stage 4: `tools/send_telegram_report.py --use-latest`
2. `praecursor.cli.telegram.main()` calls `TelegramReportFormatter.format_scanner_result()`
3. Formatter dynamically inspects `reports/dashboard.html` for exact parity, or evaluates `ScannerRunResult` / database record with live ATR TP/SL and Half-Kelly sizing
4. `TelegramClient.send_message()` delivers HTML message with 3-attempt exponential backoff to `Chat ID 8196296723`.
