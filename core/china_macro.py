"""
China macro indicator dashboard.
Data source: Tushare (cn_cpi, cn_pmi, cn_m, cn_gdp).

Tushare API field reference:
  cn_cpi  → start_m/end_m, fields: month, cpi_yoy
  cn_pmi  → start_m/end_m, fields: month, pmi
  cn_m    → start_m/end_m, fields: month, m2 (absolute) → compute YoY
  cn_gdp  → start_q/end_q, fields: quarter, gdp_yoy
"""

import datetime
import time
import pandas as pd
from core.data_providers import _tushare_items

# stale-cache: if API fails, serve last successful result
_last_success: dict = {"data": None, "ts": 0, "errors": 0}

def get_china_macro(months: int = 24) -> dict:
    end = datetime.date.today()
    result = {}

    # ── CPI (YoY %) ────────────────────────────────────────
    try:
        items = _tushare_items("cn_cpi", params={
            "start_m": (end - datetime.timedelta(days=months*33)).strftime("%Y%m"),
            "end_m": end.strftime("%Y%m"),
        }, fields="month,cpi_yoy")
        if items:
            df = pd.DataFrame(items)
            # auto-detect column: date col is first, value col is last numeric
            date_col = df.columns[0]
            val_col = next((c for c in df.columns[1:] if df[c].astype(str).str.replace('.','',1).str.isdigit().all()), df.columns[-1])
            df[date_col] = df[date_col].astype(str)
            df = df.sort_values(date_col)
            vals = pd.to_numeric(df[val_col], errors='coerce').dropna().tolist()
            dates = df[date_col].tolist()
            cur = vals[-1] if vals else 0
            prev = vals[-2] if len(vals) > 1 else cur
            result["cpi"] = {
                "dates": dates, "values": vals,
                "current": round(cur, 2),
                "change": round(cur - prev, 2),
                "signal": "通缩" if cur < 0 else ("温和" if cur < 2 else "通胀压力"),
                "color": "#4ade80" if 0 <= cur <= 2 else ("#fbbf24" if cur < 3 else "#ef4444"),
            }
    except Exception as e:
        print(f"[china_macro] CPI failed: {e}")

    # ── PMI (Manufacturing) ────────────────────────────────
    try:
        items = _tushare_items("cn_pmi", params={
            "start_m": (end - datetime.timedelta(days=months*33)).strftime("%Y%m"),
            "end_m": end.strftime("%Y%m"),
        }, fields="month,pmi")
        if items:
            df = pd.DataFrame(items)
            date_col = df.columns[0]
            val_col = next((c for c in df.columns[1:] if df[c].astype(str).str.replace('.','',1).str.isdigit().all()), df.columns[-1])
            df[date_col] = df[date_col].astype(str)
            df = df.sort_values(date_col)
            vals = pd.to_numeric(df[val_col], errors='coerce').dropna().tolist()
            dates = df[date_col].tolist()
            cur = vals[-1] if vals else 50
            result["pmi"] = {
                "dates": dates, "values": vals,
                "current": round(cur, 1),
                "signal": "扩张" if cur >= 50 else "收缩",
                "color": "#4ade80" if cur >= 50 else "#ef4444",
            }
    except Exception as e:
        print(f"[china_macro] PMI failed: {e}")

    # ── M2 YoY ─────────────────────────────────────────────
    try:
        items = _tushare_items("cn_m", params={
            "start_m": (end - datetime.timedelta(days=(months+12)*33)).strftime("%Y%m"),
            "end_m": end.strftime("%Y%m"),
        }, fields="month,m2")
        if items:
            df = pd.DataFrame(items)
            if df.shape[1] >= 2:
                df = df.iloc[:, :2]
                df.columns = ["month", "m2"]
            df = df.sort_values("month")
            raw = df["m2"].astype(float)
            yoy = raw.pct_change(12, fill_method=None).dropna() * 100
            dates = df["month"].iloc[12:].tolist()
            vals = yoy.round(1).tolist()
            cur = vals[-1] if vals else 0
            result["m2"] = {
                "dates": dates, "values": vals,
                "current": round(cur, 1),
                "signal": "宽松" if cur > 10 else ("中性" if cur > 8 else "偏紧"),
                "color": "#4ade80" if cur > 9 else ("#fbbf24" if cur > 7 else "#ef4444"),
            }
    except Exception as e:
        print(f"[china_macro] M2 failed: {e}")

    # ── GDP YoY ────────────────────────────────────────────
    try:
        items = _tushare_items("cn_gdp", params={
            "start_q": (end - datetime.timedelta(days=months*5*33)).strftime("%YQ1"),
            "end_q": end.strftime("%YQ4"),
        }, fields="quarter,gdp_yoy")
        if items:
            df = pd.DataFrame(items)
            if df.shape[1] >= 2:
                df = df.iloc[:, :2]
                df.columns = ["quarter", "gdp"]
            df = df.sort_values("quarter")
            vals = df["gdp"].astype(float).tolist()
            dates = df["quarter"].tolist()
            cur = vals[-1] if vals else 0
            result["gdp"] = {
                "dates": dates, "values": vals,
                "current": round(cur, 1),
                "signal": "稳健" if cur > 5 else ("放缓" if cur > 3 else "低迷"),
                "color": "#4ade80" if cur >= 5 else ("#fbbf24" if cur >= 3 else "#ef4444"),
            }
    except Exception as e:
        print(f"[china_macro] GDP failed: {e}")

    result["updated"] = end.strftime("%Y-%m-%d")

    # ── stale cache ──────────────────────────────────────────
    if len(result) >= 2:  # at least 2 indicators succeeded
        _last_success["data"] = result
        _last_success["ts"] = time.time()
        _last_success["errors"] = 0
        return result
    _last_success["errors"] = _last_success.get("errors", 0) + 1
    if _last_success["data"] is not None:
        stale = dict(_last_success["data"])
        stale["updated"] = f'{end.strftime("%Y-%m-%d")} (stale, {_last_success["errors"]} failures)'
        return stale
    return result
