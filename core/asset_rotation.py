"""Theme and ETF rotation panels backed by shared market snapshots."""

from core.data_providers import get_multi_asset_snapshot


THEME_SECTORS = {
    "801081.SI": "半导体",
    "801101.SI": "计算机设备",
    "801742.SI": "航空装备",
    "801056.SI": "能源金属",
    "801152.SI": "生物制品",
    "801078.SI": "自动化设备",
    "801738.SI": "电网设备",
    "801223.SI": "通信服务",
}

DOMESTIC_ETFS = {
    "510300.SH": "沪深300ETF",
    "510500.SH": "中证500ETF",
    "512100.SH": "中证1000ETF",
    "510050.SH": "上证50ETF",
    "588000.SH": "科创50ETF",
    "159915.SZ": "创业板ETF",
}

GLOBAL_ETFS = {
    "513500.SH": "标普500ETF",
    "513100.SH": "纳指100ETF",
    "513520.SH": "日经225ETF",
    "513050.SH": "中概互联ETF",
    "510900.SH": "H股ETF",
    "513180.SH": "恒生科技ETF",
}


def _rotation_stance(breadth: int) -> str:
    if breadth >= 65:
        return "扩散偏强"
    if breadth <= 35:
        return "防御收缩"
    return "结构分化"


def _build_rotation_response(api_name: str, codes: dict, benchmark: str, label: str) -> dict:
    rows = get_multi_asset_snapshot(api_name, codes, benchmark)
    if not rows:
        return {"error": "No data available"}

    rows.sort(key=lambda row: row["ret_20d"], reverse=True)
    best = [row["name"] for row in rows[:3]]
    worst = [row["name"] for row in rows[-3:]]
    positives = sum(1 for row in rows if row.get("ret_20d", 0) > 0)
    breadth = int(positives / max(len(rows), 1) * 100)
    return {
        "sectors": rows,
        "insight": (
            f"近20日强势：{', '.join(best)}；弱势：{', '.join(worst)}。"
            f"{label}扩散度{breadth}%，当前状态：{_rotation_stance(breadth)}。"
        ),
    }


def get_theme_rotation() -> dict:
    return _build_rotation_response("sw_daily", THEME_SECTORS, "801081.SI", "政策主题")


def get_domestic_etf_rotation() -> dict:
    return _build_rotation_response("fund_daily", DOMESTIC_ETFS, "510300.SH", "境内ETF")


def get_global_etf_rotation() -> dict:
    return _build_rotation_response("fund_daily", GLOBAL_ETFS, "513500.SH", "全球ETF")
