import logging
from dataclasses import dataclass
from math import isnan

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class PositionSizeSuggestion:
    recommended_weight_percent: float
    max_risk_percent: float
    shares_per_100k: int
    reasoning: list[str]

def calculate_position_size(
    win_probability_percent: float,
    entry_price: float,
    stop_loss_price: float,
    target_price: float,
    portfolio_value: float = 100_000.0,
    max_portfolio_risk_per_trade: float = 0.02, # 2% max risk per trade
) -> PositionSizeSuggestion:
    reasons = []
    
    if win_probability_percent < 50.0:
        return PositionSizeSuggestion(0.0, 0.0, 0, ["Probability too low for Kelly allocation."])
        
    if stop_loss_price >= entry_price:
        return PositionSizeSuggestion(0.0, 0.0, 0, ["Invalid stop loss (above or equal to entry)."])
        
    if target_price <= entry_price:
        return PositionSizeSuggestion(0.0, 0.0, 0, ["Invalid target (below or equal to entry)."])

    p = win_probability_percent / 100.0
    risk_per_share = entry_price - stop_loss_price
    reward_per_share = target_price - entry_price
    
    b = reward_per_share / risk_per_share # Reward to Risk Ratio
    
    # Kelly Formula: f = p - (1-p)/b
    kelly_f = p - ((1.0 - p) / b)
    
    if kelly_f <= 0:
        return PositionSizeSuggestion(0.0, 0.0, 0, ["Negative Kelly edge. Do not trade."])
        
    # We use Half-Kelly for safety
    half_kelly = kelly_f * 0.5
    
    reasons.append(f"Win Probability: {p*100:.1f}%")
    reasons.append(f"Reward/Risk Ratio: {b:.2f}")
    reasons.append(f"Half-Kelly Allocation: {half_kelly*100:.1f}% of capital")
    
    # Volatility / Risk limitation
    max_capital_at_risk = portfolio_value * max_portfolio_risk_per_trade
    max_shares_by_risk = int(max_capital_at_risk / risk_per_share)
    
    max_capital_allocation = portfolio_value * half_kelly
    max_shares_by_kelly = int(max_capital_allocation / entry_price)
    
    # Take the safer of the two
    shares = min(max_shares_by_risk, max_shares_by_kelly)
    actual_allocation = (shares * entry_price) / portfolio_value
    actual_risk = (shares * risk_per_share) / portfolio_value
    
    if shares == max_shares_by_risk:
        reasons.append("Sizing constrained by 2% max portfolio risk limit.")
    else:
        reasons.append("Sizing constrained by Half-Kelly optimal growth limit.")
        
    return PositionSizeSuggestion(
        recommended_weight_percent=actual_allocation * 100.0,
        max_risk_percent=actual_risk * 100.0,
        shares_per_100k=shares,
        reasoning=reasons
    )
