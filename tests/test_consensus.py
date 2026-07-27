import unittest
from datetime import date

from praecursor.consensus.price_consensus import PriceConsensusEngine, SourcePrice


class ConsensusTests(unittest.TestCase):
    def test_consensus_accepts_majority_and_flags_outlier(self):
        prices = [
            SourcePrice("source1", "COMI", date(2026, 7, 26), 100.00),
            SourcePrice("source2", "COMI", date(2026, 7, 26), 100.10),
            SourcePrice("source3", "COMI", date(2026, 7, 26), 99.95),
            SourcePrice("source4", "COMI", date(2026, 7, 26), 100.05),
            SourcePrice("outlier", "COMI", date(2026, 7, 26), 110.00),
        ]
        result = PriceConsensusEngine(
            tolerance_percent=0.5,
            minimum_agreeing_sources=3,
            target_source_count=5,
        ).calculate("COMI", date(2026, 7, 26), prices)

        self.assertTrue(result.accepted)
        self.assertEqual(result.agreeing_source_count, 4)
        self.assertEqual(result.confidence_label, "high")
        outlier = [agreement for agreement in result.agreements if agreement.source_name == "outlier"][0]
        self.assertFalse(outlier.agrees)

    def test_consensus_rejects_insufficient_sources(self):
        prices = [SourcePrice("source1", "COMI", date(2026, 7, 26), 100.0)]
        result = PriceConsensusEngine(
            tolerance_percent=0.5,
            minimum_agreeing_sources=2,
            target_source_count=5,
        ).calculate("COMI", date(2026, 7, 26), prices)

        self.assertFalse(result.accepted)
        self.assertEqual(result.confidence_label, "low")


if __name__ == "__main__":
    unittest.main()
