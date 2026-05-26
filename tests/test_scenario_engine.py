from core.portfolio_book import build_portfolio_snapshot, get_sample_portfolio
from core.scenario_engine import run_portfolio_scenarios


def test_run_portfolio_scenarios_applies_asset_class_shocks():
    snapshot = build_portfolio_snapshot(get_sample_portfolio())
    result = run_portfolio_scenarios(snapshot)

    assert result["worst_scenario"]["id"] == "equity_liquidity_shock"
    assert result["worst_scenario"]["portfolio_loss_pct"] == -7.65
    assert len(result["scenarios"]) == 6


def test_run_portfolio_scenarios_applies_region_shocks():
    snapshot = {
        "positions": [
            {"symbol": "CSI300_ETF", "asset_class": "equity", "region": "China", "weight": 0.5},
            {"symbol": "SP500_ETF", "asset_class": "equity", "region": "US", "weight": 0.3},
            {"symbol": "GOLD_ETF", "asset_class": "gold", "region": "Gold", "weight": 0.2},
        ]
    }

    result = run_portfolio_scenarios(snapshot)
    china_shock = next(item for item in result["scenarios"] if item["id"] == "china_equity_shock")

    assert china_shock["portfolio_loss_pct"] == -13.5
    assert china_shock["region_shocks"]["China"] == -0.12


def test_run_portfolio_scenarios_applies_strategy_shocks():
    snapshot = {
        "positions": [
            {"symbol": "STAR50_ETF", "asset_class": "equity", "region": "China", "strategy": "technology", "weight": 0.4},
            {"symbol": "CSI300_ETF", "asset_class": "equity", "region": "China", "strategy": "broad_market", "weight": 0.4},
            {"symbol": "GOLD_ETF", "asset_class": "gold", "region": "Gold", "strategy": "gold", "weight": 0.2},
        ]
    }

    result = run_portfolio_scenarios(snapshot)
    tech_shock = next(item for item in result["scenarios"] if item["id"] == "technology_drawdown")

    assert tech_shock["portfolio_loss_pct"] == -8.8
    assert tech_shock["strategy_shocks"]["semiconductor"] == -0.20
