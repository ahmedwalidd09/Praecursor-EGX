#!/usr/bin/env python3
"""
tools/predict_kronos.py

Standalone CLI tool to run inference with the Kronos Candlestick Foundation Model
(v6.3 Institutional Alpha) for any EGX symbol.

Usage:
    python tools/predict_kronos.py --symbol AIH
"""

import argparse
import sys
from pathlib import Path

# Ensure repo root is on sys.path
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from praecursor.ml.kronos_forecaster import (
    predict_next_candle,
    fetch_historical_prices,
    KronosPrediction,
)


def main():
    parser = argparse.ArgumentParser(
        description="Forecast next-day financial candlestick using Kronos Foundation Model (v6.3)"
    )
    parser.add_argument(
        "--symbol",
        "-s",
        type=str,
        default="AIH",
        help="EGX symbol to forecast (e.g. AIH, EBSC, AMOC)",
    )
    parser.add_argument(
        "--history-bars",
        type=int,
        default=5,
        help="Number of recent historical bars to display (default: 5)",
    )

    args = parser.parse_args()
    symbol = args.symbol.upper().strip()

    print("=" * 72)
    print(f"🏛  PRAECURSOR-EGX // KRONOS FOUNDATION MODEL (v6.3 Institutional Alpha)")
    print(f"   Candlestick Forecaster for Symbol: {symbol}")
    print("=" * 72)

    # 1. Fetch recent history for display
    history_df = fetch_historical_prices(symbol, lookback=100)
    if history_df is None or history_df.empty:
        print(f"\n❌ Error: No price history found in database for ticker '{symbol}'.")
        print("   Please ensure prices are collected or run scanner first.")
        sys.exit(1)

    recent_bars = history_df.tail(args.history_bars)
    current_close = float(recent_bars["close"].iloc[-1])
    last_date = str(recent_bars["trade_date"].iloc[-1])

    print(f"\n📊 Recent Daily OHLCV History (Last {len(recent_bars)} bars, ending {last_date}):")
    print(f"{'Date':<12} {'Open':>10} {'High':>10} {'Low':>10} {'Close':>10} {'Volume':>14}")
    print("-" * 72)
    for _, row in recent_bars.iterrows():
        print(
            f"{str(row['trade_date']):<12} "
            f"{row['open']:>10.3f} "
            f"{row['high']:>10.3f} "
            f"{row['low']:>10.3f} "
            f"{row['close']:>10.3f} "
            f"{int(row['volume']):>14,}"
        )
    print("-" * 72)
    print(f"Current Reference Close: {current_close:.3f} EGP")

    # 2. Run Kronos Foundation Model Inference
    print(f"\n🔮 Generating Kronos autoregressive forecast for next daily candle...")
    prediction: KronosPrediction | None = predict_next_candle(symbol, history_df=history_df)

    if prediction is None or not prediction.is_valid:
        print(f"\n⚠️ Kronos Prediction unavailable (model offline or insufficient data).")
        sys.exit(1)

    dir_icon = "🟢" if prediction.direction == "BULLISH" else "🔴"
    ret_sign = "+" if prediction.expected_return_pct >= 0 else ""

    print("\n" + "=" * 72)
    print(f"🎯 KRONOS NEXT-DAY CANDLE FORECAST ({symbol})")
    print("=" * 72)
    print(f"  • Direction:         {dir_icon} {prediction.direction}")
    print(f"  • Expected Return:   {ret_sign}{prediction.expected_return_pct:.2f}%")
    print(f"  • Current Close:     {prediction.current_close:.3f} EGP")
    print(f"  • Predicted Open:    {prediction.predicted_open:.3f} EGP")
    print(f"  • Predicted High:    {prediction.predicted_high:.3f} EGP (Max Upside: {((prediction.predicted_high - current_close) / current_close * 100):+.2f}%)")
    print(f"  • Predicted Low:     {prediction.predicted_low:.3f} EGP (Max Drawdown: {((prediction.predicted_low - current_close) / current_close * 100):+.2f}%)")
    print(f"  • Predicted Close:   {prediction.predicted_close:.3f} EGP")
    print("=" * 72)
    print("✨ Foundation model alignment completed.")


if __name__ == "__main__":
    main()
