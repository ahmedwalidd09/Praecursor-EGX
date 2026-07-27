from datetime import date, datetime, time
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from praecursor.collectors.collection_result import CollectionResult
from praecursor.collectors.market_data_source import MarketDataSource
from praecursor.core.price_bar import PriceBar
from praecursor.data.symbol_mapper import SymbolMapper


class StockAnalysisTableParser(HTMLParser):
    """Extract table rows from a StockAnalysis historical prices page."""

    def __init__(self):
        super().__init__()
        self.rows: list[list[str]] = []
        self._current_row: list[str] = []
        self._current_cell_parts: list[str] = []
        self._inside_row = False
        self._inside_cell = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._inside_row = True
            self._current_row = []

        if tag in {"td", "th"} and self._inside_row:
            self._inside_cell = True
            self._current_cell_parts = []

    def handle_data(self, data: str) -> None:
        if self._inside_cell:
            stripped_data = data.strip()

            if stripped_data:
                self._current_cell_parts.append(stripped_data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._inside_cell:
            cell_text = " ".join(self._current_cell_parts).strip()
            self._current_row.append(cell_text)
            self._inside_cell = False
            self._current_cell_parts = []

        if tag == "tr" and self._inside_row:
            if self._current_row:
                self.rows.append(self._current_row)

            self._inside_row = False
            self._current_row = []


class StockAnalysisSource(MarketDataSource):
    """
    Fetch daily historical OHLCV data from StockAnalysis.

    This is a second independent source. It is primarily useful for recent
    history and cross-checking Yahoo Finance close prices.
    """

    BASE_URL = "https://stockanalysis.com/quote/egx"
    DEFAULT_CONFIDENCE = 0.65

    def __init__(
        self,
        symbol_mapper: SymbolMapper | None = None,
        timeout_seconds: int = 30,
    ):
        self.symbol_mapper = symbol_mapper or SymbolMapper.from_csv()
        self.timeout_seconds = timeout_seconds

    @property
    def name(self) -> str:
        return "stockanalysis"

    def fetch_history(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> CollectionResult:
        if start_date > end_date:
            raise ValueError("start_date must be before or equal to end_date.")

        stockanalysis_symbol = self.symbol_mapper.get_stockanalysis_symbol(symbol)
        url = self._build_url(stockanalysis_symbol)
        html_text = self._download_html(url, stockanalysis_symbol)
        price_bars, warnings = self._parse_price_bars(html_text, symbol, start_date, end_date)

        return CollectionResult(
            symbol=symbol.strip().upper(),
            source_name=self.name,
            price_bars=price_bars,
            warnings=warnings,
            confidence=self.DEFAULT_CONFIDENCE,
        )

    def _build_url(self, stockanalysis_symbol: str) -> str:
        encoded_symbol = quote(stockanalysis_symbol.strip().upper())
        return f"{self.BASE_URL}/{encoded_symbol}/history/"

    def _download_html(self, url: str, stockanalysis_symbol: str) -> str:
        request = Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; Praecursor-EGX/0.1; "
                    "+https://github.com/ahmedwalidd09/Praecursor-EGX)"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return response.read().decode("utf-8", errors="replace")
        except HTTPError as error:
            raise RuntimeError(
                f"StockAnalysis returned HTTP {error.code} for {stockanalysis_symbol}."
            ) from error
        except URLError as error:
            raise RuntimeError(
                f"Could not connect to StockAnalysis for {stockanalysis_symbol}: {error.reason}"
            ) from error

    def _parse_price_bars(
        self,
        html_text: str,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> tuple[list[PriceBar], list[str]]:
        parser = StockAnalysisTableParser()
        parser.feed(html_text)

        price_bars: list[PriceBar] = []
        warnings: list[str] = []

        for row in parser.rows:
            price_bar = self._parse_row(row, symbol, warnings)

            if price_bar is None:
                continue

            trade_date = price_bar.date.date()

            if start_date <= trade_date <= end_date:
                price_bars.append(price_bar)

        price_bars.sort(key=lambda bar: bar.date)

        if not price_bars:
            warnings.append(
                f"{symbol}: StockAnalysis returned no price bars in requested date range."
            )

        return price_bars, warnings

    def _parse_row(
        self,
        row: list[str],
        symbol: str,
        warnings: list[str],
    ) -> PriceBar | None:
        # Expected columns: Date, Open, High, Low, Close, Adj. Close, Change, Volume
        if len(row) < 8:
            return None

        trade_date = self._parse_date(row[0])

        if trade_date is None:
            return None

        try:
            open_price = self._parse_float(row[1])
            high_price = self._parse_float(row[2])
            low_price = self._parse_float(row[3])
            close_price = self._parse_float(row[4])
            volume = self._parse_volume(row[7])
        except ValueError as error:
            warnings.append(f"{symbol} {trade_date}: skipped malformed StockAnalysis row: {error}")
            return None

        normalized_high = max(high_price, open_price, close_price)
        normalized_low = min(low_price, open_price, close_price)

        if normalized_high != high_price or normalized_low != low_price:
            warnings.append(
                f"{symbol} {trade_date}: adjusted high/low range to include "
                "open and close values."
            )

        return PriceBar(
            date=datetime.combine(trade_date, time.min),
            open=open_price,
            high=normalized_high,
            low=normalized_low,
            close=close_price,
            volume=volume,
        )

    def _parse_date(self, value: str) -> date | None:
        try:
            return datetime.strptime(value.strip(), "%b %d, %Y").date()
        except ValueError:
            return None

    def _parse_float(self, value: str) -> float:
        normalized_value = value.replace(",", "").strip()

        if normalized_value in {"", "-"}:
            raise ValueError("missing numeric value")

        return float(normalized_value)

    def _parse_volume(self, value: str) -> int:
        normalized_value = value.replace(",", "").strip()

        if normalized_value in {"", "-"}:
            return 0

        return int(float(normalized_value))
