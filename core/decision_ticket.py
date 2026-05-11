from core.decision_policy import DecisionPolicy, as_policy


def _portfolio_summary(portfolio: dict | None) -> dict:
    if not portfolio:
        return {}
    return {
        "asset_class_exposure": portfolio.get("asset_class_exposure", {}),
        "region_exposure": portfolio.get("region_exposure", {}),
        "strategy_exposure": portfolio.get("strategy_exposure", {}),
        "currency_exposure": portfolio.get("currency_exposure", {}),
        "largest_position": portfolio.get("largest_position", {}),
        "top_3_weight": portfolio.get("top_3_weight"),
        "concentration_level": portfolio.get("concentration_level"),
    }


def build_decision_ticket(
    data_quality: dict,
    risk: dict,
    scenarios: dict,
    portfolio: dict | None = None,
    policy: DecisionPolicy | dict | None = None,
) -> dict:
    decision_policy = as_policy(policy)
    score = 100
    gates_failed: list[str] = []

    if data_quality["score"] < decision_policy.data_quality_min_score:
        score -= 25
        gates_failed.append("data_quality_weak")
    if risk["risk_level"] == "high":
        score -= 25
        gates_failed.append("risk_budget_exceeded")
    elif risk["risk_level"] == "medium":
        score -= 10
    if scenarios["worst_scenario"]["portfolio_loss_pct"] < decision_policy.scenario_loss_limit_pct:
        score -= 17
        gates_failed.append("scenario_loss_high")
    elif scenarios["worst_scenario"]["portfolio_loss_pct"] <= decision_policy.scenario_loss_watch_pct:
        score -= 7

    if score >= decision_policy.allow_min_score and not gates_failed:
        status = "allow"
        action = "Proceed with constrained execution."
    elif score >= decision_policy.limited_min_score:
        status = "limited"
        action = "Use staged execution and keep cash buffer."
    else:
        status = "observe"
        action = "Hold risk steady until data quality improves."

    policy_snapshot = decision_policy.to_dict()

    return {
        "decision_status": status,
        "score": score,
        "policy_version": decision_policy.version,
        "policy_hash": policy_snapshot["policy_hash"],
        "policy_snapshot": policy_snapshot,
        "suggested_action": action,
        "gates_failed": gates_failed,
        "risk_summary": {
            "var_95_pct": risk["var_95_pct"],
            "worst_scenario_loss_pct": scenarios["worst_scenario"]["portfolio_loss_pct"],
        },
        "portfolio_summary": _portfolio_summary(portfolio),
        "review_schedule": ["T+1", "T+5", "T+20"],
        "invalidates_when": [
            "data quality score changes materially",
            "VaR breaches the configured risk budget",
            "worst scenario loss breaches the configured loss limit",
        ],
    }
