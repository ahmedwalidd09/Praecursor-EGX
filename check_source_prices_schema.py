import sqlite3

conn = sqlite3.connect(r'C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\database\praecursor.db')
columns = conn.execute("PRAGMA table_info(source_prices)").fetchall()
print("source_prices columns:")
for col in columns:
    print(col)
