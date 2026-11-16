import json
from pathlib import Path

import pandas as pd
import pytest

from praecursor.analysis.outcomes import evaluate_path
from praecursor.notifications.telegram import TelegramReportFormatter
from praecursor.scoring.next_day import _calculate_structural_levels, calculate_next_day_prediction
from praecursor.scoring.opportunity_score import OpportunityScore
from praecursor.scoring.swing import calculate_swing_prediction
from tools.chart_generator import generate_chart_html


@pytest.mark.parametrize("atr,target,stop,target_term,stop_term", [
    (1, 104, 97.5, "floor bound at 4.00%", "floor bound at 2.50%"),
    (4, 106, 96, "6.00% applied", "4.00% applied"),
    (10, 112, 93.5, "cap bound at 12.00%", "cap bound at 6.50%"),
])
def test_atr_explanation_records_unclamped_and_applied_distances(atr, target, stop, target_term, stop_term):
    actual_target, actual_stop, target_reason, stop_reason = _calculate_structural_levels(100, None, {"ATR14": atr}, "EGP")
    assert (actual_target, actual_stop) == pytest.approx((target, stop))
    assert target_term in target_reason and stop_term in stop_reason
    assert "1.5× ATR14" in target_reason and "1.0× ATR14" in stop_reason


@pytest.mark.parametrize("reference,atr", [(100, None), (100, 0.), (100, float("inf")), (100, float("nan")),
                                           (0, 4.), (float("inf"), 4.)])
def test_invalid_reference_or_missing_atr_does_not_invent_levels(reference, atr):
    setup = OpportunityScore(symbol="EGP", company="Example", latest_close=reference,
                             total_score=55, max_score=100, indicator_values={"ATR14": atr})
    for calculate in (calculate_next_day_prediction, calculate_swing_prediction):
        plan = calculate(setup)
        assert plan.plan["status"] == "unavailable"
        assert plan.probability is None
        assert plan.target_price is None and plan.stop_loss_price is None
        assert evaluate_path([], reference, plan.target_price, plan.stop_loss_price, 1).status == "invalid_levels"


def test_legacy_reconstruction_and_observed_structural_levels():
    old_target, old_stop, *_ = _calculate_structural_levels(100, None, {}, "EGP", legacy=True)
    assert (old_target, old_stop) == (106, 96)
    target, stop, target_reason, stop_reason = _calculate_structural_levels(
        100, None, {"EMA20": 97, "CloseHigh250": 106}, "EGP")
    assert (target, stop) == pytest.approx((106, 96.03))
    assert "250-day resistance" in target_reason and "EMA20" in stop_reason


def test_telegram_and_chart_use_saved_prices_and_scenario_cost():
    setup = OpportunityScore(symbol="EGP", company="Example", latest_close=.02123456,
                             total_score=55, max_score=100, indicator_values={"ATR14": .0001})
    prediction = calculate_next_day_prediction(setup)
    plan = prediction.plan
    assert plan["status"] == "heuristic-active"
    assert plan["net_reward_risk"] < plan["gross_reward_risk"]
    saved = dict(symbol=setup.symbol, candidate_rank=1, next_day_score=prediction.score,
                 latest_close=setup.latest_close, next_day_target=prediction.target_price,
                 next_day_stop_loss=prediction.stop_loss_price, plans={"next_day": plan})
    message = TelegramReportFormatter().format_snapshot({"signals": [saved]})
    frame = pd.DataFrame([dict(trade_date=pd.Timestamp("2026-11-10"), open=.02, high=.03,
                               low=.01, close=setup.latest_close, volume=1000)])
    chart = generate_chart_html(setup.symbol, frame, saved)
    assert "0.02123456" in message and "0.02123456" in chart
    assert plan["policy"] in message and plan["policy"] in chart
    assert "25 bps" in message and "25 bps" in chart
    missing = dict(saved, next_day_target=None, next_day_stop_loss=None, plans={})
    assert "Unavailable / Unavailable" in TelegramReportFormatter().format_snapshot({"signals": [missing]})
    assert "Reward / risk" not in generate_chart_html(setup.symbol, frame, missing)
