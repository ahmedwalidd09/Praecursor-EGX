import unittest

from praecursor.scoring.opportunity_score import OpportunityScorer
from helpers import build_stock


class OpportunityScorerTests(unittest.TestCase):
    def test_scorer_returns_components_and_label_inputs(self):
        stock = build_stock(symbol="TEST", days=300, daily_change=0.2, volume_step=25)
        score = OpportunityScorer().score(stock)

        component_names = {component.name for component in score.components}

        self.assertEqual(score.symbol, "TEST")
        self.assertGreaterEqual(score.total_score, 0)
        self.assertLessEqual(score.total_score, score.max_score)
        self.assertIn("EMA Alignment", component_names)
        self.assertIn("RSI14 momentum", component_names)
        self.assertIn("MACD confirmation", component_names)
        self.assertIn("Momentum20", component_names)
        self.assertIn("Relative Volume20", component_names)
        self.assertIn("Breakout setup", component_names)
        self.assertIn("ATR14", score.indicator_values)
        self.assertIn("Breakout20", score.indicator_values)


if __name__ == "__main__":
    unittest.main()
