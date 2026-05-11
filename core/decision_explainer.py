from core.decision_policy import DecisionPolicy, as_policy


def _reason(code: str, severity: str, message: str, evidence: dict | None = None) -> dict:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "evidence": evidence or {},
    }


def _top_key(exposure: dict | None) -> tuple[str | None, float]:
    rows = [
        (str(key), float(value))
        for key, value in (exposure or {}).items()
    ]
    if not rows:
        return None, 0.0
    return max(rows, key=lambda item: item[1])


def _execution_readiness(decision_ticket: dict, what_if: dict, recommended_action: dict) -> str:
    constraints = what_if.get("constraints", {})
    if recommended_action.get("status") == "blocked" or not constraints.get("passed", True):
        return "blocked"
    if decision_ticket.get("decision_status") == "observe":
        return "review_required"
    if recommended_action.get("status") == "staged_execution":
        return "executable_with_review"
    return "executable"


def _review_focus(reason_codes: list[dict]) -> list[str]:
    focus = []
    for item in reason_codes:
        code = item["code"]
        if code in {"scenario_loss_high", "scenario_loss_watch"}:
            focus.append("stress loss path")
        elif code == "portfolio_technology_exposure":
            focus.append("technology exposure")
        elif code == "portfolio_china_exposure":
            focus.append("China exposure")
        elif code.startswith("constraint_"):
            focus.append("constraint breach")
        elif code == "data_quality_weak":
            focus.append("data quality")
        elif code == "risk_budget_exceeded":
            focus.append("risk budget")
    return list(dict.fromkeys(focus))


def _dedupe_reasons(reason_codes: list[dict]) -> list[dict]:
    deduped = {}
    severity_rank = {"critical": 0, "warning": 1, "info": 2, "positive": 3}
    for item in reason_codes:
        existing = deduped.get(item["code"])
        if existing is None:
            deduped[item["code"]] = item
            continue
        if severity_rank.get(item["severity"], 9) < severity_rank.get(existing["severity"], 9):
            deduped[item["code"]] = item
    return list(deduped.values())


