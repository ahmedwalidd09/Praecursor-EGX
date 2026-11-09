from datetime import datetime, date, timedelta
from unittest.mock import patch
import math
import pytest

from praecursor.core.price_bar import PriceBar
from praecursor.core.stock import Stock
from praecursor.scoring.analyzer import Analyzer
from praecursor.scoring.vpoc import VPOCIndicator
from praecursor.scoring.market_context import attach_market_context
from praecursor.data.canonical import Candle, select_candle
from praecursor.data.validation import PriceBarValidator
from praecursor.analysis.outcomes import evaluate_path
from praecursor.ml.features import feature_row
from praecursor.core.sessions import completed_session, next_session, CAIRO


def stock(symbol="TEST", sector="Banks", scale=1):
    bars = [PriceBar(datetime(2025, 1, 1) + timedelta(days=i),
                     scale*(100+i), scale*(102+i), scale*(99+i), scale*(101+i), 1000+i)
            for i in range(260)]
    return Stock(symbol, symbol, sector, bars)


def candle(o=100, h=104, l=99, c=102, day="2026-09-14"):
    return Candle(day,o,h,l,c,100000,"tradingview",2)


def test_vpoc_survives_without_intraday_and_has_consistent_units():
    analyzer=Analyzer(); analyzer.add_indicator(VPOCIndicator())
    values={r.name:r.value for r in analyzer.analyze(stock())}
    assert isinstance(values["VPOC_Distance"],dict)
    assert math.isnan(values["IntradayVPOCDistancePct"])
    row=feature_row(values,65)
    assert row["vpoc_distance"] == values["VPOC_Distance"]["VPOC_Distance"]*100
    assert math.isnan(row["adx14"])


def test_sector_context_independent_of_iteration_order_and_session():
    stocks=[stock(str(i),scale=i+1) for i in range(12)]
    session=stocks[0].history[-1].date.date()
    attach_market_context(stocks,session)
    first=[s.market_context.copy() for s in stocks]
    attach_market_context(list(reversed(stocks)),session)
    assert first==[s.market_context for s in stocks]
    assert first[0]["sector_breakouts"]==11
    attach_market_context(stocks,session+timedelta(days=1))
    assert "sector_breakouts" not in stocks[0].market_context


def test_canonical_rejects_outlier_high_instead_of_counting_it_as_hit():
    def row(source,high):
        return dict(source=source,trade_date="2026-09-14",open=100,high=high,low=99,close=102,volume=10000)
    assert select_candle([row("tradingview",104),row("stockanalysis",150)]) is None
    selected=select_candle([row("tradingview",104),row("stockanalysis",104),row("other",150)])
    assert selected.high==104 and selected.agreeing_sources==2
    assert select_candle([row("mubasher",104)]) is None


def test_target_touch_and_trade_success_are_distinct():
    out=evaluate_path([candle(h=106,l=94)],100,105,95,1)
    assert out.target_hit==1 and out.trade_hit is None
    assert out.status=="ambiguous_barrier_order"
    gap=evaluate_path([candle(o=106,h=107,l=105,c=106)],100,105,95,1)
    assert gap.status=="unfilled" and gap.trade_hit is None


def test_next_open_costs_and_missing_sessions():
    out=evaluate_path([candle(o=102,h=106,l=101,c=104)],100,105,95,1)
    assert out.net_return_pct==pytest.approx((105/102-1)*100-.25)
    assert evaluate_path([None,candle()],100,105,95,1).status=="missing_or_conflicting_candle"
    assert evaluate_path([candle()],100,105,95,20).status=="pending"
    assert evaluate_path([candle(o=50,h=55,l=49,c=53)],100,105,95,1).status=="corporate_action_review"


def test_infinite_prices_are_invalid():
    b=PriceBar(datetime(2026,9,14),100,float("inf"),99,102,100)
    assert not PriceBarValidator().validate([b]).is_valid


def test_cairo_cutoff_and_weekend():
    assert completed_session(datetime(2026,11,5,15,tzinfo=CAIRO))==date(2026,11,4)
    assert completed_session(datetime(2026,11,5,17,tzinfo=CAIRO))==date(2026,11,5)
    assert next_session(date(2026,11,5))==date(2026,11,8)


def test_next_day_prediction_is_cached_and_missing_consensus_fails_closed():
    from praecursor.workflows.scanner import SymbolScanResult
    from praecursor.scoring.opportunity_score import OpportunityScore
    opportunity=OpportunityScore("TEST","Test",100,65,100,{})
    item=SymbolScanResult("TEST",260,260,260,[],opportunity)
    with patch("praecursor.workflows.scanner.calculate_next_day_prediction") as predict:
        assert item.next_day_prediction is item.next_day_prediction
        assert predict.call_count==1
        assert predict.call_args.kwargs["consensus_accepted"] is False
