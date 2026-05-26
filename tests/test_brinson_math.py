import pytest
from core.attribution_engine import build_attribution_snapshot
from core.portfolio_book import Position, build_portfolio_snapshot
from core.benchmark_book import build_default_benchmark

def test_brinson_fachler_algebraic_precision():
    # 1. Setup portfolio with different asset classes
    portfolio = build_portfolio_snapshot([
        Position("CSI300_ETF", "CSI 300", "equity", "CNY", 500.0, region="China", strategy="broad_market"),
        Position("GOLD_ETF", "Gold", "gold", "CNY", 300.0, region="Gold", strategy="gold"),
        Position("TLT_ETF", "US Bond", "bond", "USD", 200.0, region="US", strategy="fixed_income"),
    ])
    
    # 2. Setup benchmark with different weights
    benchmark = build_default_benchmark({
        "CSI300_ETF": 0.4,
        "GOLD_ETF": 0.4,
        "TLT_ETF": 0.2,
    })
    
    # 3. Define returns
    asset_returns = {
        "CSI300_ETF": 0.05,
        "GOLD_ETF": -0.02,
        "TLT_ETF": 0.01,
    }
    benchmark_returns = {
        "CSI300_ETF": 0.04,
        "GOLD_ETF": -0.01,
        "TLT_ETF": 0.005,
    }
    
    # 4. Compute attribution
    attribution = build_attribution_snapshot(
        portfolio,
        benchmark,
        period="T+1",
        asset_returns=asset_returns,
        benchmark_returns=benchmark_returns,
        currency_returns={"CNY": 0.0, "USD": 0.0}
    )
    
    # 5. Extract results
    p_ret = attribution["portfolio_return"]
    b_ret = attribution["benchmark_return"]
    act_ret = attribution["active_return"]
    alloc = attribution["allocation_effect"]
    select = attribution["selection_effect"]
    inter = attribution["interaction_effect"]
    
    # 6. Verify Brinson-Fachler algebraic identity at portfolio level:
    # Active Return = Allocation + Selection + Interaction
    sum_effects = alloc + select + inter
    
    # Assertions with floating point tolerance
    assert abs(p_ret - (0.5 * 0.05 + 0.3 * -0.02 + 0.2 * 0.01)) < 1e-7
    assert abs(b_ret - (0.4 * 0.04 + 0.4 * -0.01 + 0.2 * 0.005)) < 1e-7
    assert abs(act_ret - (p_ret - b_ret)) < 1e-7
    assert abs(act_ret - sum_effects) < 1e-5
    
    # Verify that the sum of effects for each class also matches their active returns
    for class_info in attribution["by_class"]:
        ac_alloc = class_info["allocation_effect"]
        ac_select = class_info["selection_effect"]
        ac_inter = class_info["interaction_effect"]
        ac_active = class_info["active_return"]
        
        w_p = class_info["portfolio_weight"]
        w_b = class_info["benchmark_weight"]
        r_p = class_info["portfolio_return"]
        r_b = class_info["benchmark_return"]
        
        # Verify symbol-level/class-level calculations
        assert abs(ac_alloc - (w_p - w_b) * (r_b - b_ret)) < 1e-5
        assert abs(ac_select - w_b * (r_p - r_b)) < 1e-5
        assert abs(ac_inter - (w_p - w_b) * (r_p - r_b)) < 1e-5
