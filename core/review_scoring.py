def _verdict(score: int) -> str:
    if score >= 80:
        return "effective"
    if score >= 50:
        return "mixed"
    return "ineffective"


def score_review(audit_record: dict, review_window: str) -> dict:
    payload = audit_record.get("payload", {})
    action = payload.get("recommended_action", {})
    attribution = payload.get("attribution", {})
    what_if = payload.get("what_if", {})
    risk_delta = what_if.get("risk_delta", {})
    constraints = what_if.get("constraints", {})

    score = 50
    evidence: list[str] = []

    if action.get("status") in {"staged_execution", "allow"}:
        score += 20
        evidence.append("action_executable")
    elif action.get("status") == "blocked":
        score -= 20
        evidence.append("action_blocked")

    if constraints.get("passed") is True:
        score += 10
        evidence.append("constraints_passed")
    else:
        score -= 10
        evidence.append("constraints_failed")

    if risk_delta.get("var_95_pct", 0) > 0 and risk_delta.get("worst_scenario_loss_pct", 0) >= 0:
        score += 10
        evidence.append("risk_improved")
    else:
        evidence.append("risk_worsened")

    decision_effect = float(attribution.get("decision_effect", 0.0) or 0.0)
    selection_effect = float(attribution.get("selection_effect", 0.0) or 0.0)
    currency_effect = float(attribution.get("currency_effect", 0.0) or 0.0)
    if decision_effect > 0:
        score += 10
        evidence.append("attribution_positive")
    elif decision_effect < 0:
        score -= 10
        evidence.append("attribution_negative")

    if selection_effect > 0:
        evidence.append("selection_positive")
    elif selection_effect < 0:
        evidence.append("selection_negative")

    if currency_effect < 0:
        score -= 2
        evidence.append("currency_drag")
    elif currency_effect > 0:
        score += 2
        evidence.append("currency_tailwind")

    score = max(0, min(100, score))
    return {
        "ticket_id": audit_record["ticket_id"],
        "review_window": review_window,
        "score": score,
        "verdict": _verdict(score),
        "evidence": evidence,
        "attribution": {
            "period": attribution.get("period"),
            "decision_effect": decision_effect,
            "allocation_effect": float(attribution.get("allocation_effect", 0.0) or 0.0),
            "selection_effect": selection_effect,
            "currency_effect": currency_effect,
        },
    }
