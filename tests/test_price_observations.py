from datetime import date, datetime, timedelta, timezone
import sqlite3
import pytest
from praecursor.collectors.collection_result import CollectionResult
from praecursor.core.price_bar import PriceBar
from praecursor.storage.price_cache import PriceCache
from praecursor.collectors.stockanalysis_source import StockAnalysisSource
from praecursor.data.data_manager import DataManager


def test_revised_prices_preserve_original_observation_and_currency(tmp_path):
    path=tmp_path/'prices.db';cache=PriceCache(path)
    stamp=datetime(2026,11,9,18,tzinfo=timezone.utc)
    result=CollectionResult(symbol='COMI',source_name='stockanalysis',collected_at=stamp,
        price_bars=[PriceBar(date=datetime(2026,11,9),open=100,high=105,low=99,close=103,volume=10000)],
        quote_currency='EGP',reference_url='https://stockanalysis.com/quote/egx/COMI/history/')
    cache.save(result);cache.save(result)
    result.collected_at=stamp+timedelta(days=1)
    result.price_bars=[PriceBar(date=datetime(2026,11,9),open=100,high=105,low=99,close=104,volume=10000)]
    cache.save(result)
    with sqlite3.connect(path) as conn:
        assert conn.execute('SELECT count(*) FROM price_observations').fetchone()[0]==2
        assert conn.execute('SELECT min(first_seen_at) FROM price_observations').fetchone()[0]==stamp.isoformat()
        assert conn.execute('SELECT close FROM source_prices').fetchone()[0]==104
        assert conn.execute('SELECT currency FROM instrument_observations LIMIT 1').fetchone()[0]=='EGP'


def test_stockanalysis_preserves_valid_rows_and_currency_on_bad_history(tmp_path, monkeypatch):
    path = tmp_path / "prices.db"
    source = StockAnalysisSource()
    cache = PriceCache(path)
    rows = [
        ["Nov 12, 2026", "130.34", "130.32", "128.60", "128.75", "128.75", "-", "1,515,863"],
        ["Nov 11, 2026", "130.34", "132.00", "128.60", "128.75", "128.75", "-", "1,515,863"],
    ]
    table = "<table>" + "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows) + "</table>"
    page = "<title>Bank (EGX:COMI)</title><p>Currency is EGP · Price in USD</p>" + table
    monkeypatch.setattr(source, "_download_html", lambda *_: page)
    expected = date(2026, 11, 12)
    result = DataManager([source], price_cache=cache).fetch_history("COMI", date(2026, 11, 11), expected)
    assert [bar.date.date() for bar in result.price_bars] == [date(2026, 11, 11)]
    assert any("skipped invalid" in warning for warning in result.warnings)
    with pytest.raises(ValueError, match="no price bars"):
        DataManager([source], price_cache=cache).fetch_history("COMI", expected, expected)
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT DISTINCT currency FROM instrument_observations").fetchall() == [("USD",)]
        assert conn.execute("SELECT count(*) FROM instrument_observations").fetchone()[0] == 2
        assert conn.execute("SELECT trade_date FROM source_prices").fetchall() == [("2026-11-11",)]
