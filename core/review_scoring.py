def _verdict(score: int) -> str:
    if score >= 80:
        return "effective"
    if score >= 50:
        return "mixed"
    return "ineffective"


def _score_allocation_model(allocation_model: dict, evidence: list[str]) -> tuple[int, dict]:
    if not allocation_model:
        return 0, {}

    score_delta = 0
    status = allocation_model.get("status")
    constraint_status = (allocation_model.get("constraint_result") or {}).get("status")
    expected = allocation_model.get("expected_effect") or {}
    evidence_chain = allocation_model.get("evidence_chain") or []
    var_delta = float(expected.get("var_95_delta_pct", 0.0) or 0.0)
    stress_delta = float(expected.get("worst_scenario_delta_pct", 0.0) or 0.0)
    turnover_pct = float(expected.get("turnover_pct", 0.0) or 0.0)

    if status == "allow":
        score_delta += 8
        evidence.append("allocation_model_allow")
    elif status == "limited":
        score_delta += 4
        evidence.append("allocation_model_limited")
    elif status == "observe":
        score_delta -= 6
        evidence.append("allocation_model_observe")

    if constraint_status == "pass":
        score_delta += 4
        evidence.append("allocation_constraints_pass")
    elif constraint_status == "warn":
        evidence.append("allocation_constraints_warn")
    elif constraint_status == "block":
        score_delta -= 8
        evidence.append("allocation_constraints_block")

    if var_delta > 0 and stress_delta >= 0:
        score_delta += 5
        evidence.append("allocation_risk_improved")
    elif var_delta < 0 or stress_delta < 0:
        score_delta -= 5
        evidence.append("allocation_risk_worsened")

    if turnover_pct > 10:
        score_delta -= 3
        evidence.append("allocation_turnover_high")

    return score_delta, {
        "status": status,
        "constraint_status": constraint_status,
        "var_95_delta_pct": var_delta,
        "worst_scenario_delta_pct": stress_delta,
        "turnover_pct": turnover_pct,
        "evidence_count": len(evidence_chain),
    }


def score_review(audit_record: dict, review_window: str) -> dict:
    payload = audit_record.get("payload", {})
    action = payload.get("recommended_action", {})
    attribution = payload.get("attribution", {})
    what_if = payload.get("what_if", {})
    risk_delta = what_if.get("risk_delta", {})
    constraints = what_if.get("constraints", {})
    allocation_model = payload.get("allocation_model", {})

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

    allocation_delta, allocation_summary = _score_allocation_model(allocation_model, evidence)
    score += allocation_delta

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
        "allocation_model": allocation_summary,
    }
