#!/usr/bin/env python
"""Calibrate FACTOR_REGISTRY exposures using 3-5 years of daily returns.

Maps each portfolio symbol to a Tushare ETF code, then computes:
  equity_beta         → regression against 513500.SH (SP500 proxy)
  liquidity_sensitivity → correlation with VIX changes (via FRED VIXCLS)
  dollar_sensitivity  → correlation with DXY changes (via FRED DTWEXBGS)
  rate_sensitivity    → correlation with TNX changes (via FRED DGS10)
  inflation_sensitivity → correlation with GLD changes (518880.SH)

Output: calibrated FACTOR_REGISTRY dict, ready for factor_risk.py.
"""

import json, sys
import numpy as np
import pandas as pd
sys.path.insert(0, ".")

from core.data_providers import _tushare_items, _ts_items_to_series, _fred_series
from core.factor_risk import FACTOR_REGISTRY

# Symbol → Tushare code + API mapping
TS_MAP = {
    "CSI300_ETF":  ("index_daily", "000300.SH"),
    "CSI500_ETF":  ("index_daily", "000905.SH"),
    "STAR50_ETF":  ("fund_daily",  "588000.SH"),
    "HSTECH_ETF":  ("fund_daily",  "513180.SH"),
    "SP500_ETF":   ("fund_daily",  "513500.SH"),
    "NASDAQ_ETF":  ("fund_daily",  "513100.SH"),
    "NIKKEI225_ETF": ("fund_daily", "513520.SH"),
    "CHIP_ETF":    ("fund_daily",  "159995.SZ"),
    "GOLD_ETF":    ("fund_daily",  "518880.SH"),
}

# Market benchmarks for regression
MARKET_PROXY = ("fund_daily", "513500.SH")   # S&P 500
BOND_PROXY   = ("fund_daily", "511260.SH")   # 10Y China bond (directional)
GOLD_PROXY   = ("fund_daily", "518880.SH")


def _load_series(api: str, code: str, days: int) -> pd.Series:
    """Fetch daily close from Tushare → returns series."""
    import datetime
    end = datetime.date.today()
    start = end - datetime.timedelta(days=days + 30)
    try:
        items = _tushare_items(api, {
            "ts_code": code,
            "start_date": start.strftime("%Y%m%d"),
            "end_date": end.strftime("%Y%m%d"),
        }, "trade_date,close")
        s = _ts_items_to_series(items, date_col=0, val_col=1, name=code)
        return s.pct_change().dropna()
    except Exception as e:
        print(f"  [warn] {api}/{code}: {e}")
        return pd.Series(dtype=float)


def _rolling_beta(y: pd.Series, x: pd.Series, window: int = 252) -> float:
    """Compute trailing beta = cov(y,x)/var(x) over the last `window` days."""
    common = y.dropna().index.intersection(x.dropna().index)
    if len(common) < window // 2:
        return 0.0
    yy = y[common].iloc[-window:]
    xx = x[common].iloc[-window:]
    if len(yy) < 60:
        return 0.0
    cov = np.cov(yy, xx)[0, 1]
    var = np.var(xx)
    return float(cov / var) if var > 1e-9 else 0.0


def _rolling_corr(y: pd.Series, x: pd.Series, window: int = 252) -> float:
    """Trailing Pearson correlation."""
    common = y.dropna().index.intersection(x.dropna().index)
    if len(common) < window // 2:
        return 0.0
    yy = y[common].iloc[-window:]
    xx = x[common].iloc[-window:]
    if len(yy) < 60:
        return 0.0
    return float(yy.corr(xx) or 0.0)


def main():
    print("[calibrate_factors] Loading benchmark series …")
    days = 365 * 5  # 5 years

    market_ret = _load_series(*MARKET_PROXY, days)
    gold_ret   = _load_series(*GOLD_PROXY, days)
    bond_ret   = _load_series(*BOND_PROXY, days)

    # VIX and TNX from FRED
    try:
        vix_raw = _fred_series("VIXCLS", limit=days).pct_change().dropna()
    except Exception:
        vix_raw = pd.Series(dtype=float)
    try:
        tnx_raw = _fred_series("DGS10", limit=days).diff().dropna()
    except Exception:
        tnx_raw = pd.Series(dtype=float)
    try:
        dxy_raw = _fred_series("DTWEXBGS", limit=days).pct_change().dropna()
    except Exception:
        dxy_raw = pd.Series(dtype=float)

    calibrated = {}
    for symbol, (api, code) in TS_MAP.items():
        print(f"  calibrating {symbol} ({code}) …")
        asset_ret = _load_series(api, code, days)
        if asset_ret.empty:
            calibrated[symbol] = FACTOR_REGISTRY.get(symbol, {})
            print(f"    ⚠ no data, keeping hardcoded")
            continue

        equity_beta  = round(_rolling_beta(asset_ret, market_ret), 3)
        liquidity    = round(_rolling_corr(asset_ret, vix_raw), 3) if not vix_raw.empty else FACTOR_REGISTRY.get(symbol, {}).get("macro", {}).get("liquidity_sensitivity", 0)
        dollar       = round(_rolling_corr(asset_ret, dxy_raw), 3) if not dxy_raw.empty else FACTOR_REGISTRY.get(symbol, {}).get("macro", {}).get("dollar_sensitivity", 0)
        rate_sens    = round(_rolling_corr(asset_ret, tnx_raw), 3) if not tnx_raw.empty else FACTOR_REGISTRY.get(symbol, {}).get("macro", {}).get("rate_sensitivity", 0)
        inflation    = round(_rolling_corr(asset_ret, gold_ret), 3) if not gold_ret.empty else FACTOR_REGISTRY.get(symbol, {}).get("macro", {}).get("inflation_sensitivity", 0)

        orig = FACTOR_REGISTRY.get(symbol, {})
        calibrated[symbol] = {
            "region":      orig.get("region", {}),
            "asset_class": orig.get("asset_class", {}),
            "strategy":    orig.get("strategy", {}),
            "macro": {
                "equity_beta":          equity_beta,
                "liquidity_sensitivity": liquidity,
                "dollar_sensitivity":    dollar,
                "rate_sensitivity":      rate_sens,
                "inflation_sensitivity": inflation,
            },
            "theme":       orig.get("theme", {}),
        }
        print(f"    equity_beta={equity_beta} dollar={dollar} rate={rate_sens} liq={liquidity} infl={inflation}")

    print("\n[calibrate_factors] DONE. Calibrated FACTOR_REGISTRY:")
    print(json.dumps(calibrated, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
