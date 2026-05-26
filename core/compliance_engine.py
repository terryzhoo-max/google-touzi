from dataclasses import asdict, dataclass
import hashlib
import json


@dataclass(frozen=True)
class CompliancePolicy:
    version: str = "compliance_policy_v1"
    max_position_weight: float = 0.5
    max_region_weight: float = 0.6
    max_strategy_weight: float = 0.45
    max_turnover: float = 0.2
    max_trade_weight: float = 0.1
    max_dtl: float = 5.0
    weak_data_score: int = 80
    warning_buffer: float = 0.03


def _policy_hash(policy: CompliancePolicy) -> str:
    payload = asdict(policy)
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _weights(snapshot: dict) -> dict[str, float]:
    return {position["symbol"]: float(position["weight"]) for position in snapshot["positions"]}


def _exposure(snapshot: dict, key: str) -> dict[str, float]:
    return {
        str(name): float(weight)
        for name, weight in snapshot.get(key, {}).items()
    }


def _turnover(current_weights: dict[str, float], target_weights: dict[str, float]) -> float:
    symbols = set(current_weights) | set(target_weights)
    return round(sum(abs(target_weights.get(symbol, 0.0) - current_weights.get(symbol, 0.0)) for symbol in symbols) / 2, 6)


def _adds_risk(current_snapshot: dict, target_snapshot: dict) -> bool:
    current_equity = float(current_snapshot.get("asset_class_exposure", {}).get("equity", 0.0))
    target_equity = float(target_snapshot.get("asset_class_exposure", {}).get("equity", 0.0))
    current_tech = float(current_snapshot.get("strategy_exposure", {}).get("technology", 0.0))
    target_tech = float(target_snapshot.get("strategy_exposure", {}).get("technology", 0.0))
    current_gold = float(current_snapshot.get("asset_class_exposure", {}).get("gold", 0.0))
    target_gold = float(target_snapshot.get("asset_class_exposure", {}).get("gold", 0.0))
    return target_equity > current_equity or target_tech > current_tech or target_gold < current_gold


def _append_limit_results(
    exposure: dict[str, float],
    limit: float,
    warning_buffer: float,
    prefix: str,
    violations: list[str],
    warnings: list[str],
) -> None:
    for name, weight in exposure.items():
        if weight > limit:
            violations.append(f"{prefix}_limit_exceeded:{name}")
        elif weight >= limit - warning_buffer:
            warnings.append(f"{prefix}_limit_near:{name}")


def evaluate_pre_trade_compliance(
    current_snapshot: dict,
    target_snapshot: dict,
    data_quality: dict,
    current_risk: dict,
    policy: CompliancePolicy | None = None,
) -> dict:
    limits = policy or CompliancePolicy()
    current_weights = _weights(current_snapshot)
    target_weights = _weights(target_snapshot)
    violations: list[str] = []
    warnings: list[str] = []
    repair_suggestions: list[str] = []

    turnover = _turnover(current_weights, target_weights)
    if turnover > limits.max_turnover:
        violations.append("turnover_exceeded")
        repair_suggestions.append("Split the rebalance into smaller staged trades.")

    for symbol, weight in target_weights.items():
        trade_size = abs(weight - current_weights.get(symbol, 0.0))
        if weight > limits.max_position_weight:
            violations.append(f"position_limit_exceeded:{symbol}")
        elif weight >= limits.max_position_weight - limits.warning_buffer:
            warnings.append(f"position_limit_near:{symbol}")
        if trade_size > limits.max_trade_weight:
            violations.append(f"trade_size_exceeded:{symbol}")
            repair_suggestions.append("Reduce proposed single-trade size before approval.")

    # 3. Liquidity Risk (Days to Liquidate - DTL) compliance check
    from core.risk_engine import calculate_portfolio_risk
    target_risk = calculate_portfolio_risk(target_snapshot)
    target_liquidity = target_risk.get("liquidity_metrics", {})
    target_dtl = target_liquidity.get("days_to_liquidate", {})
    
    for symbol, dtl in target_dtl.items():
        if dtl > 10.0:  # Block threshold for extreme illiquidity
            violations.append(f"liquidity_limit_exceeded:{symbol}")
            repair_suggestions.append(f"Reduce position qty for {symbol} to lower Days to Liquidate below 10.0 days.")
        elif dtl > limits.max_dtl:  # Warning buffer for liquidity
            warnings.append(f"liquidity_limit_near:{symbol}")

    _append_limit_results(
        _exposure(target_snapshot, "region_exposure"),
        limits.max_region_weight,
        limits.warning_buffer,
        "region",
        violations,
        warnings,
    )
    _append_limit_results(
        _exposure(target_snapshot, "strategy_exposure"),
        limits.max_strategy_weight,
        limits.warning_buffer,
        "strategy",
        violations,
        warnings,
    )

    fallback_active = "fallback" in data_quality.get("flags", [])
    weak_data = int(data_quality.get("score", 0)) < limits.weak_data_score
    risk_is_high = current_risk.get("risk_level") == "high"
    adds_risk = _adds_risk(current_snapshot, target_snapshot)

    if risk_is_high and adds_risk:
        violations.append("no_new_risk_when_risk_high")
        repair_suggestions.append("Reduce equity or technology exposure before adding risk.")
    if (fallback_active or weak_data) and adds_risk:
        violations.append("fallback_data_non_defensive_action")
        repair_suggestions.append("Use observation or defensive risk reduction until data quality recovers.")

    if violations:
        status = "block"
    elif warnings:
        status = "warn"
    else:
        status = "pass"

    score = max(0, 100 - len(violations) * 25 - len(warnings) * 8)
    return {
        "status": status,
        "score": score,
        "violations": list(dict.fromkeys(violations)),
        "warnings": list(dict.fromkeys(warnings)),
        "repair_suggestions": list(dict.fromkeys(repair_suggestions)),
        "turnover": turnover,
        "policy_version": limits.version,
        "policy_hash": _policy_hash(limits),
        "limits": asdict(limits),
    }
