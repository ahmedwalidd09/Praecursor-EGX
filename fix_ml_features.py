import pathlib
import re

def fix_retrain_models():
    file_path = pathlib.Path(r'C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\tools\retrain_models.py')
    text = file_path.read_text(encoding='utf-8')
    
    new_dict = '''INDICATOR_TO_FEATURE = {
    "RSI14": "rsi14",
    "RelVolume20": "rel_volume20",
    "MACDHistogram": "macd_histogram",
    "Momentum20": "momentum20",
    "Breakout20": "breakout20",
    "Breakout50": "breakout50",
    "RSIRebound": "rsi_rebound",
    "EMA20Reclaim": "ema20_reclaim",
    "MACDHistogramImprovement": "macd_histogram_improvement",
    "VolumeSpikeFromWeakness": "volume_spike_from_weakness",
    "Momentum5": "momentum5",
    "BBW20": "bbw20",
    "MTF_Trend": "mtf_trend",
    "VPOC_Distance": "vpoc_distance",
    "ADX14": "adx14",
    "ROC10": "roc10",
    "StochRSI": "stoch_rsi",
    "VWAPMom10": "vwap_mom10",
    "AvgTurnover20": "avg_turnover_20",
    "ClosedAtLimitUp": "closed_at_limit_up",
    "ATRPercent14": "atr_pct14",
    "KalmanTrend": "kalman_trend",
    "RSI14_ZScore": "rsi_zscore",
    "Momentum20_ZScore": "mom_zscore",
    "LiquidityVacuumScore": "liquidity_vacuum_score",
    "Distance_To_ATH": "distance_to_ath",
    "New_ATH_Made_Today": "new_ath_made_today",
    "ATR_Expansion_Ratio": "atr_expansion_ratio",
    "ATR_Exploding": "atr_exploding",
    "Squeeze_Fired": "squeeze_fired",
    "Squeeze_Building": "squeeze_building",
    "Full_Confirmation": "nhm_full",
    "Partial_Confirmation": "nhm_partial",
    "Very_Near": "nhm_very_near",
    "Near_High": "nhm_near_high",
    "Momentum1": "momentum1",
    "RSISlope3": "rsi_slope3",
    "ConsecutiveGreen": "consecutive_green",
    "DayOfWeek": "day_of_week",
    "hurst_exponent": "hurst_exponent",
    "news_sentiment": "news_sentiment",
    "lstm_prob": "lstm_prob",
}'''
    start = text.find('INDICATOR_TO_FEATURE = {')
    end = text.find('}', start) + 1
    text = text[:start] + new_dict + text[end:]

    def_extract = '''def extract_features_from_stock(stock: Stock, scorer: OpportunityScorer) -> dict | None:
    """Run the full scoring pipeline and extract the 20 ML features."""
    try:
        opp_score = scorer.score(stock)
        
        flat_values = {}
        for k, v in opp_score.indicator_values.items():
            if isinstance(v, dict):
                for sub_k, sub_v in v.items():
                    flat_values[sub_k] = sub_v
            else:
                flat_values[k] = v

        row = {}
        for indicator_name, feature_name in INDICATOR_TO_FEATURE.items():
            val = flat_values.get(indicator_name, 0.0)
            if val != val:  # NaN check
                val = 0.0
            row[feature_name] = val

        return row
    except Exception as e:
        logger.debug(f"Failed to score {stock.symbol}: {e}")
        return None'''
    text = re.sub(r'def extract_features_from_stock.*?return None', def_extract, text, flags=re.DOTALL)

    def_extract_2 = '''                    cached_vals = json.loads(cached_json)
                    flat_vals = {}
                    for k, v in cached_vals.items():
                        if isinstance(v, dict):
                            for sub_k, sub_v in v.items():
                                flat_vals[sub_k] = sub_v
                        else:
                            flat_vals[k] = v
                    feat_row = {}
                    for indicator_name, feature_name in INDICATOR_TO_FEATURE.items():
                        val = flat_vals.get(indicator_name, 0.0)
                        if val != val:  # NaN
                            val = 0.0
                        feat_row[feature_name] = val
                    X.append([feat_row[f] for f in FEATURES])'''
    text = re.sub(r'                    cached_vals = json.loads\(cached_json\).*?X\.append\(\[feat_row\[f\] for f in FEATURES\]\)', def_extract_2, text, flags=re.DOTALL)
    
    file_path.write_text(text, encoding='utf-8')
    print('Fixed retrain_models.py')


