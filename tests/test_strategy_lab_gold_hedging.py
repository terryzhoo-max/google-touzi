import numpy as np
import pandas as pd

from core import strategy_lab


def _price_frame(returns):
    close = 100.0 * (1.0 + pd.Series(returns)).cumprod()
    return pd.DataFrame({"Close": close})


def test_gold_hedging_keeps_zero_weight_when_panic_low_and_trend_bearish(monkeypatch):
    bearish_returns = np.full(90, -0.001)

    def fake_get_symbol_data(symbol, years=1):
        assert symbol == "518880.SH"
        return _price_frame(bearish_returns)

    def fake_get_vix_history(days):
        return pd.Series([14.8, 15.0])

    monkeypatch.setattr(strategy_lab, "get_symbol_data", fake_get_symbol_data)
    monkeypatch.setattr("core.data_providers.get_vix_history", fake_get_vix_history)

    result = strategy_lab.compute_gold_hedging()

    assert result["status"] == "active"
    assert result["tradeable"] is True
    assert result["signal"] == "NEUTRAL_ON_GOLD"
    assert result["decision_state"] == "no_action"
    assert result["target_weight"] == 0.0
    assert result["hedge_score"] < 40
    assert result["confidence"] == "LOW"
    assert result["execution_plan"][0]["action"] == "HOLD"
    assert any(driver["name"] == "Panic Score" for driver in result["drivers"])
    assert any(item["label"] == "Gold Hedge Score" for item in result["details"])


def test_gold_hedging_degrades_and_blocks_trading_when_vix_missing(monkeypatch):
    bullish_returns = np.full(90, 0.0015)

    def fake_get_symbol_data(symbol, years=1):
        assert symbol == "518880.SH"
        return _price_frame(bullish_returns)

    def fake_get_vix_history(days):
        return pd.Series(dtype=float)

    monkeypatch.setattr(strategy_lab, "get_symbol_data", fake_get_symbol_data)
    monkeypatch.setattr("core.data_providers.get_vix_history", fake_get_vix_history)

    result = strategy_lab.compute_gold_hedging()

    assert result["status"] == "degraded"
    assert result["tradeable"] is False
    assert result["signal"] == "NO_SIGNAL"
    assert result["decision_state"] == "blocked"
    assert result["target_weight"] == 0.0
    assert result["data_quality"]["fallback_used"] is False
    assert "vix" in result["data_quality"]["degraded_reason"].lower()


def test_gold_hedging_allocates_defensive_weight_only_after_confirmed_pressure_and_trend(monkeypatch):
    bullish_returns = np.full(90, 0.0018)

    def fake_get_symbol_data(symbol, years=1):
        assert symbol == "518880.SH"
        return _price_frame(bullish_returns)

    def fake_get_vix_history(days):
        return pd.Series([19.0, 21.5, 24.0, 27.5, 31.0])

    monkeypatch.setattr(strategy_lab, "get_symbol_data", fake_get_symbol_data)
    monkeypatch.setattr("core.data_providers.get_vix_history", fake_get_vix_history)

    result = strategy_lab.compute_gold_hedging()

    assert result["status"] == "active"
    assert result["tradeable"] is True
    assert result["signal"] == "BULLISH_ON_GOLD"
    assert result["decision_state"] == "rebalance_required"
    assert result["target_weight"] >= 0.08
    assert result["target_weight"] <= 0.15
    assert result["execution_plan"][0]["action"] == "BUY"
    assert result["execution_plan"][0]["trade_weight"] <= 0.03
    assert result["confidence"] in {"MEDIUM", "HIGH"}
