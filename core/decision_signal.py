"""
Institutional composite decision-signal engine.

Aggregates 7 macro factors into a single 0-100 score mapped to
STRONG_SELL / SELL / NEUTRAL / BUY / STRONG_BUY.

Factors:
  1. VIX  regime    → 20%
  2. TNX  direction  → 15%
  3. Yield-curve     → 15%
  4. Correlation     → 15%
  5. Current regime  → 15%
  6. China macro     → 10%   (CPI/PMI/M2/GDP composite)
  7. Valuation       → 10%   (PE percentile inverse)
"""

from core.alert_state import get_active_alerts

SIGNAL_BANDS = [
    (0,   20,  "强烈卖出 STRONG SELL", "STRONG_SELL", "#ef4444"),
    (20,  40,  "卖出 SELL",      "SELL",       "#f97316"),
    (40,  60,  "中性 NEUTRAL",      "NEUTRAL",    "#fbbf24"),
    (60,  80,  "买入 BUY",      "BUY",        "#4ade80"),
    (80,  101, "强烈买入 STRONG BUY",  "STRONG_BUY", "#22c55e"),
]


def _score_vix(vix_val: float) -> tuple:
    if vix_val > 30:
        return 0,  f"VIX {vix_val:.1f} — 极度恐慌"
    if vix_val > 25:
        return 15, f"VIX {vix_val:.1f} — 高波动警戒"
    if vix_val > 20:
        return 35, f"VIX {vix_val:.1f} — 恐慌上行"
    if vix_val > 15:
        return 65, f"VIX {vix_val:.1f} — 舒适区间"
    if vix_val > 12:
        return 85, f"VIX {vix_val:.1f} — 低波动安全区"
    return 100, f"VIX {vix_val:.1f} — 极低波动"


def _score_tnx(tnx_val: float, fr_data: dict = None) -> tuple:
    """Rate level + directional trend."""
    if tnx_val <= 0:
        return 50, "TNX 数据缺失"
    base = 50
    if tnx_val > 5.0:
        base = 5
    elif tnx_val > 4.5:
        base = 15
    elif tnx_val > 4.0:
        base = 35
    elif tnx_val > 3.5:
        base = 60
    elif tnx_val > 3.0:
        base = 80
    else:
        base = 95

    # trend bonus from TNX data
    trend = ""
    if fr_data and isinstance(fr_data, dict):
        vals = fr_data.get("data", [])
        if isinstance(vals, list) and len(vals) >= 5:
            recent = vals[-1]
            older  = vals[-5]
            if recent < older:
                base = min(100, base + 10)
                trend = " ↓下行"
            elif recent > older:
                base = max(0, base - 10)
                trend = " ↑上行"

    return base, f"TNX {tnx_val:.2f}%{trend}"


def _score_yc(data: dict = None) -> tuple:
    """Yield curve — pull from FRED data (if already fetched) or default."""
    spread = 0.0
    inversion_days = 0
    if data is not None and isinstance(data, dict):
        vals = data.get("spread_values", [])
        if vals:
            spread = vals[-1]
        inversion_days = data.get("inversion_days", 0)

    if spread < -80:
        return 5,  f"2s10s {spread:.0f}bp 深度倒挂 ({inversion_days}d)"
    if spread < -40:
        return 20, f"2s10s {spread:.0f}bp 倒挂 ({inversion_days}d)"
    if spread < 0:
        return 40, f"2s10s {spread:.0f}bp 轻微倒挂"
    if spread < 60:
        return 60, f"2s10s {spread:.0f}bp 平坦"
    if spread < 120:
        return 80, f"2s10s {spread:.0f}bp 陡峭"
    return 95, f"2s10s {spread:.0f}bp 极度陡峭"


def _score_corr(spy_tlt: float = 0.0) -> tuple:
    if spy_tlt > 0.4:
        return 5,  f"股债双杀 +{spy_tlt:.2f}"
    if spy_tlt > 0.15:
        return 30, f"股债正相关 +{spy_tlt:.2f}"
    if spy_tlt > -0.1:
        return 55, f"股债低相关 {spy_tlt:.2f}"
    if spy_tlt > -0.3:
        return 75, f"股债负相关 {spy_tlt:.2f}"
    return 95, f"股债强对冲 {spy_tlt:.2f}"


def _score_regime(regime: str) -> tuple:
    r = regime.lower() if regime else ""
    if "流动性枯竭" in r:
        return 5,  "全球流动性枯竭"
    if "通胀型恐慌" in r or "极致防守" in r:
        return 15, "通胀型恐慌"
    if "通缩型恐慌" in r or "美债避险" in r:
        return 35, "通缩型恐慌"
    if "尾部" in r:
        return 25, "尾部重仓预警"
    if "常态" in r or "均衡" in r or "扩张" in r:
        return 85, "常态扩张期"
    return 50, "中性震荡"


