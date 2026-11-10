from dataclasses import dataclass, replace
from datetime import date, timedelta
from types import SimpleNamespace as NS
from unittest.mock import patch
import json

from praecursor.scoring.candidates import select_daily_candidates
from praecursor.notifications.telegram import TelegramReportFormatter
from tools.run_autonomous_pipeline import is_egx_scan_day, run_pipeline


@dataclass(frozen=True)
class Setup:
    symbol: str
    next_day_score: float
    opportunity_score: object
    next_day_prediction: object
    data_quality_score: float = 100
    consensus_result: object = None
    candidate_rank: int | None = None
    selection_reasons: tuple = ()
    override_next_day_label: str | None = None


def setup(symbol, score=65, sector="Banks"):
    return Setup(symbol, score, NS(latest_close=100, stock=NS(sector=sector),
        indicator_values=dict(AvgTurnover20=1_000_000, EMA20=95)),
        NS(score=score, target_price=105, stop_loss_price=97))


def test_five_ranked_research_candidates_without_inventing_consensus():
    rows=[setup(str(i),80-i,"Banks" if i<4 else "Energy") for i in range(8)]
    result=select_daily_candidates(rows)
    chosen=sorted((r for r in result if r.candidate_rank),key=lambda r:r.candidate_rank)
    assert [r.symbol for r in chosen]==["0","1","4","5","2"]
    assert all(r.consensus_result is None and len(r.selection_reasons)==3 for r in chosen)
    assert all(r.candidate_rank is None for r in rows)
    assert chosen[0].override_next_day_label=="Daily Candidate #1"


def test_quality_filters_do_not_fill_quota_with_invalid_data():
    low_history=replace(setup("SHORT"),data_quality_score=0)
    conflict=replace(setup("CONFLICT"),consensus_result=NS(accepted=False))
    illiquid=setup("ILLIQUID");illiquid.opportunity_score.indicator_values["AvgTurnover20"]=0
    locked=setup("LOCKED");locked.opportunity_score.indicator_values["ClosedAtLimitUp"]=1
    invalid=setup("INVALID");invalid.next_day_prediction.target_price=float("nan")
    result=select_daily_candidates([setup("VALID"),low_history,conflict,illiquid,locked,invalid])
    assert [r.symbol for r in result if r.candidate_rank]==["VALID"]


def test_scan_days_are_evenings_before_market_sessions():
    saturday=date(2026,11,7)
    assert [is_egx_scan_day(saturday+timedelta(days=i)) for i in range(7)]==[True]*5+[False]*2


def test_telegram_reasons_order_and_shortage_are_explicit():
    rows=[dict(candidate_rank=i,symbol=f"TEST{i}",next_day_score=70,latest_close=100,
               next_day_target=105,next_day_stop_loss=97,selection_reasons=["Price > EMA20", "Liquid & active"],
               source_status="Single source",next_day_probability=None) for i in range(5,0,-1)]
    formatter=TelegramReportFormatter()
    message=formatter.format_snapshot(dict(signals=rows,target_session="2026-11-08",price_session="2026-11-05"))
    assert message.index("TEST1")<message.index("TEST5")
    assert "Price &gt; EMA20" in message and "Liquid &amp; active" in message
    assert len(message)<4096 and message.count("Single source")==5
    assert "Only 0/5" in formatter.format_snapshot(dict(signals=[]))


def test_delivery_failure_fails_daily_pipeline_and_daily_skips_retraining(tmp_path):
    with patch("tools.run_autonomous_pipeline.run_stage",side_effect=[True,True,True,True,False]) as stage:
        assert run_pipeline(tmp_path,tmp_path/"logs",run_date=date(2026,11,7))==1
    assert len(stage.call_args_list)==5
    assert all("tools/retrain_models.py" not in c.args[3] for c in stage.call_args_list)
    status=json.loads((tmp_path/"data/scan_status.json").read_text())
    assert not status["completed"] and status["telegram_status"]=="Delivery failed"


def test_preview_never_claims_delivery(tmp_path):
    with patch("tools.run_autonomous_pipeline.run_stage",return_value=True):
        assert run_pipeline(tmp_path,tmp_path/"logs",dry_run_telegram=True,run_date=date(2026,11,7))==0
    assert json.loads((tmp_path/"data/scan_status.json").read_text())["telegram_status"]=="Preview only"


def test_telegram_shows_paper_decisions_only_for_matching_session():
    saved=dict(target_session="2026-11-11", signals=[dict(symbol="TEST",candidate_rank=1,next_day_score=70)],
               paper=dict(session="2026-11-11",orders=[dict(symbol="TEST",decision="watch_only",quantity=0,reasons=["Sector limit"])]))
    assert "Watch only: Sector limit" in TelegramReportFormatter().format_snapshot(saved)
    saved["paper"]["session"]="2026-11-10"
    assert "Watch only" not in TelegramReportFormatter().format_snapshot(saved)
