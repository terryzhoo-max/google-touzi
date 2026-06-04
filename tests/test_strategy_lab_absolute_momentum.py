import numpy as np
import pandas as pd

from core import strategy_lab


def _price_frame(values):
    index = pd.date_range("2025-01-02", periods=len(values), freq="B")
    return pd.DataFrame({"Close": values}, index=index)


def _flat_then_tail(days, tail_values):
    base = np.full(days - len(tail_values), 100.0)
    return _price_frame(np.concatenate([base, np.array(tail_values, dtype=float)]))


def _patch_market_data(monkeypatch, frames):
    def fake_get_symbol_data(symbol, years=2):
        if symbol not in frames:
            raise AssertionError(f"unexpected symbol {symbol}")
        return frames[symbol]

    monkeypatch.setattr(strategy_lab, "get_symbol_data", fake_get_symbol_data)


def test_absolute_momentum_blocks_trading_when_history_is_insufficient(monkeypatch):
    _patch_market_data(
        monkeypatch,
        {
            "510300.SH": _flat_then_tail(150, [101.0, 102.0, 103.0]),
            "513500.SH": _flat_then_tail(150, [101.0, 102.0, 103.0]),
        },
    )

    result = strategy_lab.analyze_absolute_momentum()

    assert result["status"] == "degraded"
    assert result["tradeable"] is False
    assert result["decision_state"] == "blocked"
    assert result["blocking_reason"] == "insufficient_market_history"
    assert result["risk_action"]["equity_budget_multiplier"] == 0.0
    assert result["data_quality"]["status"] == "degraded"
    assert result["data_quality"]["required_history_days"] == 220
    assert all(item["trade_weight"] == 0.0 for item in result["execution_plan"])


def test_absolute_momentum_cuts_a_share_and_theme_risk_after_confirmed_break(monkeypatch):
    _patch_market_data(
        monkeypatch,
        {
            "510300.SH": _flat_then_tail(230, [96.0, 95.0, 94.0]),
            "513500.SH": _flat_then_tail(230, [103.0, 104.0, 105.0, 106.0, 107.0]),
        },
    )

    result = strategy_lab.analyze_absolute_momentum()

    assert result["status"] == "active"
    assert result["tradeable"] is True
    assert result["decision_state"] == "risk_off"
    assert result["regime_state"] == "bearish_confirmed"
    assert result["risk_action"]["equity_budget_multiplier"] == 0.5
    assert result["target_weights"]["159601.SZ"] == 0.0
    assert result["target_weights"]["159819.SZ"] == 0.0
    assert result["execution_plan"][0]["action"] == "LIQUIDATE"
    assert result["details"][-1]["value"] == "TRIGGERED (A-SHARE)"


def test_absolute_momentum_allows_broad_risk_but_blocks_inactive_ai_theme(monkeypatch):
    _patch_market_data(
        monkeypatch,
        {
            "510300.SH": _flat_then_tail(230, [103.0, 104.0, 105.0, 106.0, 107.0]),
            "513500.SH": _flat_then_tail(230, [103.0, 104.0, 105.0, 106.0, 107.0]),
        },
    )

    result = strategy_lab.analyze_absolute_momentum()

    assert result["status"] == "active"
    assert result["tradeable"] is True
    assert result["decision_state"] == "risk_on"
    assert result["regime_state"] == "bullish_confirmed"
    assert result["risk_action"]["equity_budget_multiplier"] == 1.0
    assert result["risk_action"]["theme_cap_pct"] == 0.0
    assert result["target_weights"]["159601.SZ"] == 0.15
    assert result["target_weights"]["159819.SZ"] == 0.0
    assert result["execution_plan"][1]["action"] == "BLOCKED"
    assert result["execution_plan"][1]["blocking_reason"] == "theme_model_not_connected"
    assert result["data_quality"]["fallback_used"] is False
