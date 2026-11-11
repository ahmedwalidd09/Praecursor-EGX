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
    from contextlib import closing
    from praecursor.storage.database import connect
    from praecursor.analysis.research import measurement_samples, save_research
    with closing(connect(ROOT / "database/praecursor.db")) as conn:
        from praecursor.analysis.data_quality import audit_data
        from praecursor.analysis.shadow_experiments import resolve_shadows
        quality = audit_data(conn)
        experiments = resolve_shadows(conn)
        research = save_research(conn, measurement_samples(conn))
    (ROOT / "reports/data_quality.json").write_text(json.dumps(quality, indent=2), encoding="utf-8")
    (ROOT / "reports/shadow_experiments.json").write_text(json.dumps(experiments, indent=2), encoding="utf-8")
    (ROOT / "reports/research_evidence.json").write_text(json.dumps(research, indent=2), encoding="utf-8")
    (ROOT / "reports/learning_feedback.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
