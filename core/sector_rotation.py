"""
Shenwan (申万) 31-sector rotation heatmap engine.
Data source: Tushare sw_daily.  Uses shared get_multi_asset_snapshot.
"""

import pandas as pd
from core.data_providers import get_multi_asset_snapshot

SW_SECTORS = {
    "801010.SI": "农林牧渔", "801020.SI": "采掘",      "801030.SI": "化工",
    "801040.SI": "钢铁",     "801050.SI": "有色金属",   "801080.SI": "电子",
    "801110.SI": "家用电器", "801120.SI": "食品饮料",   "801130.SI": "纺织服装",
    "801140.SI": "轻工制造", "801150.SI": "医药生物",   "801160.SI": "公用事业",
    "801170.SI": "交通运输", "801180.SI": "房地产",     "801200.SI": "商贸零售",
    "801210.SI": "休闲服务", "801230.SI": "综合",       "801710.SI": "建筑材料",
    "801720.SI": "建筑装饰", "801730.SI": "电气设备",   "801740.SI": "国防军工",
    "801750.SI": "计算机",   "801760.SI": "传媒",       "801770.SI": "通信",
    "801780.SI": "银行",     "801790.SI": "非银金融",   "801880.SI": "汽车",
    "801890.SI": "机械设备",
}


def get_sector_rotation(days_back: int = 90) -> dict:
    rows = get_multi_asset_snapshot('sw_daily', SW_SECTORS, '801010.SI', days_back)
    if not rows:
        return {"error": "No sector data available"}

    df = pd.DataFrame(rows).sort_values("ret_20d", ascending=False).reset_index(drop=True)
    df["rank_20d"] = range(1, len(df) + 1)

    max_ret = max(abs(df["ret_20d"].max()), abs(df["ret_20d"].min()), 1)
    def _color(r):
        i = int(80 + 175 * min(abs(r) / max_ret, 1))
        return f"rgb(0,{i},80)" if r >= 0 else f"rgb({i},30,30)"

    sectors = []
    for _, row in df.iterrows():
        sectors.append({"name": row["name"], "ret_5d": row["ret_5d"], "ret_20d": row["ret_20d"],
                         "ret_60d": row["ret_60d"], "rank_20d": row["rank_20d"],
                         "color": _color(row["ret_20d"]), "value": abs(row["ret_20d"]) + 1})

    top3 = df.head(3)["name"].tolist()
    bot3 = df.tail(3)["name"].tolist()
    return {
        "sectors": sectors,
        "insight": f"近 20 日领涨: {', '.join(top3)} | 领跌: {', '.join(bot3)}",
        "updated": pd.Timestamp.now().strftime("%Y-%m-%d"),
    }
