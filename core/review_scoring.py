def _verdict(score: int) -> str:
    if score >= 80:
        return "effective"
    if score >= 50:
        return "mixed"
    return "ineffective"


def score_review(audit_record: dict, review_window: str) -> dict:
    payload = audit_record.get("payload", {})
    action = payload.get("recommended_action", {})
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

    score = max(0, min(100, score))
    return {
        "ticket_id": audit_record["ticket_id"],
        "review_window": review_window,
        "score": score,
        "verdict": _verdict(score),
        "evidence": evidence,
    }
