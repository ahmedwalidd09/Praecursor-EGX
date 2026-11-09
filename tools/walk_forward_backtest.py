"""Replay top-five selection with date-grouped training and outcome-maturity cutoffs."""
import argparse
import json
import sys
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from praecursor.ml.walk_forward import replay
from praecursor.ml.research import DATASET


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--horizon",choices=["next_day","swing"],default="next_day")
    args=parser.parse_args()
    if not DATASET.exists(): raise SystemExit("Run tools/build_research_dataset.py first")
    selected=replay(pd.read_csv(DATASET),args.horizon)
    path=ROOT/"reports"/(args.horizon+"_walk_forward.csv");path.parent.mkdir(exist_ok=True)
    selected.to_csv(path,index=False)
    summary={"selections":len(selected),"sessions":int(selected.session.nunique()) if len(selected) else 0,
             "resolved":int(selected.target_hit.notna().sum()) if len(selected) else 0,
             "unresolved":int(selected.target_hit.isna().sum()) if len(selected) else 0,
             "target_precision_resolved":float(selected.target_hit.mean()) if len(selected) and selected.target_hit.notna().any() else None,
             "conservative_net_return_pct":float(selected.net_return_pct.mean()) if len(selected) and selected.net_return_pct.notna().any() else None,
             "provenance":"Retrospective simulation; unknown outcomes retained in selections"}
    path.with_suffix(".json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))


if __name__=="__main__":main()
