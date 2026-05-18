"""
Margin Trading Monitor — tracks A-share 融资融券 (margin/short-selling) balances.
Data: Tushare margin (requires 5000+ points).
"""

import datetime
from core.data_providers import _tushare_items


def get_margin_data(days: int = 60) -> dict:
    end = datetime.date.today()
    start = end - datetime.timedelta(days=days + 10)

    try:
        items = _tushare_items("margin", {
            "start_date": start.strftime("%Y%m%d"),
            "end_date": end.strftime("%Y%m%d"),
        }, "trade_date,rzye,rqye")
    except Exception:
        items = []

    # Group by date to sum SSE, SZSE, BSE
    daily_totals = {}
    for row in (items or []):
        try:
            dt = row[0]
            raw_rz = float(row[1] or 0)
            raw_rq = float(row[2] or 0)
            
            if dt not in daily_totals:
                daily_totals[dt] = {'rz': 0, 'rq': 0}
                
            if raw_rz > 1e8:
                daily_totals[dt]['rz'] += raw_rz / 1e8
                daily_totals[dt]['rq'] += raw_rq / 1e8
            else:
                daily_totals[dt]['rz'] += raw_rz / 10000
                daily_totals[dt]['rq'] += raw_rq / 10000
        except (IndexError, ValueError):
            continue

    sorted_dates = sorted(daily_totals.keys())[-days:]
    dates, rz_balance, rq_balance = [], [], []
    for dt in sorted_dates:
        dates.append(dt)
        rz_balance.append(round(daily_totals[dt]['rz'], 2))
        rq_balance.append(round(daily_totals[dt]['rq'], 2))

    cur_rz = rz_balance[-1] if rz_balance else 0
    cur_rq = rq_balance[-1] if rq_balance else 0
    total = round(cur_rz + cur_rq, 0)
    ratio = round(cur_rq / max(cur_rz, 1) * 100, 1)

    if rz_balance and len(rz_balance) > 5:
        trend_rz = rz_balance[-1] - rz_balance[-5]
        trend_signal = "融资加杠杆 MARGIN EXPANSION" if trend_rz > 200 else ("融资降杠杆 DELEVERAGING" if trend_rz < -200 else "持平 FLAT")
    else:
        trend_signal = "--"

    if "加杠杆" in trend_signal:
        zone, zone_color = "● 市场偏多 BULLISH", "#22c55e"
    elif "降杠杆" in trend_signal:
        zone, zone_color = "● 市场偏空 BEARISH", "#ef4444"
    else:
        zone, zone_color = "● 中性 NEUTRAL", "#fbbf24"

    return {
        "dates": dates, "rz_balance": rz_balance, "rq_balance": rq_balance,
        "current_rz": cur_rz, "current_rq": cur_rq, "total": total, "ratio": ratio,
        "trend": trend_signal, "zone": zone, "zone_color": zone_color,
        "insight": f"两融余额 {total:.0f}亿 · 融资 {cur_rz:.0f}亿 · 融券 {cur_rq:.0f}亿 · 券资比 {ratio}% · {trend_signal}",
        "updated": end.strftime("%Y-%m-%d"),
    }
