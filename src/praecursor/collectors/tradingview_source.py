import logging
import threading
import time as time_module
from datetime import date, datetime, timedelta, time
import pandas as pd
from tvDatafeed import TvDatafeed, Interval

from praecursor.collectors.collection_result import CollectionResult
from praecursor.collectors.market_data_source import MarketDataSource
from praecursor.core.price_bar import PriceBar
from praecursor.data.symbol_mapper import SymbolMapper

logger = logging.getLogger(__name__)
_TV_LOCK = threading.Lock()


class TradingViewSource(MarketDataSource):
    """
    Fetch daily historical OHLCV data from TradingView.
    """

    DEFAULT_CONFIDENCE = 0.85

    def __init__(self, symbol_mapper: SymbolMapper | None = None):
        self.symbol_mapper = symbol_mapper or SymbolMapper.from_csv()
        # Initialize tvDatafeed anonymously under lock
        with _TV_LOCK:
            try:
                self.tv = TvDatafeed()
            except Exception as e:
                logger.warning(f"Failed to initialize TvDatafeed: {e}")
                self.tv = None

    @property
    def name(self) -> str:
        return "tradingview"

    def fetch_history(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        interval: Interval = Interval.in_daily,
    ) -> CollectionResult:
        if start_date > end_date:
            raise ValueError("start_date must be before or equal to end_date.")

        tv_symbol = symbol.strip().upper()

        warnings: list[str] = []
        price_bars: list[PriceBar] = []

        # Calculate approximate number of bars needed
        days_diff = (end_date - start_date).days
        # Fetch a bit more to ensure we get enough trading days
        n_bars = int(days_diff * 1.5) + 10
        if interval == Interval.in_15_minute:
            n_bars = max(n_bars * 20, 500)  # Roughly 20 15m bars per day
        else:
            if n_bars < 50:
                n_bars = 50

        df = None
        fetch_error = None

        with _TV_LOCK:
            for attempt in range(2):
                try:
                    if self.tv is None:
                        self.tv = TvDatafeed()

                    # exchange is typically 'EGX'
                    df = self.tv.get_hist(
                        symbol=tv_symbol,
                        exchange="EGX",
                        interval=interval,
                        n_bars=n_bars,
                    )

                    # When connection is dropped, tvDatafeed returns None without an exception
                    if df is None:
                        self.tv = None
                        if attempt == 0:
                            logger.info(f"{symbol}: TradingView returned None (connection lost); retrying once...")
                            time_module.sleep(0.5)
                            continue
                    break
                except Exception as e:
                    fetch_error = e
                    self.tv = None
                    if attempt == 0:
                        logger.info(f"{symbol}: Error fetching from TradingView ({e}); retrying once...")
                        time_module.sleep(0.5)
                    else:
                        break

        if fetch_error is not None and df is None:
            warnings.append(f"{symbol}: Error fetching from TradingView: {fetch_error}")
        elif df is None or df.empty:
            warnings.append(f"{symbol}: TradingView returned no data.")
        else:
            try:
                # df index is datetime
                for index, row in df.iterrows():
                    bar_dt = index.to_pydatetime()
                    if bar_dt.tzinfo is not None:
                        bar_dt = bar_dt.replace(tzinfo=None)
                    bar_date = bar_dt.date()
                    if start_date <= bar_date <= end_date:
                        try:
                            open_p = float(row["open"])
                            high_p = float(row["high"])
                            low_p = float(row["low"])
                            close_p = float(row["close"])
                            vol = int(row["volume"])

                            # Normalize high/low
                            norm_high = max(high_p, open_p, close_p)
                            norm_low = min(low_p, open_p, close_p)

                            if norm_high != high_p or norm_low != low_p:
                                warnings.append(
                                    f"{symbol} {bar_dt}: adjusted high/low range to include open/close values."
                                )

                            final_date = (
                                bar_dt if interval == Interval.in_15_minute else datetime.combine(bar_date, time.min)
                            )

                            price_bars.append(
                                PriceBar(
                                    date=final_date,
                                    open=open_p,
                                    high=norm_high,
                                    low=norm_low,
                                    close=close_p,
                                    volume=vol,
                                )
                            )
                        except (ValueError, TypeError, KeyError) as e:
                            warnings.append(f"{symbol} {bar_dt}: invalid row data: {e}")
            except Exception as e:
                warnings.append(f"{symbol}: Error parsing TradingView data: {e}")

        # Sort bars by date
        price_bars.sort(key=lambda bar: bar.date)

        return CollectionResult(
            symbol=symbol.strip().upper(),
            source_name=self.name,
            price_bars=price_bars,
            warnings=warnings,
            confidence=self.DEFAULT_CONFIDENCE,
        )
