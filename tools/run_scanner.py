from praecursor.cli.scanner import main
from praecursor.analysis.accuracy_tracker import AccuracyTracker

if __name__ == "__main__":
    result = main()
    print("Updating accuracy tracker...")
    try:
        AccuracyTracker().update_historical_outcomes()
        print("Accuracy tracker updated successfully.")
    except Exception as e:
        print(f"Failed to update accuracy tracker: {e}")
    raise SystemExit(result)
