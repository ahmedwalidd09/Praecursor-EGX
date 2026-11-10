"""Train and promote only feature-compatible, chronologically validated models."""
import argparse
import logging
import sqlite3
from contextlib import closing
import json
import hashlib
from importlib.metadata import version
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from praecursor.ml.features import FEATURES, INDICATOR_TO_FEATURE, FEATURE_VERSION
from praecursor.analysis.outcomes import LABEL_VERSION
from praecursor.ml.validation import train_validate
import pandas as pd


def dataset_is_current(metadata, latest, price_rows, last_collection):
    return (metadata.get("feature_version") == FEATURE_VERSION
            and metadata.get("label_version") == LABEL_VERSION
            and metadata.get("last_source_session") == latest
            and metadata.get("price_rows") == price_rows
            and metadata.get("last_collection") == last_collection)


def train_published_if_changed(frame, horizon):
    # Include pending sessions: they affect chronological split/maturity boundaries.
    columns = [c for c in frame.columns if not c.startswith(("next_day_", "swing_")) or c.startswith(horizon + "_")]
    stable = frame[sorted(columns)].sort_values(["session", "symbol"]).reset_index(drop=True)
    digest = hashlib.sha256(stable.to_csv(index=False).encode())
    for name in ("src/praecursor/ml/validation.py", "src/praecursor/ml/features.py",
                 "src/praecursor/analysis/outcomes.py", "tools/retrain_models.py"):
        digest.update((ROOT / name).read_bytes())
    for package in ("pandas", "numpy", "scikit-learn", "xgboost", "lightgbm"):
        digest.update(version(package).encode())
    fingerprint = digest.hexdigest()
    path = ROOT / "reports" / f"{horizon}_validation.json"
    previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    incumbent_available = not previous.get("promoted") or (ROOT / "models" / f"active_{horizon}.json").exists()
    if previous.get("input_fingerprint") == fingerprint and incumbent_available:
        return dict(previous, reused_validation=True)
    report = train_validate(frame, horizon, input_fingerprint=fingerprint)
    report["input_fingerprint"] = fingerprint
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--rebuild",action="store_true")
    parser.add_argument("--published-only",action="store_true",help="Train only from exported, verified published predictions.")
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    database=ROOT/"database/praecursor.db"
    if args.published_only:
        frame=pd.read_csv(ROOT/"data/published_samples.csv")
    elif not database.exists():
        raise SystemExit("Database unavailable; run the scanner first")
    else:
        from praecursor.ml.research import build_dataset, DATASET
        with closing(sqlite3.connect(database.as_uri()+"?mode=ro",uri=True)) as c:
            latest=c.execute("SELECT max(date(trade_date)) FROM source_prices WHERE source!='mubasher'").fetchone()[0]
            price_rows,last_collection=c.execute("SELECT count(*),max(collected_at) FROM source_prices").fetchone()
        metadata=json.loads(DATASET.with_suffix(".meta.json").read_text()) if DATASET.with_suffix(".meta.json").exists() else {}
        if args.rebuild or not DATASET.exists() or not dataset_is_current(metadata,latest,price_rows,last_collection):
            build_dataset(database)
        frame=pd.read_csv(DATASET)
    for horizon in ("next_day","swing"):
        report=train_published_if_changed(frame,horizon) if args.published_only and not args.rebuild else train_validate(frame,horizon)
        print(json.dumps({k:report.get(k) for k in ("horizon","status","promoted","reason","promotion_reasons","metrics","reused_validation")},indent=2))


if __name__=="__main__":
    main()
