"""
Global Cross-Asset Dashboard — Bloomberg MOST-style single-view table.
Tracks 14 major global assets with D/W/M/Q/YTD returns.
Data: Tushare QDII ETFs + existing data providers.
"""

import datetime
import pandas as pd
from core.data_providers import get_us_etf_history, _tushare_items, _ts_items_to_series


# Asset definitions: (label, ticker, category, api, ts_code)
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


def get_global_assets() -> dict:
    """Return multi-horizon returns for all tracked global assets.

    Returns:
        dict with:
          - assets: [{name, cat, daily, weekly, monthly, quarterly, ytd}]
          - updated: str
    """
    end = datetime.date.today()
    start = end - datetime.timedelta(days=280)
    rows = []

    for name, ticker, cat, api, code in ASSETS:
        try:
            if api == "fred":
                from core.data_providers import _fred_series
                s = _fred_series(code, limit=260)
                s.name = ticker
            else:
                items = _tushare_items(api, {
                    "ts_code": code,
                    "start_date": start.strftime("%Y%m%d"),
                    "end_date": end.strftime("%Y%m%d"),
                }, "trade_date,close" if "index" in api else "trade_date,close")
                s = _ts_items_to_series(items, date_col=0, val_col=1, name=ticker)
                if api == "fx_daily":
                    items2 = _tushare_items(api, {
                        "ts_code": code,
                        "start_date": start.strftime("%Y%m%d"),
                        "end_date": end.strftime("%Y%m%d"),
                    }, "trade_date,bid_close")
                    s = _ts_items_to_series(items2, date_col=0, val_col=1, name=ticker)

            if s.empty or len(s) < 5:
                continue

            vals = s.values
            last = float(vals[-1])
            day = round((last / float(vals[-2]) - 1) * 100, 2) if len(vals) >= 2 else 0
            week = round((last / float(vals[-5]) - 1) * 100, 2) if len(vals) >= 5 else 0
            month = round((last / float(vals[-21]) - 1) * 100, 2) if len(vals) >= 21 else 0
            quarter = round((last / float(vals[-63]) - 1) * 100, 2) if len(vals) >= 63 else 0
            ytd_slice = [v for d, v in zip(s.index, vals) if d.year == end.year]
            ytd = round((last / float(ytd_slice[0]) - 1) * 100, 2) if ytd_slice else 0

            rows.append({
                "name": name, "cat": cat,
                "daily": day, "weekly": week, "monthly": month,
                "quarterly": quarter, "ytd": ytd,
            })
        except Exception as e:
            print(f"[global_assets] skip {name}: {e}")

    return {
        "assets": rows,
        "updated": end.strftime("%Y-%m-%d"),
    }
