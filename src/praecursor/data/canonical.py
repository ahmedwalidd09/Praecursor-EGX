"""Select complete observed candles; never combine a high from one source with another close."""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class Candle:
    session: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    source: str
    agreeing_sources: int


def select_candle(rows, tolerance=.01):
    candidates = []
    seen = set()
    for row in rows:
        r = dict(row)
        # Latest-page quotes have no verified session timestamp or complete OHLCV.
        source = r.get("source", "")
        if source == "mubasher" or source in seen:
            continue
        vals = [r.get(k) for k in ("open", "high", "low", "close", "volume")]
        if any(v is None or not isfinite(float(v)) for v in vals):
            continue
        o, h, l, c, v = map(float, vals)
        if min(o, h, l, c) <= 0 or v <= 0 or not (l <= min(o, c) <= max(o, c) <= h):
            continue
        seen.add(source)
        candidates.append(Candle(str(r["trade_date"])[:10], o, h, l, c, v, source, 1))
    if not candidates:
        return None
    def agrees(a, b):
        return all(abs(getattr(a, k) / getattr(b, k) - 1) <= tolerance for k in ("open", "high", "low", "close"))
    ranked = sorted(candidates, key=lambda a: (
        -sum(agrees(a, b) for b in candidates),
        {"official_egx": 0, "tradingview": 1, "stockanalysis": 2}.get(a.source, 3), a.source))
    chosen = ranked[0]
    count = sum(agrees(chosen, b) for b in candidates)
    if len(candidates) > 1 and count <= len(candidates) / 2:
        return None
    return Candle(chosen.session, chosen.open, chosen.high, chosen.low, chosen.close,
                  chosen.volume, chosen.source, count)
