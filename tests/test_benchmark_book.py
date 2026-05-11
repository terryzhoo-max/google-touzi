from core.benchmark_book import (
    build_active_risk_snapshot,
    build_default_benchmark,
    benchmark_to_dict,
)
from core.portfolio_book import Position, build_portfolio_snapshot


def _portfolio():
    return build_portfolio_snapshot([
        Position("CSI300_ETF", "CSI 300", "equity", "CNY", 100.0, region="China", strategy="broad_market"),
        Position("NASDAQ_ETF", "Nasdaq", "equity", "CNY", 100.0, region="US", strategy="technology"),
        Position("GOLD_ETF", "Gold", "gold", "CNY", 100.0, region="Gold", strategy="gold"),
    ])


def test_default_benchmark_has_stable_hash():
    benchmark = build_default_benchmark({
        "CSI300_ETF": 0.5,
        "NASDAQ_ETF": 0.3,
        "GOLD_ETF": 0.2,
    })

    payload = benchmark_to_dict(benchmark)

    assert payload["benchmark_id"] == "alphacore_policy_benchmark"
    assert payload["version"] == "benchmark_v1"
    assert len(payload["benchmark_hash"]) == 64
    assert payload["positions"]["CSI300_ETF"] == 0.5
    assert benchmark_to_dict(benchmark)["benchmark_hash"] == payload["benchmark_hash"]


def test_active_risk_snapshot_calculates_active_weights_and_tracking_error():
    benchmark = build_default_benchmark({
        "CSI300_ETF": 0.5,
        "NASDAQ_ETF": 0.3,
        "GOLD_ETF": 0.2,
    })

    active = build_active_risk_snapshot(_portfolio(), benchmark)

    assert active["active_weights"]["CSI300_ETF"] == -0.166667
    assert active["active_weights"]["NASDAQ_ETF"] == 0.033333
    assert active["active_weights"]["GOLD_ETF"] == 0.133333
    assert active["tracking_error_proxy_pct"] == 21.6025
    assert active["largest_active_exposures"][0]["symbol"] == "CSI300_ETF"
    assert active["largest_active_exposures"][0]["active_weight"] == -0.166667


def test_active_risk_reports_missing_benchmark_weight():
    benchmark = build_default_benchmark({"CSI300_ETF": 1.0})

    active = build_active_risk_snapshot(_portfolio(), benchmark)

    assert active["active_weights"]["NASDAQ_ETF"] == 0.333333
    assert active["active_weights"]["GOLD_ETF"] == 0.333333
    assert "NASDAQ_ETF" in active["unbenchmarked_symbols"]
    assert "GOLD_ETF" in active["unbenchmarked_symbols"]
