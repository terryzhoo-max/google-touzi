"""
Yield Curve engine — monitors the US Treasury term structure.
Primary recession indicator: 2s10s spread (2Y vs 10Y).

Data source: FRED (DGS2, DGS5, DGS10, DGS30)
"""

import datetime
import pandas as pd
from core.data_providers import _fred_series
from core.config import settings
from core.alert_state import set_alert, clear_alert

# curve tenors we monitor
TENORS = {
    "2Y":  "DGS2",
    "5Y":  "DGS5",
    "10Y": "DGS10",
    "30Y": "DGS30",
}


def get_yield_curve(days: int = 60) -> dict:
    """Return the latest yield curve snapshot + 2s10s spread history.

    Returns:
        dict with keys:
          - snapshot: {label: yield} for today's curve
          - spread_dates: [...]
          - spread_values: [...]  (2s10s in basis points)
          - inversion_days: int   consecutive trading days inverted
          - signal_state: str
          - signal_color: str
          - insight: str
    """
    today = datetime.date.today()
    start = today - datetime.timedelta(days=days + 10)

    # 1. snapshot — latest single value per tenor
    snapshot: dict[str, float] = {}
    for label, series_id in TENORS.items():
        try:
            s = _fred_series(series_id, limit=5)
            if len(s) > 0:
                snapshot[label] = round(float(s.iloc[-1]), 2)
        except Exception as e:
            print(f"[yield_curve] FRED {series_id} failed: {e}")

    # 2. spread history — load DGS2 + DGS10 for 2s10s calculation
    spread_dates: list[str] = []
    spread_values: list[float] = []
    inversion_days = 0
    try:
        s2  = _fred_series("DGS2", limit=days)
        s10 = _fred_series("DGS10", limit=days)
        common = s2.index.intersection(s10.index)
        if len(common) > 0:
            spread_bp = ((s10[common] - s2[common]) * 100).round(1)  # basis points
            spread_dates = [d.strftime("%Y-%m-%d") for d in common]
            spread_values = spread_bp.tolist()

            # count consecutive inversion days (trading days, backward)
            for val in reversed(spread_values):
                if val < 0:
                    inversion_days += 1
                else:
                    break
    except Exception as e:
        print(f"[yield_curve] Spread history failed: {e}")

    # 3. signal
    latest_spread = spread_values[-1] if spread_values else 0.0
    if latest_spread < -50:
        signal_state = "深度倒挂 (极高衰退概率)"
        signal_color = "#ef4444"
        insight = f"🔴 2s10s利差深度倒挂 ({latest_spread:.0f}bp)，连续{inversion_days}个交易日。历史上此形态出现后6-24个月内衰退概率超过80%。防御仓位优先。"
    elif latest_spread < 0:
        signal_state = "倒挂预警 (衰退信号)"
        signal_color = "#fbbf24"
        insight = f"🟡 2s10s利差倒挂 ({latest_spread:.0f}bp)，已持续{inversion_days}个交易日。收益率曲线形态预示未来经济放缓，建议降低权益久期敞口。"
    elif latest_spread < 50:
        signal_state = "平坦化 (观察期)"
        signal_color = "#00F0FF"
        insight = f"🔵 2s10s利差收窄 ({latest_spread:.0f}bp)，曲线趋于平坦。流动性中性，建议维持当前配置但密切关注。"
    else:
        signal_state = "陡峭化 (经济扩张)"
        signal_color = "#4ade80"
        insight = f"🟢 2s10s利差健康 ({latest_spread:.0f}bp)，收益率曲线陡峭。银行信贷扩张顺畅，利好权益资产与价值股。"

    # ── alert state ──────────────────────────────────────────
    if latest_spread < 0:
        set_alert("yield_curve", "warning" if latest_spread > -50 else "danger",
                  f"2s10s 利差{ '深度' if latest_spread < -50 else '' }倒挂 {latest_spread:.0f}bp（已持续 {inversion_days} 个交易日）")
    else:
        clear_alert("yield_curve")

    return {
        "snapshot": snapshot,
        "spread_dates": spread_dates,
        "spread_values": spread_values,
        "inversion_days": inversion_days,
        "signal_state": signal_state,
        "signal_color": signal_color,
        "insight": insight,
    }
