from core.portfolio_book import build_portfolio_snapshot, get_sample_portfolio
from core.risk_engine import calculate_portfolio_risk


def test_calculate_portfolio_risk_from_asset_class_shocks():
    from core.config import settings
    snapshot = build_portfolio_snapshot(get_sample_portfolio())
    risk = calculate_portfolio_risk(snapshot)

    var_95 = risk["var_95_pct"]
    var_high = getattr(settings, "CALIBRATED_VAR_HIGH", -6.0)
    var_medium = getattr(settings, "CALIBRATED_VAR_MEDIUM", -1.0)
    
    if var_95 <= var_high or risk["max_single_position_weight"] > 0.5:
        expected_level = "high"
    elif var_95 <= var_medium:
        expected_level = "medium"
    else:
        expected_level = "low"

    assert risk["risk_level"] == expected_level
    assert risk["var_95_pct"] == -1.02
    assert risk["cvar_95_pct"] == -1.38
    assert risk["max_single_position_weight"] == 0.45
    assert risk["risk_contribution"]["equity"] > risk["risk_contribution"]["cash"]


def test_risk_marginal_contributions():
    snapshot = build_portfolio_snapshot(get_sample_portfolio())
    risk = calculate_portfolio_risk(snapshot)
    
    assert "mctr" in risk
    assert "actr" in risk
    assert "normalized_risk_contribution" in risk
    assert "mctr_by_class" in risk
    assert "actr_by_class" in risk
    
    # Mathematical check: Sum of all position ACTRs should equal the daily volatility
    daily_vol = risk["daily_vol_pct"] / 100.0
    sum_actr = sum(risk["actr"].values())
    
    # High precision float check
    assert abs(sum_actr - daily_vol) < 1e-5
    
    # Cash MCTR should be 0 because cash correlation with other assets is 0 and cash vol is extremely low
    assert risk["mctr"]["CASH"] == 0.0


