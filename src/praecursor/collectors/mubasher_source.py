import re
from datetime import date, datetime, time
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from praecursor.collectors.collection_result import CollectionResult
from praecursor.collectors.market_data_source import MarketDataSource
from praecursor.core.price_bar import PriceBar


class MubasherTextParser(HTMLParser):
    """Extract visible text from a Mubasher stock page."""

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return

        stripped_data = data.strip()
        if stripped_data:
            self.parts.append(stripped_data)

    def text(self) -> str:
        return "\n".join(self.parts)


class MubasherSource(MarketDataSource):
    """
    Fetch delayed/latest quote data from Mubasher Info.

    Mubasher pages are useful for latest quote validation, not long historical
    indicator history. This source returns one PriceBar dated today.
    """

    BASE_URL = "https://english.mubasher.info/markets/EGX/stocks"
    DEFAULT_CONFIDENCE = 0.5

    @property
    def name(self) -> str:
        return "mubasher"

    def __init__(self, timeout_seconds: int = 30):
        self.timeout_seconds = timeout_seconds

    def fetch_history(self, symbol: str, start_date: date, end_date: date) -> CollectionResult:
        if start_date > end_date:
            raise ValueError("start_date must be before or equal to end_date.")

        normalized_symbol = symbol.strip().upper()
        quote_date = date.today()

        if quote_date < start_date or quote_date > end_date:
            return CollectionResult(
                symbol=normalized_symbol,
                source_name=self.name,
                warnings=[
                    f"Mubasher latest quote date {quote_date} is outside requested range."
                ],
                confidence=self.DEFAULT_CONFIDENCE,
            )

        html_text = self._download_html(normalized_symbol)
        page_text = self._extract_text(html_text)
        price_bar, warnings = self._parse_latest_quote(normalized_symbol, quote_date, page_text)

        warnings.append(
            "Mubasher quote is delayed/latest-page data and may not match end-of-day close."
        )

        return CollectionResult(
            symbol=normalized_symbol,
            source_name=self.name,
            price_bars=[price_bar],
            warnings=warnings,
            confidence=self.DEFAULT_CONFIDENCE,
        )

    def _download_html(self, symbol: str) -> str:
        encoded_symbol = quote(symbol)
        url = f"{self.BASE_URL}/{encoded_symbol}/"
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
            raise RuntimeError(f"Mubasher returned HTTP {error.code} for {symbol}.") from error
        except URLError as error:
            raise RuntimeError(f"Could not connect to Mubasher for {symbol}: {error.reason}") from error

    def _extract_text(self, html_text: str) -> str:
        parser = MubasherTextParser()
        parser.feed(html_text)
        return parser.text()

    def _parse_latest_quote(self, symbol: str, quote_date: date, page_text: str) -> tuple[PriceBar, list[str]]:
        warnings: list[str] = []
        normalized_text = self._normalize_text(page_text)

        close_price = self._parse_latest_price(page_text, normalized_text)
        open_price = self._parse_labeled_number(normalized_text, "Open")
        high_price = self._parse_labeled_number(normalized_text, "High")
        low_price = self._parse_labeled_number(normalized_text, "Low")
        volume = self._parse_labeled_integer(normalized_text, "Volume")

        if close_price is None:
            raise RuntimeError(f"Could not parse latest Mubasher price for {symbol}.")

        if open_price is None:
            open_price = close_price
            warnings.append(f"{symbol}: Mubasher open price missing; using latest price.")

        if high_price is None:
            high_price = max(open_price, close_price)
            warnings.append(f"{symbol}: Mubasher high price missing; inferred from open/latest.")

        if low_price is None:
            low_price = min(open_price, close_price)
            warnings.append(f"{symbol}: Mubasher low price missing; inferred from open/latest.")

        if volume is None:
            volume = 0
            warnings.append(f"{symbol}: Mubasher volume missing; using zero.")

        normalized_high = max(high_price, open_price, close_price)
        normalized_low = min(low_price, open_price, close_price)

        if normalized_high != high_price or normalized_low != low_price:
            warnings.append(
                f"{symbol} {quote_date}: adjusted high/low range to include open and latest price."
            )

        return (
            PriceBar(
                date=datetime.combine(quote_date, time.min),
                open=float(open_price),
                high=float(normalized_high),
                low=float(normalized_low),
                close=float(close_price),
                volume=int(volume),
            ),
            warnings,
        )

    def _normalize_text(self, value: str) -> str:
        return " ".join(value.split())

    def _parse_latest_price(self, page_text: str, normalized_text: str) -> float | None:
        # Prefer the first standalone number after the Last update text.
        update_match = re.search(
            r"Last update:.*?market time\.\s*([0-9]+(?:\.[0-9]+)?)",
            normalized_text,
            flags=re.IGNORECASE,
        )
        if update_match:
            return float(update_match.group(1))

        # Fallback for pages where HTML parser separated the price onto a new line.
        lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        for index, line in enumerate(lines):
            if line.lower().startswith("last update"):
                for candidate in lines[index + 1 : index + 6]:
                    if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", candidate):
                        return float(candidate)

        return None

    def _parse_labeled_number(self, normalized_text: str, label: str) -> float | None:
        pattern = rf"{re.escape(label)}\s*([0-9]+(?:\.[0-9]+)?)"
        match = re.search(pattern, normalized_text, flags=re.IGNORECASE)
        if not match:
            return None

        return float(match.group(1).replace(",", ""))

    def _parse_labeled_integer(self, normalized_text: str, label: str) -> int | None:
        pattern = rf"{re.escape(label)}\s*([0-9,]+)"
        match = re.search(pattern, normalized_text, flags=re.IGNORECASE)
        if not match:
            return None

        return int(match.group(1).replace(",", ""))
