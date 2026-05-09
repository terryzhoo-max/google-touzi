"""
Markowitz mean-variance portfolio optimizer.
Computes efficient frontier, GMV, and tangency portfolios using scipy.

Tickers: SPY / TLT / GLD (from data_providers → Tushare QDII ETFs)
Risk-free rate: from TNX cache or config default.
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from core.data_providers import get_us_etf_history
from core.market_data import DATA_CACHE
from core.config import settings

TICKERS = ["SPY", "TLT", "GLD"]


def _portfolio_stats(weights: np.ndarray, mu: np.ndarray, cov: np.ndarray, rf: float):
    """Return (return, volatility, sharpe) for given weights."""
    w = np.asarray(weights)
    ret = np.dot(w, mu)
    vol = np.sqrt(np.dot(w.T, np.dot(cov, w)))
    sharpe = (ret - rf) / vol if vol > 0 else 0.0
    return ret, vol, sharpe


def _neg_sharpe(weights: np.ndarray, mu: np.ndarray, cov: np.ndarray, rf: float):
    return -_portfolio_stats(weights, mu, cov, rf)[2]


def _portfolio_vol(weights: np.ndarray, cov: np.ndarray):
    return np.sqrt(np.dot(weights.T, np.dot(cov, weights)))


def run_efficient_frontier() -> dict:
    """Compute and return Markowitz efficient frontier data.

    Returns:
        dict with:
          - random_portfolios: [{ret, vol, weights}]
          - gmv: {ret, vol, weights, label}
          - tangency: {ret, vol, weights, sharpe, label}
          - alphacore: {ret, vol, label}
          - insight: str
    """
    # 1. fetch returns
    returns_list = []
    for t in TICKERS:
        s = get_us_etf_history(t, months=12)
        if s.empty:
            return {"error": f"No data for {t}"}
        r = s.pct_change().dropna()
        r.name = t
        returns_list.append(r)

    df = pd.concat(returns_list, axis=1).dropna()
    mu = df.mean().values * 252
    cov = df.cov().values * 252
    n = len(TICKERS)

    # risk-free rate
    tnx_cache = DATA_CACHE.get("tnx", {}).get("data")
    tnx_vals = tnx_cache.get("data", tnx_cache) if isinstance(tnx_cache, dict) else tnx_cache
    try:
        if hasattr(tnx_vals, "iloc"):
            rf = float(tnx_vals.iloc[-1]) / 100.0 if len(tnx_vals) > 0 else 0.04
        elif isinstance(tnx_vals, (list, tuple)):
            rf = float(tnx_vals[-1]) / 100.0 if len(tnx_vals) > 0 else 0.04
        else:
            rf = 0.04
    except Exception:
        rf = 0.04

    constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1}
    bounds = tuple((0, 1) for _ in range(n))
    x0 = np.ones(n) / n

    # 2. GMV (min variance)
    gmv_res = minimize(_portfolio_vol, x0, args=(cov,),
                       bounds=bounds, constraints=constraints)
    gmv_w = gmv_res.x
    gmv_ret, gmv_vol, gmv_sharpe = _portfolio_stats(gmv_w, mu, cov, rf)

    # 3. Tangency (max Sharpe)
    tan_res = minimize(_neg_sharpe, x0, args=(mu, cov, rf),
                       bounds=bounds, constraints=constraints)
    tan_w = tan_res.x
    tan_ret, tan_vol, tan_sharpe = _portfolio_stats(tan_w, mu, cov, rf)

    # 4. Random portfolios for scatter
    np.random.seed(42)
    rand_w = np.random.dirichlet(np.ones(n), 500)
    rand_ports = []
    for w in rand_w:
        r, v, _ = _portfolio_stats(w, mu, cov, rf)
        rand_ports.append({"ret": round(r * 100, 2), "vol": round(v * 100, 2)})

    # 5. Current AlphaCore portfolio
    try:
        from core.quant_engine import calculate_asset_allocation
        alloc = calculate_asset_allocation()["allocation"]
        ac_w = np.zeros(n)
        for item in alloc:
            name = item["name"]
            val = item["value"] / 100.0
            if "权益" in name or "SPY" in name or "股" in name:
                ac_w[0] += val
            elif "债" in name or "TLT" in name or "票据" in name:
                ac_w[1] += val
            elif "黄金" in name or "GLD" in name or "另类" in name:
                ac_w[2] += val
        if ac_w.sum() == 0:
            ac_w = np.array([0.6, 0.3, 0.1])
        else:
            ac_w = ac_w / ac_w.sum()
    except Exception:
        ac_w = np.array([0.6, 0.3, 0.1])

    ac_ret, ac_vol, ac_sharpe = _portfolio_stats(ac_w, mu, cov, rf)

    # 6. insight
    w_str = f'{int(ac_w[0]*100)}%/{int(ac_w[1]*100)}%/{int(ac_w[2]*100)}%'
    if ac_sharpe > tan_sharpe * 0.9:
        insight = f'✅ AlphaCore策略({w_str})夏普 {ac_sharpe:.2f} 接近最优切线组合({tan_sharpe:.2f})，配置效率高。'
    elif ac_sharpe > 0:
        insight = f'📊 AlphaCore策略({w_str})夏普 {ac_sharpe:.2f}，最优切线组合夏普 {tan_sharpe:.2f}。存在 {round((tan_sharpe-ac_sharpe)/tan_sharpe*100)}% 的效率提升空间。'
    else:
        insight = f'⚠ AlphaCore策略({w_str})当前位于有效前沿内侧，建议重新审视配置。'

    return {
        "random_portfolios": rand_ports,
        "gmv": {
            "ret": round(gmv_ret * 100, 2),
            "vol": round(gmv_vol * 100, 2),
            "weights": [round(w, 3) for w in gmv_w],
            "label": "最小方差 (GMV)",
        },
        "tangency": {
            "ret": round(tan_ret * 100, 2),
            "vol": round(tan_vol * 100, 2),
            "sharpe": round(tan_sharpe, 2),
            "weights": [round(w, 3) for w in tan_w],
            "label": "最大夏普 (切线)",
        },
        "alphacore": {
            "ret": round(ac_ret * 100, 2),
            "vol": round(ac_vol * 100, 2),
            "weights": [round(w, 3) for w in ac_w],
            "label": "AlphaCore 策略",
        },
        "assets": TICKERS,
        "insight": insight,
    }
