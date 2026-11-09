"""Reconstruct an explicitly labelled research dataset from canonical OHLCV.

Historical vendor data can be revised. These are retrospective simulations, never
claimed to be immutable live predictions or prospective performance.
"""
from collections import defaultdict
from contextlib import closing
from dataclasses import asdict
from datetime import datetime, date
from pathlib import Path
import csv
import sqlite3
import json
import logging
import hashlib
from joblib import Parallel, delayed, parallel_config

from praecursor.core.price_bar import PriceBar
from praecursor.core.stock import Stock
from praecursor.data.canonical import select_candle
from praecursor.scoring.opportunity_score import OpportunityScorer
from praecursor.scoring.market_context import attach_market_context
from praecursor.scoring.next_day import _calculate_structural_levels
from praecursor.analysis.outcomes import evaluate_path, LABEL_VERSION
from praecursor.ml.features import feature_row, FEATURE_VERSION

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[3]
DATASET = ROOT / "data" / "research_samples.csv"


def _sample(stock, path, day):
    # Unverified discontinuities invalidate indicators across the affected window.
    if any(abs(b.close/a.close-1) > .35 for a,b in zip(stock.history[-251:-1],stock.history[-250:])):
        return None
    score = OpportunityScorer().score(stock)
    values = score.indicator_values
    if score.latest_close < .2 or values.get("AvgTurnover20",0) < 250000:
        return None
    target,stop,_,_ = _calculate_structural_levels(score.latest_close,stock,values,stock.symbol)
    nd = evaluate_path(path,score.latest_close,target,stop,1)
    atr = values.get("ATR14",0)
    sw = evaluate_path(path,score.latest_close,score.latest_close+3*atr,score.latest_close-atr,20)
    record = dict(symbol=stock.symbol,session=day,feature_version=FEATURE_VERSION,
                  label_version=LABEL_VERSION,opportunity_score=score.score_percent,
                  reference=score.latest_close,next_day_target=target,next_day_stop=stop,
                  regime=stock.market_context.get("regime","Unknown"),provenance="retrospective_reconstruction")
    record.update(feature_row(values,score.score_percent))
    for name,outcome in (("next_day",nd),("swing",sw)):
        record.update({name+"_"+k:v for k,v in asdict(outcome).items()})
    return record

def build_dataset(db_path, output=DATASET, minimum_history=251):
    with closing(sqlite3.connect(Path(db_path).resolve().as_uri()+"?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM source_prices ORDER BY trade_date,source").fetchall()
    grouped = defaultdict(list)
    for r in rows:
        grouped[(r["ticker"], str(r["trade_date"])[:10])].append(r)
    canonical = {key:select_candle(group) for key,group in grouped.items()}
    fingerprint = hashlib.sha256(repr((FEATURE_VERSION, LABEL_VERSION, canonical)).encode()).hexdigest()[:16]
    checkpoint_dir = Path(output).parent / "research_checkpoints" / fingerprint
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    by_date = defaultdict(dict)
    for (symbol, day), candle in canonical.items():
        if candle:
            by_date[day][symbol] = candle
    sessions = sorted(d for d, bars in by_date.items() if len(bars) >= 10)
    sectors = {}
    with (ROOT / "config/symbols.csv").open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            sectors[r["egx_symbol"]] = (r["company"],r["sector"])
    histories = defaultdict(list)
    samples = []
    with parallel_config(backend="loky", n_jobs=4, inner_max_num_threads=1), Parallel() as parallel:
        for index, day in enumerate(sessions):
            stocks = []
            for symbol,candle in by_date[day].items():
                history = histories[symbol]
                history.append(PriceBar(datetime.fromisoformat(day),candle.open,candle.high,candle.low,candle.close,int(candle.volume)))
                if len(history) >= minimum_history and symbol in sectors:
                    company, sector = sectors[symbol]
                    stocks.append(Stock(symbol,company,sector,list(history[-350:])))
            # Evaluate the latest trading year; older observations only warm indicators.
            if not stocks or index < len(sessions) - 252:
                continue
            attach_market_context(stocks,date.fromisoformat(day))
            checkpoint = checkpoint_dir / f"{day}.json"
            if checkpoint.exists():
                records = json.loads(checkpoint.read_text(encoding="utf-8"))
            else:
                records = parallel(delayed(_sample)(stock,
                    [canonical.get((stock.symbol,d)) for d in sessions[index+1:index+21]],day) for stock in stocks)
                temporary = checkpoint.with_suffix(".tmp")
                temporary.write_text(json.dumps(records), encoding="utf-8")
                temporary.replace(checkpoint)
            samples.extend(record for record in records if record is not None)
            log.info("Research session %s: %d eligible stocks, %d cumulative records",day,len(stocks),len(samples))
    output = Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    if samples:
        temp = output.with_suffix(".tmp")
        with temp.open("w",newline="",encoding="utf-8") as f:
            writer=csv.DictWriter(f,fieldnames=list(samples[0])); writer.writeheader(); writer.writerows(samples)
        temp.replace(output)
    summary=dict(rows=len(samples),sessions=len({r["session"] for r in samples}),
                 feature_version=FEATURE_VERSION,label_version=LABEL_VERSION,
                 source_fingerprint=fingerprint,
                 last_source_session=max(str(r["trade_date"])[:10] for r in rows if r["source"]!="mubasher"),
                 price_rows=len(rows),canonical_candles=sum(c is not None for c in canonical.values()),
                 last_collection=max(str(r["collected_at"]) for r in rows),
                 rejected_candles=sum(c is None for c in canonical.values()),
                 provenance="Retrospective vendor history; revisions and historical universe membership are not recoverable")
    output.with_suffix(".meta.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    return summary
