from praecursor.scoring.indicator import Indicator as BaseIndicator
from praecursor.scoring.result import IndicatorResult
from praecursor.core.stock import Stock

class AllTimeHighIndicator(BaseIndicator):
    def calculate(self, stock: Stock) -> IndicatorResult:
        return self.analyze(stock)

    def analyze(self, stock: Stock) -> IndicatorResult:
        if not stock.history:
            return IndicatorResult(
                name="AllTimeHigh",
                value={
                    "ATH_Price": 0.0,
                    "Distance_To_ATH": 0.0,
                    "New_ATH_Made_Today": 0.0
                }
            )

        # Find the absolute highest `high` price in the entire history
        ath_price = max(record.high for record in stock.history)

        latest_record = stock.history[-1]
        latest_close = latest_record.close
        latest_high = latest_record.high

        if ath_price > 0:
            distance_to_ath = ((latest_close - ath_price) / ath_price) * 100
        else:
            distance_to_ath = 0.0

        new_ath_made_today = 1.0 if latest_high >= ath_price else 0.0

        return IndicatorResult(
            name="AllTimeHigh",
            value={
                "ATH_Price": ath_price,
                "Distance_To_ATH": distance_to_ath,
                "New_ATH_Made_Today": new_ath_made_today
            }
        )
