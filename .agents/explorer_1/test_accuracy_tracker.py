import sys
from praecursor.analysis.accuracy_tracker import AccuracyTracker

tracker = AccuracyTracker()
print("Before update:")
print(tracker.get_accuracy_stats()['next_day'])

tracker.update_historical_outcomes()

print("\nAfter update:")
stats = tracker.get_accuracy_stats()
print(f"Total: {stats['next_day']['total']}, Hits: {stats['next_day']['hits']}, Accuracy: {stats['next_day']['accuracy']:.2f}%")
print("\nHistory records count:", len(stats['history']))
for h in stats['history']:
    print(h)
