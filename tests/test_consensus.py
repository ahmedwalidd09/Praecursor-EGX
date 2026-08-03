import logging
import unittest
from datetime import date

from praecursor.consensus.price_consensus import PriceConsensusEngine, SourcePrice


class ConsensusTests(unittest.TestCase):
    def test_consensus_accepts_majority_and_flags_outlier(self):
        prices = [
            SourcePrice("source1", "COMI", date(2026, 7, 26), close=100.00, high=105.00),
            SourcePrice("source2", "COMI", date(2026, 7, 26), close=100.10, high=105.10),
            SourcePrice("source3", "COMI", date(2026, 7, 26), close=99.95, high=104.95),
            SourcePrice("source4", "COMI", date(2026, 7, 26), close=100.05, high=105.05),
            SourcePrice("outlier", "COMI", date(2026, 7, 26), close=110.00, high=115.00),
        ]
        result = PriceConsensusEngine(
            tolerance_percent=0.5,
            minimum_agreeing_sources=3,
            target_source_count=5,
        ).calculate("COMI", date(2026, 7, 26), prices)

        self.assertTrue(result.accepted)
        self.assertEqual(result.agreeing_source_count, 4)
        self.assertEqual(result.confidence_label, "high")
        self.assertAlmostEqual(result.consensus_close, 100.05, places=2)
        self.assertAlmostEqual(result.consensus_high, 105.05, places=2)

        outlier = [agreement for agreement in result.agreements if agreement.source_name == "outlier"][0]
        self.assertFalse(outlier.agrees)
        self.assertFalse(outlier.agrees_close)
        self.assertFalse(outlier.agrees_high)

    def test_consensus_rejects_insufficient_sources(self):
        prices = [SourcePrice("source1", "COMI", date(2026, 7, 26), close=100.0, high=105.0)]
        result = PriceConsensusEngine(
            tolerance_percent=0.5,
            minimum_agreeing_sources=2,
            target_source_count=5,
        ).calculate("COMI", date(2026, 7, 26), prices)

        self.assertFalse(result.accepted)
        self.assertEqual(result.confidence_label, "low")

    def test_consensus_high_and_close_multi_source_logging(self):
        prices = [
            SourcePrice("TradingView", "COMI", date(2026, 7, 26), close=100.00, high=105.00),
            SourcePrice("Mubasher", "COMI", date(2026, 7, 26), close=100.20, high=105.20),
        ]

        with self.assertLogs("praecursor.consensus.price_consensus", level="INFO") as cm:
            result = PriceConsensusEngine(
                tolerance_percent=0.5,
                minimum_agreeing_sources=2,
                target_source_count=5,
            ).calculate("COMI", date(2026, 7, 26), prices)

        self.assertTrue(result.accepted)
        self.assertEqual(result.consensus_close, 100.10)
        self.assertEqual(result.consensus_high, 105.10)

        log_output = "\n".join(cm.output)
        self.assertIn("TradingView", log_output)
        self.assertIn("Mubasher", log_output)
        self.assertIn("Comparing multi-source price data for COMI", log_output)
        self.assertIn("Consensus High = 105.10", log_output)
        self.assertIn("Consensus Close = 100.10", log_output)


if __name__ == "__main__":
    unittest.main()

