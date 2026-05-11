from dataclasses import dataclass


@dataclass(frozen=True)
class TradeConstraints:
    max_turnover: float = 0.2
    min_cash_weight: float = 0.05
    max_position_weight: float = 0.6
    cost_bps_per_turnover: float = 10.0


def evaluate_trade_constraints(
    target_weights: dict[str, float],
    current_weights: dict[str, float],
    constraints: TradeConstraints | None = None,
) -> dict:
    limits = constraints or TradeConstraints()
    violations: list[str] = []

    turnover = round(
        sum(abs(target_weights.get(symbol, 0.0) - current_weights.get(symbol, 0.0))
            for symbol in set(target_weights) | set(current_weights)) / 2,
        6,
    )

    if turnover > limits.max_turnover:
        violations.append("turnover_exceeded")
    if "CASH" in current_weights or "CASH" in target_weights:
        cash_weight = target_weights.get("CASH", 0.0)
    else:
        cash_weight = limits.min_cash_weight

    if cash_weight < limits.min_cash_weight:
        violations.append("cash_below_minimum")

    for symbol, weight in target_weights.items():
        if weight < 0:
            violations.append(f"negative_weight:{symbol}")
        if weight > limits.max_position_weight:
            violations.append(f"position_limit_exceeded:{symbol}")

    return {
        "passed": not violations,
        "violations": violations,
        "turnover": round(turnover, 4),
        "estimated_cost_bps": round(turnover * limits.cost_bps_per_turnover, 2),
        "limits": {
            "max_turnover": limits.max_turnover,
            "min_cash_weight": limits.min_cash_weight,
            "max_position_weight": limits.max_position_weight,
        },
    }
