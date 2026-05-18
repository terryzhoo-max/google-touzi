"""
Economic Surprise Index — Bloomberg/Citi CESI style.
Tracks whether China macro data is beating or missing expectations.

Method: rolling 12-month median as "expected"; Z-score = (actual - expected) / σ.
Cumulative sum of standardized surprises forms the index.

Data: Tushare cn_cpi, cn_pmi, cn_m, cn_gdp (already used in china_macro).
"""

import datetime
import pandas as pd
import numpy as np
from core.data_providers import _tushare_items


def _fetch_series(api: str, start: str, end: str, fields: str, val_col: str) -> pd.Series:
    items = _tushare_items(api, {"start_m": start, "end_m": end}, fields)
    if not items:
        return pd.Series(dtype=float)
    df = pd.DataFrame(items)
    if df.shape[1] < 2:
        return pd.Series(dtype=float)
    df = df.iloc[:, :2]
    df.columns = ["month", "val"]
    df["month"] = df["month"].astype(str)
    df["val"] = pd.to_numeric(df["val"], errors="coerce")
    df = df.dropna().sort_values("month").drop_duplicates(subset=["month"], keep="last")
    return pd.Series(df["val"].values, index=df["month"])


def get_surprise_index(months: int = 36) -> dict:
    try:
        return _build_surprise(months)
    except Exception as e:
        print(f"[surprise_index] failed: {e}")
        return {"error": str(e), "dates": [], "values": [], "current": 0, "signal": "数据不足", "color": "#94a3b8", "insight": f"计算失败: {e}"}

def _build_surprise(months: int) -> dict:
    end = datetime.date.today()
    start = end - datetime.timedelta(days=(months + 12) * 33)
    s_str = start.strftime("%Y%m")
    e_str = end.strftime("%Y%m")

    # fetch individual series
    # CPI YoY uses nt_yoy in Tushare cn_cpi
    cpi = _fetch_series("cn_cpi", s_str, e_str, "month,nt_yoy", "nt_yoy")
    
    # For PMI, Tushare often ignores fields if we specify "month,pmi", just pass "" to get all fields, then grab col 1
    pmi = _fetch_series("cn_pmi", s_str, e_str, "", "")
    
    # M2 YoY
    m2  = _fetch_series("cn_m",   s_str, e_str, "month,m2_yoy", "m2_yoy")

    # GDP needs different date format
    try:
        q_start = f"{start.year}Q{(start.month-1)//3+1}"
        q_end   = f"{end.year}Q{(end.month-1)//3+1}"
        items = _tushare_items("cn_gdp", {"start_q": q_start, "end_q": q_end}, "quarter,gdp_yoy")
        if items:
            gdf = pd.DataFrame(items)
            if gdf.shape[1] >= 2:
                gdf = gdf.iloc[:, :2]
                gdf.columns = ["quarter", "val"]
                gdf["val"] = pd.to_numeric(gdf["val"], errors="coerce")
                gdf = gdf.dropna().sort_values("quarter").drop_duplicates(subset=["quarter"], keep="last")
                gdp = pd.Series(gdf["val"].values, index=gdf["quarter"])
            else:
                gdp = pd.Series(dtype=float)
        else:
            gdp = pd.Series(dtype=float)
    except Exception as e:
        print(f"[surprise] GDP fetch failed: {e}")
        gdp = pd.Series(dtype=float)

    # For M2: compute YoY
    if len(m2) > 12:
        m2 = m2.pct_change(12).dropna() * 100

    series = {"CPI": cpi, "PMI": pmi, "M2": m2, "GDP": gdp}
    surprises = {}

    for name, s in series.items():
        if len(s) < 14:
            continue
        # rolling 12-month median as "expected"
        expected = s.rolling(12, min_periods=6).median().shift(1)
        std = s.rolling(24, min_periods=12).std()
        z = ((s - expected) / std.replace(0, 1)).fillna(0)
        surprises[name] = z

    if not surprises:
        return {"error": "No surprise data available", "index": [], "dates": []}

    # Equal-weight composite
    composite = pd.DataFrame(surprises).mean(axis=1).dropna()
    cumulative = composite.cumsum()

    dates = list(composite.index)
    values = cumulative.round(2).tolist()
    current = values[-1] if values else 0

    if current > 1.5:
        signal, color = "数据持续超预期 UPSIDE SURPRISE ↑", "#22c55e"
    elif current > 0:
        signal, color = "温和超预期 MILD UPSIDE ↗", "#4ade80"
    elif current > -1.5:
        signal, color = "温和不及预期 MILD DOWNSIDE ↘", "#fbbf24"
    else:
        signal, color = "数据持续不及预期 DOWNSIDE SURPRISE ↓", "#ef4444"

    return {
        "dates": dates[-months:],
        "values": values[-months:],
        "current": round(current, 2),
        "signal": signal,
        "color": color,
        "insight": f"经济意外指数 {current:+.1f} — {signal}",
        "updated": end.strftime("%Y-%m-%d"),
    }
