from core.portfolio_book import build_portfolio_snapshot, get_sample_portfolio
from core.risk_engine import calculate_portfolio_risk


def test_calculate_portfolio_risk_from_asset_class_shocks():
    snapshot = build_portfolio_snapshot(get_sample_portfolio())
    risk = calculate_portfolio_risk(snapshot)

    assert risk["risk_level"] == "medium"
    assert risk["var_95_pct"] == -1.26
    assert risk["cvar_95_pct"] == -1.7
    assert risk["max_single_position_weight"] == 0.45
    assert risk["risk_contribution"]["equity"] > risk["risk_contribution"]["cash"]
