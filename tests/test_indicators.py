import unittest

from praecursor.scoring.atr import ATRIndicator, ATRPercentIndicator
from praecursor.scoring.average_volume import AverageVolumeIndicator
from praecursor.scoring.breakout import CloseBreakoutIndicator, NearCloseHighIndicator
from praecursor.scoring.ema import EMAIndicator
from praecursor.scoring.macd import MACDHistogramIndicator, MACDLineIndicator
from praecursor.scoring.price_momentum import PriceMomentumIndicator
from praecursor.scoring.relative_volume import RelativeVolumeIndicator
from praecursor.scoring.reversal import (
    EMA20ReclaimIndicator,
    MACDHistogramImprovementIndicator,
    Momentum5Indicator,
    RSIReboundIndicator,
    VolumeSpikeFromWeaknessIndicator,
)
from praecursor.scoring.rsi import RSIIndicator
from praecursor.scoring.squeeze import SqueezeIndicator
from praecursor.scoring.trend_strength import TrendStrengthIndicator
from helpers import build_stock


class IndicatorTests(unittest.TestCase):
    def setUp(self):
        self.stock = build_stock(days=260, daily_change=0.2, volume_step=20)

    def test_ema_returns_value(self):
        result = EMAIndicator(20).calculate(self.stock)
        self.assertEqual(result.name, "EMA20")
        self.assertGreater(result.value, 0)

    def test_rsi_rising_stock_is_high(self):
        result = RSIIndicator(14).calculate(self.stock)
        self.assertEqual(result.name, "RSI14")
        self.assertGreaterEqual(result.value, 90)

    def test_volume_indicators_return_values(self):
        avg = AverageVolumeIndicator(20).calculate(self.stock)
        rel = RelativeVolumeIndicator(20).calculate(self.stock)
        self.assertEqual(avg.name, "AvgVolume20")
        self.assertEqual(rel.name, "RelVolume20")
        self.assertGreater(avg.value, 0)
        self.assertGreater(rel.value, 0)

    def test_macd_returns_values(self):
        macd = MACDLineIndicator().calculate(self.stock)
        hist = MACDHistogramIndicator().calculate(self.stock)
        self.assertEqual(macd.name, "MACD")
        self.assertEqual(hist.name, "MACDHistogram")
        self.assertFalse(macd.value != macd.value)
        self.assertFalse(hist.value != hist.value)

    def test_momentum_and_trend_strength(self):
        momentum = PriceMomentumIndicator(20).calculate(self.stock)
        trend = TrendStrengthIndicator().calculate(self.stock)
        self.assertEqual(momentum.name, "Momentum20")
        self.assertEqual(trend.name, "TrendStrength")
        self.assertGreater(momentum.value, 0)
        self.assertEqual(trend.value, 100)

    def test_atr_returns_values(self):
        atr = ATRIndicator(14).calculate(self.stock)
        atr_percent = ATRPercentIndicator(14).calculate(self.stock)
        self.assertEqual(atr.name, "ATR14")
        self.assertEqual(atr_percent.name, "ATRPercent14")
        self.assertGreater(atr.value, 0)
        self.assertGreater(atr_percent.value, 0)

    def test_breakout_indicators(self):
        breakout = CloseBreakoutIndicator(20).calculate(self.stock)
        near_high = NearCloseHighIndicator(250).calculate(self.stock)
        self.assertEqual(breakout.name, "Breakout20")
        self.assertEqual(near_high.name, "NearCloseHigh250Percent")
        self.assertEqual(breakout.value, 1.0)
        self.assertAlmostEqual(near_high.value, 0.0)

    def test_reversal_indicators_return_values(self):
        indicators = [
            RSIReboundIndicator(),
            EMA20ReclaimIndicator(),
            MACDHistogramImprovementIndicator(),
            VolumeSpikeFromWeaknessIndicator(),
            Momentum5Indicator(),
        ]

        for indicator in indicators:
            result = indicator.calculate(self.stock)
            self.assertTrue(result.name)
            self.assertFalse(result.value != result.value)

    def test_squeeze_indicator(self):
        squeeze = SqueezeIndicator()
        result = squeeze.calculate(self.stock)
        self.assertEqual(result.name, "Squeeze")
        self.assertIn("BBW_Current", result.value)
        self.assertIn("BBW_Min_120", result.value)
        self.assertIn("Squeeze_Building", result.value)
        self.assertIn("Squeeze_Fired", result.value)


if __name__ == "__main__":
    unittest.main()

