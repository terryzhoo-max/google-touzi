def _direction(value: float, threshold: float, higher_is_better: bool = True) -> str:
    if higher_is_better:
        return "above_threshold" if value >= threshold else "below_threshold"
    return "below_threshold" if value <= threshold else "above_threshold"


def _source_quality(data_quality: dict) -> dict:
    flags = data_quality.get("flags", [])
    if "fallback" in flags:
        mode = "fallback"
    elif "stale" in flags:
        mode = "stale"
    else:
        mode = "live"
    return {
        "mode": mode,
        "source": data_quality.get("source"),
        "flags": flags,
        "score": data_quality.get("score"),
    }


def _evidence(metric: str, value, threshold, direction: str, reason: str, source: str = "rule") -> dict:
    return {
        "metric": metric,
        "value": value,
        "threshold": threshold,
        "direction": direction,
        "reason": reason,
        "source": source,
    }


def build_evidence_chain(
    decision_ticket: dict,
    data_quality: dict,
    risk: dict,
    scenarios: dict,
    factor_risk: dict,
    active_risk: dict,
    compliance: dict,
) -> dict:
    quality_score = float(data_quality.get("score", 0))
    var_95 = float(risk.get("var_95_pct", 0.0))
    worst = scenarios.get("worst_scenario", {})
    worst_loss = float(worst.get("portfolio_loss_pct", 0.0))
    top_factor = factor_risk.get("top_factor", {})
    tracking_error = float(active_risk.get("tracking_error_proxy_pct", 0.0))
    largest_active = active_risk.get("largest_active_exposures", [])

    items = [
        _evidence(
            "data_quality_score",
            round(quality_score, 2),
            80,
            _direction(quality_score, 80, higher_is_better=True),
            "Data quality controls the allowed strength of recommendations.",
            data_quality.get("source", "unknown"),
        ),
        _evidence(
            "var_95_pct",
            round(var_95, 2),
            -1.0,
            _direction(var_95, -1.0, higher_is_better=True),
            "Portfolio VaR determines whether execution requires staging or risk reduction.",
        ),
        _evidence(
            "worst_scenario_loss_pct",
            round(worst_loss, 2),
            -4.0,
            _direction(worst_loss, -4.0, higher_is_better=True),
            f"Worst scenario is {worst.get('id')}.",
        ),
        _evidence(
            "top_factor_exposure",
            top_factor.get("exposure", 0.0),
            0.5,
            _direction(abs(float(top_factor.get("exposure", 0.0))), 0.5, higher_is_better=False),
            f"Top factor is {top_factor.get('factor_group')}:{top_factor.get('factor_name')}.",
        ),
        _evidence(
            "tracking_error_proxy_pct",
            round(tracking_error, 4),
            10.0,
            _direction(tracking_error, 10.0, higher_is_better=False),
            "Active risk measures deviation from the policy benchmark.",
        ),
        _evidence(
            "largest_active_exposure",
            largest_active[0] if largest_active else None,
            None,
            "informational",
            "Largest active exposure explains the main benchmark deviation.",
        ),
        _evidence(
            "compliance_status",
            compliance.get("status"),
            "pass",
            "above_threshold" if compliance.get("status") == "pass" else "below_threshold",
            "Pre-trade compliance controls whether action generation can proceed.",
        ),
    ]

    return {
        "policy_version": decision_ticket.get("policy_version"),
        "policy_hash": decision_ticket.get("policy_hash"),
        "decision_status": decision_ticket.get("decision_status"),
        "decision_score": decision_ticket.get("score"),
        "source_quality": _source_quality(data_quality),
        "items": items,
    }
