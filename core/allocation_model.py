import hashlib
import json

from core.allocation_policy import (
    AllocationPolicy,
    allocation_policy_to_dict,
    get_default_allocation_policy,
)
from core.compliance_engine import evaluate_pre_trade_compliance
from core.etf_signal_model import build_etf_signals
from core.factor_risk import build_factor_risk_snapshot
from core.portfolio_book import Position, build_portfolio_snapshot
from core.risk_engine import calculate_portfolio_risk
from core.scenario_engine import run_portfolio_scenarios


MODEL_VERSION = "allocation-v1"


def _model_hash(policy_payload: dict) -> str:
    raw = json.dumps({"model_version": MODEL_VERSION, "policy": policy_payload}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _current_weights(portfolio: dict) -> dict[str, float]:
    return {row["symbol"]: float(row["weight"]) for row in portfolio["positions"]}


def _normalize(weights: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, value) for value in weights.values()) or 1.0
    normalized = {symbol: round(max(0.0, value) / total, 6) for symbol, value in weights.items()}
    drift = round(1.0 - sum(normalized.values()), 6)
    if normalized and drift:
        largest = max(normalized, key=normalized.get)
        normalized[largest] = round(normalized[largest] + drift, 6)
    return normalized


def _score_to_delta(score: float, policy: AllocationPolicy) -> float:
    if score >= 68:
        return policy.max_step_weight
    if score >= 58:
        return policy.max_step_weight / 2
    if score <= 32:
        return -policy.max_step_weight
    if score <= 42:
        return -policy.max_step_weight / 2
    return 0.0


def _apply_basic_caps(weights: dict[str, float], portfolio: dict, policy: AllocationPolicy) -> dict[str, float]:
    capped = {symbol: min(weight, policy.max_single_weight) for symbol, weight in weights.items()}
    gold_symbols = [row["symbol"] for row in portfolio["positions"] if row["asset_class"] == "gold"]
    if gold_symbols:
        gold = gold_symbols[0]
        capped[gold] = min(max(capped.get(gold, 0.0), policy.min_gold_weight), policy.max_gold_weight)
    return _normalize(capped)


def _limit_turnover(current: dict[str, float], target: dict[str, float], policy: AllocationPolicy) -> dict[str, float]:
    turnover = sum(abs(target.get(symbol, 0.0) - current.get(symbol, 0.0)) for symbol in set(current) | set(target)) / 2
    if turnover <= policy.max_turnover or turnover <= 0:
        return target
    scale = policy.max_turnover / turnover
    return _normalize({
        symbol: current.get(symbol, 0.0) + (target.get(symbol, 0.0) - current.get(symbol, 0.0)) * scale
        for symbol in set(current) | set(target)
    })


def _snapshot_from_weights(portfolio: dict, target_weights: dict[str, float]) -> dict:
    by_symbol = {row["symbol"]: row for row in portfolio["positions"]}
    total = float(portfolio["total_market_value"])
    positions = []
    for symbol, weight in target_weights.items():
        source = by_symbol[symbol]
        positions.append(Position(
            symbol=symbol,
            name=source["name"],
            asset_class=source["asset_class"],
            currency=source["currency"],
            market_value=round(total * weight, 2),
            quantity=float(source.get("quantity", 0.0)),
            cost_basis=float(source.get("cost_basis", 0.0)),
            region=source.get("region", "Global"),
            strategy=source.get("strategy", "core"),
        ))
    return build_portfolio_snapshot(positions)


def _target_weights(portfolio: dict, signals: list[dict], policy: AllocationPolicy, data_quality: dict) -> dict[str, float]:
    current = _current_weights(portfolio)
    if int(data_quality.get("score", 0) or 0) < policy.data_quality_min_score or "fallback" in data_quality.get("flags", []):
        return current

    adjusted = current.copy()
    for signal in signals:
        symbol = signal["symbol"]
        adjusted[symbol] = adjusted.get(symbol, 0.0) + _score_to_delta(float(signal["composite_score"]), policy)
    adjusted = _apply_basic_caps(_normalize(adjusted), portfolio, policy)
    return _limit_turnover(current, adjusted, policy)


