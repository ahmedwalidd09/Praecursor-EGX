from praecursor.collectors.csv_loader import CSVLoader
from praecursor.scoring.analyzer import Analyzer
from praecursor.scoring.ema import EMAIndicator
from praecursor.scoring.rsi import RSIIndicator


def main():
    # Load stock data
    loader = CSVLoader()
    stocks = loader.load("data/raw/sample.csv")

    # Create analyzer and register indicators
    analyzer = Analyzer()
    analyzer.add_indicator(EMAIndicator(20))
    analyzer.add_indicator(RSIIndicator(14))

    print(f"Loaded {len(stocks)} stocks\n")

    # Analyze each stock
    for stock in stocks:
        print("=" * 40)
        print(stock.symbol)
        print(stock.company)

        latest = stock.latest()
        print(f"Latest Close: {latest.close:.2f}")

        results = analyzer.analyze(stock)

        for result in results:
            print(f"{result.name}: {result.value:.2f}")

        print()


if __name__ == "__main__":
    main()