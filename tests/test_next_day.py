import unittest

from praecursor.scoring.next_day import calculate_next_day_prediction
from praecursor.scoring.opportunity_score import OpportunityScorer
from helpers import build_stock


class NextDayPredictionTests(unittest.TestCase):
    def test_next_day_prediction_returns_label_and_reasons(self):
        stock = build_stock(symbol="TEST", days=300, daily_change=0.2, volume_step=25)
        score = OpportunityScorer().score(stock)
        prediction = calculate_next_day_prediction(
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