def fix_next_day():
    file_path = pathlib.Path(r'C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\src\praecursor\scoring\next_day.py')
    text = file_path.read_text(encoding='utf-8')

    old_features_block = '''        features = [
            "RSI14", "RelVolume20", "MACDHistogram", "Momentum20", 
            "Breakout20", "Breakout50", "RSIRebound", "EMA20Reclaim", 
            "MACDHistogramImprovement", "VolumeSpikeFromWeakness", "Momentum5", "BBW20",
            "MTF_Trend", "VPOC_Distance", "ADX14", "ROC10", "StochRSI", "VWAPMom10",
            "AvgTurnover20", "ClosedAtLimitUp", "ATRPercent14",
            "Momentum1", "RSISlope3", "ConsecutiveGreen", "DayOfWeek",
            "hurst_exponent", "news_sentiment", "lstm_prob"
        ]
        csv_features = [
            "rsi14", "rel_volume20", "macd_histogram", "momentum20", "breakout20", "breakout50",
            "rsi_rebound", "ema20_reclaim", "macd_histogram_improvement", "volume_spike_from_weakness", "momentum5", "bbw20",
            "mtf_trend", "vpoc_distance", "adx14", "roc10", "stoch_rsi", "vwap_mom10",
            "avg_turnover_20", "closed_at_limit_up", "atr_pct14",
            "momentum1", "rsi_slope3", "consecutive_green", "day_of_week",
            "hurst_exponent", "news_sentiment", "lstm_prob"
        ]'''

    new_features_block = '''        features = [
            "RSI14", "RelVolume20", "MACDHistogram", "Momentum20", 
            "Breakout20", "Breakout50", "RSIRebound", "EMA20Reclaim", 
            "MACDHistogramImprovement", "VolumeSpikeFromWeakness", "Momentum5", "BBW20",
            "MTF_Trend", "VPOC_Distance", "ADX14", "ROC10", "StochRSI", "VWAPMom10",
            "AvgTurnover20", "ClosedAtLimitUp", "ATRPercent14",
            "KalmanTrend", "RSI14_ZScore", "Momentum20_ZScore", "LiquidityVacuumScore",
            "Distance_To_ATH", "New_ATH_Made_Today", "ATR_Expansion_Ratio", "ATR_Exploding",
            "Squeeze_Fired", "Squeeze_Building", "Full_Confirmation", "Partial_Confirmation",
            "Very_Near", "Near_High",
            "Momentum1", "RSISlope3", "ConsecutiveGreen", "DayOfWeek",
            "hurst_exponent", "news_sentiment", "lstm_prob"
        ]
        csv_features = [
            "rsi14", "rel_volume20", "macd_histogram", "momentum20", "breakout20", "breakout50",
            "rsi_rebound", "ema20_reclaim", "macd_histogram_improvement", "volume_spike_from_weakness", "momentum5", "bbw20",
            "mtf_trend", "vpoc_distance", "adx14", "roc10", "stoch_rsi", "vwap_mom10",
            "avg_turnover_20", "closed_at_limit_up", "atr_pct14",
            "kalman_trend", "rsi_zscore", "mom_zscore", "liquidity_vacuum_score",
            "distance_to_ath", "new_ath_made_today", "atr_expansion_ratio", "atr_exploding",
            "squeeze_fired", "squeeze_building", "nhm_full", "nhm_partial",
            "nhm_very_near", "nhm_near_high",
            "momentum1", "rsi_slope3", "consecutive_green", "day_of_week",
            "hurst_exponent", "news_sentiment", "lstm_prob"
        ]'''
        
    text = text.replace(old_features_block, new_features_block)
    
    old_row_data = '''row_data = {csv_name: values.get(orig_name, 0.0) for csv_name, orig_name in zip(csv_features, features)}'''
    new_row_data = '''flat_values = {}
        for k, v in values.items():
            if isinstance(v, dict):
                for sub_k, sub_v in v.items():
                    flat_values[sub_k] = sub_v
            else:
                flat_values[k] = v
        row_data = {csv_name: flat_values.get(orig_name, 0.0) for csv_name, orig_name in zip(csv_features, features)}'''
    text = text.replace(old_row_data, new_row_data)

    file_path.write_text(text, encoding='utf-8')
    print('Fixed next_day.py')


if __name__ == '__main__':
    fix_retrain_models()
    fix_next_day()
