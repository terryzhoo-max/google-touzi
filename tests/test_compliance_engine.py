from core.compliance_engine import CompliancePolicy, evaluate_pre_trade_compliance
from core.portfolio_book import Position, build_portfolio_snapshot
from core.what_if_engine import run_what_if


def _snapshot():
    return build_portfolio_snapshot([
        Position("CSI300_ETF", "CSI 300", "equity", "CNY", 500.0, region="China", strategy="broad_market"),
        Position("NASDAQ_ETF", "Nasdaq", "equity", "CNY", 300.0, region="US", strategy="technology"),
        Position("GOLD_ETF", "Gold", "gold", "CNY", 200.0, region="Gold", strategy="gold"),
    ])


def test_compliance_passes_low_turnover_risk_reduction():
    current = _snapshot()
    what_if = run_what_if(current, {"CSI300_ETF": -0.05, "GOLD_ETF": 0.05})

    result = evaluate_pre_trade_compliance(
        current,
        what_if["after"]["portfolio"],
        data_quality={"score": 95, "flags": []},
        current_risk={"risk_level": "medium"},
        policy=CompliancePolicy(max_region_weight=0.65, max_strategy_weight=0.6),
    )

    assert result["status"] == "pass"
    assert result["violations"] == []
    assert result["warnings"] == []
    assert result["policy_version"] == "compliance_policy_v1"
    assert len(result["policy_hash"]) == 64


def test_compliance_warns_on_concentration_but_does_not_block():
    current = _snapshot()
    what_if = run_what_if(current, {"NASDAQ_ETF": 0.05, "GOLD_ETF": -0.05})

    result = evaluate_pre_trade_compliance(
        current,
        what_if["after"]["portfolio"],
        data_quality={"score": 95, "flags": []},
        current_risk={"risk_level": "medium"},
        policy=CompliancePolicy(max_strategy_weight=0.52),
    )

    assert result["status"] == "warn"
    assert "strategy_limit_near:broad_market" in result["warnings"]
    assert result["violations"] == []


def test_compliance_blocks_new_risk_when_portfolio_risk_is_high():
    current = _snapshot()
    what_if = run_what_if(current, {"NASDAQ_ETF": 0.05, "GOLD_ETF": -0.05})

    result = evaluate_pre_trade_compliance(
        current,
        what_if["after"]["portfolio"],
        data_quality={"score": 95, "flags": []},
        current_risk={"risk_level": "high"},
    )

    assert result["status"] == "block"
    assert "no_new_risk_when_risk_high" in result["violations"]
    assert "Reduce equity or technology exposure before adding risk." in result["repair_suggestions"]


def test_compliance_blocks_fallback_data_from_non_defensive_action():
    current = _snapshot()
    what_if = run_what_if(current, {"NASDAQ_ETF": 0.05, "GOLD_ETF": -0.05})

    result = evaluate_pre_trade_compliance(
        current,
        what_if["after"]["portfolio"],
        data_quality={"score": 70, "flags": ["fallback"]},
        current_risk={"risk_level": "medium"},
    )

    assert result["status"] == "block"
    assert "fallback_data_non_defensive_action" in result["violations"]
