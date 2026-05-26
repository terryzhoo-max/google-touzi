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


def get_structured_covariance(symbols: list[str]) -> tuple[np.ndarray, np.ndarray]:
    from core.factor_risk import FACTOR_REGISTRY
    
    # 5 Factors
    factors = [
        "equity_beta",
        "liquidity_sensitivity",
        "dollar_sensitivity",
        "rate_sensitivity",
        "inflation_sensitivity"
    ]
    
    vol = np.array([0.16, 0.60, 0.08, 0.15, 0.05])
    corr = np.eye(5)
    
    # SPY vs VIX
    corr[0, 1] = corr[1, 0] = -0.7
    # SPY vs DXY
    corr[0, 2] = corr[2, 0] = -0.2
    # SPY vs TNX
    corr[0, 3] = corr[3, 0] = 0.1
    # SPY vs Inflation
    corr[0, 4] = corr[4, 0] = 0.2
    
    phi = np.zeros((5, 5))
    for i in range(5):
        for j in range(5):
            phi[i, j] = corr[i, j] * vol[i] * vol[j]
            
    n = len(symbols)
    B = np.zeros((n, 5))
    for idx, sym in enumerate(symbols):
        registry = FACTOR_REGISTRY.get(sym, {})
        macro = registry.get("macro", {})
        for f_idx, f in enumerate(factors):
            B[idx, f_idx] = macro.get(f, 0.0)
            
    cov_macro = np.dot(B, np.dot(phi, B.T))
    cov = cov_macro + np.eye(n) * (0.08 ** 2)
    return cov, B


