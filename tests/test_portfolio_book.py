from core.portfolio_book import (
    Position,
    build_portfolio_snapshot,
    get_sample_portfolio,
    load_portfolio_positions,
)


def test_sample_portfolio_weights_sum_to_one():
    snapshot = build_portfolio_snapshot(get_sample_portfolio())

    assert snapshot["total_market_value"] == 1000000.0
    assert round(sum(item["weight"] for item in snapshot["positions"]), 6) == 1.0
    assert snapshot["asset_class_exposure"]["equity"] == 0.45
    assert snapshot["asset_class_exposure"]["bond"] == 0.25
    assert snapshot["asset_class_exposure"]["gold"] == 0.15
    assert snapshot["asset_class_exposure"]["cash"] == 0.15


def test_position_rejects_negative_market_value():
    try:
        Position("SPY", "SPDR S&P 500 ETF", "equity", "USD", -1.0)
    except ValueError as exc:
        assert "market_value must be non-negative" in str(exc)
    else:
        raise AssertionError("negative market value was accepted")


def test_load_portfolio_positions_reads_json_file(tmp_path):
    path = tmp_path / "portfolio.json"
    path.write_text(
        """
        {
          "positions": [
            {
              "symbol": "AAPL",
              "name": "Apple Inc.",
              "asset_class": "equity",
              "region": "US",
              "strategy": "single_stock",
              "currency": "USD",
              "market_value": 300000,
              "quantity": 1000,
              "cost_basis": 250000
            },
            {
              "symbol": "CASH",
              "name": "Cash",
              "asset_class": "cash",
              "currency": "USD",
              "market_value": 200000
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    positions = load_portfolio_positions(str(path))
    snapshot = build_portfolio_snapshot(positions)

    assert [item.symbol for item in positions] == ["AAPL", "CASH"]
    assert positions[0].region == "US"
    assert positions[0].strategy == "single_stock"
    assert snapshot["total_market_value"] == 500000.0
    assert snapshot["asset_class_exposure"]["equity"] == 0.6
    assert snapshot["region_exposure"]["US"] == 0.6
    assert snapshot["strategy_exposure"]["single_stock"] == 0.6
    assert snapshot["currency_exposure"]["USD"] == 1.0


def test_build_portfolio_snapshot_reports_region_exposure():
    snapshot = build_portfolio_snapshot([
        Position("CSI300_ETF", "沪深300ETF", "equity", "CNY", 300000.0, region="China", strategy="broad_market"),
        Position("SP500_ETF", "标普500ETF", "equity", "CNY", 200000.0, region="US", strategy="overseas"),
    ])

    assert snapshot["region_exposure"] == {"China": 0.6, "US": 0.4}
    assert snapshot["strategy_exposure"] == {"broad_market": 0.6, "overseas": 0.4}
    assert snapshot["currency_exposure"] == {"CNY": 1.0}


def test_build_portfolio_snapshot_reports_concentration_diagnostics():
    snapshot = build_portfolio_snapshot([
        Position("A", "A", "equity", "CNY", 600000.0),
        Position("B", "B", "equity", "CNY", 250000.0),
        Position("C", "C", "gold", "CNY", 150000.0),
    ])

    assert snapshot["largest_position"]["symbol"] == "A"
    assert snapshot["largest_position"]["weight"] == 0.6
    assert snapshot["top_3_weight"] == 1.0
    assert snapshot["concentration_level"] == "high"


def test_load_portfolio_positions_falls_back_to_sample_when_path_missing():
    positions = load_portfolio_positions("")

    assert positions == get_sample_portfolio()
