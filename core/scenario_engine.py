SCENARIO_SHOCKS = [
    {
        "id": "equity_liquidity_shock",
        "name": "Equity liquidity shock",
        "shocks": {"equity": -0.15, "bond": 0.0, "gold": 0.0, "cash": 0.0},
        "region_shocks": {},
        "strategy_shocks": {},
    },
    {
        "id": "rate_shock",
        "name": "Rate shock",
        "shocks": {"equity": -0.06, "bond": -0.10, "gold": -0.03, "cash": 0.0},
        "region_shocks": {},
        "strategy_shocks": {},
    },
    {
        "id": "risk_on",
        "name": "Risk-on recovery",
        "shocks": {"equity": 0.08, "bond": -0.02, "gold": -0.01, "cash": 0.0},
        "region_shocks": {},
        "strategy_shocks": {},
    },
    {
        "id": "china_equity_shock",
        "name": "China equity shock",
        "shocks": {},
        "region_shocks": {"China": -0.12, "HongKong": -0.10},
        "strategy_shocks": {},
    },
    {
        "id": "us_tech_shock",
        "name": "US technology shock",
        "shocks": {},
        "region_shocks": {"US": -0.10},
        "strategy_shocks": {},
    },
    {
        "id": "technology_drawdown",
        "name": "Technology drawdown",
        "shocks": {},
        "region_shocks": {},
        "strategy_shocks": {"technology": -0.18},
    },
]


def _scenario_loss(
    snapshot: dict,
    shocks: dict[str, float],
    region_shocks: dict[str, float] | None = None,
    strategy_shocks: dict[str, float] | None = None,
) -> float:
    loss = 0.0
    region_shocks = region_shocks or {}
    strategy_shocks = strategy_shocks or {}
    for p in snapshot["positions"]:
        asset_shock = shocks.get(p["asset_class"], 0.0)
        region_shock = region_shocks.get(p.get("region", "Global"), 0.0)
        strategy_shock = strategy_shocks.get(p.get("strategy", "core"), 0.0)
        loss += float(p["weight"]) * (asset_shock + region_shock + strategy_shock)
    return round(loss * 100, 2)


def run_portfolio_scenarios(snapshot: dict) -> dict:
    rows = []
    for scenario in SCENARIO_SHOCKS:
        rows.append({
            "id": scenario["id"],
            "name": scenario["name"],
            "portfolio_loss_pct": _scenario_loss(
                snapshot,
                scenario["shocks"],
                scenario.get("region_shocks", {}),
                scenario.get("strategy_shocks", {}),
            ),
            "shocks": scenario["shocks"],
            "region_shocks": scenario.get("region_shocks", {}),
            "strategy_shocks": scenario.get("strategy_shocks", {}),
        })

    worst = min(rows, key=lambda row: row["portfolio_loss_pct"])
    return {
        "scenarios": rows,
        "worst_scenario": worst,
    }
