import sqlite3

def main():
    conn = sqlite3.connect('database/praecursor.db')
    conn.row_factory = sqlite3.Row
    run = conn.execute('SELECT id, generated_at FROM scanner_runs ORDER BY id DESC LIMIT 1').fetchone()
    if not run:
        print('No runs found')
        return
        
    print(f"Run ID: {run['id']} at {run['generated_at']}")
    print("-" * 60)
    
    signals = conn.execute(
        'SELECT rank, symbol, next_day_label, final_predictor_score, latest_close, next_day_target '
        'FROM scanner_signals WHERE run_id=? ORDER BY rank ASC LIMIT 5', 
        (run['id'],)
    ).fetchall()
    
    for s in signals:
        label = s['next_day_label'].replace('\u2b50', '*')
        print(f"#{s['rank']} {s['symbol']} | {label} | AI Score: {s['final_predictor_score']*100:.1f}% | Close: {s['latest_close']:.2f} | Target: {s['next_day_target']:.2f}")

if __name__ == '__main__':
    main()
