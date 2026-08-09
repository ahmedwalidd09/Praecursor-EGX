import sqlite3
from contextlib import closing
from collections import defaultdict
import json
import logging

from praecursor.storage.database import connect

logger = logging.getLogger(__name__)

class IndicatorAttributionAnalyzer:
    def __init__(self, database_path=None):
        self.database_path = database_path

    def _connect(self):
        return connect(self.database_path)

    def analyze_components(self) -> dict:
        """
        Analyze correlation between score components and next-day hit outcomes.
        Returns a dictionary with component performance metrics.
        """
        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            
            # Fetch all outcomes joined with their scanner_signals score_components
            # score_components is stored as JSON in scanner_signals
            query = """
            SELECT o.symbol, o.signal_date, o.next_day_hit, o.next_day_return,
                   s.score_components
            FROM scanner_signal_outcomes o
            JOIN scanner_signals s ON s.run_id = o.run_id AND s.symbol = o.symbol
            WHERE o.next_day_hit IS NOT NULL
            """
            rows = conn.execute(query).fetchall()

        if not rows:
            logger.warning("No historical outcomes available for attribution analysis.")
            return {}

        component_stats = defaultdict(lambda: {
            "hit_sum": 0.0,
            "miss_sum": 0.0,
            "hit_count": 0,
            "miss_count": 0,
            "max_score_seen": 0.0
        })

        total_hits = 0
        total_misses = 0

        for r in rows:
            hit = r["next_day_hit"]
            components_json = r["score_components"]
            
            if not components_json:
                continue
                
            try:
                components = json.loads(components_json)
            except Exception:
                continue

            if hit == 1:
                total_hits += 1
            else:
                total_misses += 1

            for comp in components:
                name = comp.get("name", "Unknown")
                score = float(comp.get("score", 0.0))
                max_score = float(comp.get("max_score", 0.0))
                
                stats = component_stats[name]
                stats["max_score_seen"] = max(stats["max_score_seen"], max_score)
                
                if hit == 1:
                    stats["hit_sum"] += score
                    stats["hit_count"] += 1
                else:
                    stats["miss_sum"] += score
                    stats["miss_count"] += 1

        results = {}
        for name, stats in component_stats.items():
            avg_score_hit = stats["hit_sum"] / stats["hit_count"] if stats["hit_count"] > 0 else 0.0
            avg_score_miss = stats["miss_sum"] / stats["miss_count"] if stats["miss_count"] > 0 else 0.0
            
            # Predictive Power: How much higher does this component score on a HIT compared to a MISS?
            # Positive means it's predictive of success. Negative means it's noise or counter-indicator.
            predictive_power = avg_score_hit - avg_score_miss
            
            # Normalize by its max possible score to get a clean signal strength [0, 1]
            max_possible = stats["max_score_seen"]
            signal_strength = (predictive_power / max_possible) if max_possible > 0 else 0.0
            
            results[name] = {
                "avg_score_on_hit": round(avg_score_hit, 2),
                "avg_score_on_miss": round(avg_score_miss, 2),
                "predictive_power": round(predictive_power, 2),
                "signal_strength": round(signal_strength * 100, 2),  # Percentage
                "max_score_alloc": max_possible
            }
            
        # Sort by signal strength descending
        return dict(sorted(results.items(), key=lambda x: x[1]["signal_strength"], reverse=True))
