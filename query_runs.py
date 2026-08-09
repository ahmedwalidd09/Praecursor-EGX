import sqlite3

def query():
    conn = sqlite3.connect('database/praecursor.db')
    
    # Get the top 8 for the latest run today
    runs = conn.execute("SELECT id, generated_at FROM scanner_runs ORDER BY id DESC LIMIT 1").fetchall()
    for run in runs:
        run_id = run[0]
        gen_at = run[1]
        
        symbols = conn.execute(f"SELECT symbol, rank FROM scanner_signals WHERE run_id = {run_id} ORDER BY rank ASC LIMIT 8").fetchall()
        sym_list = [s[0] for s in symbols]
        
        print(f"LATEST RUN - ID: {run_id} | Date: {gen_at}")
        for i, s in enumerate(symbols):
            print(f"#{i+1}: {s[0]} (Rank: {s[1]})")

if __name__ == "__main__":
    query()
