from dataclasses import dataclass, field
from math import isnan

from praecursor.core.stock import Stock
from praecursor.scoring.analyzer import Analyzer
from praecursor.scoring.atr import ATRIndicator, ATRPercentIndicator
from praecursor.scoring.adx import ADXIndicator
from praecursor.scoring.average_volume import AverageVolumeIndicator
from praecursor.scoring.bollinger import BollingerBandWidthIndicator
from praecursor.scoring.breakout import CloseBreakoutIndicator, CloseHighIndicator, NearCloseHighIndicator, VolumeConfirmedBreakoutIndicator
from praecursor.scoring.cmf import CMFIndicator
from praecursor.scoring.donchian import DonchianChannelsIndicator, DonchianBreakoutIndicator
from praecursor.scoring.ema import EMAIndicator
from praecursor.scoring.elder_ray import ElderRayIndicator
from praecursor.scoring.fisher import FisherTransformIndicator
from praecursor.scoring.force_index import ForceIndexIndicator
from praecursor.scoring.ichimoku import IchimokuIndicator
from praecursor.scoring.kalman import KalmanFilterIndicator
from praecursor.scoring.keltner import KeltnerChannelsIndicator, KeltnerSqueezeIndicator
from praecursor.scoring.limit_up import LimitUpIndicator
from praecursor.scoring.liquidity_vacuum import LiquidityVacuumIndicator
from praecursor.scoring.macd import MACDHistogramIndicator, MACDLineIndicator, MACDSignalIndicator
from praecursor.scoring.mfi import MFIIndicator
from praecursor.scoring.mtf import MultiTimeframeIndicator
from praecursor.scoring.near_high_momentum import NearHighMomentumIndicator
from praecursor.scoring.price_momentum import PriceMomentumIndicator
from praecursor.scoring.relative_strength import RelativeStrengthIndicator
from praecursor.scoring.relative_volume import RelativeVolumeIndicator
from praecursor.scoring.result import IndicatorResult
from praecursor.scoring.reversal import (
    EMA20ReclaimIndicator,
    MACDHistogramImprovementIndicator,
    Momentum5Indicator,
    RSIReboundIndicator,
    VolumeSpikeFromWeaknessIndicator,
)
from praecursor.scoring.rsi import RSIIndicator
from praecursor.scoring.roc import ROCIndicator
from praecursor.scoring.squeeze import SqueezeIndicator
from praecursor.scoring.stoch_rsi import StochasticRSIIndicator
from praecursor.scoring.supertrend import SuperTrendIndicator
from praecursor.scoring.trend_strength import TrendStrengthIndicator
from praecursor.scoring.turnover import AverageTurnoverIndicator
from praecursor.scoring.volatility_expansion import VolatilityExpansionIndicator
from praecursor.scoring.vpoc import VPOCIndicator
from praecursor.scoring.vwap_momentum import VWAPMomentumIndicator
from praecursor.scoring.vwap_proximity import VWAPProximityIndicator
from praecursor.scoring.williams_r import WilliamsRIndicator
from praecursor.scoring.zscore import RollingZScoreIndicator
from praecursor.scoring.all_time_high import AllTimeHighIndicator
from praecursor.scoring.block_trade import BlockTradeIndicator
from praecursor.scoring.distribution_exhaustion import DistributionExhaustionIndicator
from praecursor.scoring.order_flow_imbalance import OrderFlowImbalanceIndicator
from praecursor.scoring.v_macd import VMACDSignalIndicator
from praecursor.scoring.vsa import VSANoDemandIndicator
from praecursor.scoring.evm import EVMIndicator
from praecursor.scoring.tsi import TSIIndicator
from praecursor.scoring.avwap import AVWAPIndicator
from praecursor.scoring.closing_aggression import ClosingAggressionIndicator
from praecursor.scoring.compression_nr7 import NR7CompressionIndicator
from praecursor.scoring.vsa_absorption import VSAAbsorptionIndicator
from praecursor.scoring.sector_spillover import SectorSpilloverIndicator
import csv
from pathlib import Path

_SECTOR_MAP = {}
_SECTOR_BREAKOUT_CACHE = {}

def _load_sectors():
    if _SECTOR_MAP:
        return
    try:
        csv_path = Path(__file__).resolve().parents[3] / "config" / "symbols.csv"
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                _SECTOR_MAP[row["egx_symbol"]] = row["sector"]
    except Exception:
        pass
    _EGX_SECTORS = {
        'Banks': ['COMI', 'QNBA', 'ADIB', 'HDBK', 'FAIS', 'CIEB', 'EGBE', 'SAIB', 'ASGC'],
        'Real Estate': ['TMGH', 'PHDC', 'EGSA', 'MNHD', 'EMFD', 'ORHD', 'EGREF'],
        'Construction': ['OCDI', 'ELEC', 'MBEG', 'HELI'],
        'Chemicals': ['EFIC', 'KABO', 'SKPC', 'EPCO'],
        'Food': ['JUFO', 'ISMA', 'EAST', 'DSCW', 'CANA'],
        'Textiles': ['GTWL', 'ORAS', 'SPIN'],
        'Pharma': ['AXPH', 'EPHA', 'PHAR'],
        'Telecom': ['ETEL', 'OTMT'],
    }
    for sector, syms in _EGX_SECTORS.items():
        for sym in syms:
            if sym not in _SECTOR_MAP:
                _SECTOR_MAP[sym] = sector

@dataclass(frozen=True)
class ScoreComponent:
    """One explainable part of the opportunity score."""

    name: str
    score: float
    max_score: float
    reason: str


@dataclass(frozen=True)
class OpportunityScore:
    """Final opportunity score for one stock."""

    symbol: str
    company: str
    latest_close: float
    total_score: float
    max_score: float
    indicator_values: dict[str, float]
    components: list[ScoreComponent] = field(default_factory=list)
    stock: Stock | None = None

    @property
    def score_percent(self) -> float:
        if self.max_score == 0:
            return 0.0

        return max(0.0, min((self.total_score / self.max_score) * 100, 100.0))


