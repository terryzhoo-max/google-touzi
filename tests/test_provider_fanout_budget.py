import datetime

import pandas as pd


def _history(name: str, periods: int = 90) -> pd.Series:
    end = pd.Timestamp(datetime.date.today())
    idx = pd.date_range(end=end, periods=periods, freq="D")
    return pd.Series([100.0 + i for i in range(periods)], index=idx, name=name)


def test_global_assets_stays_within_provider_call_budget(monkeypatch):
    import core.global_assets as global_assets

    calls = {"tushare": [], "fred": [], "dxy": []}

    def fake_tushare_items(api_name, params, fields):
        calls["tushare"].append((api_name, params.get("ts_code"), fields))
        rows = []
        for dt, value in _history(params.get("ts_code", "asset"), periods=90).items():
            rows.append([dt.strftime("%Y%m%d"), float(value)])
        return rows

    def fake_fred(series_id, limit=60):
        calls["fred"].append((series_id, limit))
        return _history(series_id, periods=90)

    def fake_dxy(days=30):
        calls["dxy"].append(days)
        return _history("DXY", periods=90)

    monkeypatch.setattr(global_assets, "_tushare_items", fake_tushare_items)
    monkeypatch.setattr(global_assets, "_fred_raw", fake_fred)
    monkeypatch.setattr("core.data_providers.get_dxy_history", fake_dxy)
    global_assets.LAST_SUCCESS.update({"data": None, "ts": 0, "errors": 0})

    result = global_assets.get_global_assets()

    assert len(result["assets"]) == len(global_assets.ASSETS)
    assert len(calls["fred"]) == 1
    assert len(calls["dxy"]) == 1
    assert len(calls["tushare"]) == 12


def test_correlation_fetches_each_core_asset_once(monkeypatch):
    import core.quant_engine as quant_engine

    calls = {"us": [], "vix": [], "csi": []}
    quant_engine.DATA_CACHE["correlation"]["data"] = None
    quant_engine.DATA_CACHE["correlation"]["timestamp"] = 0

    def fake_us(symbol, months=6):
        calls["us"].append((symbol, months))
        return _history(symbol, periods=90)

    def fake_vix(days=30):
        calls["vix"].append(days)
        return _history("VIX", periods=90)

    def fake_csi(months=6):
        calls["csi"].append(months)
        return _history("CSI300", periods=90)

    monkeypatch.setattr(quant_engine, "get_us_etf_history", fake_us)
    monkeypatch.setattr(quant_engine, "get_vix_history", fake_vix)
    monkeypatch.setattr(quant_engine, "fetch_tushare_csi300_history", fake_csi)

    result = quant_engine.calculate_correlation_matrix()

    assert "matrix" in result
    assert calls["us"] == [("SPY", 6), ("TLT", 6), ("GLD", 6)]
    assert calls["vix"] == [130]
    assert calls["csi"] == [6]


def test_montecarlo_fetches_each_core_asset_once(monkeypatch):
    import core.quant_engine as quant_engine

    calls = {"us": [], "csi": []}

    monkeypatch.setattr(
        quant_engine,
        "calculate_asset_allocation",
        lambda: {
            "allocation": [
                {"name": "equity", "value": 60},
                {"name": "bond", "value": 30},
                {"name": "gold", "value": 10},
            ]
        },
    )

    def fake_us(symbol, months=6):
        calls["us"].append((symbol, months))
        return _history(symbol, periods=90)

    def fake_csi(months=6):
        calls["csi"].append(months)
        return _history("CSI300", periods=90)

    monkeypatch.setattr(quant_engine, "get_us_etf_history", fake_us)
    monkeypatch.setattr(quant_engine, "fetch_tushare_csi300_history", fake_csi)

    result = quant_engine.run_montecarlo_sim()

    assert "p50" in result
    assert calls["us"] == [("SPY", 6), ("TLT", 6), ("GLD", 6)]
    assert calls["csi"] == [6]
