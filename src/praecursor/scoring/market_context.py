"""Date-aligned equal-weight market breadth and sector context.

This is explicitly a scan-universe benchmark, not an EGX30 index quote.
No state survives a scan and no observation after the requested session is used.
"""
from datetime import date
from statistics import mean


def session_of(bar):
    return bar.date.date() if hasattr(bar.date, "date") else bar.date


def attach_market_context(stocks, session: date):
    observations = {}
    for stock in stocks:
        bars = [b for b in stock.history if session_of(b) <= session]
        if len(bars) < 51 or session_of(bars[-1]) != session:
            continue
        close = bars[-1].close
        if min(b.close for b in bars[-51:]) <= 0:
            continue
        observations[stock.symbol] = {
            "sector": stock.sector, "close": close,
            "past_date": session_of(bars[-51]),
            "past_close": bars[-51].close,
            "return1": close / bars[-2].close - 1,
            "return50": close / bars[-51].close - 1,
            "above_ma50": close > mean(b.close for b in bars[-50:]),
            "breakout": close > max(b.close for b in bars[-21:-1]),
        }
    for stock in stocks:
        own = observations.get(stock.symbol)
        context = {"session": session.isoformat(), "benchmark": "Scan-universe breadth", "regime": "Unknown"}
        if own:
            peers = [v for k, v in observations.items() if k != stock.symbol and v["past_date"] == own["past_date"]]
            if len(peers) >= 10:
                breadth = mean(v["above_ma50"] for v in peers)
                context.update(breadth=breadth, relative_strength50=(
                    (1 + own["return50"]) / (1 + mean(v["return50"] for v in peers)) - 1) * 100,
                    regime="Bull Trend" if breadth >= .6 else "Bear Trend" if breadth <= .4 else "Sideways Chop")
            sector_peers = [v for v in peers if v["sector"] == own["sector"] and own["sector"] not in ("", "General")]
            if sector_peers:
                context["sector_breakouts"] = sum(v["breakout"] for v in sector_peers)
                context["sector_spillover"] = 100 * mean(v["return1"] > .01 for v in sector_peers)
        stock.market_context = context
