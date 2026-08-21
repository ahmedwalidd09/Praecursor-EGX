COMPANY_SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    ticker TEXT PRIMARY KEY,
    name TEXT,
    sector TEXT,
    free_float REAL,
    market_cap REAL,
    created_at TEXT
);
"""

LEGACY_PRICE_SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT,
    trade_date TEXT,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    value REAL
);
"""

PRICE_CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS source_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    source TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume INTEGER NOT NULL,
    confidence REAL NOT NULL DEFAULT 0,
    collected_at TEXT NOT NULL,
    UNIQUE(ticker, trade_date, source)
);

CREATE INDEX IF NOT EXISTS idx_source_prices_lookup
ON source_prices (ticker, source, trade_date);
"""

DISCLOSURE_SCHEMA = """
CREATE TABLE IF NOT EXISTS disclosures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT,
    title TEXT,
    source TEXT,
    url TEXT,
    published_at TEXT,
    collected_at TEXT
);
"""

OWNERSHIP_SCHEMA = """
CREATE TABLE IF NOT EXISTS ownership (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT,
    investor TEXT,
    shares REAL,
    ownership_before REAL,
    ownership_after REAL,
    transaction_date TEXT,
    disclosure_date TEXT
);
"""

SCORE_SCHEMA = """
CREATE TABLE IF NOT EXISTS scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT,
    score REAL,
    confidence REAL,
    generated_at TEXT
);
"""

INTRADAY_PRICE_SCHEMA = """
CREATE TABLE IF NOT EXISTS intraday_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    trade_time TEXT NOT NULL,
    source TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume INTEGER NOT NULL,
    collected_at TEXT NOT NULL,
    UNIQUE(ticker, trade_time, source)
);

CREATE INDEX IF NOT EXISTS idx_intraday_prices_lookup
ON intraday_prices (ticker, source, trade_time);
"""

SCHEMA = "\n".join(
    [
        COMPANY_SCHEMA,
        LEGACY_PRICE_SCHEMA,
        PRICE_CACHE_SCHEMA,
        DISCLOSURE_SCHEMA,
        OWNERSHIP_SCHEMA,
        SCORE_SCHEMA,
        INTRADAY_PRICE_SCHEMA,
    ]
)
