from core.portfolio_book import Position, build_portfolio_snapshot
from core.risk_engine import calculate_portfolio_risk
from core.scenario_engine import run_portfolio_scenarios
from core.trade_constraints import TradeConstraints, evaluate_trade_constraints


def _current_weights(snapshot: dict) -> dict[str, float]:
    return {p["symbol"]: float(p["weight"]) for p in snapshot["positions"]}


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    if abs(total - 1.0) > 0.00001:
        raise ValueError("target weights must sum to 1.0")
    return {symbol: round(weight / total, 6) for symbol, weight in weights.items()}


def _apply_adjustments(current_weights: dict[str, float], adjustments: dict[str, float]) -> dict[str, float]:
    target = current_weights.copy()
    for symbol, delta in adjustments.items():
        target[symbol] = round(target.get(symbol, 0.0) + float(delta), 6)
    return _normalize_weights(target)


def _snapshot_from_weights(current_snapshot: dict, target_weights: dict[str, float]) -> dict:
    by_symbol = {p["symbol"]: p for p in current_snapshot["positions"]}
    total_value = float(current_snapshot["total_market_value"])
    positions = []
    for symbol, weight in target_weights.items():
        source = by_symbol.get(symbol, {
            "symbol": symbol,
            "name": symbol,
            "asset_class": "cash" if symbol == "CASH" else "equity",
            "currency": "USD",
            "quantity": 0.0,
            "cost_basis": 0.0,
            "region": "Global",
            "strategy": "core",
        })
        positions.append(Position(
            symbol=source["symbol"],
            name=source["name"],
            asset_class=source["asset_class"],
            currency=source["currency"],
            market_value=round(total_value * weight, 2),
            quantity=float(source.get("quantity", 0.0)),
            cost_basis=float(source.get("cost_basis", 0.0)),
            region=source.get("region", "Global"),
            strategy=source.get("strategy", "core"),
        ))
    return build_portfolio_snapshot(positions)


def build_default_risk_reduction_adjustments(current_snapshot: dict) -> dict[str, float]:
    positions = current_snapshot["positions"]
    equity_positions = [p for p in positions if p["asset_class"] == "equity"]
    defensive_positions = [p for p in positions if p["asset_class"] in {"gold", "cash"}]
    if not equity_positions or not defensive_positions:
        return {}

    reduce_position = max(equity_positions, key=lambda p: float(p["weight"]))
    add_position = max(defensive_positions, key=lambda p: (p["asset_class"] == "gold", float(p["weight"])))
    if reduce_position["symbol"] == add_position["symbol"]:
        return {}
    return {
        reduce_position["symbol"]: -0.05,
        add_position["symbol"]: 0.05,
    }


def run_what_if(
    current_snapshot: dict,
    adjustments: dict[str, float],
    constraints: TradeConstraints | None = None,
) -> dict:
    current_weights = _current_weights(current_snapshot)
    target_weights = _apply_adjustments(current_weights, adjustments)
    target_snapshot = _snapshot_from_weights(current_snapshot, target_weights)

    before_risk = calculate_portfolio_risk(current_snapshot)
    after_risk = calculate_portfolio_risk(target_snapshot)
    before_scenarios = run_portfolio_scenarios(current_snapshot)
    after_scenarios = run_portfolio_scenarios(target_snapshot)
    constraint_result = evaluate_trade_constraints(target_weights, current_weights, constraints)

    risk_delta = {
        "var_95_pct": round(after_risk["var_95_pct"] - before_risk["var_95_pct"], 2),
        "cvar_95_pct": round(after_risk["cvar_95_pct"] - before_risk["cvar_95_pct"], 2),
        "worst_scenario_loss_pct": round(
            after_scenarios["worst_scenario"]["portfolio_loss_pct"]
            - before_scenarios["worst_scenario"]["portfolio_loss_pct"],
            2,
        ),
    }

    improves_risk = (
        risk_delta["var_95_pct"] > 0
        and risk_delta["worst_scenario_loss_pct"] >= 0
        and constraint_result["passed"]
    )

    return {
        "adjustments": adjustments,
        "target_weights": target_weights,
        "before": {
            "portfolio": current_snapshot,
            "risk": before_risk,
            "scenarios": before_scenarios,
        },
        "after": {
            "portfolio": target_snapshot,
            "risk": after_risk,
            "scenarios": after_scenarios,
        },
        "risk_delta": risk_delta,
        "constraints": constraint_result,
        "improves_risk": improves_risk,
    }
