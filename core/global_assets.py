"""
Global Cross-Asset Dashboard — Bloomberg MOST-style single-view table.
Tracks 14 major global assets with D/W/M/Q/YTD returns.
Data: Tushare QDII ETFs + FRED.  L2-cached + stale-cache resilient.
"""

import datetime
import time
import pandas as pd
from core.data_providers import _tushare_items, _ts_items_to_series, _fred_series as _fred_raw

LAST_SUCCESS: dict = {"data": None, "ts": 0, "errors": 0}


ASSETS = [
    ("S&P 500",      "SPY",     "美股",     "fund_daily", "513500.SH"),
    ("纳斯达克100",  "QQQ",     "美股",     "fund_daily", "513100.SH"),
    ("沪深300",      "CSI300",  "A股",      "index_daily", "000300.SH"),
    ("中证500",      "CSI500",  "A股",      "index_daily", "000905.SH"),
    ("创业板指",     "GEM",     "A股",      "index_daily", "399006.SZ"),
    ("恒生指数",     "HSI",     "港股",     "fund_daily", "510900.SH"),
    ("恒生科技",     "HSTECH",  "港股",     "fund_daily", "513180.SH"),
    ("日经225",      "N225",    "亚太",     "fund_daily", "513520.SH"),
    ("黄金",         "GLD",     "商品",     "fund_daily", "518880.SH"),
    ("原油",         "USO",     "商品",     "fund_daily", "159930.SZ"),
    ("美元指数",     "DXY",     "外汇",     "fx_daily",   "USDOLLAR.FXCM"),
    ("10Y美债",      "TNX",     "债券",     "fred",       "DGS10"),
    ("10Y中债",      "CN10Y",   "债券",     "fund_daily", "511260.SH"),
    ("中证红利",     "DIV",     "策略",     "fund_daily", "510880.SH"),
]


def _compute_composite_signal(rows: list[dict]) -> dict:
    """Derive composite market sentiment from the return matrix."""
    all_vals = []
    for r in rows:
        for k in ("daily","weekly","monthly","quarterly","ytd"):
            all_vals.append(r.get(k, 0))
    if not all_vals:
        return {"zone": "● 数据不足 NO DATA", "color": "#94a3b8", "pct_up": 0, "avg_ret": 0}
    pct_up = sum(1 for v in all_vals if v > 0) / len(all_vals)
    avg_ret = sum(all_vals) / len(all_vals)
    if pct_up > 0.65 and avg_ret > 1:
        return {"zone": "● 整体偏多 BULLISH", "color": "#22c55e", "pct_up": round(pct_up*100), "avg_ret": round(avg_ret,2)}
    elif pct_up > 0.45:
        return {"zone": "● 中性偏多 MILD BULL", "color": "#fbbf24", "pct_up": round(pct_up*100), "avg_ret": round(avg_ret,2)}
    elif pct_up > 0.30:
        return {"zone": "● 中性偏空 MILD BEAR", "color": "#f97316", "pct_up": round(pct_up*100), "avg_ret": round(avg_ret,2)}
    return {"zone": "● 整体偏空 BEARISH", "color": "#ef4444", "pct_up": round(pct_up*100), "avg_ret": round(avg_ret,2)}


def get_global_assets() -> dict:
    end = datetime.date.today()
    start = end - datetime.timedelta(days=280)
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from core.data_providers import get_dxy_history
    
    def fetch_asset(item):
        name, ticker, cat, api, code = item
        try:
            if api == "fred":
                s = _fred_raw(code, limit=260)
                s.name = ticker
            elif api == "fx_daily":
                s = get_dxy_history(260)
                s.name = ticker
            else:
                items = _tushare_items(api, {"ts_code": code,
                    "start_date": start.strftime("%Y%m%d"), "end_date": end.strftime("%Y%m%d")},
                    "trade_date,close")
                s = _ts_items_to_series(items, date_col=0, val_col=1, name=ticker)

            if s.empty or len(s) < 5:
                return None
            vals = s.values; last = float(vals[-1])
            ytd_vals = [v for d,v in zip(s.index,vals) if pd.to_datetime(d).year==end.year]
            return {"name": name, "cat": cat, "ticker": ticker,
                "daily":    round((last/float(vals[-2])-1)*100,2) if len(vals)>=2 else 0,
                "weekly":   round((last/float(vals[-5])-1)*100,2) if len(vals)>=5 else 0,
                "monthly":  round((last/float(vals[-21])-1)*100,2) if len(vals)>=21 else 0,
                "quarterly":round((last/float(vals[-63])-1)*100,2) if len(vals)>=63 else 0,
                "ytd":      round((last/float(ytd_vals[0])-1)*100,2) if ytd_vals else 0,
            }
        except Exception as e:
            print(f"[global_assets] skip {name}: {e}")
            return None

    rows = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_item = {executor.submit(fetch_asset, item): item for item in ASSETS}
        for future in as_completed(future_to_item):
            res = future.result()
            if res:
                rows.append(res)
    
    for res in rows:
        # Momentum Factor Score (Backtested Weights: 1Q(35%), 1M(25%), YTD(25%), 1W(10%), 1D(5%))
        res["score"] = round(
            res["daily"] * 0.05 + 
            res["weekly"] * 0.10 + 
            res["monthly"] * 0.25 + 
            res["quarterly"] * 0.35 + 
            res["ytd"] * 0.25, 2
        )

    # Compute Relative Strength (RS) Rating (1-99)
    rows.sort(key=lambda x: x["score"])
    n = len(rows)
    for i, res in enumerate(rows):
        res["rs_rating"] = max(1, int(round((i / max(n - 1, 1)) * 98)) + 1) # 1 to 99

    # Sort dynamically by momentum score descending
    rows.sort(key=lambda x: x["score"], reverse=True)

    result = {"assets": rows, "updated": end.strftime("%Y-%m-%d"),
              "composite": _compute_composite_signal(rows)}

    # stale cache
    if len(rows) >= 8:
        LAST_SUCCESS["data"] = result; LAST_SUCCESS["ts"] = time.time(); LAST_SUCCESS["errors"] = 0
        return result
    LAST_SUCCESS["errors"] = LAST_SUCCESS.get("errors",0) + 1
    if LAST_SUCCESS["data"] is not None:
        stale = dict(LAST_SUCCESS["data"])
        stale["updated"] = f'{end.strftime("%Y-%m-%d")} (stale)'
        return stale
    return result
