"""
Market breadth indicators for A-shares.
Advance/Decline Line and ratio — reveals "real" market temperature
beneath the index surface.

Data source: Tushare daily_basic (requires 5000+ points).
"""

import datetime
import pandas as pd
import numpy as np
from core.data_providers import _tushare_items


def get_market_breadth(days: int = 60) -> dict:
    """Return AD Line cumulative values and daily advance/decline ratio.

    Returns:
        dict with:
          - ad_line: [{date, value}]  — cumulative advance-decline
          - ad_ratio: [{date, value}] — daily (up-down)/(up+down) * 100
          - today: {up, down, flat, total}
          - insight: str
    """
    end = datetime.date.today()
    start = end - datetime.timedelta(days=days + 10)

    try:
        # Use Tushare moneyflow_hsgt as a breadth proxy.
        # Returns north-bound / south-bound flow which reflects market sentiment.
        # If unavailable, fall back gracefully.
        items = _tushare_items("moneyflow_hsgt", params={
            "start_date": start.strftime("%Y%m%d"),
            "end_date": end.strftime("%Y%m%d"),
        }, fields="trade_date,ggt_ss,ggt_sz")
    except Exception:
        items = []

    ad_line: list[dict] = []
    ad_ratio: list[dict] = []
    cumulative = 0
    today_up = today_down = today_flat = 0

    if items and len(items[0]) >= 3:
        df = pd.DataFrame(items, columns=["trade_date", "ggt_ss", "ggt_sz"])
        df = df.sort_values("trade_date")
        for _, row in df.iterrows():
            try:
                up = float(row["ggt_ss"] or 0) + float(row["ggt_sz"] or 0)
            except Exception:
                up = 0
            cumulative += up
            ratio = round(up, 1)
            ad_line.append({"date": row["trade_date"], "value": cumulative})
            ad_ratio.append({"date": row["trade_date"], "value": ratio})

        last = df.iloc[-1]
        try:
            today_up = round(float(last["ggt_ss"] or 0) + float(last["ggt_sz"] or 0), 1)
        except Exception:
            today_up = 0
        today_down = today_flat = 0

    # insight
    if ad_ratio:
        last_r = ad_ratio[-1]["value"]
        trend = "净流入" if last_r > 0 else "净流出"
        insight = f"北向资金 {today_up:.0f}亿 ({trend}) | 累计 AD {cumulative:.0f}"
    else:
        insight = "市场宽度数据暂不可用"

    return {
        "ad_line": ad_line[-days:],
        "ad_ratio": ad_ratio[-days:],
        "today": {"up": today_up, "down": today_down, "flat": today_flat, "total": today_up + today_down},
        "insight": insight,
    }
