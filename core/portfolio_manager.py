"""
Portfolio Manager — import user holdings via CSV and compute analytics.
CSV format: symbol, name, quantity, cost_price (no header row)
"""

import os
import csv
import datetime
from core.data_providers import _tushare_items

HOLDINGS_FILE = os.path.join(os.path.dirname(__file__), "..", "my_portfolio.csv")


def get_holdings() -> list[dict]:
    """Read holdings from CSV. Returns list of {symbol, name, qty, cost, current, pnl}."""
    if not os.path.exists(HOLDINGS_FILE):
        return []

    rows = []
    with open(HOLDINGS_FILE, "r", encoding="utf-8") as f:
        for line in csv.reader(f):
            if len(line) < 4:
                continue
            symbol, name, qty, cost = line[0], line[1], float(line[2]), float(line[3])
            rows.append({"symbol": symbol, "name": name, "qty": qty, "cost": cost})

    # fetch current prices
    end = datetime.date.today()
    start = end - datetime.timedelta(days=10)
    for r in rows:
        try:
            items = _tushare_items("fund_daily", {
                "ts_code": r["symbol"],
                "start_date": start.strftime("%Y%m%d"),
                "end_date": end.strftime("%Y%m%d"),
            }, "trade_date,close")
            r["current"] = round(float(items[-1][1]), 3) if items else r["cost"]
        except Exception:
            r["current"] = r["cost"]
        r["pnl_pct"] = round((r["current"] / r["cost"] - 1) * 100, 2)
        r["market_value"] = round(r["current"] * r["qty"], 2)
        r["pnl_abs"] = round((r["current"] - r["cost"]) * r["qty"], 2)

    return rows


def get_portfolio_summary() -> dict:
    holdings = get_holdings()
    if not holdings:
        return {"holdings": [], "total_value": 0, "total_pnl": 0, "total_pnl_pct": 0}

    total_cost = sum(h["cost"] * h["qty"] for h in holdings)
    total_value = sum(h["market_value"] for h in holdings)
    return {
        "holdings": holdings,
        "total_value": round(total_value, 2),
        "total_cost": round(total_cost, 2),
        "total_pnl": round(total_value - total_cost, 2),
        "total_pnl_pct": round((total_value / total_cost - 1) * 100, 2) if total_cost else 0,
        "updated": datetime.date.today().strftime("%Y-%m-%d"),
    }
