import sqlite3
import pandas as pd

conn = sqlite3.connect('database/praecursor.db')
query = "SELECT MAX(date) FROM source_prices WHERE symbol='UEFM';"
df = pd.read_sql_query(query, conn)
print("Latest date for UEFM:", df.iloc[0, 0])
