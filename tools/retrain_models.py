"""Train and promote only feature-compatible, chronologically validated models."""
import argparse
import logging
import sqlite3
from contextlib import closing
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from praecursor.ml.features import FEATURES, INDICATOR_TO_FEATURE, FEATURE_VERSION
from praecursor.analysis.outcomes import LABEL_VERSION
from praecursor.ml.research import build_dataset, DATASET
from praecursor.ml.validation import train_validate
import pandas as pd


def dataset_is_current(metadata, latest, price_rows, last_collection):
    return (metadata.get("feature_version") == FEATURE_VERSION
            and metadata.get("label_version") == LABEL_VERSION
            and metadata.get("last_source_session") == latest
            and metadata.get("price_rows") == price_rows
            and metadata.get("last_collection") == last_collection)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--rebuild",action="store_true")
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    database=ROOT/"database/praecursor.db"
    if not database.exists():
        raise SystemExit("Database unavailable; run the scanner first")
    with closing(sqlite3.connect(database.as_uri()+"?mode=ro",uri=True)) as c:
        latest=c.execute("SELECT max(date(trade_date)) FROM source_prices WHERE source!='mubasher'").fetchone()[0]
        price_rows,last_collection=c.execute("SELECT count(*),max(collected_at) FROM source_prices").fetchone()
    metadata=json.loads(DATASET.with_suffix(".meta.json").read_text()) if DATASET.with_suffix(".meta.json").exists() else {}
    if args.rebuild or not DATASET.exists() or not dataset_is_current(metadata,latest,price_rows,last_collection):
        build_dataset(database)
    frame=pd.read_csv(DATASET)
    for horizon in ("next_day","swing"):
        report=train_validate(frame,horizon)
        print(json.dumps({k:report.get(k) for k in ("horizon","status","promoted","reason","promotion_reasons","metrics")},indent=2))


if __name__=="__main__":
    main()
