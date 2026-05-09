"""
Valuation Thermometer — PE/PB percentile ranking for major indices.
Data: Tushare index_dailybasic or daily_basic for index-level valuation.
Shows where current valuation stands in 10-year history.

Indices: 沪深300(000300.SH), 中证500(000905.SH), 创业板指(399006.SZ)
"""

import datetime
import pandas as pd
import numpy as np
from core.data_providers import _tushare_items


INDICES = {
    "000300.SH": "沪深300",
    "000905.SH": "中证500",
    "399006.SZ": "创业板指",
}

COLORS = ["#22c55e", "#4ade80", "#a3e635", "#fbbf24", "#f97316", "#ef4444"]


def _percentile_color(pct: float) -> str:
    """Map percentile to a thermometer color."""
    if pct < 10:   return COLORS[0]
    if pct < 25:   return COLORS[1]
    if pct < 50:   return COLORS[2]
    if pct < 70:   return COLORS[3]
    if pct < 90:   return COLORS[4]
    return COLORS[5]


def _signal(pct: float) -> str:
    if pct < 10:  return "极度低估"
    if pct < 25:  return "低估"
    if pct < 50:  return "合理偏低"
    if pct < 70:  return "合理偏高"
    if pct < 90:  return "高估"
    return "泡沫区间"


def get_valuation() -> dict:
    """Return PE/PB percentile data for major A-share indices.

    Returns:
        dict with:
          - indices: [{name, pe_current, pe_pct, pe_signal, pb_current, pb_pct, pb_signal, color}]
          - insight: str
    """
    end = datetime.date.today()
    start = end - datetime.timedelta(days=365 * 10 + 30)

    result_indices = []
    for code, name in INDICES.items():
        try:
            items = _tushare_items("index_dailybasic", {
                "ts_code": code,
                "start_date": start.strftime("%Y%m%d"),
                "end_date": end.strftime("%Y%m%d"),
            }, "trade_date,pe,pb")
            if not items:
                continue

            df = pd.DataFrame(items)
            if df.shape[1] < 3:
                continue
            df = df.iloc[:, :3]
            df.columns = ["date", "pe", "pb"]
            df["pe"] = pd.to_numeric(df["pe"], errors="coerce")
            df["pb"] = pd.to_numeric(df["pb"], errors="coerce")
            df = df.dropna(subset=["pe", "pb"]).sort_values("date")

            if len(df) < 252:
                continue

            pe_cur = float(df["pe"].iloc[-1])
            pb_cur = float(df["pb"].iloc[-1])
            pe_pct = round(float((df["pe"] < pe_cur).mean()) * 100, 1)
            pb_pct = round(float((df["pb"] < pb_cur).mean()) * 100, 1)

            result_indices.append({
                "name": name,
                "pe_current": round(pe_cur, 1),
                "pe_pct": pe_pct,
                "pe_signal": _signal(pe_pct),
                "pb_current": round(pb_cur, 1),
                "pb_pct": pb_pct,
                "pb_signal": _signal(pb_pct),
                "color": _percentile_color(pe_pct),
            })
        except Exception as e:
            print(f"[valuation] skip {name}: {e}")

    if result_indices:
        high = [i["name"] for i in result_indices if i["pe_pct"] > 70]
        low = [i["name"] for i in result_indices if i["pe_pct"] < 30]
        insight = "PE 分位: " + ", ".join(f"{i['name']} {i['pe_pct']}%" for i in result_indices)
    else:
        insight = "估值数据暂不可用"

    return {
        "indices": result_indices,
        "insight": insight,
        "updated": end.strftime("%Y-%m-%d"),
    }
