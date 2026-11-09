from dataclasses import dataclass, field

from praecursor.core.price_bar import PriceBar


@dataclass
class Stock:
    symbol: str
    company: str
    sector: str = ""
    history: list[PriceBar] = field(default_factory=list)
    intraday_history: list[PriceBar] = field(default_factory=list)
    market_context: dict = field(default_factory=dict)

    def latest(self) -> PriceBar:
        return self.history[-1]
