import logging
from datetime import date, datetime, timedelta, time
import pandas as pd
from tvDatafeed import TvDatafeed, Interval

from praecursor.collectors.collection_result import CollectionResult
from praecursor.collectors.market_data_source import MarketDataSource
from praecursor.core.price_bar import PriceBar
from praecursor.data.symbol_mapper import SymbolMapper

logger = logging.getLogger(__name__)

class TradingViewSource(MarketDataSource):
    """
    Fetch daily historical OHLCV data from TradingView.
    """

    DEFAULT_CONFIDENCE = 0.85

    def __init__(self, symbol_mapper: SymbolMapper | None = None):
        self.symbol_mapper = symbol_mapper or SymbolMapper.from_csv()
        # Initialize tvDatafeed anonymously
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
    ) -> CollectionResult:
        if start_date > end_date:
            raise ValueError("start_date must be before or equal to end_date.")

        tv_symbol = symbol.strip().upper()
        
        warnings: list[str] = []
        price_bars: list[PriceBar] = []
        
        if self.tv is None:
            warnings.append(f"{symbol}: TvDatafeed is not initialized.")
            return CollectionResult(
                symbol=symbol.strip().upper(),
                source_name=self.name,
                price_bars=price_bars,
                warnings=warnings,
                confidence=self.DEFAULT_CONFIDENCE,
            )
        
        # Calculate approximate number of bars needed
        days_diff = (end_date - start_date).days
        # Fetch a bit more to ensure we get enough trading days
        n_bars = int(days_diff * 1.5) + 10
        if n_bars < 50:
            n_bars = 50

        try:
            # exchange is typically 'EGX'
            df = self.tv.get_hist(
                symbol=tv_symbol,
                exchange='EGX',
                interval=Interval.in_daily,
                n_bars=n_bars
            )
            
            if df is None or df.empty:
                warnings.append(f"{symbol}: TradingView returned no data.")
            else:
                # df index is datetime
                for index, row in df.iterrows():
                    bar_date = index.date()
                    if start_date <= bar_date <= end_date:
                        try:
                            # Normalize high/low
                            open_p = float(row['open'])
                            high_p = float(row['high'])
                            low_p = float(row['low'])
                            close_p = float(row['close'])
                            vol = int(row['volume'])
                            
                            norm_high = max(high_p, open_p, close_p)
                            norm_low = min(low_p, open_p, close_p)
                            
                            if norm_high != high_p or norm_low != low_p:
                                warnings.append(
                                    f"{symbol} {bar_date}: adjusted high/low range to include open/close values."
                                )
                                
                            price_bars.append(
                                PriceBar(
                                    date=datetime.combine(bar_date, time.min),
                                    open=open_p,
                                    high=norm_high,
                                    low=norm_low,
                                    close=close_p,
                                    volume=vol
                                )
                            )
                        except (ValueError, TypeError, KeyError) as e:
                            warnings.append(f"{symbol} {bar_date}: invalid row data: {e}")
                            
        except Exception as e:
            warnings.append(f"{symbol}: Error fetching from TradingView: {e}")

        # Sort bars by date
        price_bars.sort(key=lambda bar: bar.date)

        return CollectionResult(
            symbol=symbol.strip().upper(),
            source_name=self.name,
            price_bars=price_bars,
            warnings=warnings,
            confidence=self.DEFAULT_CONFIDENCE,
        )