class OpportunityScorer:
    """
    Calculate an explainable opportunity score.

    Enhanced model (v2.0):
    - Trend Structure (EMA alignment, ADX, SuperTrend, Ichimoku): 30 points
    - Momentum Oscillators (RSI, MFI, Williams %R, StochRSI, Fisher): 10 points
    - MACD & MACD Histogram: 10 points
    - Price Momentum (20-bar, 5-bar, ROC, VWAP Momentum): 15 points
    - Volume & Flow (Rel Volume, CMF, Force Index, Turnover): 15 points
    - Breakout & Channel Setup (Donchian, Keltner, Bollinger, Breakouts): 20 points
    - Reversal & Reclaim Signals: 10 points
    - Market Structure (MTF Trend, VPOC, Relative Strength): 10 points
    - Limit Up Detection: 5 points
    Total: 125 points (normalized to 100%)
    """

    MAX_SCORE = 170.0

    def __init__(self):
        self.analyzer = Analyzer()
        # Core EMAs
        self.analyzer.add_indicator(EMAIndicator(20))
        self.analyzer.add_indicator(EMAIndicator(50))
        self.analyzer.add_indicator(EMAIndicator(200))
        # Momentum Oscillators
        self.analyzer.add_indicator(RSIIndicator(14))
        self.analyzer.add_indicator(MFIIndicator(14))
        self.analyzer.add_indicator(WilliamsRIndicator(14))
        self.analyzer.add_indicator(StochasticRSIIndicator())
        self.analyzer.add_indicator(FisherTransformIndicator(10))
        # Volume & Flow
        self.analyzer.add_indicator(AverageVolumeIndicator(20))
        self.analyzer.add_indicator(RelativeVolumeIndicator(20))
        self.analyzer.add_indicator(CMFIndicator(20))
        self.analyzer.add_indicator(ForceIndexIndicator(13))
        self.analyzer.add_indicator(AverageTurnoverIndicator(20))
        # MACD
        self.analyzer.add_indicator(MACDLineIndicator())
        self.analyzer.add_indicator(MACDSignalIndicator())
        self.analyzer.add_indicator(MACDHistogramIndicator())
        # Price Momentum
        self.analyzer.add_indicator(PriceMomentumIndicator(20))
        self.analyzer.add_indicator(ROCIndicator(10))
        self.analyzer.add_indicator(Momentum5Indicator())
        # Trend & Structure
        self.analyzer.add_indicator(TrendStrengthIndicator())
        self.analyzer.add_indicator(ADXIndicator(14))
        self.analyzer.add_indicator(IchimokuIndicator())
        self.analyzer.add_indicator(SuperTrendIndicator(10, 3.0))
        self.analyzer.add_indicator(ElderRayIndicator(13))
        self.analyzer.add_indicator(RelativeStrengthIndicator(50))
        # Volatility & Channels
        self.analyzer.add_indicator(ATRIndicator(14))
        self.analyzer.add_indicator(ATRPercentIndicator(14))
        self.analyzer.add_indicator(BollingerBandWidthIndicator(20, 2.0))
        self.analyzer.add_indicator(KeltnerChannelsIndicator(20, 2.0))
        self.analyzer.add_indicator(KeltnerSqueezeIndicator(20, 2.0, 50))
        self.analyzer.add_indicator(DonchianChannelsIndicator(20))
        self.analyzer.add_indicator(DonchianBreakoutIndicator(20))
        # Breakout & Reversal
        self.analyzer.add_indicator(CloseBreakoutIndicator(20))
        self.analyzer.add_indicator(CloseBreakoutIndicator(50))
        self.analyzer.add_indicator(CloseHighIndicator(250))
        self.analyzer.add_indicator(NearCloseHighIndicator(250))
        self.analyzer.add_indicator(VolumeConfirmedBreakoutIndicator())
        self.analyzer.add_indicator(RSIReboundIndicator())
        self.analyzer.add_indicator(EMA20ReclaimIndicator())
        self.analyzer.add_indicator(MACDHistogramImprovementIndicator())
        self.analyzer.add_indicator(VolumeSpikeFromWeaknessIndicator())
        self.analyzer.add_indicator(LimitUpIndicator())
        # Multi-timeframe & Market Structure
        self.analyzer.add_indicator(MultiTimeframeIndicator())
        self.analyzer.add_indicator(VPOCIndicator(100))
        self.analyzer.add_indicator(VWAPMomentumIndicator(10))
        self.analyzer.add_indicator(VWAPProximityIndicator(20))  # Upgrade #4
        # Advanced Features
        self.analyzer.add_indicator(KalmanFilterIndicator())
        self.analyzer.add_indicator(LiquidityVacuumIndicator())
        self.analyzer.add_indicator(RollingZScoreIndicator())
        self.analyzer.add_indicator(AllTimeHighIndicator())
        self.analyzer.add_indicator(BlockTradeIndicator()) # Batch 2 Upgrade #2
        self.analyzer.add_indicator(DistributionExhaustionIndicator()) # Batch 2 Upgrade #5
        self.analyzer.add_indicator(OrderFlowImbalanceIndicator()) # Batch 2 Upgrade #9
        # Explosive Setup Hunters
        self.analyzer.add_indicator(VolatilityExpansionIndicator())
        self.analyzer.add_indicator(SqueezeIndicator())
        self.analyzer.add_indicator(NearHighMomentumIndicator())
        # Batch 3 Upgrades
        self.analyzer.add_indicator(VMACDSignalIndicator())
        self.analyzer.add_indicator(VSANoDemandIndicator())
        self.analyzer.add_indicator(EVMIndicator())
        self.analyzer.add_indicator(TSIIndicator())
        self.analyzer.add_indicator(AVWAPIndicator())
        # v6.1 Next-Day Alpha Hunters
        self.analyzer.add_indicator(ClosingAggressionIndicator())
        self.analyzer.add_indicator(NR7CompressionIndicator())
        self.analyzer.add_indicator(VSAAbsorptionIndicator())
        self.analyzer.add_indicator(SectorSpilloverIndicator())

    def score(self, stock: Stock) -> OpportunityScore:
        latest_close = stock.latest().close
        indicator_values = self._calculate_indicators(stock)
        components = self._build_components(stock.symbol, latest_close, indicator_values)
        total_score = sum(component.score for component in components)

        return OpportunityScore(
            symbol=stock.symbol,
            company=stock.company,
            latest_close=latest_close,
            total_score=total_score,
            max_score=sum(c.max_score for c in components),
            indicator_values=indicator_values,
            components=components,
            stock=stock,
        )

    def _calculate_indicators(self, stock: Stock) -> dict[str, float]:
        results: list[IndicatorResult] = self.analyzer.analyze(stock)
        return {result.name: result.value for result in results}

    def _build_components(
        self,
        symbol: str,
        latest_close: float,
        indicator_values: dict[str, float],
    ) -> list[ScoreComponent]:
        # Extract all indicator values
        ema20 = indicator_values.get("EMA20", float("nan"))
        ema50 = indicator_values.get("EMA50", float("nan"))
        ema200 = indicator_values.get("EMA200", float("nan"))
        rsi14 = indicator_values.get("RSI14", float("nan"))
        mfi14 = indicator_values.get("MFI14", float("nan"))
        williams_r14 = indicator_values.get("WilliamsR14", float("nan"))
        stoch_rsi = indicator_values.get("StochRSI", float("nan"))
        fisher10 = indicator_values.get("Fisher10", float("nan"))
        relative_volume20 = indicator_values.get("RelVolume20", float("nan"))
        cmf20 = indicator_values.get("CMF20", float("nan"))
        force_index13 = indicator_values.get("ForceIndex13", float("nan"))
        avg_turnover20 = indicator_values.get("AvgTurnover20", float("nan"))
        macd = indicator_values.get("MACD", float("nan"))
        macd_histogram = indicator_values.get("MACDHistogram", float("nan"))
        momentum20 = indicator_values.get("Momentum20", float("nan"))
        roc10 = indicator_values.get("ROC10", float("nan"))
        momentum5 = indicator_values.get("Momentum5", float("nan"))
        new_ath_today = indicator_values.get("New_ATH_Made_Today", float("nan"))
        
        # Batch 2: Block Trade & Distribution
        recent_block_trade = indicator_values.get("RecentBlockTrade", float("nan"))
        distribution_exhaustion = indicator_values.get("DistributionExhaustion", float("nan"))
        order_flow_imbalance = indicator_values.get("OrderFlowImbalance", float("nan"))
        vwap_mom10 = indicator_values.get("VWAPMom10", float("nan"))
        trend_strength = indicator_values.get("TrendStrength", float("nan"))
        adx14 = indicator_values.get("ADX14", float("nan"))
        ichimoku = indicator_values.get("Ichimoku_Score", float("nan"))
        supertrend10 = indicator_values.get("SuperTrend10", float("nan"))
        elder_ray = indicator_values.get("ElderRay_Score", float("nan"))
        rs_egx30_50 = indicator_values.get("RS_vs_EGX30_50", float("nan"))
        atr14 = indicator_values.get("ATR14", float("nan"))
        atr_pct14 = indicator_values.get("ATRPercent14", float("nan"))
        bbw20 = indicator_values.get("BBW20", float("nan"))
        kc_position = indicator_values.get("KC20_Position", float("nan"))
        kc_squeeze = indicator_values.get("KCSqueeze20", float("nan"))
        dc_position = indicator_values.get("DC20_Position", float("nan"))
        dc_breakout = indicator_values.get("DCBreakout20", float("nan"))
        breakout20 = indicator_values.get("Breakout20", float("nan"))
        breakout50 = indicator_values.get("Breakout50", float("nan"))
        near_close_high250 = indicator_values.get("NearCloseHigh250Percent", float("nan"))
        close_high250 = indicator_values.get("CloseHigh250", float("nan"))
        volume_confirmed_breakout = indicator_values.get("VolumeConfirmedBreakout", float("nan"))
        rsi_rebound = indicator_values.get("RSIRebound", float("nan"))
        ema20_reclaim = indicator_values.get("EMA20Reclaim", float("nan"))
        macd_hist_improvement = indicator_values.get("MACDHistogramImprovement", float("nan"))
        volume_spike = indicator_values.get("VolumeSpikeFromWeakness", float("nan"))
        limit_up = indicator_values.get("ClosedAtLimitUp", float("nan"))
        mtf_trend = indicator_values.get("MTF_Trend", float("nan"))
        # Upgrade #5: VPOC is now a dict with distance, price, and overhead flag
        vpoc_raw = indicator_values.get("VPOC_Distance", float("nan"))
        if isinstance(vpoc_raw, dict):
            vpoc_distance = vpoc_raw.get("VPOC_Distance", float("nan"))
            vpoc_above = vpoc_raw.get("VPOC_Above", 0.0)
        else:
            vpoc_distance = vpoc_raw
            vpoc_above = 0.0
        # Upgrade #4: VWAP proximity
        vwap_proximity = indicator_values.get("VWAP_Proximity20", float("nan"))
        liquidity_vacuum_score = indicator_values.get("LiquidityVacuumScore", float("nan"))
        zscore_dict = indicator_values.get("RollingZScore", {})
        rsi_zscore = zscore_dict.get("RSI14_ZScore", float("nan")) if isinstance(zscore_dict, dict) else float("nan")
        mom_zscore = zscore_dict.get("Momentum20_ZScore", float("nan")) if isinstance(zscore_dict, dict) else float("nan")
        kalman_dict = indicator_values.get("KalmanFilter", {})
        kalman_trend = kalman_dict.get("KalmanTrend", 0.0) if isinstance(kalman_dict, dict) else 0.0
        ath_dict = indicator_values.get("AllTimeHigh", {})
        distance_to_ath = ath_dict.get("Distance_To_ATH", float("nan")) if isinstance(ath_dict, dict) else float("nan")
        new_ath_today = ath_dict.get("New_ATH_Made_Today", 0.0) if isinstance(ath_dict, dict) else 0.0
        vol_exp_dict = indicator_values.get("VolatilityExpansion", {})
        atr_expansion_ratio = vol_exp_dict.get("ATR_Expansion_Ratio", float("nan")) if isinstance(vol_exp_dict, dict) else float("nan")
        atr_exploding = vol_exp_dict.get("ATR_Exploding", 0.0) if isinstance(vol_exp_dict, dict) else 0.0
        squeeze_dict = indicator_values.get("Squeeze", {})
        squeeze_fired = squeeze_dict.get("Squeeze_Fired", 0.0) if isinstance(squeeze_dict, dict) else 0.0
        squeeze_building = squeeze_dict.get("Squeeze_Building", 0.0) if isinstance(squeeze_dict, dict) else 0.0
        nhm_dict = indicator_values.get("NearHighMomentum", {})
        nhm_full = nhm_dict.get("Full_Confirmation", 0.0) if isinstance(nhm_dict, dict) else 0.0
        nhm_partial = nhm_dict.get("Partial_Confirmation", 0.0) if isinstance(nhm_dict, dict) else 0.0
        nhm_very_near = nhm_dict.get("Very_Near", 0.0) if isinstance(nhm_dict, dict) else 0.0
        nhm_near_high = nhm_dict.get("Near_High", 0.0) if isinstance(nhm_dict, dict) else 0.0
        
        # Batch 3
        v_macd_signal = indicator_values.get("VMACD_Signal", float("nan"))
        vsa_no_demand = indicator_values.get("VSA_NoDemand", float("nan"))
        evm = indicator_values.get("EVM", float("nan"))
        tsi = indicator_values.get("TSI", float("nan"))
        avwap_dist = indicator_values.get("AVWAP_Distance_Pct", float("nan"))
        # v6.1 Next-Day Alpha Hunters
        closing_aggression = indicator_values.get("ClosingAggression", float("nan"))
        nr7_compression = indicator_values.get("NR7_Compression", float("nan"))
        vsa_absorption = indicator_values.get("VSA_Absorption", float("nan"))
        sector_spillover = indicator_values.get("SectorSpillover", float("nan"))

        return [
            # Trend Structure (30 pts)
            self._score_ema_alignment(ema20, ema50, ema200, latest_close),
            self._score_kalman_trend(kalman_trend),
            self._score_trend_strength(trend_strength),
            self._score_adx(adx14),
            self._score_supertrend(supertrend10, latest_close),
            self._score_ichimoku(ichimoku),
            self._score_elder_ray(elder_ray),
            # Momentum Oscillators (10 pts)
            self._score_rsi14(rsi14),
            self._score_rsi14_zscore(rsi_zscore),
            self._score_mfi14(mfi14),
            self._score_williams_r(williams_r14),
            self._score_stoch_rsi(stoch_rsi),
            self._score_fisher(fisher10),
            # MACD (10 pts)
            self._score_macd(macd, macd_histogram),
            # Price Momentum (15 pts)
            self._score_momentum20(momentum20),
            self._score_momentum20_zscore(mom_zscore),
            self._score_momentum5(momentum5),
            self._score_roc10(roc10),
            self._score_vwap_momentum(vwap_mom10),
            # Volume & Flow (15 pts)
            self._score_relative_volume20(relative_volume20),
            self._score_cmf(cmf20),
            self._score_force_index(force_index13),
            self._score_block_trade(recent_block_trade), # Batch 2 Upgrade #2
            self._score_distribution_exhaustion(distribution_exhaustion), # Batch 2 Upgrade #5
            self._score_order_flow_imbalance(order_flow_imbalance), # Batch 2 Upgrade #9
            self._score_turnover(avg_turnover20),
            # Breakout & Channel Setup (20 pts)
            self._score_donchian(dc_position, dc_breakout),
            self._score_keltner(kc_position, kc_squeeze),
            self._score_bollinger_width(bbw20),
            self._score_breakout_setup(
                breakout20, breakout50, near_close_high250, close_high250, volume_confirmed_breakout
            ),
            # Volatility (5 pts)
            self._score_volatility(atr_pct14),
            # Reversal & Reclaim (10 pts)
            self._score_rsi_rebound(rsi_rebound),
            self._score_ema20_reclaim(ema20_reclaim),
            self._score_macd_improvement(macd_hist_improvement),
            self._score_volume_spike(volume_spike),
            # Market Structure (15 pts)
            self._score_mtf_trend(mtf_trend),
            self._score_vpoc(vpoc_distance, vpoc_above),   # Upgrade #5
            self._score_vwap_proximity(vwap_proximity),    # Upgrade #4
            self._score_liquidity_vacuum(liquidity_vacuum_score),
            self._score_relative_strength(rs_egx30_50),
            self._score_ath(distance_to_ath, new_ath_today),
            # Explosive Setup Hunters (26 pts)
            self._score_volatility_expansion(atr_expansion_ratio, atr_exploding),
            self._score_squeeze(squeeze_fired, squeeze_building),
            self._score_near_high_momentum(nhm_full, nhm_partial, nhm_very_near, nhm_near_high),
            # Limit Up (5 pts)
            self._score_limit_up(limit_up),
            # Batch 3 (20 pts)
            self._score_v_macd(v_macd_signal),
            self._score_vsa_no_demand(vsa_no_demand),
            self._score_evm(evm),
            self._score_tsi(tsi),
            self._score_sector_sympathy(symbol, breakout20),
            self._score_avwap(avwap_dist),
            # v6.1 Next-Day Alpha Hunters (20 pts)
            self._score_closing_aggression(closing_aggression),
            self._score_nr7_compression(nr7_compression),
            self._score_vsa_absorption(vsa_absorption),
            self._score_sector_spillover(sector_spillover),
        ]


    def _score_closing_aggression(self, closing_aggression: float) -> ScoreComponent:
        max_score = 5.0
        if self._missing(closing_aggression) or closing_aggression <= 0:
            return ScoreComponent("Closing Aggression (MOC)", 0.0, max_score, "No closing bar aggression.")
        pts = round(min(max_score, (closing_aggression / 100.0) * max_score), 2)
        return ScoreComponent("Closing Aggression (MOC)", pts, max_score, f"Institutional closing aggression: {closing_aggression:.1f}%.")

    def _score_nr7_compression(self, nr7_compression: float) -> ScoreComponent:
        max_score = 5.0
        if self._missing(nr7_compression) or nr7_compression <= 0:
            return ScoreComponent("NR7 Compression", 0.0, max_score, "No volatility coiling detected.")
        pts = round(min(max_score, (nr7_compression / 100.0) * max_score), 2)
        return ScoreComponent("NR7 Compression", pts, max_score, f"Spring-loaded volatility compression: {nr7_compression:.1f}%.")

    def _score_vsa_absorption(self, vsa_absorption: float) -> ScoreComponent:
        max_score = 5.0
        if self._missing(vsa_absorption) or vsa_absorption <= 0:
            return ScoreComponent("VSA Absorption", 0.0, max_score, "No supply absorption detected.")
        pts = round(min(max_score, (vsa_absorption / 100.0) * max_score), 2)
        return ScoreComponent("VSA Absorption", pts, max_score, f"Institutional supply absorption: {vsa_absorption:.1f}%.")

    def _score_sector_spillover(self, sector_spillover: float) -> ScoreComponent:
        max_score = 5.0
        if self._missing(sector_spillover) or sector_spillover <= 0:
            return ScoreComponent("Sector Spillover", 0.0, max_score, "No sector momentum spillover.")
        pts = round(min(max_score, (sector_spillover / 100.0) * max_score), 2)
        return ScoreComponent("Sector Spillover", pts, max_score, f"Sector lead-lag momentum: {sector_spillover:.1f}%.")

    def _score_sector_sympathy(self, symbol: str, breakout20: float) -> ScoreComponent:
        max_score = 5.0
        _load_sectors()
        
        # update cache
        if not self._missing(breakout20) and breakout20 == 1.0:
            _SECTOR_BREAKOUT_CACHE[symbol] = 1.0
            
        sector = _SECTOR_MAP.get(symbol)
        if not sector:
            return ScoreComponent("Sector Sympathy", 0.0, max_score, "Sector unknown.")
            
        peers_breaking_out = 0
        for peer, peer_sector in _SECTOR_MAP.items():
            if peer != symbol and peer_sector == sector:
                if _SECTOR_BREAKOUT_CACHE.get(peer) == 1.0:
                    peers_breaking_out += 1
                    
        if peers_breaking_out >= 2:
            return ScoreComponent("Sector Sympathy", 5.0, max_score, "Sector Cluster Breakout: 2+ peers breaking out.")
        elif peers_breaking_out == 1:
            return ScoreComponent("Sector Sympathy", 2.0, max_score, "Sector Peer Confirmation: 1 peer breaking out.")
            
        return ScoreComponent("Sector Sympathy", 0.0, max_score, "No sector peers breaking out.")

    def _score_avwap(self, avwap_dist: float) -> ScoreComponent:
        max_score = 5.0
        if self._missing(avwap_dist):
            return ScoreComponent("Anchored VWAP", 0.0, max_score, "AVWAP unavailable.")
            
        if 0.0 <= avwap_dist <= 3.0:
            return ScoreComponent("Anchored VWAP", 5.0, max_score, "institutional accumulation zone.")
        elif 3.0 < avwap_dist <= 8.0:
            return ScoreComponent("Anchored VWAP", 3.0, max_score, "healthy trend.")
        else:
            return ScoreComponent("Anchored VWAP", 0.0, max_score, "overextended or weak.")

    def _score_rsi14(self, rsi14: float) -> ScoreComponent:
        max_score = 5.0

        if self._missing(rsi14):
            return ScoreComponent("RSI14 momentum", 0.0, max_score, "RSI14 is unavailable.")

        if 50 <= rsi14 <= 70:
            return ScoreComponent("RSI14 momentum", 5.0, max_score, "RSI is in a healthy bullish range.")

        if 70 < rsi14 <= 75:
            return ScoreComponent(
                "RSI14 momentum",
                3.0,
                max_score,
                "RSI shows strong momentum but is becoming extended.",
            )

        if rsi14 > 75:
            return ScoreComponent(
                "RSI14 momentum",
                1.0,
                max_score,
                "RSI is overextended; risk of pullback is higher.",
            )

        if 40 <= rsi14 < 50:
            return ScoreComponent("RSI14 momentum", 2.0, max_score, "RSI is neutral to slightly weak.")

        return ScoreComponent("RSI14 momentum", 0.0, max_score, "RSI is weak.")

    def _score_macd(self, macd: float, macd_histogram: float) -> ScoreComponent:
        max_score = 10.0

        if self._missing(macd) or self._missing(macd_histogram):
            return ScoreComponent("MACD confirmation", 0.0, max_score, "MACD is unavailable.")

        if macd > 0 and macd_histogram > 0:
            return ScoreComponent(
                "MACD confirmation",
                10.0,
                max_score,
                "MACD is positive and histogram confirms bullish momentum.",
            )

        if macd_histogram > 0:
            return ScoreComponent(
                "MACD confirmation",
                6.0,
                max_score,
                "MACD histogram is positive, but MACD line is not yet above zero.",
            )

        if macd > 0:
            return ScoreComponent(
                "MACD confirmation",
                3.0,
                max_score,
                "MACD is positive, but histogram is not confirming acceleration.",
            )

        return ScoreComponent("MACD confirmation", 0.0, max_score, "MACD is not bullish.")

    def _score_momentum20(self, momentum20: float) -> ScoreComponent:
        max_score = 10.0

        if self._missing(momentum20):
            return ScoreComponent("Momentum20", 0.0, max_score, "20-bar momentum is unavailable.")

        if momentum20 >= 10:
            return ScoreComponent("Momentum20", 10.0, max_score, "20-bar price momentum is strong.")

        if momentum20 >= 3:
            return ScoreComponent("Momentum20", 8.0, max_score, "20-bar price momentum is positive.")

        if momentum20 >= 0:
            return ScoreComponent("Momentum20", 4.0, max_score, "20-bar price momentum is mildly positive.")

        return ScoreComponent("Momentum20", 0.0, max_score, "20-bar price momentum is negative.")

    def _score_relative_volume20(self, relative_volume20: float) -> ScoreComponent:
        max_score = 10.0

        if self._missing(relative_volume20):
            return ScoreComponent("Relative Volume20", 0.0, max_score, "Relative volume is unavailable.")

        if relative_volume20 >= 1.5:
            return ScoreComponent(
                "Relative Volume20",
                10.0,
                max_score,
                "Volume is strongly above its 20-day average.",
            )

        if relative_volume20 >= 1.0:
            return ScoreComponent(
                "Relative Volume20",
                7.0,
                max_score,
                "Volume is above or near its 20-day average.",
            )

        if relative_volume20 >= 0.75:
            return ScoreComponent(
                "Relative Volume20",
                4.0,
                max_score,
                "Volume is slightly below its 20-day average.",
            )

        return ScoreComponent(
            "Relative Volume20",
            0.0,
            max_score,
            "Volume is weak relative to recent activity.",
        )

    def _score_breakout_setup(
        self,
        breakout20: float,
        breakout50: float,
        near_close_high250: float,
        close_high250: float,
        volume_confirmed_breakout: float,
    ) -> ScoreComponent:
        max_score = 12.0

        if self._missing(breakout20) or self._missing(breakout50) or self._missing(near_close_high250):
            return ScoreComponent("Breakout setup", 0.0, max_score, "Breakout indicators are unavailable.")

        score = 0.0
        reasons: list[str] = []

        if breakout20 == 1.0:
            score += 4.0
            reasons.append("latest close broke above the previous 20-bar closing high")

        if breakout50 == 1.0:
            score += 4.0
            reasons.append("latest close broke above the previous 50-bar closing high")

        if near_close_high250 >= -3.0:
            score += 2.0
            reasons.append("close is within 3% of its 250-bar closing high")
        elif near_close_high250 >= -7.0:
            score += 1.0
            reasons.append("close is within 7% of its 250-bar closing high")

        if not self._missing(volume_confirmed_breakout) and volume_confirmed_breakout == 1.0:
            score += 2.0
            reasons.append("breakout is volume-confirmed")

        if not reasons:
            return ScoreComponent("Breakout setup", 0.0, max_score, "No close-based breakout setup is present.")

        return ScoreComponent("Breakout setup", min(score, max_score), max_score, "; ".join(reasons) + ".")

    def _missing(self, value: float) -> bool:
        if value is None:
            return True
        try:
            return isnan(float(value))
        except (ValueError, TypeError):
            return True

    def _score_ema_alignment(self, ema20: float, ema50: float, ema200: float, latest_close: float) -> ScoreComponent:
        max_score = 15.0
        if self._missing(ema20) or self._missing(ema50) or self._missing(ema200):
            return ScoreComponent("EMA Alignment", 0.0, max_score, "EMAs unavailable.")
        score = 0.0
        reasons = []
        if latest_close > ema20:
            score += 5.0
            reasons.append("Close > EMA20")
        if ema20 > ema50:
            score += 5.0
            reasons.append("EMA20 > EMA50")
        if ema50 > ema200:
            score += 5.0
            reasons.append("EMA50 > EMA200")
        return ScoreComponent("EMA Alignment", score, max_score, ", ".join(reasons) if reasons else "Poor alignment.")

    def _score_trend_strength(self, trend_strength: float) -> ScoreComponent:
        max_score = 5.0
        if self._missing(trend_strength): return ScoreComponent("Trend Strength", 0.0, max_score, "Unavailable.")
        if trend_strength > 20: return ScoreComponent("Trend Strength", max_score, max_score, "Strong trend.")
        if trend_strength > 10: return ScoreComponent("Trend Strength", 3.0, max_score, "Moderate trend.")
        return ScoreComponent("Trend Strength", 0.0, max_score, "Weak trend.")

    def _score_adx(self, adx14: float) -> ScoreComponent:
        max_score = 5.0
        if self._missing(adx14): return ScoreComponent("ADX", 0.0, max_score, "ADX unavailable.")
        if adx14 > 25: return ScoreComponent("ADX", max_score, max_score, "Strong trend (ADX > 25).")
        if adx14 > 20: return ScoreComponent("ADX", 2.0, max_score, "Developing trend.")
        return ScoreComponent("ADX", 0.0, max_score, "Weak trend.")

    def _score_supertrend(self, supertrend10: float, latest_close: float) -> ScoreComponent:
        max_score = 5.0
        if self._missing(supertrend10): return ScoreComponent("SuperTrend", 0.0, max_score, "SuperTrend unavailable.")
        if supertrend10 > 0: return ScoreComponent("SuperTrend", max_score, max_score, "Bullish SuperTrend.")
        return ScoreComponent("SuperTrend", 0.0, max_score, "Bearish SuperTrend.")

    def _score_ichimoku(self, ichimoku: float) -> ScoreComponent:
        max_score = 3.0
        if self._missing(ichimoku): return ScoreComponent("Ichimoku", 0.0, max_score, "Ichimoku unavailable.")
        score = min(max(ichimoku, 0.0), max_score)
        return ScoreComponent("Ichimoku", score, max_score, f"Ichimoku score {ichimoku}.")

    def _score_elder_ray(self, elder_ray: float) -> ScoreComponent:
        max_score = 2.0
        if self._missing(elder_ray): return ScoreComponent("Elder Ray", 0.0, max_score, "Elder Ray unavailable.")
        return ScoreComponent("Elder Ray", min(max(elder_ray, 0.0), max_score), max_score, f"Elder Ray score {elder_ray}.")

    def _score_mfi14(self, mfi14: float) -> ScoreComponent:
        """Upgrade #2: Enhanced volume-weighted MFI scoring with gradient scoring and overbought penalty."""
        max_score = 3.0  # Increased weight to reward volume-backed momentum
        if self._missing(mfi14): return ScoreComponent("MFI", 0.0, max_score, "MFI unavailable.")
        if 55 <= mfi14 <= 80:
            return ScoreComponent("MFI", max_score, max_score, f"Bullish volume-backed MFI ({mfi14:.0f}).")
        if 50 <= mfi14 < 55:
            return ScoreComponent("MFI", 1.5, max_score, f"Mildly bullish MFI ({mfi14:.0f}).")
        if mfi14 > 80:
            return ScoreComponent("MFI", 1.0, max_score, f"MFI overbought ({mfi14:.0f}): Risk of reversal.")
        if 40 <= mfi14 < 50:
            return ScoreComponent("MFI", 0.0, max_score, f"MFI neutral ({mfi14:.0f}).")
        # < 40: bearish money flow
        return ScoreComponent("MFI", 0.0, max_score, f"Bearish MFI ({mfi14:.0f}): Distribution detected.")

    def _score_williams_r(self, williams_r14: float) -> ScoreComponent:
        max_score = 1.0
        if self._missing(williams_r14): return ScoreComponent("Williams %R", 0.0, max_score, "Unavailable.")
        if williams_r14 > -50: return ScoreComponent("Williams %R", max_score, max_score, "Bullish.")
        return ScoreComponent("Williams %R", 0.0, max_score, "Bearish.")

    def _score_stoch_rsi(self, stoch_rsi: float) -> ScoreComponent:
        max_score = 1.0
        if self._missing(stoch_rsi): return ScoreComponent("StochRSI", 0.0, max_score, "Unavailable.")
        if stoch_rsi > 0: return ScoreComponent("StochRSI", max_score, max_score, "Bullish StochRSI cross.")
        return ScoreComponent("StochRSI", 0.0, max_score, "Bearish StochRSI.")

    def _score_fisher(self, fisher10: float) -> ScoreComponent:
        max_score = 1.0
        if self._missing(fisher10): return ScoreComponent("Fisher", 0.0, max_score, "Unavailable.")
        if fisher10 > 0: return ScoreComponent("Fisher", max_score, max_score, "Positive Fisher transform.")
        return ScoreComponent("Fisher", 0.0, max_score, "Negative Fisher.")

    def _score_momentum5(self, momentum5: float) -> ScoreComponent:
        max_score = 2.0
        if self._missing(momentum5): return ScoreComponent("Momentum5", 0.0, max_score, "Unavailable.")
        if momentum5 > 0: return ScoreComponent("Momentum5", max_score, max_score, "Positive short-term momentum.")
        return ScoreComponent("Momentum5", 0.0, max_score, "Negative short-term momentum.")

    def _score_roc10(self, roc10: float) -> ScoreComponent:
        max_score = 1.0
        if self._missing(roc10): return ScoreComponent("ROC10", 0.0, max_score, "Unavailable.")
        if roc10 > 0: return ScoreComponent("ROC10", max_score, max_score, "Positive ROC.")
        return ScoreComponent("ROC10", 0.0, max_score, "Negative ROC.")

    def _score_vwap_momentum(self, vwap_mom10: float) -> ScoreComponent:
        max_score = 2.0
        if self._missing(vwap_mom10): return ScoreComponent("VWAP Mom", 0.0, max_score, "Unavailable.")
        if vwap_mom10 > 0: return ScoreComponent("VWAP Mom", max_score, max_score, "Price above VWAP.")
        return ScoreComponent("VWAP Mom", 0.0, max_score, "Price below VWAP.")

    def _score_cmf(self, cmf20: float) -> ScoreComponent:
        max_score = 2.0
        if self._missing(cmf20): return ScoreComponent("CMF", 0.0, max_score, "Unavailable.")
        if cmf20 > 0: return ScoreComponent("CMF", max_score, max_score, "Positive money flow.")
        return ScoreComponent("CMF", 0.0, max_score, "Negative money flow.")

    def _score_force_index(self, force_index13: float) -> ScoreComponent:
        max_score = 1.0
        if self._missing(force_index13): return ScoreComponent("Force Index", 0.0, max_score, "Unavailable.")
        if force_index13 > 0: return ScoreComponent("Force Index", max_score, max_score, "Positive Force Index.")
        return ScoreComponent("Force Index", 0.0, max_score, "Negative Force Index.")

    def _score_turnover(self, avg_turnover20: float) -> ScoreComponent:
        max_score = 2.0
        if self._missing(avg_turnover20): return ScoreComponent("Turnover", 0.0, max_score, "Unavailable.")
        if avg_turnover20 > 1000000: return ScoreComponent("Turnover", max_score, max_score, "High turnover liquidity.")
        return ScoreComponent("Turnover", 0.0, max_score, "Low turnover.")

    def _score_donchian(self, dc_position: float, dc_breakout: float) -> ScoreComponent:
        max_score = 3.0
        if self._missing(dc_breakout): return ScoreComponent("Donchian", 0.0, max_score, "Unavailable.")
        if dc_breakout > 0: return ScoreComponent("Donchian", max_score, max_score, "Donchian Breakout.")
        return ScoreComponent("Donchian", 0.0, max_score, "No breakout.")

    def _score_keltner(self, kc_position: float, kc_squeeze: float) -> ScoreComponent:
        max_score = 3.0
        if self._missing(kc_position): return ScoreComponent("Keltner", 0.0, max_score, "Unavailable.")
        if kc_position > 50: return ScoreComponent("Keltner", max_score, max_score, "Bullish Keltner position.")
        return ScoreComponent("Keltner", 0.0, max_score, "Bearish Keltner.")

    def _score_bollinger_width(self, bbw20: float) -> ScoreComponent:
        max_score = 2.0
        if self._missing(bbw20): return ScoreComponent("BBW", 0.0, max_score, "Unavailable.")
        return ScoreComponent("BBW", max_score/2, max_score, "Normal BBW.")

    def _score_volatility(self, atr_pct14: float) -> ScoreComponent:
        """Upgrade #1: Tiered volatility scoring. Low-vol stocks that might be mega-caps penalised."""
        max_score = 5.0
        if self._missing(atr_pct14): return ScoreComponent("Volatility", 0.0, max_score, "ATR% unavailable.")
        if atr_pct14 >= 7.0: return ScoreComponent("Volatility", max_score, max_score, f"Explosive volatility ({atr_pct14:.1f}%): High-energy setup.")
        if atr_pct14 >= 5.0: return ScoreComponent("Volatility", 4.0, max_score, f"Strong volatility ({atr_pct14:.1f}%).")
        if atr_pct14 >= 3.0: return ScoreComponent("Volatility", 3.0, max_score, f"Healthy volatility ({atr_pct14:.1f}%).")
        if atr_pct14 >= 2.0: return ScoreComponent("Volatility", 1.0, max_score, f"Low-ish volatility ({atr_pct14:.1f}%): Limited upside range.")
        return ScoreComponent("Volatility", 0.0, max_score, f"Very low volatility ({atr_pct14:.1f}%): Avoid for momentum trades.")

    def _score_rsi_rebound(self, rsi_rebound: float) -> ScoreComponent:
        max_score = 2.0
        if self._missing(rsi_rebound): return ScoreComponent("RSI Rebound", 0.0, max_score, "Unavailable.")
        if rsi_rebound > 0: return ScoreComponent("RSI Rebound", max_score, max_score, "RSI Rebound detected.")
        return ScoreComponent("RSI Rebound", 0.0, max_score, "No RSI Rebound.")

    def _score_ema20_reclaim(self, ema20_reclaim: float) -> ScoreComponent:
        max_score = 3.0
        if self._missing(ema20_reclaim): return ScoreComponent("EMA20 Reclaim", 0.0, max_score, "Unavailable.")
        if ema20_reclaim > 0: return ScoreComponent("EMA20 Reclaim", max_score, max_score, "EMA20 Reclaim detected.")
        return ScoreComponent("EMA20 Reclaim", 0.0, max_score, "No EMA20 reclaim.")

    def _score_macd_improvement(self, macd_hist_improvement: float) -> ScoreComponent:
        max_score = 2.0
        if self._missing(macd_hist_improvement): return ScoreComponent("MACD Imp", 0.0, max_score, "Unavailable.")
        if macd_hist_improvement > 0: return ScoreComponent("MACD Imp", max_score, max_score, "MACD Histogram Improvement.")
        return ScoreComponent("MACD Imp", 0.0, max_score, "No MACD improvement.")

    def _score_volume_spike(self, volume_spike: float) -> ScoreComponent:
        max_score = 3.0
        if self._missing(volume_spike): return ScoreComponent("Vol Spike", 0.0, max_score, "Unavailable.")
        if volume_spike > 0: return ScoreComponent("Vol Spike", max_score, max_score, "Volume Spike detected.")
        return ScoreComponent("Vol Spike", 0.0, max_score, "No Volume Spike.")

    def _score_block_trade(self, block_trade: float) -> ScoreComponent:
        """Batch 2 Upgrade #2: Institutional absorption reward."""
        max_score = 5.0
        if self._missing(block_trade): return ScoreComponent("Block Trade", 0.0, max_score, "Unavailable.")
        if block_trade == 1.0:
            return ScoreComponent("Block Trade", max_score, max_score, "Institutional Block Trade (Absorption) detected recently! Strong accumulation sign.")
        return ScoreComponent("Block Trade", 0.0, max_score, "No recent absorption block trades.")

    def _score_distribution_exhaustion(self, distribution: float) -> ScoreComponent:
        """Batch 2 Upgrade #5: Distribution Exhaustion penalty."""
        max_score = 0.0 # This is a penalty component, doesn't add to max
        if self._missing(distribution): return ScoreComponent("Distribution", 0.0, max_score, "Unavailable.")
        if distribution == 1.0:
            return ScoreComponent("Distribution", -15.0, max_score, "Distribution Exhaustion detected: Massive volume turnover without price progress. High risk of dump.")
        return ScoreComponent("Distribution", 0.0, max_score, "No distribution exhaustion.")

    def _score_order_flow_imbalance(self, order_flow: float) -> ScoreComponent:
        """Batch 2 Upgrade #9: Order Flow Imbalance."""
        max_score = 3.0
        if self._missing(order_flow): return ScoreComponent("Order Flow", 0.0, max_score, "Unavailable.")
        if order_flow > 1.5:
            return ScoreComponent("Order Flow", max_score, max_score, f"Strong buying pressure into the close ({order_flow:.1f}x average volume).")
        if order_flow < -1.5:
            return ScoreComponent("Order Flow", -2.0, max_score, f"Heavy distribution into the close ({order_flow:.1f}x average volume).")
        return ScoreComponent("Order Flow", 0.0, max_score, f"Neutral order flow ({order_flow:.1f}x).")

    def _score_mtf_trend(self, mtf_trend: float) -> ScoreComponent:
        max_score = 3.0
        if self._missing(mtf_trend): return ScoreComponent("MTF Trend", 0.0, max_score, "Unavailable.")
        if mtf_trend > 0: return ScoreComponent("MTF Trend", max_score, max_score, "MTF Trend is bullish.")
        return ScoreComponent("MTF Trend", 0.0, max_score, "MTF Trend is not bullish.")

    def _score_vpoc(self, vpoc_distance: float, vpoc_above: float = 0.0) -> ScoreComponent:
        """Upgrade #5: VPOC scoring with overhead resistance flag."""
        max_score = 3.0  # Increased weight; VPOC is strong structural evidence
        if self._missing(vpoc_distance): return ScoreComponent("VPOC", 0.0, max_score, "Unavailable.")
        if vpoc_above == 1.0:
            # VPOC is above price = overhead resistance; this is a bearish structural signal
            return ScoreComponent("VPOC", 0.0, max_score, "VPOC is ABOVE price: Overhead resistance present. Caution.")
        if vpoc_distance > 0.05:  # price >5% above VPOC
            return ScoreComponent("VPOC", max_score, max_score, f"Price well above VPOC (+{vpoc_distance*100:.1f}%): VPOC is deep support.")
        if vpoc_distance > 0:
            return ScoreComponent("VPOC", 2.0, max_score, f"Price above VPOC (+{vpoc_distance*100:.1f}%): VPOC support intact.")
        return ScoreComponent("VPOC", 0.0, max_score, f"Price below VPOC ({vpoc_distance*100:.1f}%).")

    def _score_vwap_proximity(self, vwap_proximity: float) -> ScoreComponent:
        """Upgrade #4: Score VWAP proximity. Breakouts from VWAP get a bonus; overextended moves above VWAP are penalised."""
        max_score = 3.0
        if self._missing(vwap_proximity): return ScoreComponent("VWAP Proximity", 0.0, max_score, "Unavailable.")
        if 0.0 <= vwap_proximity <= 3.0:
            return ScoreComponent("VWAP Proximity", max_score, max_score, f"Price just above VWAP (+{vwap_proximity:.1f}%): Ideal launch zone.")
        if 3.0 < vwap_proximity <= 7.0:
            return ScoreComponent("VWAP Proximity", 1.5, max_score, f"Price extended above VWAP (+{vwap_proximity:.1f}%): Some fade risk.")
        if vwap_proximity > 7.0:
            return ScoreComponent("VWAP Proximity", 0.0, max_score, f"Price very overextended above VWAP (+{vwap_proximity:.1f}%): High fade risk.")
        if -2.0 <= vwap_proximity < 0:
            return ScoreComponent("VWAP Proximity", 1.0, max_score, f"Price just below VWAP ({vwap_proximity:.1f}%): Watch for reclaim.")
        return ScoreComponent("VWAP Proximity", 0.0, max_score, f"Price below VWAP ({vwap_proximity:.1f}%).")

    def _score_relative_strength(self, rs_egx30_50: float) -> ScoreComponent:
        max_score = 5.0
        if self._missing(rs_egx30_50): return ScoreComponent("Rel Strength", 0.0, max_score, "Unavailable.")
        if rs_egx30_50 > 0: return ScoreComponent("Rel Strength", max_score, max_score, "Outperforming EGX30.")
        return ScoreComponent("Rel Strength", 0.0, max_score, "Underperforming EGX30.")

    def _score_limit_up(self, limit_up: float) -> ScoreComponent:
        max_score = 5.0
        if self._missing(limit_up): return ScoreComponent("Limit Up", 0.0, max_score, "Unavailable.")
        if limit_up > 0: return ScoreComponent("Limit Up", max_score, max_score, "Closed at limit up.")
        return ScoreComponent("Limit Up", 0.0, max_score, "Did not close at limit up.")

    # === Advanced Indicators ===

    def _score_kalman_trend(self, kalman_trend: float) -> ScoreComponent:
        max_score = 10.0
        if kalman_trend > 0: return ScoreComponent("Kalman Trend", max_score, max_score, "Kalman Filter detects underlying uptrend.")
        if kalman_trend < 0: return ScoreComponent("Kalman Trend", 0.0, max_score, "Kalman Filter detects underlying downtrend.")
        return ScoreComponent("Kalman Trend", 0.0, max_score, "Kalman trend flat or unavailable.")

    def _score_rsi14_zscore(self, rsi_zscore: float) -> ScoreComponent:
        max_score = 5.0
        if self._missing(rsi_zscore): return ScoreComponent("RSI Z-Score", 0.0, max_score, "Z-Score unavailable.")
        if rsi_zscore > 1.5: return ScoreComponent("RSI Z-Score", max_score, max_score, "RSI is historically elevated (strong momentum).")
        if rsi_zscore > 0.5: return ScoreComponent("RSI Z-Score", 3.0, max_score, "RSI moderately above its historical norm.")
        if rsi_zscore > -0.5: return ScoreComponent("RSI Z-Score", 1.0, max_score, "RSI near its historical average.")
        return ScoreComponent("RSI Z-Score", 0.0, max_score, "RSI below historical norm.")

    def _score_momentum20_zscore(self, mom_zscore: float) -> ScoreComponent:
        max_score = 10.0
        if self._missing(mom_zscore): return ScoreComponent("Mom20 Z-Score", 0.0, max_score, "Momentum Z-Score unavailable.")
        if mom_zscore > 2.0: return ScoreComponent("Mom20 Z-Score", max_score, max_score, "Exceptional momentum surge.")
        if mom_zscore > 1.0: return ScoreComponent("Mom20 Z-Score", 7.0, max_score, "Strong momentum above historical norm.")
        if mom_zscore > 0.0: return ScoreComponent("Mom20 Z-Score", 3.0, max_score, "Positive momentum.")
        return ScoreComponent("Mom20 Z-Score", 0.0, max_score, "Negative momentum.")

    def _score_liquidity_vacuum(self, lv_score: float) -> ScoreComponent:
        max_score = 5.0
        if self._missing(lv_score): return ScoreComponent("Liq Vacuum", 0.0, max_score, "Unavailable.")
        if lv_score >= 0.8: return ScoreComponent("Liq Vacuum", max_score, max_score, "Massive liquidity vacuum above price.")
        if lv_score >= 0.5: return ScoreComponent("Liq Vacuum", 3.0, max_score, "Moderate liquidity vacuum above.")
        return ScoreComponent("Liq Vacuum", 0.0, max_score, "No significant liquidity vacuum.")

    def _score_ath(self, distance_to_ath: float, new_ath: float) -> ScoreComponent:
        max_score = 10.0
        if self._missing(distance_to_ath): return ScoreComponent("ATH Magnetic", 0.0, max_score, "Unavailable.")
        if new_ath == 1.0: return ScoreComponent("ATH Magnetic", 10.0, max_score, "Made a NEW All-Time High today! (Explosive Momentum).")
        if -1.0 <= distance_to_ath <= 0.0: return ScoreComponent("ATH Magnetic", 8.0, max_score, "Closed directly at the All-Time High (Coiled Spring).")
        if -5.0 <= distance_to_ath < -1.0: return ScoreComponent("ATH Magnetic", 5.0, max_score, "Closing in on the All-Time High (Magnetic Effect).")
        return ScoreComponent("ATH Magnetic", 0.0, max_score, "Price is far below the All-Time High.")

    # === Explosive Setup Hunters ===

    def _score_volatility_expansion(self, ratio: float, exploding: float) -> ScoreComponent:
        max_score = 8.0
        if self._missing(ratio): return ScoreComponent("Vol Expansion", 0.0, max_score, "Unavailable.")
        if exploding == 1.0: return ScoreComponent("Vol Expansion", 8.0, max_score, "ATR EXPLODING (>1.5x avg) — Volatility Explosion!")
        if ratio > 1.2: return ScoreComponent("Vol Expansion", 5.0, max_score, "ATR expanding (>1.2x avg) — Building energy.")
        return ScoreComponent("Vol Expansion", 0.0, max_score, "ATR flat or contracting.")

    def _score_squeeze(self, fired: float, building: float) -> ScoreComponent:
        max_score = 8.0
        if fired == 1.0: return ScoreComponent("BB Squeeze", 8.0, max_score, "Squeeze FIRED — Explosive breakout imminent!")
        if building == 1.0: return ScoreComponent("BB Squeeze", 4.0, max_score, "Squeeze building — Price compression detected.")
        return ScoreComponent("BB Squeeze", 0.0, max_score, "No squeeze detected.")

    def _score_near_high_momentum(self, full: float, partial: float, very_near: float, near_high: float) -> ScoreComponent:
        max_score = 10.0
        if full == 1.0 and very_near == 1.0: return ScoreComponent("NearHigh Mom", 10.0, max_score, "Within 2% of 250d high + MACD & Mom5 confirmed — Explosive Breakout Imminent!")
        if partial == 1.0 and near_high == 1.0: return ScoreComponent("NearHigh Mom", 4.0, max_score, "Within 5% of 250d high + positive momentum building.")
        if near_high == 1.0: return ScoreComponent("NearHigh Mom", 2.0, max_score, "Price is near 250d high but lacks momentum confirmation.")
        return ScoreComponent("NearHigh Mom", 0.0, max_score, "Price is far from 250d high or lacks momentum.")

    # === Batch 3 ===
    def _score_v_macd(self, v_macd: float):
        max_score = 10.0
        if self._missing(v_macd): return ScoreComponent('V-MACD', 0.0, max_score, 'Unavailable.')
        if v_macd > 0: return ScoreComponent('V-MACD', max_score, max_score, 'V-MACD positive.')
        return ScoreComponent('V-MACD', 0.0, max_score, 'V-MACD negative.')

    def _score_vsa_no_demand(self, vsa_no_demand: float):
        max_score = 0.0
        if self._missing(vsa_no_demand): return ScoreComponent('VSA No Demand', 0.0, max_score, 'Unavailable.')
        if vsa_no_demand == 1.0: return ScoreComponent('VSA No Demand', -5.0, max_score, 'VSA No Demand Bar.')
        return ScoreComponent('VSA No Demand', 0.0, max_score, 'No VSA No Demand Bar.')

    def _score_evm(self, evm: float):
        max_score = 0.0
        if self._missing(evm): return ScoreComponent('EVM', 0.0, max_score, 'Unavailable.')
        if evm > 5.0: return ScoreComponent('EVM', -5.0, max_score, 'High EVM.')
        return ScoreComponent('EVM', 0.0, max_score, 'EVM is normal.')

    def _score_tsi(self, tsi: float):
        max_score = 5.0
        if self._missing(tsi): return ScoreComponent('TSI', 0.0, max_score, 'Unavailable.')
        if tsi > 25: return ScoreComponent('TSI', max_score, max_score, 'TSI is strongly bullish.')
        if tsi > 0: return ScoreComponent('TSI', 2.5, max_score, 'TSI is positive.')
        return ScoreComponent('TSI', 0.0, max_score, 'TSI is negative.')
