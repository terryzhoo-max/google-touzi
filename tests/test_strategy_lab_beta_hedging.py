import numpy as np
import pandas as pd

from core import strategy_lab


def _price_frame(returns):
    close = 100.0 * (1.0 + pd.Series(returns)).cumprod()
    return pd.DataFrame({"Close": close})


def test_beta_hedging_returns_paper_decision_without_enabling_trading(monkeypatch):
    rng = np.random.default_rng(17)
    benchmark = rng.normal(0.0003, 0.009, 180)
    theme = (benchmark * 1.22) + rng.normal(0.0004, 0.006, 180)

    def fake_get_symbol_data(symbol, years=1):
        if symbol == "510300.SH":
            return _price_frame(benchmark)
        if symbol in {"512760.SH", "159819.SZ", "159825.SZ", "512660.SH"}:
            return _price_frame(theme)
        raise AssertionError(f"unexpected symbol {symbol}")

    monkeypatch.setattr(strategy_lab, "get_symbol_data", fake_get_symbol_data)

    result = strategy_lab.compute_beta_hedging()

    assert result["status"] == "standby"
    assert result["model_mode"] == "paper"
    assert result["tradeable"] is False
    assert result["decision_state"] == "paper_blocked"
    assert result["data_quality"]["status"] == "ok"
    assert result["risk_metrics"]["primary_beta"] > 0.9
    assert result["risk_metrics"]["r_squared"] > 0.4
    assert result["risk_metrics"]["model_confidence"] >= 0.5
    assert result["target_exposure"]["hedge_ratio"] > 0.0
    assert result["target_exposure"]["net_beta_after_hedge"] >= 0.0
    assert "paper_mode_not_approved_for_live" in result["blockers"]
    assert result["holdings"][0]["symbol"] == "510300.SH"
    assert result["holdings"][0]["action"] == "PAPER_HEDGE"


def test_beta_hedging_blocks_when_market_data_is_unavailable(monkeypatch):
    def failing_get_symbol_data(symbol, years=1):
        raise RuntimeError("market source unavailable")

    monkeypatch.setattr(strategy_lab, "get_symbol_data", failing_get_symbol_data)

    result = strategy_lab.compute_beta_hedging()

    assert result["status"] == "degraded"
    assert result["model_mode"] == "blocked"
    assert result["tradeable"] is False
    assert result["decision_state"] == "blocked"
    assert result["target_exposure"]["hedge_ratio"] == 0.0
    assert result["data_quality"]["status"] == "degraded"
    assert result["data_quality"]["degraded_reason"] == "beta_hedging_market_data_unavailable"
    assert "market_source_unavailable" in result["blockers"]
