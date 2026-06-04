import numpy as np
import pandas as pd

from core import strategy_lab
from core.portfolio_book import Position


def _price_frame(returns):
    close = 100.0 * (1.0 + pd.Series(returns)).cumprod()
    return pd.DataFrame({"Close": close})


def test_global_risk_parity_returns_bounded_institutional_decision(monkeypatch):
    rng = np.random.default_rng(7)
    base = rng.normal(0.0004, 0.008, 180)
    a_share = base + rng.normal(0.0, 0.004, 180)
    overseas = (base * 0.45) + rng.normal(0.0002, 0.012, 180)

    def fake_get_symbol_data(symbol, years=1):
        if symbol == "510300.SH":
            return _price_frame(a_share)
        if symbol == "513500.SH":
            return _price_frame(overseas)
        raise AssertionError(f"unexpected symbol {symbol}")

    monkeypatch.setattr(strategy_lab, "get_symbol_data", fake_get_symbol_data)

    result = strategy_lab.compute_global_risk_parity()

    assert result["status"] == "active"
    assert result["tradeable"] is True
    assert result["decision_state"] in {"rebalance_required", "no_action"}
    assert result["target_weights"]["510300.SH"] >= 0.30
    assert result["target_weights"]["510300.SH"] <= 0.65
    assert result["target_weights"]["513500.SH"] >= 0.20
    assert result["target_weights"]["513500.SH"] <= 0.60
    assert abs(sum(result["target_weights"].values()) - 1.0) < 0.0001
    assert "portfolio_volatility_pct" in result["risk_metrics"]
    assert "actual_risk_contribution_pct" in result["risk_metrics"]["risk_contribution"]["510300.SH"]
    assert len(result["execution_plan"]) == 2
    assert all("target_weight" in item for item in result["execution_plan"])


def test_global_risk_parity_degrades_to_policy_weights_when_market_data_fails(monkeypatch):
    def failing_get_symbol_data(symbol, years=1):
        raise RuntimeError("market source unavailable")

    monkeypatch.setattr(strategy_lab, "get_symbol_data", failing_get_symbol_data)

    result = strategy_lab.compute_global_risk_parity()

    assert result["status"] == "degraded"
    assert result["tradeable"] is False
    assert result["decision_state"] == "blocked"
    assert result["target_weights"] == {"510300.SH": 0.5, "513500.SH": 0.5}
    assert result["holdings"][0]["weight"] == "50%"
    assert result["holdings"][1]["weight"] == "50%"
    assert result["data_quality"]["fallback_used"] is True


def test_global_risk_parity_uses_live_portfolio_weights_for_execution(monkeypatch):
    returns = np.full(180, 0.0003)
    returns[::5] = -0.001

    def fake_get_symbol_data(symbol, years=1):
        if symbol in {"510300.SH", "513500.SH"}:
            return _price_frame(returns)
        raise AssertionError(f"unexpected symbol {symbol}")

    def fake_load_portfolio_positions():
        return [
            Position("510300.SH", "CSI 300 ETF", "equity", "CNY", 200.0),
            Position("513500.SH", "S&P 500 ETF", "equity", "CNY", 800.0),
        ]

    monkeypatch.setattr(strategy_lab, "get_symbol_data", fake_get_symbol_data)
    monkeypatch.setattr(strategy_lab, "load_portfolio_positions", fake_load_portfolio_positions)

    result = strategy_lab.compute_global_risk_parity()
    execution_by_symbol = {item["symbol"]: item for item in result["execution_plan"]}

    assert result["current_weights"] == {"510300.SH": 0.2, "513500.SH": 0.8}
    assert execution_by_symbol["513500.SH"]["action"] == "REDUCE"
    assert execution_by_symbol["513500.SH"]["trade_weight"] == -0.1
    assert execution_by_symbol["510300.SH"]["action"] == "BUY"
    assert execution_by_symbol["510300.SH"]["trade_weight"] == 0.1
