"""
Theme + ETF rotation panels — thematic sectors, domestic A-share ETFs,
and global cross-border ETFs.  All use shared get_multi_asset_snapshot.
"""

from core.data_providers import get_multi_asset_snapshot

THEME_SECTORS = {
    "801081.SI": "半导体",
    "801101.SI": "计算机设备",
    "801742.SI": "航空装备",
    "801056.SI": "能源金属",
    "801152.SI": "生物制品",
    "801078.SI": "自动化设备",
    "801738.SI": "电网设备",
    "801223.SI": "通信服务"
}

DOMESTIC_ETFS = {
    "510300.SH": "沪深300 ETF",
    "510500.SH": "中证500 ETF",
    "512100.SH": "中证1000 ETF",
    "510050.SH": "上证50 ETF",
    "588000.SH": "科创50 ETF",
    "159915.SZ": "创业板 ETF"
}

GLOBAL_ETFS = {
    "513500.SH": "标普500 ETF",
    "513100.SH": "纳指100 ETF",
    "513520.SH": "日经225 ETF",
    "513050.SH": "中概互联 ETF",
    "510900.SH": "H股 ETF",
    "513180.SH": "恒生科技 ETF"
}


def _build_rotation_response(api_name: str, codes: dict, benchmark: str) -> dict:
    rows = get_multi_asset_snapshot(api_name, codes, benchmark)
    if not rows:
        return {"error": "No data available"}
    rows.sort(key=lambda r: r["ret_20d"], reverse=True)
    best = [r["name"] for r in rows[:3]]
    worst = [r["name"] for r in rows[-3:]]
    return {
        "sectors": rows,
        "insight": f"近 20 日领涨: {', '.join(best)} | 领跌: {', '.join(worst)}",
    }


def get_theme_rotation() -> dict:
    return _build_rotation_response('sw_daily', THEME_SECTORS, '801081.SI')

def get_domestic_etf_rotation() -> dict:
    return _build_rotation_response('fund_daily', DOMESTIC_ETFS, '510300.SH')

def get_global_etf_rotation() -> dict:
    return _build_rotation_response('fund_daily', GLOBAL_ETFS, '513500.SH')
