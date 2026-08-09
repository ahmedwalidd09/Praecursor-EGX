import sqlite3

conn = sqlite3.connect(r'C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\database\praecursor.db')
cursor = conn.cursor()
cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
tables = cursor.fetchall()
for t in tables:
    print(t[0])