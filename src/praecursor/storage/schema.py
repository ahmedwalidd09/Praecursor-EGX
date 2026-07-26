SCHEMA = """

CREATE TABLE IF NOT EXISTS companies (
    ticker TEXT PRIMARY KEY,
    name TEXT,
    sector TEXT,
    free_float REAL,
    market_cap REAL,
    created_at TEXT
);

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

CREATE TABLE IF NOT EXISTS disclosures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT,
    title TEXT,
    source TEXT,
    url TEXT,
    published_at TEXT,
    collected_at TEXT
);

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

CREATE TABLE IF NOT EXISTS scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT,
    score REAL,
    confidence REAL,
    generated_at TEXT
);

"""