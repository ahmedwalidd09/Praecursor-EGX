from datetime import date
import logging
import pytest
from praecursor.consensus.price_consensus import PriceConsensusEngine, SourcePrice


class TestR4DataConsensusTier1:
    """Tier 1: Feature Coverage for R4 Data Source Consensus."""

    def test_r4_multi_source_fetch_logs(self, caplog):
        """Verify logs explicitly show fetching/comparing from TradingView and Mubasher."""
        caplog.set_level(logging.INFO)
        engine = PriceConsensusEngine(tolerance_percent=0.5, minimum_agreeing_sources=2, target_source_count=2)

        today = date(2026, 8, 1)
        prices = [
            SourcePrice(source_name="TradingView", symbol="COMI", trade_date=today, close=80.0, high=82.5),
            SourcePrice(source_name="Mubasher", symbol="COMI", trade_date=today, close=80.0, high=82.5),
        ]

        result = engine.calculate("COMI", today, prices)
        assert result.accepted is True
        log_text = caplog.text

        assert "TradingView" in log_text
        assert "Mubasher" in log_text
        assert "Comparing multi-source price data" in log_text

    def test_r4_consensus_matching_sources(self):
        """Verify consensus engine resolves price when TradingView and Mubasher agree."""
        engine = PriceConsensusEngine(tolerance_percent=0.5, minimum_agreeing_sources=2, target_source_count=2)
        today = date(2026, 8, 1)
        prices = [
            SourcePrice(source_name="TradingView", symbol="COMI", trade_date=today, close=80.0, high=82.5),
            SourcePrice(source_name="Mubasher", symbol="COMI", trade_date=today, close=80.0, high=82.5),
        ]

        result = engine.calculate("COMI", today, prices)
        assert result.accepted is True
        assert result.consensus_close == 80.0
        assert result.consensus_high == 82.5
        assert result.agreeing_source_count == 2

    def test_r4_consensus_outlier_rejection(self, caplog):
        """Verify consensus engine rejects anomalous data from one source when others agree."""
        caplog.set_level(logging.INFO)
        engine = PriceConsensusEngine(tolerance_percent=0.5, minimum_agreeing_sources=2, target_source_count=3)
        today = date(2026, 8, 1)

        prices = [
            SourcePrice(source_name="TradingView", symbol="COMI", trade_date=today, close=80.0, high=82.5),
            SourcePrice(source_name="Mubasher", symbol="COMI", trade_date=today, close=80.0, high=82.5),
            SourcePrice(source_name="OutlierSource", symbol="COMI", trade_date=today, close=120.0, high=125.0), # Bad spike +50%
        ]

        result = engine.calculate("COMI", today, prices)
        assert result.accepted is True
        assert result.consensus_close == 80.0
        assert result.agreeing_source_count == 2 # 2 sources agree (TradingView & Mubasher), Outlier is rejected

        # Check that OutlierSource was rejected in agreement status
        outlier_ag = next(a for a in result.agreements if a.source_name == "OutlierSource")
        assert outlier_ag.agrees is False

    def test_r4_consensus_log_comparison(self, caplog):
        """Verify explicit output logging comparing values from at least 2 data sources."""
        caplog.set_level(logging.INFO)
        engine = PriceConsensusEngine(tolerance_percent=0.5, minimum_agreeing_sources=2, target_source_count=2)
        today = date(2026, 8, 1)

        prices = [
            SourcePrice(source_name="TradingView", symbol="SWDY", trade_date=today, close=35.0, high=36.0),
            SourcePrice(source_name="Mubasher", symbol="SWDY", trade_date=today, close=35.1, high=36.1),
        ]

        engine.calculate("SWDY", today, prices)
        log_text = caplog.text

        assert "Close Diff =" in log_text
        assert "High Diff =" in log_text
        assert "Overall Agrees:" in log_text

    def test_r4_source_fallback(self):
        """Verify system handles single-source availability gracefully with warning."""
        engine = PriceConsensusEngine(tolerance_percent=0.5, minimum_agreeing_sources=2, target_source_count=2)
        today = date(2026, 8, 1)

        prices = [
            SourcePrice(source_name="Mubasher", symbol="HRHO", trade_date=today, close=18.5, high=19.0),
        ]

        result = engine.calculate("HRHO", today, prices)
        assert result.accepted is False # Requires min 2 agreeing sources
        assert result.source_count == 1
        assert len(result.warnings) > 0
        assert "Only 1 source(s) available" in result.warnings[0]


