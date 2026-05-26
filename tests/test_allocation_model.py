from dataclasses import replace

from core.allocation_model import build_allocation_recommendation
from core.allocation_policy import (
    allocation_policy_hash,
    allocation_policy_to_dict,
    get_default_allocation_policy,
)
from core.etf_signal_model import build_etf_signals
from core.factor_risk import build_factor_risk_snapshot
from core.portfolio_book import build_portfolio_snapshot, load_portfolio_positions
from core.risk_engine import calculate_portfolio_risk
from core.scenario_engine import run_portfolio_scenarios


def _portfolio():
    from core.portfolio_book import Position
    positions = [
        Position("CSI300_ETF", "CSI300 ETF", "equity", "CNY", 100000.0, region="China", strategy="broad_market"),
        Position("CSI500_ETF", "CSI500 ETF", "equity", "CNY", 100000.0, region="China", strategy="small_mid_cap"),
        Position("STAR50_ETF", "STAR50 ETF", "equity", "CNY", 100000.0, region="China", strategy="technology"),
        Position("HSTECH_ETF", "HSTECH ETF", "equity", "HKD", 100000.0, region="HongKong", strategy="technology"),
        Position("SP500_ETF", "SP500 ETF", "equity", "USD", 100000.0, region="US", strategy="broad_market"),
        Position("NASDAQ_ETF", "NASDAQ ETF", "equity", "USD", 100000.0, region="US", strategy="technology"),
        Position("NIKKEI225_ETF", "NIKKEI225 ETF", "equity", "JPY", 100000.0, region="Japan", strategy="overseas"),
        Position("CHIP_ETF", "CHIP ETF", "equity", "CNY", 100000.0, region="China", strategy="technology"),
        Position("GOLD_ETF", "GOLD ETF", "gold", "CNY", 100000.0, region="Gold", strategy="gold"),
    ]
    return build_portfolio_snapshot(positions)


def _quality(score=100, flags=None):
    return {
        "score": score,
        "status": "strong" if score >= 80 else "weak",
        "flags": flags or [],
        "source": "portfolio_file",
    }


def _market_context():
    return {
        "macro_decision": {"score": 64, "signal_en": "BUY"},
        "valuation": {"indices": [{"name": "CSI300", "pe_pct": 42}]},
        "domestic_rotation": {
            "items": [
                {"code": "510300.SH", "ret_20d": 2.1},
                {"code": "510500.SH", "ret_20d": 1.4},
                {"code": "588000.SH", "ret_20d": -2.2},
            ]
        },
        "global_rotation": {
            "items": [
                {"code": "513500.SH", "ret_20d": 1.2},
                {"code": "513100.SH", "ret_20d": 2.8},
                {"code": "513520.SH", "ret_20d": 0.5},
                {"code": "513180.SH", "ret_20d": -1.0},
            ]
        },
    }


def test_allocation_policy_hash_is_stable_and_sensitive():
    policy = get_default_allocation_policy()
    payload = allocation_policy_to_dict(policy)

    assert payload["version"] == "allocation_policy_v1"
    assert payload["policy_hash"] == allocation_policy_hash(policy)
    assert len(payload["policy_hash"]) == 64
    assert allocation_policy_hash(policy) == allocation_policy_hash(get_default_allocation_policy())
    assert allocation_policy_hash(replace(policy, max_turnover=policy.max_turnover + 0.01)) != payload["policy_hash"]


def test_etf_signal_builder_returns_one_signal_per_real_holding():
    portfolio = _portfolio()
    signals = build_etf_signals(
        portfolio,
        factor_risk=build_factor_risk_snapshot(portfolio),
        risk=calculate_portfolio_risk(portfolio),
        scenarios=run_portfolio_scenarios(portfolio),
        data_quality=_quality(),
        market_context=_market_context(),
    )

    assert len(signals) == 9
    assert {row["symbol"] for row in signals} == {row["symbol"] for row in portfolio["positions"]}
    for row in signals:
        assert 0 <= row["composite_score"] <= 100
        assert 0 <= row["confidence"] <= 1
        assert row["component_scores"].keys() >= {
            "regime_fit",
            "valuation_score",
            "momentum_score",
            "risk_diversification_score",
            "data_confidence_score",
        }
        assert row["reasons"]


def test_etf_signal_builder_accepts_rotation_sector_payloads():
    portfolio = _portfolio()
    signals = build_etf_signals(
        portfolio,
        factor_risk=build_factor_risk_snapshot(portfolio),
        risk=calculate_portfolio_risk(portfolio),
        scenarios=run_portfolio_scenarios(portfolio),
        data_quality=_quality(),
        market_context={
            "macro_decision": {"score": 60, "signal_en": "BUY"},
            "valuation": {"indices": []},
            "global_rotation": {
                "sectors": [
                    {"code": "513100.SH", "ret_20d": 3.0},
                ]
            },
        },
    )

    nasdaq = next(row for row in signals if row["symbol"] == "NASDAQ_ETF")

    assert nasdaq["component_scores"]["momentum_score"] == 65


def test_allocation_recommendation_returns_constraint_checked_target_weights():
    portfolio = _portfolio()
    recommendation = build_allocation_recommendation(
        portfolio,
        data_quality=_quality(),
        market_context=_market_context(),
    )

    assert recommendation["model_version"] == "allocation-v1"
    assert len(recommendation["model_hash"]) == 64
    assert recommendation["status"] in {"allow", "limited", "observe"}
    assert round(sum(recommendation["target_weights"].values()), 6) == 1.0
    assert recommendation["constraint_result"]["status"] in {"pass", "warn", "block"}
    assert "var_95_delta_pct" in recommendation["expected_effect"]
    assert "worst_scenario_delta_pct" in recommendation["expected_effect"]
    assert "turnover_pct" in recommendation["expected_effect"]
    assert recommendation["review_schedule"] == ["T+1", "T+5", "T+20"]
    assert recommendation["evidence_chain"]
    assert all(abs(row["delta_weight"]) >= recommendation["policy"]["min_trade_size"] for row in recommendation["proposed_trades"])


def test_allocation_recommendation_observes_when_data_quality_is_weak():
    recommendation = build_allocation_recommendation(
        _portfolio(),
        data_quality=_quality(score=55, flags=["fallback"]),
        market_context=_market_context(),
    )

    assert recommendation["status"] in {"limited", "observe"}
    assert any(item["code"] == "data_quality_guardrail" for item in recommendation["evidence_chain"])
