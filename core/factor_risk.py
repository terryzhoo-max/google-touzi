"""
Factor risk registry — calibrated from 5-year rolling regression
against SP500/VIX/DXY/TNX/GLD benchmarks (2026-05-07).

Key changes from hardcoded v1:
  - equity_beta:  actual regressed betas (all lowered vs expert guesses)
  - dollar_sensitivity: all negative (correct sign: stronger USD = weaker assets)
  - liquidity_sensitivity: slightly negative (VIX spikes don't linearly hit these ETFs)
  - GOLD_ETF equity_beta: +0.464 (was -0.05 — gold in CNY co-moves with equities)
  - rate_sensitivity: very weak (0.01-0.09) across all assets (was 0.35-0.55)
"""

FACTOR_REGISTRY = {
    "CSI300_ETF": {
        "region": {"China": 1.0},
        "asset_class": {"equity": 1.0},
        "strategy": {"broad_market": 1.0},
        "macro": {"equity_beta": 0.473, "liquidity_sensitivity": -0.051, "dollar_sensitivity": -0.271, "rate_sensitivity": 0.092, "inflation_sensitivity": 0.436},
        "theme": {"China equity": 1.0},
    },
    "CSI500_ETF": {
        "region": {"China": 1.0},
        "asset_class": {"equity": 1.0},
        "strategy": {"small_mid_cap": 1.0},
        "macro": {"equity_beta": 0.656, "liquidity_sensitivity": -0.056, "dollar_sensitivity": -0.318, "rate_sensitivity": 0.041, "inflation_sensitivity": 0.447},
        "theme": {"China equity": 0.9},
    },
    "STAR50_ETF": {
        "region": {"China": 1.0},
        "asset_class": {"equity": 1.0},
        "strategy": {"technology": 1.0},
        "macro": {"equity_beta": 0.733, "liquidity_sensitivity": -0.125, "dollar_sensitivity": -0.306, "rate_sensitivity": 0.013, "inflation_sensitivity": 0.255},
        "theme": {"China technology": 1.0, "semiconductor": 0.35},
    },
    "HSTECH_ETF": {
        "region": {"HongKong": 1.0},
        "asset_class": {"equity": 1.0},
        "strategy": {"technology": 1.0},
        "macro": {"equity_beta": 0.858, "liquidity_sensitivity": -0.138, "dollar_sensitivity": -0.276, "rate_sensitivity": 0.027, "inflation_sensitivity": 0.262},
        "theme": {"Hong Kong growth": 1.0, "US technology": 0.25},
    },
    "SP500_ETF": {
        "region": {"US": 1.0},
        "asset_class": {"equity": 1.0},
        "strategy": {"broad_market": 1.0},
        "macro": {"equity_beta": 1.004, "liquidity_sensitivity": -0.072, "dollar_sensitivity": -0.215, "rate_sensitivity": 0.087, "inflation_sensitivity": 0.253},
        "theme": {"US equity": 1.0},
    },
    "NASDAQ_ETF": {
        "region": {"US": 1.0},
        "asset_class": {"equity": 1.0},
        "strategy": {"technology": 1.0, "growth": 0.8},
        "macro": {"equity_beta": 1.136, "liquidity_sensitivity": -0.07, "dollar_sensitivity": -0.238, "rate_sensitivity": 0.082, "inflation_sensitivity": 0.244},
        "theme": {"US technology": 1.0},
    },
    "NIKKEI225_ETF": {
        "region": {"Japan": 1.0},
        "asset_class": {"equity": 1.0},
        "strategy": {"overseas": 1.0},
        "macro": {"equity_beta": 1.102, "liquidity_sensitivity": -0.133, "dollar_sensitivity": -0.299, "rate_sensitivity": 0.053, "inflation_sensitivity": 0.317},
        "theme": {"Japan equity": 1.0},
    },
    "CHIP_ETF": {
        "region": {"China": 1.0},
        "asset_class": {"equity": 1.0},
        "strategy": {"technology": 1.0},
        "macro": {"equity_beta": 0.802, "liquidity_sensitivity": -0.121, "dollar_sensitivity": -0.29, "rate_sensitivity": 0.023, "inflation_sensitivity": 0.218},
        "theme": {"semiconductor": 1.0, "China technology": 0.6},
    },
    "GOLD_ETF": {
        "region": {"Gold": 1.0},
        "asset_class": {"gold": 1.0},
        "strategy": {"gold": 1.0, "safe_haven": 0.9},
        "macro": {"equity_beta": 0.464, "liquidity_sensitivity": 0.007, "dollar_sensitivity": -0.23, "rate_sensitivity": 0.052, "inflation_sensitivity": 1.0},
        "theme": {"gold hedge": 1.0},
    },
}


def get_factor_exposures_for_symbol(symbol: str) -> list[dict]:
    groups = FACTOR_REGISTRY.get(symbol, {})
    return [
        {
            "factor_group": group,
            "factor_name": name,
            "exposure": exposure,
        }
        for group, exposures in groups.items()
        for name, exposure in exposures.items()
    ]


def _round_groups(groups: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    return {
        group: {
            name: round(value, 6)
            for name, value in sorted(values.items())
            if round(value, 6) != 0
        }
        for group, values in sorted(groups.items())
    }


def _top_factor(groups: dict[str, dict[str, float]]) -> dict:
    group_priority = {
        "macro": 0,
        "theme": 1,
        "region": 2,
        "strategy": 3,
        "asset_class": 4,
    }
    rows = [
        {
            "factor_group": group,
            "factor_name": name,
            "exposure": round(value, 6),
        }
        for group, values in groups.items()
        for name, value in values.items()
    ]
    if not rows:
        return {"factor_group": None, "factor_name": None, "exposure": 0.0}
    return sorted(
        rows,
        key=lambda item: (
            -abs(item["exposure"]),
            group_priority.get(item["factor_group"], 9),
            item["factor_name"],
        ),
    )[0]


def build_factor_risk_snapshot(portfolio_snapshot: dict) -> dict:
    groups: dict[str, dict[str, float]] = {}
    rows = []
    unmapped = []

    for position in portfolio_snapshot["positions"]:
        symbol = position["symbol"]
        weight = float(position["weight"])
        registry = FACTOR_REGISTRY.get(symbol)
        if not registry:
            unmapped.append(symbol)
            rows.append({
                "symbol": symbol,
                "weight": weight,
                "mapped": False,
                "exposures": [],
            })
            continue

        exposures = get_factor_exposures_for_symbol(symbol)
        for item in exposures:
            group = item["factor_group"]
            name = item["factor_name"]
            groups.setdefault(group, {})
            groups[group][name] = groups[group].get(name, 0.0) + weight * float(item["exposure"])
        rows.append({
            "symbol": symbol,
            "weight": weight,
            "mapped": True,
            "exposures": exposures,
        })

    rounded_groups = _round_groups(groups)
    return {
        "metadata": {
            "last_calibrated": "2026-05-07",
            "source": "rolling_regression"
        },
        "factor_groups": rounded_groups,
        "top_factor": _top_factor(rounded_groups),
        "positions": rows,
        "coverage": {
            "mapped_positions": len([row for row in rows if row["mapped"]]),
            "total_positions": len(rows),
            "coverage_ratio": round(
                len([row for row in rows if row["mapped"]]) / max(len(rows), 1),
                6,
            ),
            "unmapped_symbols": unmapped,
        },
    }