def calculate_black_litterman(
    portfolio_snapshot: dict,
    benchmark_weights: dict[str, float],
    views: dict[str, float],
    confidences: dict[str, float],
    risk_aversion: float = 2.5,
    tau: float = 0.025
) -> dict:
    positions = portfolio_snapshot.get("positions", [])
    symbols = [p["symbol"] for p in positions if p["symbol"] != "CASH"]
    cash_pos = [p for p in positions if p["symbol"] == "CASH"]
    cash_weight = sum(float(p["weight"]) for p in cash_pos)
    
    n = len(symbols)
    if n == 0:
        # Return fallback with original weights
        original = {p["symbol"]: float(p["weight"]) for p in positions}
        return {
            "original_weights": original,
            "benchmark_weights": original,
            "optimized_weights": original,
            "posterior_returns": {},
            "prior_returns": {}
        }
        
    cov, B = get_structured_covariance(symbols)
    
    # Standard Equilibrium Excess Returns (Pi)
    w_eq = np.zeros(n)
    for idx, sym in enumerate(symbols):
        w_eq[idx] = benchmark_weights.get(sym, 0.0)
    if w_eq.sum() <= 0:
        w_eq = np.ones(n) / n
    else:
        w_eq = w_eq / w_eq.sum()
        
    Pi = risk_aversion * np.dot(cov, w_eq)
    
    valid_views = []
    for sym, val in views.items():
        if sym in symbols:
            valid_views.append((sym, val, confidences.get(sym, 0.5)))
            
    k = len(valid_views)
    if k == 0:
        posterior_ret = Pi
    else:
        P = np.zeros((k, n))
        Q = np.zeros(k)
        omega_diag = np.zeros(k)
        
        for v_idx, (sym, val, conf) in enumerate(valid_views):
            a_idx = symbols.index(sym)
            P[v_idx, a_idx] = 1.0
            Q[v_idx] = val
            p_cov_p = cov[a_idx, a_idx]
            c = max(0.01, min(0.99, conf))
            omega_diag[v_idx] = max(1e-6, p_cov_p * (1.0 - c) / c)
            
        Omega = np.diag(omega_diag)
        
        inv_tau_sigma = np.linalg.inv(tau * cov)
        inv_omega = np.linalg.inv(Omega)
        
        posterior_cov_inv = inv_tau_sigma + np.dot(P.T, np.dot(inv_omega, P))
        posterior_cov = np.linalg.inv(posterior_cov_inv)
        
        posterior_ret = np.dot(posterior_cov, np.dot(inv_tau_sigma, Pi) + np.dot(P.T, np.dot(inv_omega, Q)))
        
    def obj(w):
        return -np.dot(w, posterior_ret) + (risk_aversion / 2.0) * np.dot(w.T, np.dot(cov, w))
        
    constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}
    bounds = tuple((0.0, 1.0) for _ in range(n))
    x0 = np.ones(n) / n
    
    res = minimize(obj, x0, bounds=bounds, constraints=constraints)
    w_opt = res.x
    
    # Scale back including Cash
    remaining_weight = 1.0 - cash_weight
    optimized_weights = {}
    for idx, sym in enumerate(symbols):
        optimized_weights[sym] = round(w_opt[idx] * remaining_weight, 6)
    for p in cash_pos:
        optimized_weights[p["symbol"]] = round(p["weight"], 6)
        
    original_weights = {p["symbol"]: float(p["weight"]) for p in positions}
    
    # Align benchmark weights back including CASH (set cash benchmark weight to its current weight)
    bench_weights_final = {}
    for idx, sym in enumerate(symbols):
        bench_weights_final[sym] = round(w_eq[idx] * remaining_weight, 6)
    for p in cash_pos:
        bench_weights_final[p["symbol"]] = round(p["weight"], 6)
        
    w_orig_noncash = np.zeros(n)
    for idx, sym in enumerate(symbols):
        w_orig_noncash[idx] = original_weights.get(sym, 0.0)
    if w_orig_noncash.sum() > 0:
        w_orig_noncash = w_orig_noncash / w_orig_noncash.sum()
    else:
        w_orig_noncash = np.ones(n) / n
        
    w_diff_orig = w_orig_noncash - w_eq
    w_diff_opt = w_opt - w_eq
    
    active_risk_orig = np.sqrt(np.dot(w_diff_orig.T, np.dot(cov, w_diff_orig)))
    active_risk_opt = np.sqrt(np.dot(w_diff_opt.T, np.dot(cov, w_diff_opt)))
    
    active_return_opt = np.dot(w_opt, posterior_ret) - np.dot(w_eq, posterior_ret)
    
    if active_risk_opt > 1e-6:
        projected_ir = active_return_opt / active_risk_opt
    else:
        projected_ir = 0.0
        
    return {
        "original_weights": original_weights,
        "benchmark_weights": bench_weights_final,
        "optimized_weights": optimized_weights,
        "posterior_returns": {sym: round(float(posterior_ret[i]) * 100, 4) for i, sym in enumerate(symbols)},
        "prior_returns": {sym: round(float(Pi[i]) * 100, 4) for i, sym in enumerate(symbols)},
        "active_risk_metrics": {
            "original_active_risk_pct": round(float(active_risk_orig) * 100, 4),
            "optimized_active_risk_pct": round(float(active_risk_opt) * 100, 4),
            "projected_information_ratio": round(float(projected_ir), 4)
        }
    }


def solve_risk_parity(cov: np.ndarray, budgets: np.ndarray) -> np.ndarray:
    """
    Solve the risk parity optimization using the strictly convex formulation:
    min_x 0.5 * x^T * Cov * x - sum(b_i * ln(x_i))
    
    The optimal x is then normalized to sum to 1.0.
    """
    n = len(budgets)
    
    def obj(x):
        if np.any(x <= 0):
            return 1e10
        val = 0.5 * np.dot(x.T, np.dot(cov, x)) - np.sum(budgets * np.log(x))
        return val
        
    def grad(x):
        return np.dot(cov, x) - budgets / x
        
    x0 = np.ones(n) / n
    bounds = tuple((1e-8, None) for _ in range(n))
    
    res = minimize(obj, x0, jac=grad, method="L-BFGS-B", bounds=bounds)
    if not res.success:
        res = minimize(obj, x0, method="Nelder-Mead", bounds=bounds)
        
    x_opt = res.x
    w_opt = x_opt / np.sum(x_opt)
    return w_opt


