import sqlite3
import pprint

def query():
    conn = sqlite3.connect('database/praecursor.db')
    results = conn.execute("""
        WITH day_runs AS (
            SELECT MAX(id) as run_id, date(generated_at) as run_date
            FROM scanner_runs
            WHERE date(generated_at) = '2026-08-02'
            GROUP BY date(generated_at)
        )
        SELECT s.symbol, s.rank, s.next_day_score 
        FROM scanner_signals s
        JOIN day_runs dr ON s.run_id = dr.run_id
        ORDER BY s.rank ASC
        LIMIT 10
    """).fetchall()
    pprint.pprint(results)

if __name__ == "__main__":
    query()