def build_decision_explanation(
    decision_ticket: dict,
    data_quality: dict,
    risk: dict,
    scenarios: dict,
    portfolio: dict,
    what_if: dict,
    recommended_action: dict,
    policy: DecisionPolicy | dict | None = None,
) -> dict:
    decision_policy = as_policy(policy or decision_ticket.get("policy_snapshot"))
    policy_snapshot = decision_policy.to_dict()
    reason_codes: list[dict] = []

    for gate in decision_ticket.get("gates_failed", []):
        reason_codes.append(_reason(
            gate,
            "critical",
            f"Decision gate failed: {gate}.",
            {"score": decision_ticket.get("score")},
        ))

    constraints = what_if.get("constraints", {})
    for violation in constraints.get("violations", []):
        reason_codes.append(_reason(
            f"constraint_{violation}",
            "critical",
            f"Trade constraint violation: {violation}.",
            {"passed": constraints.get("passed", False)},
        ))

    if data_quality.get("score", 0) < decision_policy.data_quality_strong_score:
        reason_codes.append(_reason(
            "data_quality_watch",
            "warning",
            "Data quality is below institutional strong threshold.",
            {"score": data_quality.get("score"), "flags": data_quality.get("flags", [])},
        ))

    if risk.get("risk_level") == "medium":
        reason_codes.append(_reason(
            "risk_budget_medium",
            "warning",
            "Portfolio risk is usable but requires staged execution controls.",
            {"var_95_pct": risk.get("var_95_pct")},
        ))
    elif risk.get("risk_level") == "high":
        reason_codes.append(_reason(
            "risk_budget_exceeded",
            "critical",
            "Portfolio risk exceeds the configured risk budget.",
            {"var_95_pct": risk.get("var_95_pct")},
        ))

    worst = scenarios.get("worst_scenario", {})
    worst_loss = float(worst.get("portfolio_loss_pct", 0.0))
    if worst_loss < decision_policy.scenario_loss_limit_pct:
        reason_codes.append(_reason(
            "scenario_loss_high",
            "critical",
            "Worst scenario loss exceeds the institutional loss limit.",
            {"scenario_id": worst.get("id"), "loss_pct": worst_loss},
        ))
    elif worst_loss <= decision_policy.scenario_loss_watch_pct:
        reason_codes.append(_reason(
            "scenario_loss_watch",
            "warning",
            "Worst scenario loss is near the institutional review threshold.",
            {"scenario_id": worst.get("id"), "loss_pct": worst_loss},
        ))
    elif worst_loss < decision_policy.scenario_loss_info_pct:
        reason_codes.append(_reason(
            "scenario_loss_watch",
            "info",
            "Worst scenario loss is manageable but should remain in review.",
            {"scenario_id": worst.get("id"), "loss_pct": worst_loss},
        ))

    top_strategy, top_strategy_weight = _top_key(portfolio.get("strategy_exposure"))
    if top_strategy == "technology" and top_strategy_weight >= decision_policy.technology_exposure_watch:
        reason_codes.append(_reason(
            "portfolio_technology_exposure",
            "warning",
            "Technology strategy exposure is a material portfolio driver.",
            {"weight": round(top_strategy_weight, 6)},
        ))

    china_weight = float((portfolio.get("region_exposure") or {}).get("China", 0.0))
    hong_kong_weight = float((portfolio.get("region_exposure") or {}).get("HongKong", 0.0))
    china_complex_weight = china_weight + hong_kong_weight
    if china_complex_weight >= decision_policy.china_complex_exposure_watch:
        reason_codes.append(_reason(
            "portfolio_china_exposure",
            "warning",
            "China and Hong Kong exposure is a material regional driver.",
            {"weight": round(china_complex_weight, 6)},
        ))

    if what_if.get("improves_risk", False):
        reason_codes.append(_reason(
            "what_if_improves_risk",
            "positive",
            "Proposed rebalance improves risk while passing trade constraints.",
            what_if.get("risk_delta", {}),
        ))

    if not reason_codes:
        reason_codes.append(_reason(
            "all_gates_clear",
            "positive",
            "Decision gates, risk budget, scenario loss and constraints are clear.",
        ))

    reason_codes = _dedupe_reasons(reason_codes)
    severity_rank = {"critical": 0, "warning": 1, "info": 2, "positive": 3}
    code_rank = {
        "scenario_loss_high": 0,
        "scenario_loss_watch": 1,
        "risk_budget_exceeded": 2,
        "risk_budget_medium": 3,
        "data_quality_weak": 4,
        "data_quality_watch": 5,
    }
    primary_driver = sorted(
        reason_codes,
        key=lambda item: (
            severity_rank.get(item["severity"], 9),
            code_rank.get(item["code"], 20),
        ),
    )[0]

    return {
        "policy_version": decision_policy.version,
        "policy_hash": policy_snapshot["policy_hash"],
        "execution_readiness": _execution_readiness(decision_ticket, what_if, recommended_action),
        "primary_driver": primary_driver,
        "reason_codes": reason_codes,
        "supporting_evidence": {
            "decision_status": decision_ticket.get("decision_status"),
            "decision_score": decision_ticket.get("score"),
            "policy_version": decision_policy.version,
            "policy_hash": policy_snapshot["policy_hash"],
            "data_quality_score": data_quality.get("score"),
            "risk_level": risk.get("risk_level"),
            "var_95_pct": risk.get("var_95_pct"),
            "worst_scenario_id": worst.get("id"),
            "worst_scenario_loss_pct": worst.get("portfolio_loss_pct"),
            "top_strategy": top_strategy,
            "top_strategy_weight": round(top_strategy_weight, 6),
            "china_complex_weight": round(china_complex_weight, 6),
        },
        "review_focus": _review_focus(reason_codes),
    }
