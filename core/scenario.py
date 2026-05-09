"""
Historical scenario stress test engine.
Applies current portfolio weights against three major crisis periods.

Each scenario contains calibrated per-asset total returns and max drawdowns,
derived from actual ETF price data during those periods.
"""

import numpy as np
from core.market_data import DATA_CACHE, fetch_yfinance_data, fetch_tushare_csi300_history
from core.config import settings

# ── Scenario Definitions ────────────────────────────────────────
# Each scenario: { "name": ..., "period": ..., "desc": ...,
#   "assets": { "SPY": {ret_pct, mdd_pct}, "TLT": {...}, "GLD": {...} } }

SCENARIOS = [
    {
        "id": "2008_gfc",
        "name": "2008 全球金融危机",
        "period": "2008-09-15 → 2009-03-09",
        "desc": "雷曼破产引发系统性信贷冻结。股市暴跌，国债暴涨（避险），黄金先跌后涨。",
        "assets": {
            "SPY": {"ret": -47.6, "mdd": -52.3},
            "TLT": {"ret": +21.8, "mdd": -14.2},
            "GLD": {"ret": +5.4,  "mdd": -16.8},
        },
        "bench_ret": -47.6,
        "bench_mdd": -52.3,
    },
    {
        "id": "2020_covid",
        "name": "2020 新冠流动性熔断",
        "period": "2020-02-19 → 2020-03-23",
        "desc": "COVID-19 全球扩散触发史上最快熊市。VIX 飙至 82，股债金三杀后快速反弹。",
        "assets": {
            "SPY": {"ret": -33.9, "mdd": -35.4},
            "TLT": {"ret": +12.1, "mdd": -8.3},
            "GLD": {"ret": -3.2,  "mdd": -13.6},
        },
        "bench_ret": -33.9,
        "bench_mdd": -35.4,
    },
    {
        "id": "2022_hikes",
        "name": "2022 美联储暴力加息",
        "period": "2022-01-03 → 2022-10-12",
        "desc": "40年最高通胀驱动 Fed 连续 4 次加息 75bp。股债双杀，传统 60/40 组合创百年最差表现。",
        "assets": {
            "SPY": {"ret": -24.5, "mdd": -25.4},
            "TLT": {"ret": -30.8, "mdd": -34.6},
            "GLD": {"ret": -10.1, "mdd": -20.4},
        },
        "bench_ret": -24.5,
        "bench_mdd": -25.4,
    },
]


def get_current_weights() -> dict:
    """Extract current portfolio weights from the allocation or backtest engine."""
    try:
        # try backtest first (most accurate, state-machine driven)
        from core.backtest import run_backtest
        bt = run_backtest()
        state = bt.get("current_state", {})
        return {
            "SPY": state.get("w_spy", 60) / 100.0,
            "TLT": state.get("w_tlt", 30) / 100.0,
            "GLD": state.get("w_gld", 10) / 100.0,
            "CASH": state.get("w_cash", 0) / 100.0,
        }
    except Exception:
        pass

    # fallback: parse allocation data
    try:
        from core.quant_engine import calculate_asset_allocation
        alloc = calculate_asset_allocation()["allocation"]
        w = {"SPY": 0.0, "TLT": 0.0, "GLD": 0.0, "CASH": 0.0}
        for a in alloc:
            name = a["name"]
            val = a["value"] / 100.0
            if "权益" in name or "成长" in name or "股" in name or "SPY" in name:
                w["SPY"] += val
            elif "债" in name or "票据" in name or "TLT" in name:
                w["TLT"] += val
            elif "黄金" in name or "另类" in name or "GLD" in name:
                w["GLD"] += val
            elif "现金" in name:
                w["CASH"] += val
        return w
    except Exception:
        return {"SPY": 0.60, "TLT": 0.30, "GLD": 0.10, "CASH": 0.0}


def run_scenario_analysis() -> dict:
    """Apply current portfolio weights to each historical scenario.

    Returns:
        { "scenarios": [...], "current_weights": {...}, "insight": str }
    """
    weights = get_current_weights()

    results = []
    for sc in SCENARIOS:
        port_ret = 0.0
        port_mdd = 0.0
        for asset in ["SPY", "TLT", "GLD"]:
            w = weights.get(asset, 0.0)
            a = sc["assets"].get(asset, {})
            port_ret += w * a.get("ret", 0.0)
            # MDD is roughly additive for stress scenarios (conservative estimate)
            port_mdd += w * a.get("mdd", 0.0)
        port_ret = round(port_ret, 1)
        port_mdd = round(port_mdd, 1)

        # color coding
        if port_ret > 0:
            color = "#4ade80"
            verdict = "组合抗跌"
        elif port_ret > -10:
            color = "#fbbf24"
            verdict = "中度承压"
        elif port_ret > -20:
            color = "#f97316"
            verdict = "显著受损"
        else:
            color = "#ef4444"
            verdict = "严重冲击"

        results.append({
            "id": sc["id"],
            "name": sc["name"],
            "period": sc["period"],
            "desc": sc["desc"],
            "port_ret": port_ret,
            "port_mdd": port_mdd,
            "bench_ret": sc["bench_ret"],
            "bench_mdd": sc["bench_mdd"],
            "color": color,
            "verdict": verdict,
        })

    # generate insight
    worst = min(results, key=lambda r: r["port_ret"])
    best  = max(results, key=lambda r: r["port_ret"])
    w_str = f'股{int(weights["SPY"]*100)}%/债{int(weights["TLT"]*100)}%/金{int(weights["GLD"]*100)}%/现{int(weights.get("CASH",0)*100)}%'

    if worst["port_ret"] < -20:
        insight = f'⚠️ 极端情景压力测试 ({w_str})：当前配置在「{worst["name"]}」中将遭受 {worst["port_ret"]}% 冲击 (vs 基准 {worst["bench_ret"]}%)。建议提高现金/短债比例以增强韧性。'
    elif best["port_ret"] > 0:
        insight = f'🛡️ 压力测试评估 ({w_str})：当前配置在所有历史极端情景中均表现出较强防御性。最差情景「{worst["name"]}」下策略回撤 {worst["port_ret"]}%，明显优于基准。'
    else:
        insight = f'📊 压力测试评估 ({w_str})：最差情景「{worst["name"]}」策略回撤 {worst["port_ret"]}% (vs 基准 {worst["bench_ret"]}%)。三情景平均回撤 {round(sum(r["port_ret"] for r in results)/len(results), 1)}%。'

    return {
        "scenarios": results,
        "current_weights": weights,
        "insight": insight,
    }
