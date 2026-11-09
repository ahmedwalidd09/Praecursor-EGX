from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult

class RelativeStrengthIndicator(Indicator):
    """
    Calculates relative strength against date-aligned peers in the scan universe.
    RS = Stock Close / Benchmark Close
    RS_ROC = (RS_today - RS_n_days_ago) / RS_n_days_ago
    """

    def __init__(self, period: int = 50):
        self.period = period
        self.name = f"RS_vs_EGX30_{period}"

    def calculate(self, stock: Stock) -> IndicatorResult:
        # Retain feature key for report compatibility; benchmark identity is explicit.
        return IndicatorResult(self.name, stock.market_context.get("relative_strength50", float("nan")))
