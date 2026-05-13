"""
18-year parameter scanner for institutional decision thresholds.
Calibrates decision_policy and risk_engine against actual historical
SPY/TLT/GLD/VIX/TNX data stored in alphacore.db.

Method: Uses pre-computed daily returns from the backtest dataset.
For each threshold combination, simulates the institutional decision
rules on every trading day and evaluates strategy outcomes.

Optimizes for: Sharpe ratio (primary), with penalties for excessive
false alarms and missed warning signals.
"""

import pandas as pd
import numpy as np
from core.db_layer import init_db, get_cached_timeseries
from datetime import datetime, timedelta


def _load_18yr_returns():
    """Load 18-year daily returns from backtest cache."""
    init_db()
    end = datetime.now()
    start = end - timedelta(days=365 * 18 + 30)
    s, e = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    symbols = {"SPY", "TLT", "GLD", "^VIX", "^TNX"}
    dfs = {}
    for sym in symbols:
        df = get_cached_timeseries(sym, s, e)
        if df is not None and not df.empty:
            dfs[sym] = df["Close"]
    if len(dfs) < 4:
        raise RuntimeError("Not enough cached data for calibration")
    returns = pd.DataFrame(dfs).ffill().dropna().pct_change().dropna()
    prices = pd.DataFrame(dfs).ffill().dropna()
    return returns, prices


def _rolling_volatility(returns: pd.DataFrame, window: int = 60) -> pd.DataFrame:
    """Rolling annualized volatility."""
    return returns.rolling(window).std() * np.sqrt(252)


def _rolling_var_95(returns: pd.DataFrame, window: int = 60) -> pd.Series:
    """Rolling 95% VaR (parametric)."""
    vol = returns.mean(axis=1).rolling(window).std() * np.sqrt(252)
    return -1.65 * vol * 100  # as percentage


def _rolling_mdd(returns: pd.Series, window: int = 252) -> pd.Series:
    """Rolling max drawdown over window."""
    cum = (1 + returns).cumprod()
    peak = cum.rolling(window, min_periods=1).max()
    return (cum / peak - 1).rolling(window, min_periods=1).min() * 100


def _rolling_sharpe(returns: pd.Series, window: int = 252) -> pd.Series:
    """Rolling Sharpe ratio."""
    mu = returns.rolling(window).mean() * 252
    sigma = returns.rolling(window).std() * np.sqrt(252)
    return mu / sigma.replace(0, np.nan)


def _score_thresholds(
    ret: pd.DataFrame,
    spy_tlt_corr_rolling: pd.Series,
    equity_vol: pd.Series,
    risk_var: pd.Series,
    scenario_loss_sim: float,
    allow_min: int,
    limited_min: int,
    var_high: float,
    var_medium: float,
) -> dict:
    """
    Simulate institutional decision rules over the full timeline.
    Returns aggregate metrics for this threshold combination.
    """
    n = len(ret)
    spy_ret = ret.get("SPY", pd.Series(np.zeros(n), index=ret.index))
    tlt_ret = ret.get("TLT", pd.Series(np.zeros(n), index=ret.index))
    gld_ret = ret.get("GLD", pd.Series(np.zeros(n), index=ret.index))

    # decision flags per day
    # data_quality simplified: if vol > 2x median → weak
    daily_vol_ok = equity_vol.fillna(0.15) < 0.35
    risk_level = pd.Series("low", index=ret.index)
    risk_level[risk_var <= var_high] = "high"
    risk_level[(risk_var <= var_medium) & (risk_var > var_high)] = "medium"

    # simulate score per day
    scores = np.full(n, 100.0)
    scores[~daily_vol_ok] -= 25
    scores[risk_level == "high"] -= 25
    scores[risk_level == "medium"] -= 10
    scores[scenario_loss_sim < -0.08] -= 17  # hardcoded -8% gate

    status = np.full(n, "unknown", dtype=object)
    status[(scores >= allow_min) & (scores >= limited_min)] = "allow"
    status[(scores >= limited_min) & (scores < allow_min)] = "limited"
    status[scores < limited_min] = "observe"

    # compute strategy returns: default 60/30/10, override to 0/40/60 when risk high
    w_spy = np.full(n, 0.6)
    w_tlt = np.full(n, 0.3)
    w_gld = np.full(n, 0.1)
    w_cash = np.zeros(n)

    # When institutional says "observe", shift to defensive
    observe_mask = status == "observe"
    w_spy[observe_mask] = 0.0
    w_tlt[observe_mask] = 0.0
    w_gld[observe_mask] = 0.4
    w_cash[observe_mask] = 0.6

    strat_ret = pd.Series(
        w_spy * spy_ret.values + w_tlt * tlt_ret.values +
        w_gld * gld_ret.values + w_cash * 0.0,
        index=ret.index
    )

    bench_ret = spy_ret

    # metrics
    days = 252
    eq = (1 + strat_ret).cumprod()
    years = max(len(eq) / days, 1)
    cagr = (eq.iloc[-1] ** (1 / years) - 1) * 100
    mdd = ((eq - eq.cummax()) / eq.cummax()).min() * 100
    strat_std = float(strat_ret.std())
    sharpe = (float(strat_ret.mean()) / max(strat_std, 0.0001)) * np.sqrt(days)

    # bench
    beq = (1 + bench_ret).cumprod()
    bench_cagr = (beq.iloc[-1] ** (1 / years) - 1) * 100
    bench_mdd = ((beq - beq.cummax()) / beq.cummax()).min() * 100

    # signal quality: too many observe days = opportunity cost
    observe_pct = observe_mask.mean() * 100
    allow_pct = (status == "allow").mean() * 100

    # penalty for >30% observe days (overly defensive)
    if observe_pct > 30:
        sharpe -= (observe_pct - 30) * 0.02

    return {
        "cagr": round(cagr, 2),
        "mdd": round(mdd, 2),
        "sharpe": round(sharpe, 3),
        "bench_cagr": round(bench_cagr, 2),
        "bench_mdd": round(bench_mdd, 2),
        "observe_pct": round(observe_pct, 1),
        "allow_pct": round(allow_pct, 1),
    }


