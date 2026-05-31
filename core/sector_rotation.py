"""
Shenwan sector rotation panel.

The endpoint is used by the institutional dashboard, so the payload keeps
display-ready Chinese names and a concise allocation-oriented insight.
"""

import pandas as pd

from core.data_providers import get_multi_asset_snapshot


SW_SECTORS = {
    "801010.SI": "农林牧渔",
    "801020.SI": "采掘",
    "801030.SI": "基础化工",
    "801040.SI": "钢铁",
    "801050.SI": "有色金属",
    "801080.SI": "电子",
    "801110.SI": "家用电器",
    "801120.SI": "食品饮料",
    "801130.SI": "纺织服饰",
    "801140.SI": "轻工制造",
    "801150.SI": "医药生物",
    "801160.SI": "公用事业",
    "801170.SI": "交通运输",
    "801180.SI": "房地产",
    "801200.SI": "商贸零售",
    "801210.SI": "社会服务",
    "801230.SI": "综合",
    "801710.SI": "建筑材料",
    "801720.SI": "建筑装饰",
    "801730.SI": "电力设备",
    "801740.SI": "国防军工",
    "801750.SI": "计算机",
    "801760.SI": "传媒",
    "801770.SI": "通信",
    "801780.SI": "银行",
    "801790.SI": "非银金融",
    "801880.SI": "汽车",
    "801890.SI": "机械设备",
}


def _rotation_stance(breadth: int) -> str:
    if breadth >= 65:
        return "扩散偏强"
    if breadth <= 35:
        return "防御收缩"
    return "结构分化"


def get_sector_rotation(days_back: int = 90) -> dict:
    rows = get_multi_asset_snapshot("sw_daily", SW_SECTORS, "801010.SI", days_back)
    if not rows:
        return {"error": "No sector data available"}

    df = pd.DataFrame(rows).sort_values("ret_20d", ascending=False).reset_index(drop=True)
    df["rank_20d"] = range(1, len(df) + 1)

    max_ret = max(abs(df["ret_20d"].max()), abs(df["ret_20d"].min()), 1)

    def _color(ret_20d: float) -> str:
        intensity = int(80 + 175 * min(abs(ret_20d) / max_ret, 1))
        return f"rgb(0,{intensity},80)" if ret_20d >= 0 else f"rgb({intensity},30,30)"

    sectors = []
    for _, row in df.iterrows():
        ret_20d = float(row["ret_20d"])
        sectors.append(
            {
                "name": row["name"],
                "ret_5d": float(row["ret_5d"]),
                "ret_20d": ret_20d,
                "ret_60d": float(row["ret_60d"]),
                "rank_20d": int(row["rank_20d"]),
                "color": _color(ret_20d),
                "value": abs(ret_20d) + 1,
            }
        )

    top3 = df.head(3)["name"].tolist()
    bottom3 = df.tail(3)["name"].tolist()
    breadth = int((df["ret_20d"] > 0).mean() * 100)
    return {
        "sectors": sectors,
        "insight": (
            f"近20日强势：{', '.join(top3)}；弱势：{', '.join(bottom3)}。"
            f"行业扩散度{breadth}%，当前状态：{_rotation_stance(breadth)}。"
        ),
        "updated": pd.Timestamp.now().strftime("%Y-%m-%d"),
    }
