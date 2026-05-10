"""
North-bound capital flow monitor for A-shares.

Public payload unit is always CNY 100mn ("yi yuan", 亿元).
"""

import datetime

import pandas as pd

from core.data_providers import _tushare_items


def _normalize_hsgt_flow_to_100mn(value: float) -> float:
    """Normalize HSGT flow values to CNY 100mn.

    Official Tushare moneyflow_hsgt fields north_money/hgt/sgt are
    documented as CNY million, so the normal conversion is value / 100.

    In practice, stale/proxy/cached rows may arrive in CNY 10k units and
    appear roughly 100x larger. Daily north-bound flow above CNY 1000bn is
    not a credible normal observation, so values above 100000 are treated
    as CNY 10k and converted with value / 10000.
    """
    if abs(value) > 100000:
        return round(value / 10000, 2)
    return round(value / 100, 2)


def get_market_breadth(days: int = 60) -> dict:
    """Return north-bound daily net flow and cumulative flow.

    Compatibility aliases ad_line/ad_ratio are retained for older frontend
    contracts, but they should not be interpreted as market breadth counts.
    """
    end = datetime.date.today()
    start = end - datetime.timedelta(days=days + 10)

    try:
        items = _tushare_items(
            "moneyflow_hsgt",
            params={
                "start_date": start.strftime("%Y%m%d"),
                "end_date": end.strftime("%Y%m%d"),
            },
            fields="trade_date,north_money,hgt,sgt",
        )
    except Exception:
        items = []

    cumulative_series: list[dict] = []
    flow_series: list[dict] = []
    cumulative = 0.0
    current_flow = 0.0
    flow_5d = 0.0
    flow_20d = 0.0

    if items and len(items[0]) >= 2:
        cols = ["trade_date", "north_money", "hgt", "sgt"][: len(items[0])]
        df = pd.DataFrame(items, columns=cols).sort_values("trade_date")

        flows: list[float] = []
        for _, row in df.iterrows():
            try:
                if "north_money" in row and pd.notna(row["north_money"]):
                    raw_flow = float(row["north_money"] or 0)
                else:
                    raw_flow = float(row.get("hgt", 0) or 0) + float(row.get("sgt", 0) or 0)
            except Exception:
                raw_flow = 0.0

            flow = _normalize_hsgt_flow_to_100mn(raw_flow)
            cumulative = round(cumulative + flow, 2)
            flows.append(flow)
            flow_series.append({"date": row["trade_date"], "value": flow})
            cumulative_series.append({"date": row["trade_date"], "value": cumulative})

        if flows:
            current_flow = flows[-1]
            flow_5d = round(sum(flows[-5:]), 2)
            flow_20d = round(sum(flows[-20:]), 2)

    if flow_series:
        trend = "净流入" if current_flow > 0 else ("净流出" if current_flow < 0 else "持平")
        if flow_20d > 0 and flow_5d > 0:
            signal = "外资持续流入"
        elif flow_20d < 0 and flow_5d < 0:
            signal = "外资持续流出"
        else:
            signal = "短期分歧"
        insight = (
            f"北向资金 {current_flow:.1f}亿 ({trend}) | "
            f"5日 {flow_5d:.1f}亿 | 20日 {flow_20d:.1f}亿"
        )
    else:
        signal = "数据不可用"
        insight = "北向资金数据暂不可用"

    return {
        "flow": flow_series[-days:],
        "cumulative": cumulative_series[-days:],
        "ad_line": cumulative_series[-days:],
        "ad_ratio": flow_series[-days:],
        "today": {
            "current_flow": current_flow,
            "flow_5d": flow_5d,
            "flow_20d": flow_20d,
            "cumulative": cumulative,
            "up": current_flow,
            "down": 0,
            "flat": 0,
            "total": current_flow,
        },
        "signal": signal,
        "insight": insight,
        "unit": "CNY 100mn",
        "updated": end.strftime("%Y-%m-%d"),
    }
