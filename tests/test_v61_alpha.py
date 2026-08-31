import unittest
from datetime import datetime, timedelta
from praecursor.core.price_bar import PriceBar
from praecursor.core.stock import Stock
from praecursor.scoring.closing_aggression import ClosingAggressionIndicator
from praecursor.scoring.compression_nr7 import NR7CompressionIndicator
from praecursor.scoring.vsa_absorption import VSAAbsorptionIndicator
from praecursor.scoring.sector_spillover import SectorSpilloverIndicator
from praecursor.scoring.opportunity_score import OpportunityScorer
from praecursor.scoring.next_day import calculate_next_day_prediction

class TestV61AlphaIndicators(unittest.TestCase):
    def setUp(self):
        # Create synthetic stock history
        self.bars = []
        base_date = datetime(2026, 8, 1)
        price = 20.0
        for i in range(40):
            d = base_date + timedelta(days=i)
            # Create a rising trend with tight consolidation at the end
            high = price * 1.02
            low = price * 0.98
            close = price * 1.01
            vol = 100000 + i * 5000
            self.bars.append(PriceBar(
                date=d,
                open=price,
                high=high,
                low=low,
                close=close,
                volume=vol
            ))
            price += 0.1

        # Create an explosive MOC closing aggression + NR7 inside day on the latest bar
        latest_d = base_date + timedelta(days=40)
        self.bars.append(PriceBar(
            date=latest_d,
            open=24.0,
            high=24.20,
            low=23.95,
            close=24.18, # Close at 92% of high
            volume=350000 # High volume absorption
        ))
        self.stock = Stock(symbol="EGREF", company="Egyptians Real Estate Fund", history=self.bars)

    def test_closing_aggression(self):
        ind = ClosingAggressionIndicator()
        res = ind.calculate(self.stock)
        self.assertGreater(res.value, 50.0)
        print(f"Closing Aggression: {res.value:.2f}")

    def test_nr7_compression(self):
        ind = NR7CompressionIndicator()
        res = ind.calculate(self.stock)
        self.assertGreaterEqual(res.value, 0.0)
        print(f"NR7 Compression: {res.value:.2f}")

    def test_vsa_absorption(self):
        ind = VSAAbsorptionIndicator()
        res = ind.calculate(self.stock)
        self.assertGreaterEqual(res.value, 0.0)
        print(f"VSA Absorption: {res.value:.2f}")

    def test_sector_spillover(self):
        ind = SectorSpilloverIndicator()
        res = ind.calculate(self.stock)
        self.assertGreaterEqual(res.value, 0.0)
        print(f"Sector Spillover: {res.value:.2f}")

    def test_opportunity_scorer_integration(self):
        scorer = OpportunityScorer()
        opp_score = scorer.score(self.stock)
        self.assertGreater(opp_score.total_score, 0.0)
        self.assertIn("ClosingAggression", opp_score.indicator_values)
        self.assertIn("NR7_Compression", opp_score.indicator_values)
        self.assertIn("VSA_Absorption", opp_score.indicator_values)
        self.assertIn("SectorSpillover", opp_score.indicator_values)
        print(f"Opportunity Score: {opp_score.score_percent:.2f}% (Raw: {opp_score.total_score:.1f}/{opp_score.max_score:.1f})")

        # Test next day prediction calculation
        pred = calculate_next_day_prediction(opp_score)
        self.assertGreater(pred.score, 0.0)
        print(f"Next Day Prediction Score: {pred.score:.2f}% | Label: {pred.label}")
        print("Reasons:")
        for r in pred.reasons:
            print(f"  • {r}")

if __name__ == "__main__":
    unittest.main()
