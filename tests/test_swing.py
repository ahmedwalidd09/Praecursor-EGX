import unittest

from helpers import build_stock
from praecursor.scoring.opportunity_score import OpportunityScorer
from praecursor.scoring.swing import calculate_swing_prediction


class SwingPredictionTests(unittest.TestCase):
    def test_swing_prediction_returns_label_and_reasons(self):
        stock = build_stock(symbol="TEST", days=300, daily_change=0.15, volume_step=10)
        score = OpportunityScorer().score(stock)
        prediction = calculate_swing_prediction(
            score,
            consensus_accepted=True,
            consensus_confidence=40,
            data_quality_score=90,
        )

        self.assertGreaterEqual(prediction.score, 0)
        self.assertLessEqual(prediction.score, 100)
        self.assertTrue(prediction.label)
        self.assertTrue(prediction.reasons)


if __name__ == "__main__":
    unittest.main()
