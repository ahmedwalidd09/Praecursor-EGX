from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator


class Analyzer:

    def __init__(self):
        self.indicators: list[Indicator] = []

    def add_indicator(self, indicator: Indicator):
        self.indicators.append(indicator)

    def analyze(self, stock: Stock):
        results = []

        for indicator in self.indicators:
            results.append(indicator.calculate(stock))

        return results