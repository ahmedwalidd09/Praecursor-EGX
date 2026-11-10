from datetime import datetime, timedelta, timezone
import sqlite3
from praecursor.collectors.collection_result import CollectionResult
from praecursor.core.price_bar import PriceBar
from praecursor.storage.price_cache import PriceCache


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