def _score_china_macro(cpi_val: float = 0, pmi_val: float = 50,
                       m2_val: float = 8, gdp_val: float = 5) -> tuple:
    """Composite China macro score. 0-100 based on 4 sub-indicators."""
    sub = 0
    detail_parts = []
    # CPI: 1-3% = healthy
    if cpi_val <= 0:
        sub += 10; detail_parts.append(f"CPI {cpi_val}% 通缩")
    elif cpi_val < 1:
        sub += 18; detail_parts.append(f"CPI {cpi_val}% 偏低")
    elif cpi_val <= 3:
        sub += 25; detail_parts.append(f"CPI {cpi_val}% 健康")
    else:
        sub += 10; detail_parts.append(f"CPI {cpi_val}% 偏高")
    # PMI: >50 = expansion
    if pmi_val >= 52:
        sub += 30; detail_parts.append(f"PMI {pmi_val} 扩张")
    elif pmi_val >= 50:
        sub += 22; detail_parts.append(f"PMI {pmi_val} 荣枯线上")
    elif pmi_val >= 48:
        sub += 12; detail_parts.append(f"PMI {pmi_val} 收缩")
    else:
        sub += 5;  detail_parts.append(f"PMI {pmi_val} 深度收缩")
    # M2 YoY: >10% = loose
    if m2_val > 11:
        sub += 25; detail_parts.append(f"M2 {m2_val}% 宽松")
    elif m2_val > 9:
        sub += 20; detail_parts.append(f"M2 {m2_val}% 偏松")
    elif m2_val > 7:
        sub += 15; detail_parts.append(f"M2 {m2_val}% 中性")
    else:
        sub += 5;  detail_parts.append(f"M2 {m2_val}% 偏紧")
    # GDP: >5% = robust
    if gdp_val > 6:
        sub += 20; detail_parts.append(f"GDP {gdp_val}% 强劲")
    elif gdp_val > 4.5:
        sub += 17; detail_parts.append(f"GDP {gdp_val}% 稳健")
    elif gdp_val > 3:
        sub += 10; detail_parts.append(f"GDP {gdp_val}% 放缓")
    else:
        sub += 5;  detail_parts.append(f"GDP {gdp_val}% 低迷")
    return sub, " | ".join(detail_parts)


def _score_valuation(pe_pct: float = 50) -> tuple:
    """Inverse score: low PE percentile = cheap = high score."""
    if pe_pct < 10:   return 95, f"PE 分位 {pe_pct}% 极度低估"
    if pe_pct < 25:   return 80, f"PE 分位 {pe_pct}% 低估"
    if pe_pct < 50:   return 60, f"PE 分位 {pe_pct}% 合理偏低"
    if pe_pct < 70:   return 40, f"PE 分位 {pe_pct}% 合理偏高"
    if pe_pct < 90:   return 20, f"PE 分位 {pe_pct}% 高估"
    return 10, f"PE 分位 {pe_pct}% 泡沫区间"


def compute_decision(vix: float = 20.0, tnx: float = 4.0,
                     tnx_data: dict = None, yc_data: dict = None,
                     spy_tlt_corr: float = 0.0, regime: str = "",
                     china: dict = None, pe_pct: float = 50.0) -> dict:
    """Main entry point — returns the complete decision signal payload.
    china: dict with optional keys cpi/pmi/m2/gdp each having 'current'
    pe_pct: CSI300 PE percentile (0-100) for valuation factor
    """

    s_vix, d_vix = _score_vix(vix)
    s_tnx, d_tnx = _score_tnx(tnx, tnx_data)
    s_yc,  d_yc  = _score_yc(yc_data)
    s_corr,d_corr= _score_corr(spy_tlt_corr)
    s_reg, d_reg = _score_regime(regime)

    # China macro
    c = china or {}
    s_cn, d_cn = _score_china_macro(
        cpi_val=float(c.get("cpi", {}).get("current", 0) or 0),
        pmi_val=float(c.get("pmi", {}).get("current", 50) or 50),
        m2_val=float(c.get("m2", {}).get("current", 8) or 8),
        gdp_val=float(c.get("gdp", {}).get("current", 5) or 5),
    )
    s_val, d_val = _score_valuation(pe_pct)

    factors = [
        {"name": "VIX 位势",      "score": s_vix, "detail": d_vix,  "weight": 0.20},
        {"name": "利率方向",      "score": s_tnx, "detail": d_tnx,  "weight": 0.15},
        {"name": "曲线形态",      "score": s_yc,  "detail": d_yc,   "weight": 0.15},
        {"name": "股债相关",      "score": s_corr,"detail": d_corr, "weight": 0.15},
        {"name": "当前象限",      "score": s_reg, "detail": d_reg,  "weight": 0.15},
        {"name": "中国宏观",      "score": s_cn,  "detail": d_cn,   "weight": 0.10},
        {"name": "估值分位",      "score": s_val, "detail": d_val,  "weight": 0.10},
    ]

    raw = sum(f["score"] * f["weight"] for f in factors)
    score = round(raw)

    # map to signal band
    signal, signal_en, color = "中性", "NEUTRAL", "#fbbf24"
    for lo, hi, zh, en, clr in SIGNAL_BANDS:
        if lo <= score < hi:
            signal, signal_en, color = zh, en, clr
            break

    return {
        "score": score,
        "signal": signal,
        "signal_en": signal_en,
        "color": color,
        "factors": factors,
        "active_warnings": get_active_alerts(),
    }
