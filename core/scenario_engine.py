from core.factor_risk import FACTOR_REGISTRY

SCENARIO_SHOCKS = [
    {
        "id": "equity_liquidity_shock",
        "name": "Equity liquidity shock",
        "name_zh": "权益流动性枯竭",
        "macro_shocks": {"equity_beta": -0.15, "liquidity_sensitivity": -0.10},
        "theme_shocks": {},
        "region_shocks": {},
    },
    {
        "id": "rate_shock",
        "name": "Rate shock",
        "name_zh": "全球利率飙升",
        "macro_shocks": {"rate_sensitivity": -0.30, "equity_beta": -0.08, "dollar_sensitivity": 0.10},
        "theme_shocks": {},
        "region_shocks": {},
    },
    {
        "id": "risk_on",
        "name": "Risk-on recovery",
        "name_zh": "避险情绪消退",
        "macro_shocks": {"equity_beta": 0.10, "liquidity_sensitivity": 0.05, "dollar_sensitivity": -0.05},
        "theme_shocks": {},
        "region_shocks": {},
    },
    {
        "id": "china_equity_shock",
        "name": "China equity shock",
        "name_zh": "亚太权益震荡",
        "macro_shocks": {},
        "theme_shocks": {"China equity": -0.15},
        "region_shocks": {"China": -0.12, "HongKong": -0.10},
    },
    {
        "id": "us_tech_shock",
        "name": "US technology shock",
        "name_zh": "北美科技股崩盘",
        "macro_shocks": {"equity_beta": -0.05},
        "theme_shocks": {"US technology": -0.25},
        "region_shocks": {"US": -0.10},
    },
    {
        "id": "technology_drawdown",
        "name": "Technology drawdown",
        "name_zh": "核心科技估值杀跌",
        "macro_shocks": {},
        "theme_shocks": {"semiconductor": -0.20, "China technology": -0.15, "US technology": -0.15},
        "region_shocks": {},
    },
]


def _scenario_loss(
    snapshot: dict,
    macro_shocks: dict[str, float],
    theme_shocks: dict[str, float] | None = None,
    region_shocks: dict[str, float] | None = None,
) -> float:
    loss = 0.0
    theme_shocks = theme_shocks or {}
    region_shocks = region_shocks or {}
    
    for p in snapshot["positions"]:
        symbol = p["symbol"]
        weight = float(p["weight"])
        
        # Pull beta/exposure from registry, fallback to asset_class heuristics
        registry = FACTOR_REGISTRY.get(symbol, {})
        
        asset_loss = 0.0
        
        # 1. Macro Factor transmission (Beta-adjusted)
        macro_exp = registry.get("macro", {})
        for factor, shock in macro_shocks.items():
            # Fallback logic for unmapped symbols
            beta = macro_exp.get(factor, 0.0)
            if not macro_exp and factor == "equity_beta" and p.get("asset_class") == "equity":
                beta = 1.0  # Default beta for unknown equity
            elif not macro_exp and factor == "equity_beta" and p.get("asset_class") == "gold":
                beta = 0.4  # Default beta for unknown gold
                
            asset_loss += beta * shock
            
        # 2. Theme transmission
        theme_exp = registry.get("theme", {})
        for theme, shock in theme_shocks.items():
            exposure = theme_exp.get(theme, 0.0)
            if not theme_exp and p.get("strategy") == "technology" and "technology" in theme:
                exposure = 1.0
            elif not theme_exp and p.get("strategy") == "technology" and "semiconductor" in theme:
                exposure = 1.0
            asset_loss += exposure * shock
            
        # 3. Regional transmission
        region_exp = registry.get("region", {})
        for region, shock in region_shocks.items():
            exposure = region_exp.get(region, 0.0)
            if not region_exp and p.get("region") == region:
                exposure = 1.0 # Default region exposure
            asset_loss += exposure * shock
            
        loss += weight * asset_loss
        
    return round(loss * 100, 2)


def run_portfolio_scenarios(snapshot: dict) -> dict:
    rows = []
    for scenario in SCENARIO_SHOCKS:
        rows.append({
            "id": scenario["id"],
            "name": scenario["name"],
            "name_zh": scenario.get("name_zh", ""),
            "portfolio_loss_pct": _scenario_loss(
                snapshot,
                scenario.get("macro_shocks", {}),
                scenario.get("theme_shocks", {}),
                scenario.get("region_shocks", {}),
            ),
            "shocks": scenario.get("macro_shocks", {}),
            "region_shocks": scenario.get("region_shocks", {}),
            "strategy_shocks": scenario.get("theme_shocks", {}),
        })

    if not rows:
        return {"scenarios": [], "worst_scenario": None}
        
    worst = min(rows, key=lambda row: row["portfolio_loss_pct"])
    return {
        "scenarios": rows,
        "worst_scenario": worst,
    }
