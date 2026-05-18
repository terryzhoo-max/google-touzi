from core.config import settings
import math

# Calibrated from 18-year backtest; overridable via config
_ASSET_VOL = getattr(settings, 'CALIBRATED_EQUITY_VOL', 0.016)
_BOND_VOL   = getattr(settings, 'CALIBRATED_BOND_VOL', 0.007)
_GOLD_VOL   = getattr(settings, 'CALIBRATED_GOLD_VOL', 0.012)

ASSET_CLASS_DAILY_VOL = {
    "equity": _ASSET_VOL,
    "bond": _BOND_VOL,
    "gold": _GOLD_VOL,
    "cash": 0.0001,
}

# Institutional default correlation matrix
# Ensures we capture tail risks of equity/gold moving together, and bond buffering.
CORRELATION_MATRIX = {
    ("equity", "equity"): 1.0,
    ("bond", "bond"): 1.0,
    ("gold", "gold"): 1.0,
    ("cash", "cash"): 1.0,
    ("equity", "bond"): -0.2,
    ("bond", "equity"): -0.2,
    ("equity", "gold"): 0.1,
    ("gold", "equity"): 0.1,
    ("bond", "gold"): 0.2,
    ("gold", "bond"): 0.2,
}

# Default correlations for cross-asset with cash is 0
def get_correlation(c1: str, c2: str) -> float:
    if c1 == c2:
        return 1.0
    if c1 == "cash" or c2 == "cash":
        return 0.0
    return CORRELATION_MATRIX.get((c1, c2), 0.0)

_VAR_HIGH   = getattr(settings, 'CALIBRATED_VAR_HIGH', -6.0)
_VAR_MEDIUM = getattr(settings, 'CALIBRATED_VAR_MEDIUM', -1.0)

def get_asset_volatility(asset_class: str) -> float:
    """Retrieve calibrated daily volatility for inverse volatility targeting."""
    return ASSET_CLASS_DAILY_VOL.get(asset_class, 0.01)


def calculate_portfolio_risk(snapshot: dict) -> dict:
    positions = snapshot["positions"]
    
    # Allow snapshot to inject dynamic vols from history if available
    dynamic_vols = snapshot.get("dynamic_vols", {})
    
    risk_contribution = {}
    variance = 0.0
    max_weight = 0.0

    # 1. Calculate Portfolio Variance using Covariance Matrix
    for i, p1 in enumerate(positions):
        w1 = float(p1["weight"])
        c1 = p1["asset_class"]
        vol1 = dynamic_vols.get(c1, ASSET_CLASS_DAILY_VOL.get(c1, 0.01))
        max_weight = max(max_weight, w1)
        
        asset_var_contrib = 0.0
        for j, p2 in enumerate(positions):
            w2 = float(p2["weight"])
            c2 = p2["asset_class"]
            vol2 = dynamic_vols.get(c2, ASSET_CLASS_DAILY_VOL.get(c2, 0.01))
            corr = get_correlation(c1, c2)
            
            covar = w1 * w2 * vol1 * vol2 * corr
            variance += covar
            asset_var_contrib += covar
            
        risk_contribution[c1] = risk_contribution.get(c1, 0.0) + asset_var_contrib

    daily_vol = math.sqrt(max(variance, 0.0))
    var_95 = round(-1.65 * daily_vol * 100, 2)
    cvar_95 = round(var_95 * 1.35, 2)
    
    risk_total = sum(risk_contribution.values()) or 1.0
    normalized = {
        k: round(v / risk_total, 4)
        for k, v in risk_contribution.items()
    }

    if var_95 <= _VAR_HIGH or max_weight > 0.5:
        level = "high"
    elif var_95 <= _VAR_MEDIUM:
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