def _proposed_trades(current: dict[str, float], target: dict[str, float], policy: AllocationPolicy) -> list[dict]:
    trades = []
    for symbol in sorted(set(current) | set(target)):
        delta = round(target.get(symbol, 0.0) - current.get(symbol, 0.0), 6)
        if abs(delta) < policy.min_trade_size:
            continue
        trades.append({
            "symbol": symbol,
            "current_weight": round(current.get(symbol, 0.0), 6),
            "target_weight": round(target.get(symbol, 0.0), 6),
            "delta_weight": delta,
            "action": "increase" if delta > 0 else "decrease",
        })
    return trades


def _worst_loss(scenarios: dict) -> float:
    return float((scenarios.get("worst_scenario") or {}).get("portfolio_loss_pct", 0.0))


def _evidence(signals: list[dict], data_quality: dict, compliance: dict, before_risk: dict, after_risk: dict) -> list[dict]:
    rows = []
    if int(data_quality.get("score", 0) or 0) < 80 or "fallback" in data_quality.get("flags", []):
        rows.append({
            "code": "data_quality_guardrail",
            "message": "Data quality forces observation or limited execution.",
            "severity": "warning",
        })
    leaders = sorted(signals, key=lambda row: row["composite_score"], reverse=True)[:3]
    rows.extend({
        "code": "signal_rank",
        "symbol": row["symbol"],
        "message": f"{row['symbol']} composite score {row['composite_score']}",
        "severity": "info",
    } for row in leaders)
    rows.append({
        "code": "risk_delta",
        "message": f"VaR moves from {before_risk['var_95_pct']}% to {after_risk['var_95_pct']}%",
        "severity": "info",
    })
    if compliance.get("status") != "pass":
        rows.append({
            "code": "constraint_guardrail",
            "message": "Allocation target requires compliance review.",
            "severity": "warning",
        })
    return rows


def build_allocation_recommendation(
    portfolio: dict,
    data_quality: dict,
    market_context: dict | None = None,
    policy: AllocationPolicy | None = None,
) -> dict:
    limits = policy or get_default_allocation_policy()
    policy_payload = allocation_policy_to_dict(limits)
    before_risk = calculate_portfolio_risk(portfolio)
    before_scenarios = run_portfolio_scenarios(portfolio)
    factor_risk = build_factor_risk_snapshot(portfolio)
    signals = build_etf_signals(
        portfolio,
        factor_risk=factor_risk,
        risk=before_risk,
        scenarios=before_scenarios,
        data_quality=data_quality,
        market_context=market_context or {},
    )
    current = _current_weights(portfolio)
    target = _target_weights(portfolio, signals, limits, data_quality)
    target_snapshot = _snapshot_from_weights(portfolio, target)
    after_risk = calculate_portfolio_risk(target_snapshot)
    after_scenarios = run_portfolio_scenarios(target_snapshot)
    compliance = evaluate_pre_trade_compliance(portfolio, target_snapshot, data_quality, before_risk)
    trades = _proposed_trades(current, target, limits)
    turnover = round(sum(abs(target.get(symbol, 0.0) - current.get(symbol, 0.0)) for symbol in set(current) | set(target)) / 2, 6)

    weak_data = int(data_quality.get("score", 0) or 0) < limits.data_quality_min_score or "fallback" in data_quality.get("flags", [])
    worsens_stress = _worst_loss(after_scenarios) < _worst_loss(before_scenarios)
    if compliance["status"] == "block" or weak_data or worsens_stress:
        status = "observe"
    elif compliance["status"] == "warn":
        status = "limited"
    else:
        status = "allow"

    return {
        "model_version": MODEL_VERSION,
        "model_hash": _model_hash(policy_payload),
        "status": status,
        "policy": policy_payload,
        "current_weights": current,
        "target_weights": target,
        "signals": signals,
        "proposed_trades": trades,
        "expected_effect": {
            "var_95_delta_pct": round(after_risk["var_95_pct"] - before_risk["var_95_pct"], 2),
            "worst_scenario_delta_pct": round(_worst_loss(after_scenarios) - _worst_loss(before_scenarios), 2),
            "turnover_pct": round(turnover * 100, 2),
            "concentration_delta": round(
                target_snapshot["largest_position"]["weight"] - portfolio["largest_position"]["weight"],
                6,
            ),
        },
        "constraint_result": compliance,
        "evidence_chain": _evidence(signals, data_quality, compliance, before_risk, after_risk),
        "review_schedule": ["T+1", "T+5", "T+20"],
    }