def run_calibration() -> dict:
    """Main entry: scan thresholds and return best combination."""
    print("[calibrator] Loading 18-year backtest data …")
    ret, prices = _load_18yr_returns()

    # compute rolling metrics once
    spy_tlt_corr = ret["SPY"].rolling(120).corr(ret.get("TLT", ret["SPY"]))
    equity_vol = _rolling_volatility(ret[["SPY"]], 60).iloc[:, 0]
    risk_var = _rolling_var_95(ret, 60)

    # scenario loss simulation: use historical worst 60-day drawdown
    spy_rolling_mdd = _rolling_mdd(ret["SPY"], 60)
    scenario_loss = spy_rolling_mdd

    # parameter sweep grid
    allow_min_range = [70, 75, 80, 85]
    limited_min_range = [50, 55, 60, 65]
    var_high_range = [-8.0, -6.0, -5.0, -4.0]
    var_medium_range = [-3.0, -2.0, -1.5, -1.0]

    best = None
    best_sharpe = -999
    results = []

    total = len(allow_min_range) * len(limited_min_range) * len(var_high_range) * len(var_medium_range)
    count = 0
    for allow_min in allow_min_range:
        for limited_min in limited_min_range:
            if limited_min >= allow_min:
                continue
            for var_high in var_high_range:
                for var_medium in var_medium_range:
                    if var_medium <= var_high:
                        continue
                    count += 1
                    r = _score_thresholds(
                        ret, spy_tlt_corr, equity_vol, risk_var,
                        scenario_loss, allow_min, limited_min,
                        var_high, var_medium,
                    )
                    r.update({
                        "allow_min": allow_min, "limited_min": limited_min,
                        "var_high": round(var_high, 1), "var_medium": round(var_medium, 1),
                    })
                    results.append(r)
                    if r["sharpe"] > best_sharpe:
                        best_sharpe = r["sharpe"]
                        best = r

    print(f"[calibrator] Scanned {count}/{total} valid combinations.")
    print(f"[calibrator] Best Sharpe: {best['sharpe']}")

    # Compute actual historical asset volatilities
    asset_vols = {}
    for col in ["SPY", "TLT", "GLD"]:
        if col in ret.columns:
            asset_vols[col] = round(float(ret[col].std() * np.sqrt(252)), 4)

    return {
        "best": best,
        "scanned_count": count,
        "historical_volatilities": asset_vols,
        "top_5": sorted(results, key=lambda x: x["sharpe"], reverse=True)[:5],
    }
