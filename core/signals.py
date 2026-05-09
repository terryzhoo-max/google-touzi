"""
Multi-timeframe signal engine.
Computes Z-Scores for VIX and TNX across short/medium/long windows.
"""

import numpy as np
from core.market_data import DATA_CACHE
from core.data_providers import get_vix_history, get_tnx_history
from core.config import settings


def _zscore(series: np.ndarray, window: int) -> float:
    """Rolling Z-Score: (last - mean) / std over `window` observations."""
    if len(series) < window:
        return 0.0
    chunk = series[-window:]
    mu = chunk.mean()
    sigma = chunk.std()
    if sigma == 0:
        return 0.0
    return float((chunk[-1] - mu) / sigma)


def get_multi_timeframe_signals() -> dict:
    """Return a 2×3 signal matrix.

    Rows: TNX (rate direction), VIX (volatility direction)
    Columns: short (20D), medium (60D), long (252D)

    Returns:
        { "tnx": [{window, zscore, label, color}, ...],
          "vix": [{...}, ...] }
    """
    windows = [
        (20,  "短期(月)"),
        (60,  "中期(季)"),
        (252, "长期(年)"),
    ]

    # fetch enough data for the longest window
    try:
        vix_raw = get_vix_history(days=300)
        tnx_raw = get_tnx_history(days=300)
    except Exception:
        return {"error": "Signal data unavailable"}

    result: dict[str, list] = {"tnx": [], "vix": []}

    for idx_series, key, thresh_high in [
        (tnx_raw, "tnx", 1.5),
        (vix_raw, "vix", 1.5),
    ]:
        if idx_series.empty:
            continue
        vals = idx_series.values
        for w, label in windows:
            z = _zscore(vals, w)
            if z > thresh_high:
                color = "#ef4444"
                signal = "⚠ 高位"
            elif z > 0.5:
                color = "#fbbf24"
                signal = "↗ 偏高"
            elif z < -thresh_high:
                color = "#4ade80"
                signal = "✅ 低位"
            elif z < -0.5:
                color = "#00F0FF"
                signal = "↘ 偏低"
            else:
                color = "#94a3b8"
                signal = "— 中性"

            result[key].append({
                "window": w,
                "label": label,
                "zscore": round(z, 2),
                "signal": signal,
                "color": color,
            })

    return result
