"""
Fed Rate Monitor — CME FedWatch style probability dashboard.
Displays current Fed Funds rate range, historical path, and
market-implied rate direction from the 2Y Treasury yield.

Data sources: FRED DFEDTARU (upper), DFEDTARL (lower), DGS2 (2Y).
"""

import datetime
import time
import pandas as pd
import numpy as np
from core.data_providers import _fred_series

_last_success: dict = {"data": None, "ts": 0, "errors": 0}

# approximate FOMC meeting dates for 2026 (updated annually)
FOMC_2026 = [
    "2026-01-28", "2026-03-18", "2026-05-06",
    "2026-06-17", "2026-07-29", "2026-09-16",
    "2026-11-05", "2026-12-16",
]


def get_fed_probability() -> dict:
    """Return Fed rate data + implied direction.

    Returns:
        dict with:
          - current_rate: {upper, lower, mid}
          - rate_path: [{date, rate_mid}] — last 3 years
          - fomc_schedule: upcoming meeting dates
          - direction: "easing" | "tightening" | "holding"
          - insight: str
    """
    now = datetime.date.today()

    # 1. Current rate range
    try:
        upper = _fred_series("DFEDTARU", limit=5)
        lower = _fred_series("DFEDTARL", limit=5)
        cur_upper = float(upper.iloc[-1]) if len(upper) > 0 else 5.25
        cur_lower = float(lower.iloc[-1]) if len(lower) > 0 else 5.00
    except Exception:
        cur_upper, cur_lower = 5.50, 5.25

    # 2. Rate path (last 3 years)
    rate_path = []
    try:
        s_mid = _fred_series("DFEDTAR", limit=252 * 3)
        for d, v in s_mid.items():
            rate_path.append({"date": d.strftime("%Y-%m-%d"), "rate": round(float(v), 2)})
    except Exception:
        rate_path = []

    # 3. 2Y Treasury vs Fed Funds — market direction signal
    direction = "holding"
    signal = "中性"
    try:
        s2 = _fred_series("DGS2", limit=5)
        y2 = float(s2.iloc[-1]) if len(s2) > 0 else 4.0
        spread = y2 - ((cur_upper + cur_lower) / 2)
        if spread < -0.75:
            direction, signal = "easing", "降息预期 (市场定价宽松)"
        elif spread < -0.25:
            direction, signal = "easing_bias", "温和降息预期"
        elif spread > 0.50:
            direction, signal = "tightening", "加息预期 (市场定价紧缩)"
        elif spread > 0.15:
            direction, signal = "tightening_bias", "温和加息预期"
        else:
            direction, signal = "holding", "按兵不动 (市场定价中性)"
    except Exception:
        spread = 0.0

    # 4. Upcoming FOMC dates
    upcoming = [d for d in FOMC_2026 if d > now.strftime("%Y-%m-%d")]

    insight = (
        f"当前联邦基金利率 {cur_lower}%-{cur_upper}% | "
        f"2Y国债 {spread:+.1f}bp vs 基准 → {signal} | "
        f"下次FOMC: {upcoming[0] if upcoming else '待公布'}"
    )

    result = {
        "current_rate": {"upper": cur_upper, "lower": cur_lower, "mid": round((cur_upper + cur_lower) / 2, 2)},
        "spread_2y": round(spread, 2),
        "direction": direction,
        "signal": signal,
        "rate_path": rate_path[-252:],
        "fomc_upcoming": upcoming[:4],
        "insight": insight,
        "updated": now.strftime("%Y-%m-%d"),
    }

    # ── stale cache ──────────────────────────────────────────
    if len(rate_path) >= 100:
        _last_success["data"] = result
        _last_success["ts"] = time.time()
        _last_success["errors"] = 0
        return result
    _last_success["errors"] = _last_success.get("errors", 0) + 1
    if _last_success["data"] is not None:
        stale = dict(_last_success["data"])
        stale["updated"] = f'{now.strftime("%Y-%m-%d")} (stale)'
        return stale
    return result
