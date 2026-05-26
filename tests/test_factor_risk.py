from core.factor_risk import build_factor_risk_snapshot, get_factor_exposures_for_symbol
from core.portfolio_book import Position, build_portfolio_snapshot


def _snapshot():
    return build_portfolio_snapshot([
        Position("CSI300_ETF", "CSI 300", "equity", "CNY", 100.0, region="China", strategy="broad_market"),
        Position("NASDAQ_ETF", "Nasdaq", "equity", "CNY", 100.0, region="US", strategy="technology"),
        Position("GOLD_ETF", "Gold", "gold", "CNY", 100.0, region="Gold", strategy="gold"),
    ])


def test_known_etf_returns_factor_exposures():
    exposures = get_factor_exposures_for_symbol("NASDAQ_ETF")

    assert {"factor_group": "region", "factor_name": "US", "exposure": 1.0} in exposures
    assert {"factor_group": "macro", "factor_name": "equity_beta", "exposure": 1.136} in exposures
    assert {"factor_group": "theme", "factor_name": "US technology", "exposure": 1.0} in exposures


def test_factor_risk_snapshot_aggregates_weighted_exposures():
    snapshot = build_factor_risk_snapshot(_snapshot())

    assert snapshot["coverage"]["mapped_positions"] == 3
    assert snapshot["coverage"]["coverage_ratio"] == 1.0
    assert snapshot["factor_groups"]["region"]["China"] == 0.333333
    assert snapshot["factor_groups"]["region"]["US"] == 0.333333
    assert snapshot["factor_groups"]["macro"]["equity_beta"] == 0.690999
    assert snapshot["factor_groups"]["theme"]["gold hedge"] == 0.333333
    assert snapshot["top_factor"]["factor_group"] == "macro"
    assert snapshot["top_factor"]["factor_name"] == "equity_beta"


def test_unknown_etf_is_reported_without_breaking_snapshot():
    portfolio = build_portfolio_snapshot([
        Position("UNKNOWN_ETF", "Unknown", "equity", "CNY", 50.0, region="Global", strategy="core"),
        Position("GOLD_ETF", "Gold", "gold", "CNY", 50.0, region="Gold", strategy="gold"),
    ])

    snapshot = build_factor_risk_snapshot(portfolio)

    assert snapshot["coverage"]["mapped_positions"] == 1
    assert snapshot["coverage"]["unmapped_symbols"] == ["UNKNOWN_ETF"]
    assert snapshot["factor_groups"]["theme"]["gold hedge"] == 0.5
