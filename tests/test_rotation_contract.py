import core.asset_rotation as asset_rotation
import core.sector_rotation as sector_rotation


def test_sector_rotation_uses_readable_chinese_names_and_insight(monkeypatch):
    rows = [
        {"code": "801080.SI", "name": "电子", "ret_5d": 2.1, "ret_20d": 8.4, "ret_60d": 12.0, "last_close": 100},
        {"code": "801750.SI", "name": "计算机", "ret_5d": 1.2, "ret_20d": 5.5, "ret_60d": 7.0, "last_close": 100},
        {"code": "801780.SI", "name": "银行", "ret_5d": -0.5, "ret_20d": -3.0, "ret_60d": 1.0, "last_close": 100},
    ]
    monkeypatch.setattr(sector_rotation, "get_multi_asset_snapshot", lambda *args, **kwargs: rows)

    payload = sector_rotation.get_sector_rotation()

    assert payload["sectors"][0]["name"] == "电子"
    assert "近20日强势" in payload["insight"]
    assert "弱势" in payload["insight"]
    assert "鏃" not in str(payload)


def test_asset_rotation_uses_readable_chinese_universes_and_insight(monkeypatch):
    rows = [
        {"code": "513100.SH", "name": "纳指100ETF", "ret_5d": 3.2, "ret_20d": 10.1, "ret_60d": 18.0, "last_close": 2.2},
        {"code": "513500.SH", "name": "标普500ETF", "ret_5d": 2.0, "ret_20d": 6.5, "ret_60d": 9.0, "last_close": 2.5},
        {"code": "510900.SH", "name": "H股ETF", "ret_5d": -1.0, "ret_20d": -4.0, "ret_60d": -6.0, "last_close": 1.0},
    ]
    monkeypatch.setattr(asset_rotation, "get_multi_asset_snapshot", lambda *args, **kwargs: rows)

    payload = asset_rotation.get_global_etf_rotation()

    assert payload["sectors"][0]["name"] == "纳指100ETF"
    assert "近20日强势" in payload["insight"]
    assert "弱势" in payload["insight"]
    assert "鏃" not in str(payload)
