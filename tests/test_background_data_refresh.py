import asyncio


def test_background_refresh_invalidates_only_macro_dependent_routes(monkeypatch):
    import core.alert_rules
    import core.market_data as market_data

    calls = {"fetch": [], "invalidate": []}
    market_data.shutdown_event.clear()

    monkeypatch.setattr(market_data, "fetch_fred_10y", lambda: calls["fetch"].append("tnx"))
    monkeypatch.setattr(
        market_data,
        "fetch_macro_indicator",
        lambda ticker, key: calls["fetch"].append((ticker, key)),
    )
    monkeypatch.setattr(market_data, "fetch_tushare_csi300", lambda: calls["fetch"].append("csi300"))
    monkeypatch.setattr(market_data, "invalidate", lambda key: calls["invalidate"].append(key))
    monkeypatch.setattr(
        core.alert_rules,
        "evaluate_all_rules",
        lambda: (_ for _ in ()).throw(RuntimeError("alert engine unavailable")),
    )

    async def stop_after_first_sleep(awaitable, timeout):
        market_data.shutdown_event.set()
        return await awaitable

    monkeypatch.setattr(market_data.asyncio, "wait_for", stop_after_first_sleep)

    asyncio.run(market_data.background_data_fetcher())

    assert calls["fetch"] == [
        "tnx",
        ("^VIX", "vix"),
        ("DX-Y.NYB", "dxy"),
        "csi300",
    ]
    assert calls["invalidate"] == [
        "erp",
        "spread",
        "yield_curve",
        "decision",
        "signals",
        "allocation",
        "fed_prob",
        "global_assets_v4",
    ]
