from datetime import date

from praecursor.consensus.price_consensus import PriceConsensusEngine, SourcePrice


def main() -> int:
    symbol = "COMI"
    trade_date = date(2026, 7, 26)

    prices = [
        SourcePrice("yahoo_finance", symbol, trade_date, close=138.70, volume=613_572),
        SourcePrice("official_egx", symbol, trade_date, close=138.68, volume=615_000),
        SourcePrice("mubasher", symbol, trade_date, close=138.72, volume=612_900),
        SourcePrice("tradingview", symbol, trade_date, close=138.69, volume=614_200),
        SourcePrice("investingpro", symbol, trade_date, close=142.50, volume=610_000),
    ]

    engine = PriceConsensusEngine(
        tolerance_percent=0.5,
        minimum_agreeing_sources=3,
        target_source_count=5,
    )
    result = engine.calculate(symbol, trade_date, prices)

    print("Checking price consensus engine")
    print(f"Symbol: {result.symbol}")
    print(f"Date: {result.trade_date}")
    print(f"Consensus close: {result.consensus_close:.2f}")
    print(f"Sources available: {result.source_count}/{result.target_source_count}")
    print(f"Agreeing sources: {result.agreeing_source_count}/{result.source_count}")
    print(f"Agreement: {result.agreement_percent:.0f}%")
    print(f"Confidence: {result.confidence_percent:.0f}%")
    print(f"Accepted: {result.accepted}")
    print()

    print("Source comparison")
    for agreement in result.agreements:
        status = "AGREE" if agreement.agrees else "DISAGREE"
        print(
            f"- {agreement.source_name}: "
            f"close={agreement.close:.2f}, "
            f"difference={agreement.difference_percent:.2f}%, "
            f"{status}"
        )

    if result.warnings:
        print()
        print("Warnings")
        for warning in result.warnings:
            print(f"- {warning}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
