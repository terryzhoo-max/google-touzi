from core.attribution_engine import build_attribution_snapshot
from core.benchmark_book import build_default_benchmark
from core.portfolio_book import Position, build_portfolio_snapshot


def _portfolio():
    return build_portfolio_snapshot([
        Position("CSI300_ETF", "CSI 300", "equity", "CNY", 600.0, region="China", strategy="broad_market"),
        Position("GOLD_ETF", "Gold", "gold", "CNY", 400.0, region="Gold", strategy="gold"),
    ])


def test_attribution_snapshot_splits_allocation_selection_currency_and_decision_effects():
    benchmark = build_default_benchmark({"CSI300_ETF": 0.5, "GOLD_ETF": 0.5})

    attribution = build_attribution_snapshot(
        _portfolio(),
        benchmark,
        period="T+5",
        asset_returns={"CSI300_ETF": 0.02, "GOLD_ETF": 0.01},
        benchmark_returns={"CSI300_ETF": 0.015, "GOLD_ETF": 0.012},
        currency_returns={"CNY": -0.001},
    )

    assert attribution["period"] == "T+5"
    assert attribution["portfolio_return"] == 0.016
    assert attribution["benchmark_return"] == 0.0135
    assert attribution["allocation_effect"] == 0.0003
    assert attribution["selection_effect"] == 0.0022
    assert attribution["currency_effect"] == -0.001
    assert attribution["decision_effect"] == 0.0025
    assert attribution["by_symbol"][0]["symbol"] == "CSI300_ETF"


def test_attribution_defaults_are_available_for_review_windows():
    attribution = build_attribution_snapshot(
        _portfolio(),
        build_default_benchmark({"CSI300_ETF": 0.5, "GOLD_ETF": 0.5}),
        period="T+1",
    )

    assert attribution["period"] == "T+1"
    assert "decision_effect" in attribution
    assert attribution["availability"]["status"] == "proxy"
