import csv
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SYMBOL_FILE = ROOT / "config" / "symbols.csv"


@dataclass(frozen=True)
class SymbolMapping:
    """Source-specific symbols for one EGX-listed security."""

    egx_symbol: str
    company: str
    yahoo_symbol: str
    stockanalysis_symbol: str


class SymbolMapper:
    """Load and resolve symbol mappings for external data sources."""

    def __init__(self, mappings: dict[str, SymbolMapping]):
        self._mappings = {
            egx_symbol.upper(): mapping
            for egx_symbol, mapping in mappings.items()
        }

    @classmethod
    def from_csv(cls, filename: str | Path = DEFAULT_SYMBOL_FILE) -> "SymbolMapper":
        path = Path(filename)

        if not path.exists():
            raise FileNotFoundError(f"Symbol mapping file was not found: {path}")

        mappings: dict[str, SymbolMapping] = {}

        with path.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            cls._validate_columns(reader.fieldnames, path)

            for row in reader:
                egx_symbol = row["egx_symbol"].strip().upper()

                if not egx_symbol:
                    continue

                mappings[egx_symbol] = SymbolMapping(
                    egx_symbol=egx_symbol,
                    company=row["company"].strip(),
                    yahoo_symbol=row["yahoo_symbol"].strip(),
                    stockanalysis_symbol=row.get("stockanalysis_symbol", egx_symbol).strip(),
                )

        return cls(mappings)

    def get_symbols(self) -> list[str]:
        """Return every EGX symbol configured in the mapping file."""
        return list(self._mappings.keys())

    def get_yahoo_symbols(self) -> list[str]:
        """Return EGX symbols that have a Yahoo Finance mapping."""
        return [
            mapping.egx_symbol
            for mapping in self._mappings.values()
            if mapping.yahoo_symbol
        ]

    def get_stockanalysis_symbols(self) -> list[str]:
        """Return EGX symbols that have a StockAnalysis mapping."""
        return [
            mapping.egx_symbol
            for mapping in self._mappings.values()
            if mapping.stockanalysis_symbol
        ]

    def get_yahoo_symbol(self, egx_symbol: str) -> str:
        symbol = self._normalize_symbol(egx_symbol)
        mapping = self._get_mapping(symbol)

        if not mapping.yahoo_symbol:
            raise KeyError(f"No Yahoo Finance symbol configured for EGX symbol '{symbol}'.")

        return mapping.yahoo_symbol

    def get_stockanalysis_symbol(self, egx_symbol: str) -> str:
        symbol = self._normalize_symbol(egx_symbol)
        mapping = self._get_mapping(symbol)

        if not mapping.stockanalysis_symbol:
            raise KeyError(f"No StockAnalysis symbol configured for EGX symbol '{symbol}'.")

        return mapping.stockanalysis_symbol

    def get_company_name(self, egx_symbol: str) -> str:
        symbol = self._normalize_symbol(egx_symbol)
        return self._get_mapping(symbol).company

    def _get_mapping(self, symbol: str) -> SymbolMapping:
        if symbol not in self._mappings:
            raise KeyError(
                f"No symbol mapping found for EGX symbol '{symbol}'. "
                "Add it to config/symbols.csv first."
            )

        return self._mappings[symbol]

    def _normalize_symbol(self, egx_symbol: str) -> str:
        return egx_symbol.strip().upper()

    @staticmethod
    def _validate_columns(fieldnames: list[str] | None, path: Path) -> None:
        required_columns = {"egx_symbol", "company", "yahoo_symbol"}
        actual_columns = set(fieldnames or [])
        missing_columns = required_columns - actual_columns

        if missing_columns:
            missing_text = ", ".join(sorted(missing_columns))
            raise ValueError(
                f"Symbol mapping file {path} is missing columns: {missing_text}"
            )
