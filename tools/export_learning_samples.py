"""Export verified published examples for the separate model-training job."""
import sys
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from praecursor.ml.published import published_samples, feedback_summary


def main():
    frame = published_samples(ROOT / "database/praecursor.db")
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "reports").mkdir(exist_ok=True)
    frame.to_csv(ROOT / "data/published_samples.csv", index=False)
    summary = feedback_summary(frame)
    (ROOT / "reports/learning_feedback.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
