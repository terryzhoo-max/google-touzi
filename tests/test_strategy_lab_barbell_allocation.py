from core import strategy_lab
from core.portfolio_book import Position


def test_barbell_allocation_returns_full_execution_review(monkeypatch):
    def fake_load_portfolio_positions():
        return [
            Position("513500.SH", "S&P 500 ETF", "equity", "CNY", 200.0),
            Position("510880.SH", "Dividend ETF", "equity", "CNY", 500.0),
            Position("510300.SH", "CSI 300 ETF", "equity", "CNY", 150.0),
            Position("512760.SH", "Chip ETF", "equity", "CNY", 150.0),
        ]

    monkeypatch.setattr(strategy_lab, "load_portfolio_positions", fake_load_portfolio_positions)

    result = strategy_lab.build_barbell_allocation()
    execution_by_symbol = {item["symbol"]: item for item in result["execution_plan"]}
    holdings_by_symbol = {item["symbol"]: item for item in result["holdings"]}

    assert result["tradeable"] is True
    assert result["decision_state"] == "rebalance_required"
    assert result["policy_version"] == strategy_lab.STRATEGY_POLICY_VERSION
    assert len(result["strategy_policy_hash"]) == 64
    assert result["target_weights"] == {
        "513500.SH": 0.4,
        "510880.SH": 0.3,
        "510300.SH": 0.15,
        "512760.SH": 0.15,
    }
    assert result["current_weights"] == {
        "513500.SH": 0.2,
        "510880.SH": 0.5,
        "510300.SH": 0.15,
        "512760.SH": 0.15,
    }
    assert len(result["execution_plan"]) == 4
    assert execution_by_symbol["513500.SH"]["action"] == "BUY"
    assert execution_by_symbol["513500.SH"]["trade_weight"] == 0.1
    assert execution_by_symbol["510880.SH"]["action"] == "REDUCE"
    assert execution_by_symbol["510880.SH"]["trade_weight"] == -0.1
    assert execution_by_symbol["510300.SH"]["action"] == "HOLD"
    assert execution_by_symbol["512760.SH"]["action"] == "HOLD"
    assert list(holdings_by_symbol) == ["513500.SH", "510880.SH", "510300.SH", "512760.SH"]
    assert holdings_by_symbol["513500.SH"]["target_weight"] == 0.4
    assert holdings_by_symbol["513500.SH"]["current_weight"] == 0.2
    assert holdings_by_symbol["513500.SH"]["drift_weight"] == 0.2


def test_barbell_allocation_blocks_trading_when_current_book_is_unavailable(monkeypatch):
    def failing_load_portfolio_positions():
        raise RuntimeError("portfolio book unavailable")

    monkeypatch.setattr(strategy_lab, "load_portfolio_positions", failing_load_portfolio_positions)

    result = strategy_lab.build_barbell_allocation()

    assert result["status"] == "degraded"
    assert result["tradeable"] is False
    assert result["decision_state"] == "blocked"
    assert result["data_quality"]["status"] == "degraded"
    assert result["data_quality"]["fallback_used"] is True
    assert "portfolio book unavailable" in result["data_quality"]["degraded_reason"]
    assert all(item["action"] == "HOLD" for item in result["execution_plan"])


def test_barbell_allocation_aggregates_equivalent_etf_aliases(monkeypatch):
    def fake_load_portfolio_positions():
        return [
            Position("513500.SH", "S&P 500 ETF", "equity", "CNY", 400.0),
            Position("512890", "Dividend Low Vol ETF", "equity", "CNY", 200.0),
            Position("159545", "Dividend Low Vol ETF", "equity", "CNY", 100.0),
            Position("510300", "CSI 300 ETF", "equity", "CNY", 200.0),
            Position("159995", "Chip ETF", "equity", "CNY", 100.0),
        ]

    monkeypatch.setattr(strategy_lab, "load_portfolio_positions", fake_load_portfolio_positions)

    result = strategy_lab.build_barbell_allocation()

    assert result["current_weights"] == {
        "513500.SH": 0.4,
        "510880.SH": 0.3,
        "510300.SH": 0.2,
        "512760.SH": 0.1,
    }
    assert result["data_quality"]["current_weights_source"] == "portfolio_book"
    assert result["data_quality"]["symbol_aliases_applied"] is True


def test_barbell_allocation_caps_total_trade_weight_for_staged_execution(monkeypatch):
    def fake_load_portfolio_positions():
        return [
            Position("CASH", "Cash", "cash", "CNY", 1000.0),
        ]

    monkeypatch.setattr(strategy_lab, "load_portfolio_positions", fake_load_portfolio_positions)

    result = strategy_lab.build_barbell_allocation()
    total_trade_weight = sum(abs(item["trade_weight"]) for item in result["execution_plan"])

    assert total_trade_weight <= 0.200001
    assert result["risk_controls"]["max_total_trade_weight"] == 0.2
