from core.portfolio_book import Position, build_portfolio_snapshot, get_sample_portfolio
from core.risk_engine import calculate_portfolio_risk
from core.what_if_engine import build_default_risk_reduction_adjustments, run_what_if


def test_what_if_applies_weight_adjustments_and_reports_risk_change():
    current = build_portfolio_snapshot(get_sample_portfolio())
    before = calculate_portfolio_risk(current)
    result = run_what_if(current, {"SPY": -0.10, "GLD": 0.05, "CASH": 0.05})

    assert result["target_weights"]["SPY"] == 0.35
    assert result["target_weights"]["GLD"] == 0.2
    assert result["target_weights"]["CASH"] == 0.2
    assert result["risk_delta"]["var_95_pct"] > 0
    assert result["before"]["risk"]["var_95_pct"] == before["var_95_pct"]
    assert result["constraints"]["passed"] is True
    assert result["improves_risk"] is True


def test_default_risk_reduction_reduces_largest_equity_and_adds_gold():
    current = build_portfolio_snapshot(get_sample_portfolio())

    adjustments = build_default_risk_reduction_adjustments(current)

    assert adjustments == {"SPY": -0.05, "GLD": 0.05}


def test_what_if_target_snapshot_preserves_position_metadata_for_scenarios():
    current = build_portfolio_snapshot([
        Position(
            "CHIP_ETF",
            "Chip ETF",
            "equity",
            "CNY",
            600000.0,
            quantity=1000,
            cost_basis=500000.0,
            region="China",
            strategy="technology",
        ),
        Position(
            "GOLD_ETF",
            "Gold ETF",
            "gold",
            "CNY",
            400000.0,
            region="Gold",
            strategy="gold",
        ),
    ])

    result = run_what_if(current, {"CHIP_ETF": -0.10, "GOLD_ETF": 0.10})
    chip = next(item for item in result["after"]["portfolio"]["positions"] if item["symbol"] == "CHIP_ETF")

    assert chip["region"] == "China"
    assert chip["strategy"] == "technology"
    assert chip["quantity"] == 1000
    assert chip["cost_basis"] == 500000.0
    assert result["after"]["portfolio"]["region_exposure"]["China"] == 0.5
    assert result["after"]["portfolio"]["strategy_exposure"]["technology"] == 0.5
