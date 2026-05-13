#!/usr/bin/env python
"""Comprehensive parameter calibration against 18-year backtest data.

Part A — Decision + Risk thresholds (carried forward)
Part B — Allocation policy thresholds (NEW)

Run:  python calibrate_params.py
"""

import json, sys
sys.path.insert(0, ".")

import numpy as np
import pandas as pd
from core.param_calibrator import _load_18yr_returns, _rolling_volatility, _rolling_var_95, _rolling_mdd


def _score_simulation(returns, prices, equity_vol, risk_var, spy_rolling_mdd,
                      allow_min, limited_min, var_high, var_medium):
    """Part A: decision thresholds — same as before."""
    n = len(returns)
    spy_ret = returns.get("SPY", pd.Series(np.zeros(n), index=returns.index))
    tlt_ret = returns.get("TLT", pd.Series(np.zeros(n), index=returns.index))
    gld_ret = returns.get("GLD", pd.Series(np.zeros(n), index=returns.index))
    daily_vol_ok = equity_vol.fillna(0.15) < 0.35
    risk_level = pd.Series("low", index=returns.index)
    risk_level[risk_var <= var_high] = "high"
    risk_level[(risk_var <= var_medium) & (risk_var > var_high)] = "medium"
    scores = np.full(n, 100.0)
    scores[~daily_vol_ok] -= 25
    scores[risk_level == "high"] -= 25
    scores[risk_level == "medium"] -= 10
    scores[spy_rolling_mdd < -0.08] -= 17
    status = np.full(n, "unknown", dtype=object)
    status[(scores >= allow_min) & (scores >= limited_min)] = "allow"
    status[(scores >= limited_min) & (scores < allow_min)] = "limited"
    status[scores < limited_min] = "observe"
    w_spy = np.full(n, 0.6); w_tlt = np.full(n, 0.3); w_gld = np.full(n, 0.1); w_cash = np.zeros(n)
    observe_mask = status == "observe"
    w_spy[observe_mask] = 0.0; w_tlt[observe_mask] = 0.0; w_gld[observe_mask] = 0.4; w_cash[observe_mask] = 0.6
    strat_ret = pd.Series(w_spy * spy_ret.values + w_tlt * tlt_ret.values + w_gld * gld_ret.values, index=returns.index)
    eq = (1 + strat_ret).cumprod()
    years = max(len(eq) / 252, 1)
    cagr = (eq.iloc[-1] ** (1/years) - 1) * 100
    mdd = ((eq - eq.cummax()) / eq.cummax()).min() * 100
    std = float(strat_ret.std())
    sharpe = (float(strat_ret.mean()) / max(std, 0.0001)) * np.sqrt(252)
    observe_pct = observe_mask.mean() * 100
    if observe_pct > 30: sharpe -= (observe_pct - 30) * 0.02
    bench_eq = (1 + spy_ret).cumprod()
    bench_cagr = (bench_eq.iloc[-1] ** (1/years) - 1) * 100
    bench_mdd = ((bench_eq - bench_eq.cummax()) / bench_eq.cummax()).min() * 100
    return dict(cagr=round(cagr,2), mdd=round(mdd,2), sharpe=round(sharpe,3),
                bench_cagr=round(bench_cagr,2), bench_mdd=round(bench_mdd,2),
                observe_pct=round(observe_pct,1))


