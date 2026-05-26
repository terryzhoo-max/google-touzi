import pytest
import math
from core.trade_constraints import calculate_ex_ante_transaction_costs, _get_liquidity_params


def test_transaction_friction_math():
    # 1. Test parameter fetching and defaults
    spy_liq = _get_liquidity_params("SP500_ETF")
    assert spy_liq["adv"] == 500000000.0
    assert spy_liq["sigma_daily"] == 0.009

    fallback_liq = _get_liquidity_params("NON_EXISTENT_TICKER")
    assert fallback_liq["adv"] == 200000000.0
    assert fallback_liq["sigma_daily"] == 0.012

    # Case insensitivity & suffix stripping
    spy_suffix_liq = _get_liquidity_params("sp500_etf.sh")
    assert spy_suffix_liq["adv"] == 500000000.0
    assert spy_suffix_liq["sigma_daily"] == 0.009


def test_calculate_ex_ante_transaction_costs_cash_free():
    # CASH holds zero covariance, infinite liquidity -> 0 cost
    current_weights = {"SP500_ETF": 0.4, "CASH": 0.6}
    target_weights = {"SP500_ETF": 0.2, "CASH": 0.8}
    total_market_value = 10000000.0  # 10M

    result = calculate_ex_ante_transaction_costs(total_market_value, current_weights, target_weights)

    # CASH is completely ignored in details and cost calculations
    assert len(result["details"]) == 1
    assert result["details"][0]["symbol"] == "SP500_ETF"

    # Only SP500_ETF has fees and impact costs
    spy_detail = result["details"][0]
    trade_val = 10000000.0 * 0.2  # 2M
    expected_commission = trade_val * 0.0003  # 万三 = 600
    assert abs(spy_detail["commission"] - expected_commission) < 1.0

    # Market impact = trade_val * 0.5 * sigma * sqrt(trade_val / ADV)
    # trade_val = 2,000,000
    # ADV = 500,000,000
    # sigma = 0.009
    # participation_rate = 2M / 500M = 0.004
    # sqrt(0.004) = 0.06324555
    # impact_cost = 2,000,000 * 0.5 * 0.009 * 0.06324555 = 569.21
    expected_impact = trade_val * 0.5 * 0.009 * math.sqrt(trade_val / 500000000.0)
    assert abs(spy_detail["impact_cost"] - expected_impact) < 1.0

    # Total cost = commission + impact
    assert abs(spy_detail["total_cost"] - (expected_commission + expected_impact)) < 1.0


def test_transaction_friction_non_linear_explosion():
    # Almgren-Chriss Square-Root law implies non-linear explosion:
    # 2M trade vs 50M trade. The participation rate in the second is 25 times larger.
    # Because of the square root, the impact cost as a percentage of trade value will be 5x higher,
    # meaning the nominal impact cost is 125x higher!
    current_weights = {"CSI300_ETF": 1.0}
    target_weights_small = {"CSI300_ETF": 0.98}  # 2% delta -> 2M
    target_weights_large = {"CSI300_ETF": 0.50}  # 50% delta -> 50M
    total_market_value = 100000000.0  # 1亿 AUM
    
    # 1. Small trade: 2M trade value
    res_small = calculate_ex_ante_transaction_costs(total_market_value, current_weights, target_weights_small)
    cost_small = res_small["total_impact_cost"]

    # 2. Large trade: 50M trade value (25x larger nominal value)
    res_large = calculate_ex_ante_transaction_costs(total_market_value, current_weights, target_weights_large)
    cost_large = res_large["total_impact_cost"]

    # If it was linear, cost_large would be exactly 25x cost_small.
    # Because of the square root law, it should be 25 * sqrt(25) = 125 times higher!
    ratio = cost_large / cost_small
    assert abs(ratio - 125.0) < 1.0


def test_liquidity_squeeze_warning():
    current_weights = {"SP500_ETF": 1.0}
    
    # 1. Participation rate = 1M / 500M = 0.2% -> Normal
    target_normal = {"SP500_ETF": 0.99}
    res_normal = calculate_ex_ante_transaction_costs(100000000.0, current_weights, target_normal)
    assert res_normal["details"][0]["warning_level"] == "NORMAL"
    assert res_normal["details"][0]["warning_msg"] == ""

    # 2. Participation rate = 30M / 500M = 6.0% -> Red Warning
    # AUM = 1000M, delta = 3% -> 30M trade. ADV = 500M. Participation rate = 30 / 500 = 6% (> 5%)
    target_red = {"SP500_ETF": 0.97}
    res_red = calculate_ex_ante_transaction_costs(1000000000.0, current_weights, target_red)
    assert res_red["details"][0]["warning_level"] == "RED"
    assert "已突破 5% 流动性红线！" in res_red["details"][0]["warning_msg"]
    assert "拆分" in res_red["details"][0]["warning_msg"]


def test_friction_endpoint_contract():
    from fastapi.testclient import TestClient
    from data_engine import app
    
    with TestClient(app) as client:
        response = client.post("/api/institutional/sandbox/friction", json={
            "target_weights": {
                "SP500_ETF": 0.5,
                "GOLD_ETF": 0.3,
                "CASH": 0.2
            }
        })
        assert response.status_code == 200
        data = response.json()
        assert "total_commission" in data
        assert "total_impact_cost" in data
        assert "net_projected_aum" in data
        assert "details" in data
        assert isinstance(data["details"], list)