def calculate_risk_parity_allocation(
    portfolio_snapshot: dict,
    benchmark_weights: dict[str, float],
    budgets: dict[str, float] | None = None
) -> dict:
    """
    Given a portfolio snapshot and benchmark weights, calculate the optimal weights
    that satisfy the specified risk budgets (or Equal Risk Parity by default).
    
    CASH is excluded from the risk parity optimization (as its variance and covariance is 0),
    and its weight remains anchored to its current level. The remaining portfolio weight is
    distributed among risky assets according to the optimized risk parity weights.
    """
    positions = portfolio_snapshot.get("positions", [])
    symbols = [p["symbol"] for p in positions if p["symbol"] != "CASH"]
    cash_pos = [p for p in positions if p["symbol"] == "CASH"]
    cash_weight = sum(float(p["weight"]) for p in cash_pos)
    
    n = len(symbols)
    original = {p["symbol"]: float(p["weight"]) for p in positions}
    
    if n == 0:
        return {
            "original_weights": original,
            "benchmark_weights": original,
            "optimized_weights": original,
            "risk_parity_details": {},
            "portfolio_volatility_pct": 0.0
        }
        
    # Get structured covariance
    cov, B = get_structured_covariance(symbols)
    
    # Standardize budgets
    b_vec = np.zeros(n)
    for idx, sym in enumerate(symbols):
        if budgets and sym in budgets:
            b_vec[idx] = max(0.0, float(budgets[sym]))
        else:
            b_vec[idx] = 1.0 / n
            
    if b_vec.sum() <= 0:
        b_vec = np.ones(n) / n
    else:
        b_vec = b_vec / b_vec.sum()
        
    # Run convex solver
    w_opt_risky = solve_risk_parity(cov, b_vec)
    
    # Scale back including Cash
    remaining_weight = 1.0 - cash_weight
    optimized_weights = {}
    for idx, sym in enumerate(symbols):
        optimized_weights[sym] = round(w_opt_risky[idx] * remaining_weight, 6)
    for p in cash_pos:
        optimized_weights[p["symbol"]] = round(p["weight"], 6)
        
    # Standardize benchmark weights including CASH
    bench_weights_final = {}
    w_eq = np.zeros(n)
    for idx, sym in enumerate(symbols):
        w_eq[idx] = benchmark_weights.get(sym, 0.0)
    if w_eq.sum() <= 0:
        w_eq = np.ones(n) / n
    else:
        w_eq = w_eq / w_eq.sum()
        
    for idx, sym in enumerate(symbols):
        bench_weights_final[sym] = round(w_eq[idx] * remaining_weight, 6)
    for p in cash_pos:
        bench_weights_final[p["symbol"]] = round(p["weight"], 6)
        
    # Calculate ACTR & Risk metrics under Optimized weights
    port_vol = np.sqrt(np.dot(w_opt_risky.T, np.dot(cov, w_opt_risky)))
    
    mctr = np.dot(cov, w_opt_risky) / port_vol if port_vol > 0 else np.zeros(n)
    actr = w_opt_risky * mctr
    
    sum_actr = actr.sum()
    actr_pct = actr / sum_actr if sum_actr > 0 else np.ones(n) / n
    
    risk_parity_details = {}
    for idx, sym in enumerate(symbols):
        risk_parity_details[sym] = {
            "risk_budget_pct": round(float(b_vec[idx]) * 100, 2),
            "actual_risk_contribution_pct": round(float(actr_pct[idx]) * 100, 2),
            "mctr_pct": round(float(mctr[idx]) * 100, 4),
            "actr": round(float(actr[idx]), 6),
            "asset_volatility_pct": round(np.sqrt(cov[idx, idx]) * 100, 2)
        }
        
    return {
        "original_weights": original,
        "benchmark_weights": bench_weights_final,
        "optimized_weights": optimized_weights,
        "risk_parity_details": risk_parity_details,
        "portfolio_volatility_pct": round(float(port_vol) * 100, 4)
    }

