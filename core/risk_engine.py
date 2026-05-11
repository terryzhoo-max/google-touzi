ASSET_CLASS_DAILY_VOL = {
    "equity": 0.016,
    "bond": 0.007,
    "gold": 0.012,
    "cash": 0.0001,
}


def calculate_portfolio_risk(snapshot: dict) -> dict:
    positions = snapshot["positions"]
    risk_contribution = {}
    variance = 0.0
    max_weight = 0.0

    for p in positions:
        weight = float(p["weight"])
        asset_class = p["asset_class"]
        vol = ASSET_CLASS_DAILY_VOL.get(asset_class, 0.01)
        contribution = (weight * vol) ** 2
        variance += contribution
        risk_contribution[asset_class] = risk_contribution.get(asset_class, 0.0) + contribution
        max_weight = max(max_weight, weight)

    daily_vol = variance ** 0.5
    var_95 = round(-1.65 * daily_vol * 100, 2)
    cvar_95 = round(var_95 * 1.35, 2)
    risk_total = sum(risk_contribution.values()) or 1.0
    normalized = {
        k: round(v / risk_total, 4)
        for k, v in risk_contribution.items()
    }

    if var_95 <= -6 or max_weight > 0.5:
        level = "high"
    elif var_95 <= -1:
        level = "medium"
    else:
        level = "low"

    return {
        "daily_vol_pct": round(daily_vol * 100, 2),
        "var_95_pct": var_95,
        "cvar_95_pct": cvar_95,
        "max_single_position_weight": round(max_weight, 4),
        "risk_contribution": normalized,
        "risk_level": level,
    }
