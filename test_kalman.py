import sys
sys.path.insert(0, "C:\\Users\\moody\\.gemini\\antigravity\\scratch\\Praecursor-EGX\\src")

from praecursor.scoring.kalman import KalmanFilterIndicator
from praecursor.core.stock import Stock
from dataclasses import dataclass

@dataclass
class Bar:
    close: float

@dataclass
class DummyStock:
    history: list

if __name__ == "__main__":
    bars = [Bar(close=float(i)) for i in range(25)]
    stock = DummyStock(history=bars)
    
    # We duck type since Stock might be complex
    indicator = KalmanFilterIndicator()
    res = indicator.calculate(stock) # type: ignore
    print(res)
    print("Success")
