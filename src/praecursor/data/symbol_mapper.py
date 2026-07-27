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
                )

        return cls(mappings)

    def get_yahoo_symbol(self, egx_symbol: str) -> str:
        symbol = egx_symbol.strip().upper()

        if symbol not in self._mappings:
            raise KeyError(
                f"No symbol mapping found for EGX symbol '{symbol}'. "
                "Add it to config/symbols.csv first."
            )

        yahoo_symbol = self._mappings[symbol].yahoo_symbol

        if not yahoo_symbol:
            raise KeyError(
                f"No Yahoo Finance symbol configured for EGX symbol '{symbol}'."
            )

        return yahoo_symbol

    def get_company_name(self, egx_symbol: str) -> str:
        symbol = egx_symbol.strip().upper()

        if symbol not in self._mappings:
            raise KeyError(f"No symbol mapping found for EGX symbol '{symbol}'.")

        return self._mappings[symbol].company

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
