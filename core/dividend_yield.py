"""
Dividend Yield Dashboard — top dividend-paying stocks and ETFs.
Data: Tushare daily_basic (dividend_yield field, 5000+ points).

Shows top 10 A-share stocks with highest dividend yield.
"""

import datetime
from core.data_providers import _tushare_items


def get_dividend_leaders(limit: int = 10) -> dict:
    end = datetime.date.today()

    try:
        # First, find the last open trading date
        start = end - datetime.timedelta(days=15)
        cal = _tushare_items('trade_cal', {
            'start_date': start.strftime("%Y%m%d"),
            'end_date': end.strftime("%Y%m%d"),
            'is_open': '1',
            'exchange': 'SSE'
        }, 'cal_date')
        
        items = []
        last_trade_date = end.strftime("%Y%m%d")
        if cal:
            # cal is typically sorted descending in Tushare if fetched correctly, 
            # or ascending. Let's sort descending just to be safe.
            dates = sorted([r[0] for r in cal], reverse=True)
            for d in dates:
                last_trade_date = d
                items = _tushare_items("daily_basic", {
                    "trade_date": last_trade_date,
                }, "ts_code,dv_ratio,pe,pb,total_mv")
                if items:
                    break
    except Exception:
        items = []
        last_trade_date = end.strftime("%Y%m%d")

    if not items:
        return {"stocks": [], "insight": "股息率数据暂不可用", "updated": last_trade_date}

    rows = []
    for item in items:
        try:
            div_yield = float(item[1] or 0)
            if div_yield <= 0 or div_yield > 20:
                continue
            pe = round(float(item[2] or 0), 1)
            pb = round(float(item[3] or 0), 1)
            mv = round(float(item[4] or 0) / 10000, 1)  # 万元→亿元

            # Institutional Quality Filters (Anti Value-Trap)
            if pe <= 0 or pe > 30: # Exclude loss-making or overvalued
                continue
            if pb <= 0: # Exclude negative equity
                continue
            if mv < 100: # Exclude micro-caps (<10B RMB)
                continue

            rows.append({
                "code": item[0], "div_yield": round(div_yield, 2),
                "pe": pe, "pb": pb, "mv": mv,
            })
        except (IndexError, ValueError):
            continue

    # Fetch stock names mapping
    name_map = {}
    try:
        basic_items = _tushare_items('stock_basic', {'list_status': 'L'}, 'ts_code,name')
        name_map = {row[0]: row[1] for row in basic_items if row and len(row) >= 2}
    except Exception:
        pass

    for r in rows:
        r["name"] = name_map.get(r["code"], r["code"])

    rows.sort(key=lambda x: x["div_yield"], reverse=True)
    top = rows[:limit]

    avg_yield = round(sum(r["div_yield"] for r in top) / max(len(top), 1), 2)
    return {
        "stocks": top,
        "count": len(top),
        "avg_yield": avg_yield,
        "insight": f"Top {len(top)} 股息率均值 {avg_yield}% · 最高 {top[0]['div_yield']}% ({top[0]['code']})" if top else "数据获取中",
        "updated": end.strftime("%Y-%m-%d"),
    }
