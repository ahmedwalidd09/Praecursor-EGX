from abc import ABC, abstractmethod

from praecursor.core.stock import Stock
from praecursor.scoring.result import IndicatorResult


class Indicator(ABC):

    @abstractmethod
    def calculate(self, stock: Stock) -> IndicatorResult:
        pass