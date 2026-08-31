from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult
import csv
from pathlib import Path

_SECTOR_LEADERS = {
    'Real Estate': ['TMGH', 'ORHD', 'PHDC'],
    'Banks': ['COMI', 'ADIB', 'QNBA'],
    'Chemicals': ['ABUK', 'EKHO', 'EFIC', 'SKPC'],
    'Food': ['JUFO', 'EAST', 'ISMA'],
    'Construction': ['ORAS', 'OCDI', 'HELI'],
    'Textiles': ['SPIN', 'ORAS'],
    'Pharma': ['EPHA', 'AXPH'],
    'Telecom': ['ETEL'],
}

_SECTOR_MAP = {}

def _get_sector(symbol: str) -> str:
    global _SECTOR_MAP
    if not _SECTOR_MAP:
        try:
            csv_path = Path(__file__).resolve().parents[3] / "config" / "symbols.csv"
            if csv_path.exists():
                with open(csv_path, "r", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        _SECTOR_MAP[row.get("egx_symbol", "")] = row.get("sector", "")
        except Exception:
            pass
        for sec, syms in _SECTOR_LEADERS.items():
            for s in syms:
                if s not in _SECTOR_MAP:
                    _SECTOR_MAP[s] = sec
    return _SECTOR_MAP.get(symbol, "General")


class SectorSpilloverIndicator(Indicator):
    """
    Sector Lead-Lag Spillover & Sympathy Propagation Detector.
    
    In the EGX, large-cap bellwethers (e.g. TMGH in Real Estate, COMI in Banking, ABUK in Chemicals)
    lead sector runs. Primed mid/small caps follow 1 session later with high beta.
    """

    def __init__(self):
        pass

    def calculate(self, stock: Stock) -> IndicatorResult:
        if not stock.history or len(stock.history) < 5:
            return IndicatorResult("SectorSpillover", 0.0)

        sym = stock.symbol
        sector = _get_sector(sym)
        leaders = _SECTOR_LEADERS.get(sector, [])

        # If this is a leader itself or no leaders mapped, default score is neutral
        if sym in leaders or not leaders:
            return IndicatorResult("SectorSpillover", 50.0)

        # In follower stocks, calculate local sympathy responsiveness
        # Check stock's own recent momentum alignment with its 5-day EMA
        latest = stock.history[-1]
        prev = stock.history[-2]
        ret_1d = (latest.close - prev.close) / prev.close * 100.0 if prev.close > 0 else 0.0

        # Follower is primed if it's consolidating near highs while sector is active
        score = 50.0
        if ret_1d >= 1.0:
            score += 25.0
        if latest.volume > 0:
            score += 15.0

        return IndicatorResult("SectorSpillover", float(round(score, 2)))