class TestR4DataConsensusTier2:
    """Tier 2: Boundary & Corner Cases for R4 Data Source Consensus."""

    def test_r4_total_source_disagreement(self):
        """Verify behavior when TradingView and Mubasher return completely conflicting values."""
        engine = PriceConsensusEngine(tolerance_percent=0.5, minimum_agreeing_sources=2, target_source_count=2)
        today = date(2026, 8, 1)

        prices = [
            SourcePrice(source_name="TradingView", symbol="COMI", trade_date=today, close=80.0, high=82.0),
            SourcePrice(source_name="Mubasher", symbol="COMI", trade_date=today, close=95.0, high=99.0),
        ]

        result = engine.calculate("COMI", today, prices)
        assert result.accepted is False
        assert result.agreeing_source_count == 0 or result.agreeing_source_count < 2
        assert "Consensus not accepted" in " ".join(result.warnings)

    def test_r4_tradingview_single_bar_anomaly(self):
        """Verify consensus engine detects TradingView 1-bar / missing bar anomaly."""
        engine = PriceConsensusEngine(tolerance_percent=0.5, minimum_agreeing_sources=2, target_source_count=2)
        today = date(2026, 8, 1)

        prices = [
            SourcePrice(source_name="TradingView", symbol="FWRY", trade_date=today, close=1.0, high=1.0), # Bad 1-bar anomaly price
            SourcePrice(source_name="Mubasher", symbol="FWRY", trade_date=today, close=6.2, high=6.5),
            SourcePrice(source_name="YahooFinance", symbol="FWRY", trade_date=today, close=6.2, high=6.5),
        ]

        result = engine.calculate("FWRY", today, prices)
        assert result.accepted is True
        assert result.consensus_close == 6.2
        assert result.consensus_high == 6.5
        tv_ag = next(a for a in result.agreements if a.source_name == "TradingView")
        assert tv_ag.agrees is False

    def test_r4_mubasher_http_error(self):
        """Verify behavior when Mubasher API returns error/unavailable (only 1 valid source remaining)."""
        engine = PriceConsensusEngine(tolerance_percent=0.5, minimum_agreeing_sources=1, target_source_count=2)
        today = date(2026, 8, 1)

        # Mubasher is absent due to HTTP 500 / timeout
        prices = [
            SourcePrice(source_name="TradingView", symbol="AMOC", trade_date=today, close=9.1, high=9.5),
        ]

        result = engine.calculate("AMOC", today, prices)
        # With min_agreeing=1 fallback setting, single valid source is processed but marked with warning
        assert result.consensus_close == 9.1
        assert result.source_count == 1

    def test_r4_extreme_price_variance(self):
        """Verify logging and flagging when price variance between sources exceeds threshold (>10%)."""
        engine = PriceConsensusEngine(tolerance_percent=0.5, minimum_agreeing_sources=2, target_source_count=2)
        today = date(2026, 8, 1)

        prices = [
            SourcePrice(source_name="TradingView", symbol="EKHO", trade_date=today, close=40.0, high=42.0),
            SourcePrice(source_name="Mubasher", symbol="EKHO", trade_date=today, close=48.0, high=52.0), # >10% variance
        ]

        result = engine.calculate("EKHO", today, prices)
        assert result.accepted is False
        assert any(ag.difference_percent > 5.0 for ag in result.agreements)

    def test_r4_partial_data_fields(self):
        """Verify handling when one data source is missing intraday high but has close price."""
        engine = PriceConsensusEngine(tolerance_percent=0.5, minimum_agreeing_sources=2, target_source_count=2)
        today = date(2026, 8, 1)

        prices = [
            SourcePrice(source_name="TradingView", symbol="ESRS", trade_date=today, close=50.0, high=None), # High missing
            SourcePrice(source_name="Mubasher", symbol="ESRS", trade_date=today, close=50.0, high=52.0),
        ]

        result = engine.calculate("ESRS", today, prices)
        assert result.consensus_close == 50.0
        assert result.consensus_high == 52.0
        assert result.accepted is True
