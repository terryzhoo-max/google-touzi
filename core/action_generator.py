def _format_adjustment(symbol: str, delta: float) -> str:
    magnitude = abs(delta) * 100
    verb = "Reduce" if delta < 0 else "add"
    return f"{verb} {symbol} by {magnitude:.1f}%"


def _format_action(adjustments: dict[str, float]) -> str:
    parts = [_format_adjustment(symbol, delta) for symbol, delta in adjustments.items() if delta != 0]
    if not parts:
        return "Hold current allocation."
    return ", ".join(parts) + "."


def generate_action_recommendation(decision_ticket: dict, what_if: dict) -> dict:
    constraints = what_if.get("constraints", {})
    compliance = what_if.get("compliance", {})
    risk_delta = what_if.get("risk_delta", {})

    if compliance.get("status") == "block":
        violations = compliance.get("violations", [])
        repairs = compliance.get("repair_suggestions", [])
        return {
            "status": "blocked",
            "action": "Do not execute the proposed rebalance.",
            "risk_improvement": " ".join(repairs) or "Pre-trade compliance blocked the proposed rebalance.",
            "rationale": f"Compliance violations: {', '.join(violations)}",
            "requires_review": True,
        }

    if not constraints.get("passed", False):
        violations = constraints.get("violations", [])
        return {
            "status": "blocked",
            "action": "Do not execute the proposed rebalance.",
            "risk_improvement": "Risk improvement is not actionable because trade constraints failed.",
            "rationale": f"Constraint violations: {', '.join(violations)}",
            "requires_review": True,
        }

    if not what_if.get("improves_risk", False):
        return {
            "status": "observe",
            "action": "Hold current allocation.",
            "risk_improvement": "Proposed rebalance does not improve portfolio risk.",
            "rationale": "What-if analysis did not pass the risk-improvement gate.",
            "requires_review": True,
        }

    if decision_ticket.get("decision_status") == "observe":
        return {
            "status": "observe",
            "action": "Hold current allocation.",
            "risk_improvement": "Decision ticket remains in observe mode.",
            "rationale": "Decision gate did not permit execution.",
            "requires_review": True,
        }

    return {
        "status": "staged_execution",
        "action": _format_action(what_if.get("adjustments", {})),
        "risk_improvement": (
            f"VaR improves by {risk_delta.get('var_95_pct', 0)} pct points; "
            f"worst scenario improves by {risk_delta.get('worst_scenario_loss_pct', 0)} pct points."
        ),
        "rationale": "What-if improves risk and all trade constraints passed.",
        "requires_review": False,
    }
