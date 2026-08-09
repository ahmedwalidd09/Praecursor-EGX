import argparse
import sys
from pathlib import Path
import json

from praecursor.analysis.indicator_attribution import IndicatorAttributionAnalyzer
from praecursor.storage.signal_history import SignalHistoryStore

def main():
    parser = argparse.ArgumentParser(description="Praecursor Backtesting & Indicator Optimization Tool")
    parser.add_argument("--db", default=None, help="Path to database (defaults to environment/standard path)")
    args = parser.parse_args()
    
    # Trigger DB migrations if needed
    SignalHistoryStore(database_path=args.db)

    print("==========================================================")
    print(" PRAECURSOR-EGX: INDICATOR ATTRIBUTION & OPTIMIZATION     ")
    print("==========================================================")
    print("Analyzing historical signals to determine which score components")
    print("have the highest predictive power for next-day hit rate...\n")

    analyzer = IndicatorAttributionAnalyzer(database_path=args.db)
    results = analyzer.analyze_components()

    if not results:
        print("No historical data available. Run the autonomous pipeline over a few days first.")
        return 1

    print(f"{'Indicator Component':<25} | {'Hit Avg':<7} | {'Miss Avg':<8} | {'Power':<6} | {'Signal %':<8}")
    print("-" * 65)
    
    for name, stats in results.items():
        hit_avg = stats['avg_score_on_hit']
        miss_avg = stats['avg_score_on_miss']
        power = stats['predictive_power']
        signal = stats['signal_strength']
        
        # Colorize signal
        if signal > 15:
            sig_str = f"\033[92m+{signal:.1f}%\033[0m" # Green
        elif signal < -5:
            sig_str = f"\033[91m{signal:.1f}%\033[0m" # Red
        else:
            sig_str = f"{signal:+.1f}%" # Neutral

        print(f"{name:<25} | {hit_avg:<7.1f} | {miss_avg:<8.1f} | {power:<+6.1f} | {sig_str:<8}")
        
    print("-" * 65)
    print("\nInterpretation:")
    print(" - 'Power' is the absolute difference in score between a HIT and a MISS.")
    print(" - 'Signal %' normalizes Power by the maximum possible allocation for that component.")
    print(" - High positive Signal % (> 15%) means the indicator strongly predicts success.")
    print(" - Negative Signal % means the indicator is actually inverted (predicts failure) or noisy.")
    print("\nRecommendation: Consider reducing weights (max_score) for components with negative or near-zero Signal %.")

    return 0

if __name__ == "__main__":
    sys.exit(main())
