import csv
from pathlib import Path
from datetime import datetime

from praecursor.core.stock import Stock
from praecursor.core.price_bar import PriceBar


class CSVLoader:
    def load(self, filename: str) -> list[Stock]:
        path = Path(filename)

        stocks = {}

        with path.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            for row in reader:
                symbol = row["Symbol"]

                if symbol not in stocks:
                    stocks[symbol] = Stock(
                        symbol=symbol,
                        company=row["Company"],
                    )

                bar = PriceBar(
                    date=datetime.strptime(row["Date"], "%Y-%m-%d"),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=int(row["Volume"]),
                )

                stocks[symbol].history.append(bar)

        return list(stocks.values())