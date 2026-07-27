import json
from datetime import date, datetime, time, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from praecursor.collectors.collection_result import CollectionResult
from praecursor.collectors.market_data_source import MarketDataSource
from praecursor.core.price_bar import PriceBar
from praecursor.data.symbol_mapper import SymbolMapper


class YahooFinanceSource(MarketDataSource):
    """
    Fetch daily historical OHLCV data from Yahoo Finance.

    This source is our first practical real-data collector. Yahoo Finance is
    not the official EGX source, so these records should later be compared
    against additional sources before being treated as high-confidence data.
    """

    BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"
    DEFAULT_CONFIDENCE = 0.6

    def __init__(
        self,
        symbol_mapper: SymbolMapper | None = None,
        timeout_seconds: int = 30,
    ):
        self.symbol_mapper = symbol_mapper or SymbolMapper.from_csv()
        self.timeout_seconds = timeout_seconds

    @property
    def name(self) -> str:
        return "yahoo_finance"

    def fetch_history(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> CollectionResult:
        if start_date > end_date:
            raise ValueError("start_date must be before or equal to end_date.")

        yahoo_symbol = self.symbol_mapper.get_yahoo_symbol(symbol)
        url = self._build_url(yahoo_symbol, start_date, end_date)
        payload = self._download_json(url, yahoo_symbol)
        price_bars, warnings = self._parse_price_bars(payload, symbol)

        return CollectionResult(
            symbol=symbol.strip().upper(),
            source_name=self.name,
            price_bars=price_bars,
            warnings=warnings,
            confidence=self.DEFAULT_CONFIDENCE,
        )

    def _build_url(self, yahoo_symbol: str, start_date: date, end_date: date) -> str:
        # Yahoo period2 is exclusive, so add one day to include end_date.
        period1 = self._to_unix_timestamp(start_date)
        period2 = self._to_unix_timestamp(end_date + timedelta(days=1))
        encoded_symbol = quote(yahoo_symbol)

        return (
            f"{self.BASE_URL}/{encoded_symbol}"
            f"?period1={period1}"
            f"&period2={period2}"
            "&interval=1d"
            "&events=history"
            "&includeAdjustedClose=true"
        )

    def _download_json(self, url: str, yahoo_symbol: str) -> dict:
        request = Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; Praecursor-EGX/0.1; "
                    "+https://github.com/ahmedwalidd09/Praecursor-EGX)"
                ),
                "Accept": "application/json",
            },
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw_text = response.read().decode("utf-8")
                return json.loads(raw_text)
        except HTTPError as error:
            raise RuntimeError(
                f"Yahoo Finance returned HTTP {error.code} for {yahoo_symbol}."
            ) from error
        except URLError as error:
            raise RuntimeError(
                f"Could not connect to Yahoo Finance for {yahoo_symbol}: {error.reason}"
            ) from error
        except json.JSONDecodeError as error:
            raise RuntimeError(
                f"Yahoo Finance returned invalid JSON for {yahoo_symbol}."
            ) from error

    def _parse_price_bars(self, payload: dict, symbol: str) -> tuple[list[PriceBar], list[str]]:
        warnings: list[str] = []
        chart = payload.get("chart", {})

        yahoo_error = chart.get("error")
        if yahoo_error:
            description = yahoo_error.get("description", "Unknown Yahoo Finance error")
            raise RuntimeError(f"Yahoo Finance error for {symbol}: {description}")

        results = chart.get("result") or []
        if not results:
            warnings.append(f"{symbol}: Yahoo Finance returned no result data.")
            return [], warnings

        result = results[0]
        timestamps = result.get("timestamp") or []
        quote_rows = result.get("indicators", {}).get("quote") or []

        if not quote_rows:
            warnings.append(f"{symbol}: Yahoo Finance returned no quote data.")
            return [], warnings

        quote_data = quote_rows[0]
        price_bars: list[PriceBar] = []

        for index, timestamp in enumerate(timestamps):
            parsed_bar = self._parse_single_bar(quote_data, index, timestamp, symbol, warnings)

            if parsed_bar is not None:
                price_bars.append(parsed_bar)

        price_bars.sort(key=lambda bar: bar.date)
        return price_bars, warnings

    def _parse_single_bar(
        self,
        quote_data: dict,
        index: int,
        timestamp: int,
        symbol: str,
        warnings: list[str],
    ) -> PriceBar | None:
        try:
            open_price = quote_data.get("open", [])[index]
            high_price = quote_data.get("high", [])[index]
            low_price = quote_data.get("low", [])[index]
            close_price = quote_data.get("close", [])[index]
            volume = quote_data.get("volume", [])[index]
        except IndexError:
            warnings.append(f"{symbol}: incomplete Yahoo Finance row at index {index}.")
            return None

        trade_date = datetime.fromtimestamp(timestamp, timezone.utc).date()

        if None in (open_price, high_price, low_price, close_price):
            warnings.append(f"{symbol} {trade_date}: missing OHLC value; row skipped.")
            return None

        normalized_high = max(float(high_price), float(open_price), float(close_price))
        normalized_low = min(float(low_price), float(open_price), float(close_price))

        if normalized_high != float(high_price) or normalized_low != float(low_price):
            warnings.append(
                f"{symbol} {trade_date}: adjusted high/low range to include "
                "open and close values."
            )

        if volume is None:
            warnings.append(f"{symbol} {trade_date}: missing volume; using zero.")
            volume = 0

        return PriceBar(
            date=datetime.combine(trade_date, time.min),
            open=float(open_price),
            high=normalized_high,
            low=normalized_low,
            close=float(close_price),
            volume=int(volume),
        )

    def _to_unix_timestamp(self, selected_date: date) -> int:
        selected_datetime = datetime.combine(selected_date, time.min, tzinfo=timezone.utc)
        return int(selected_datetime.timestamp())