def _allocation_sweep(returns, prices):
    """Part B: sweep allocation policy thresholds.

    Uses 8 ETFs as equal-weight starting basket. Tests different
    score→delta mappings and constraint thresholds.
    """
    etfs = ["SPY", "TLT", "GLD"]
    n = len(returns)
    # compute rolling 60d returns for signal scoring
    spy_ret = returns.get("SPY", pd.Series(0, index=returns.index))
    tlt_ret = returns.get("TLT", pd.Series(0, index=returns.index))
    gld_ret = returns.get("GLD", pd.Series(0, index=returns.index))

    # simple signal: rolling 60d excess return vs SPY
    spy_60d = spy_ret.rolling(60).mean() * 252 - spy_ret.rolling(60).mean() * 252
    # use momentum signal: positive 60d return = buy, negative = sell
    momentum = {}
    for name, series in [("SPY", spy_ret), ("TLT", tlt_ret), ("GLD", gld_ret)]:
        rolling = series.rolling(60).mean() * 252 * 100  # annualized %
        # map to 0-100 score
        z = (rolling - rolling.rolling(500).mean()) / rolling.rolling(500).std().replace(0, 1)
        momentum[name] = 50 + z * 15  # center at 50, SD=15

    best = None
    best_sharpe = -999
    results = []

    step_weights = [0.02, 0.03, 0.04, 0.05]
    turn_limits = [0.08, 0.12, 0.16, 0.20]
    single_limits = [0.15, 0.18, 0.22, 0.25]
    gold_maxes = [0.15, 0.18, 0.22, 0.25]

    total = len(step_weights) * len(turn_limits) * len(single_limits)
    count = 0
    for step in step_weights:
        for turn in turn_limits:
            for single in single_limits:
                for gold_max in gold_maxes:
                    if gold_max > single: continue
                    count += 1
                    # simulate equal-weight rebalancing with score→delta rules
                    base_w = 1.0 / 3
                    w = {"SPY": base_w, "TLT": base_w, "GLD": base_w}
                    strat_vals = []
                    for i in range(60, n):
                        # apply signals every ~20 trading days
                        if i % 20 == 0:
                            for name in w:
                                s = momentum[name].iloc[i] if i < len(momentum[name]) else 50
                                if s >= 68: delta = step
                                elif s >= 58: delta = step/2
                                elif s <= 32: delta = -step
                                elif s <= 42: delta = -step/2
                                else: delta = 0
                                w[name] = max(0, min(single, w[name] + delta))
                            # enforce gold max
                            w["GLD"] = min(w["GLD"], gold_max)
                            # renormalize
                            tw = sum(w.values()) or 1
                            w = {k: v/tw for k, v in w.items()}
                        ret = w["SPY"]*spy_ret.iloc[i] + w["TLT"]*tlt_ret.iloc[i] + w["GLD"]*gld_ret.iloc[i]
                        strat_vals.append(ret)
                    if len(strat_vals) < 252: continue
                    sr = pd.Series(strat_vals[-252*5:])
                    eq = (1 + sr).cumprod()
                    years2 = max(len(eq)/252, 1)
                    cagr = (eq.iloc[-1]**(1/years2)-1)*100
                    mdd = ((eq-eq.cummax())/eq.cummax()).min()*100
                    std2 = float(sr.std())
                    sh2 = (float(sr.mean())/max(std2,0.0001))*np.sqrt(252)
                    r = dict(step=round(step,2), turn=round(turn,2), single=round(single,2),
                            gold_max=round(gold_max,2), cagr=round(cagr,2), mdd=round(mdd,2), sharpe=round(sh2,3))
                    results.append(r)
                    if sh2 > best_sharpe: best_sharpe = sh2; best = r

    print(f"[alloc_sweep] Scanned {count} allocation combos. Best sharpe: {best_sharpe}")
    return best, sorted(results, key=lambda x: x["sharpe"], reverse=True)[:5]


def main():
    print("[calibrate] Loading 18-year backtest data …")
    returns, prices = _load_18yr_returns()
    vol = _rolling_volatility(returns[["SPY"]], 60).iloc[:, 0]
    var95 = _rolling_var_95(returns, 60)
    spymdd = _rolling_mdd(returns["SPY"], 60)

    # Part A
    allow_range = [70, 75, 80, 85]
    limited_range = [50, 55, 60, 65]
    vh_range = [-8.0, -6.0, -5.0, -4.0]
    vm_range = [-3.0, -2.0, -1.5, -1.0]
    best_a = None; best_s = -999; all_a = []
    for am in allow_range:
        for lm in limited_range:
            if lm >= am: continue
            for vh in vh_range:
                for vm in vm_range:
                    if vm <= vh: continue
                    r = _score_simulation(returns, prices, vol, var95, spymdd, am, lm, vh, vm)
                    r.update(allow_min=am, limited_min=lm, var_high=vh, var_medium=vm)
                    all_a.append(r)
                    if r["sharpe"] > best_s: best_s = r["sharpe"]; best_a = r
    print(f"[Part A] {len(all_a)} combos. Best Sharpe: {best_s}")

    # Part B
    best_b, top5_b = _allocation_sweep(returns, prices)

    result = {
        "part_a_decision": best_a,
        "part_b_allocation": best_b,
        "top5_allocation": top5_b,
        "recommended_env": {
            "CALIB_ALLOW_MIN": best_a["allow_min"],
            "CALIB_LIMITED_MIN": best_a["limited_min"],
            "CALIB_VAR_HIGH": best_a["var_high"],
            "CALIB_VAR_MEDIUM": best_a["var_medium"],
            "CALIB_MAX_STEP_WEIGHT": best_b["step"],
            "CALIB_MAX_SINGLE_WEIGHT": best_b["single"],
            "CALIB_MAX_TURNOVER": best_b["turn"],
            "CALIB_MAX_GOLD_WEIGHT": best_b["gold_max"],
        },
    }
    print("\n" + "=" * 60)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
