import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

class OutcomeTracker:
    def __init__(self, db_path=None):
        if db_path is None:
            # Default to database/praecursor.db relative to the project root
            root = Path(__file__).resolve().parents[3]
            self.db_path = root / "database" / "praecursor.db"
        else:
            self.db_path = Path(db_path)

    def get_14_day_stats(self):
        """
        Calculates win rate and returns a list of last 10 completed trades
        for the last 14 days, filtering by specific top-tier labels.
        """
        cutoff_date = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')
        
        target_labels = (
            "Next-Day Breakout Candidate",
            "Next-Day Breakout Candidate - Extended",
            "High-Priority Next-Day Watch",
            "Watchlist Tomorrow"
        )
        
        query = """
            SELECT 
                o.symbol,
                o.signal_date,
                o.next_day_hit,
                o.next_day_max_return
            FROM scanner_signal_outcomes o
            WHERE o.signal_date >= ?
            AND o.next_day_label IN (?, ?, ?, ?)
            AND o.next_day_hit IS NOT NULL
            ORDER BY o.signal_date DESC
        """
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(query, (cutoff_date,) + target_labels)
            rows = cursor.fetchall()
            conn.close()
            
            total_tracked = len(rows)
            total_hits = sum(1 for r in rows if r['next_day_hit'] == 1)
            total_misses = total_tracked - total_hits
            win_rate = (total_hits / total_tracked) if total_tracked > 0 else 0.0
            
            valid_returns = [r['next_day_max_return'] for r in rows if r['next_day_max_return'] is not None]
            avg_peak_return = (sum(valid_returns) / len(valid_returns)) if valid_returns else 0.0
            
            last_10_trades = []
            for r in rows[:10]:
                last_10_trades.append({
                    'symbol': r['symbol'],
                    'date': r['signal_date'],
                    'hit': r['next_day_hit'],
                    'return': r['next_day_max_return']
                })
                
            return {
                'total_tracked': total_tracked,
                'total_hits': total_hits,
                'total_misses': total_misses,
                'win_rate': win_rate,
                'avg_peak_return': avg_peak_return,
                'last_10_trades': last_10_trades
            }
        except Exception as e:
            print(f"Error fetching outcome stats: {e}")
            return {
                'total_tracked': 0,
                'total_hits': 0,
                'total_misses': 0,
                'win_rate': 0.0,
                'avg_peak_return': 0.0,
                'last_10_trades': []
            }
