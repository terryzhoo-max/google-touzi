import os

from core.action_generator import generate_action_recommendation
from core.allocation_model import build_allocation_recommendation
from core.allocation_policy import allocation_policy_to_dict, get_default_allocation_policy
from core.attribution_engine import build_attribution_snapshot
from core.benchmark_book import benchmark_to_dict, build_active_risk_snapshot
from core.compliance_engine import evaluate_pre_trade_compliance
from core.config import settings
from core.data_providers import get_attribution_returns
from core.data_quality import score_payload
from core.decision_explainer import build_decision_explanation
from core.decision_policy import get_default_decision_policy
from core.decision_ticket import build_decision_ticket
from core.evidence_chain import build_evidence_chain
from core.factor_risk import build_factor_risk_snapshot
from core.portfolio_book import build_portfolio_snapshot, load_portfolio_positions
from core.risk_engine import calculate_portfolio_risk
from core.scenario_engine import run_portfolio_scenarios
from core.what_if_engine import build_default_risk_reduction_adjustments, run_what_if


def run_historical_replication_analysis_wrapper(portfolio_snapshot: dict, benchmark, portfolio_name: str | None) -> dict:
    try:
        from core.market_data import fetch_yfinance_data
        from core.portfolio_opt import calculate_risk_parity_allocation
        from core.scenario_engine import run_historical_replication_analysis

        try:
            vix_data = fetch_yfinance_data("^VIX", "vix")
            vix = float(vix_data["data"][-1]) if vix_data.get("data") else 20.0
        except Exception:
            vix = 20.0

        benchmark_weights = benchmark.positions
        rp_res = calculate_risk_parity_allocation(portfolio_snapshot, benchmark_weights, None)
        risk_parity_weights = rp_res["optimized_weights"]

        return run_historical_replication_analysis(
            portfolio_snapshot,
            benchmark_weights,
            risk_parity_weights,
            vix=vix,
        )
    except Exception:
        return {}


def build_institutional_payload(
    portfolio_name: str | None = None,
    allocation_builder=build_allocation_recommendation,
    market_context_builder=None,
) -> dict:
    policy = get_default_decision_policy()
    portfolio = build_institutional_portfolio(portfolio_name)
    data_quality = build_institutional_data_quality(portfolio_name)
    risk = calculate_portfolio_risk(portfolio)
    scenarios = run_portfolio_scenarios(portfolio)
    factor_risk = build_factor_risk_snapshot(portfolio)

    from core.benchmark_book import get_portfolio_benchmark

    benchmark = get_portfolio_benchmark(portfolio_name)
    benchmark_payload = benchmark_to_dict(benchmark)
    active_risk = build_active_risk_snapshot(portfolio, benchmark)

    all_symbols = list(set([p["symbol"] for p in portfolio.get("positions", [])] + list(benchmark.positions.keys())))
    returns_t1 = get_attribution_returns(all_symbols, period="T-1")
    attribution = build_attribution_snapshot(
        portfolio,
        benchmark,
        period="T-1",
        asset_returns=returns_t1,
        benchmark_returns=returns_t1,
    )

    ticket = build_decision_ticket(data_quality, risk, scenarios, portfolio=portfolio, policy=policy)
    what_if = build_institutional_what_if(portfolio, build_default_risk_reduction_adjustments(portfolio), portfolio_name)
    action = generate_action_recommendation(ticket, what_if)
    compliance = what_if["compliance"]
    allocation_model = build_institutional_allocation_model(
        portfolio=portfolio,
        data_quality=data_quality,
        allocation_builder=allocation_builder,
        market_context_builder=market_context_builder,
    )
    evidence_chain = build_evidence_chain(
        decision_ticket=ticket,
        data_quality=data_quality,
        risk=risk,
        scenarios=scenarios,
        factor_risk=factor_risk,
        active_risk=active_risk,
        compliance=compliance,
    )
    explanation = build_decision_explanation(
        decision_ticket=ticket,
        data_quality=data_quality,
        risk=risk,
        scenarios=scenarios,
        portfolio=portfolio,
        what_if=what_if,
        recommended_action=action,
        policy=policy,
    )
    crisis_path_report = run_historical_replication_analysis_wrapper(portfolio, benchmark, portfolio_name)

    return {
        "policy": policy,
        "portfolio": portfolio,
        "data_quality": data_quality,
        "risk": risk,
        "scenarios": scenarios,
        "factor_risk": factor_risk,
        "benchmark": benchmark_payload,
        "active_risk": active_risk,
        "attribution": attribution,
        "compliance": compliance,
        "evidence_chain": evidence_chain,
        "decision_ticket": ticket,
        "what_if": what_if,
        "recommended_action": action,
        "allocation_model": allocation_model,
        "decision_explanation": explanation,
        "historical_crisis_replication": crisis_path_report,
        "audit": {
            "recorded": False,
            "record_endpoint": "/api/institutional/audit/decisions",
            "review_schedule": ticket["review_schedule"],
        },
    }


def build_institutional_portfolio(portfolio_name: str | None = None) -> dict:
    return build_portfolio_snapshot(load_portfolio_positions(portfolio_name or settings.PORTFOLIO_BOOK_PATH))


def build_institutional_data_quality(portfolio_name: str | None = None) -> dict:
    target_path = portfolio_name or settings.PORTFOLIO_BOOK_PATH
    has_portfolio_file = False
    if target_path:
        if os.path.exists(target_path):
            has_portfolio_file = True
        else:
            data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
            if os.path.exists(os.path.join(data_dir, f"{target_path}_portfolio.json")) or os.path.exists(os.path.join(data_dir, f"{target_path}.json")):
                has_portfolio_file = True

    source = "portfolio_file" if has_portfolio_file else "sample_portfolio"
    return score_payload(
        source=source,
        updated_secs_ago=0,
        stale_after_sec=3600,
        fallback_used=not has_portfolio_file,
        missing_ratio=0.0,
        anomaly_count=0,
    )


def build_institutional_market_context(
    valuation_fn=None,
    domestic_rotation_fn=None,
    global_rotation_fn=None,
) -> dict:
    from core.asset_rotation import get_domestic_etf_rotation, get_global_etf_rotation
    from core.valuation import get_valuation

    valuation_fn = valuation_fn or get_valuation
    domestic_rotation_fn = domestic_rotation_fn or get_domestic_etf_rotation
    global_rotation_fn = global_rotation_fn or get_global_etf_rotation

    def collect(name: str, fn, fallback: dict) -> tuple[dict, str, str | None]:
        try:
            payload = fn()
            if not isinstance(payload, dict) or payload.get("error"):
                return fallback, "degraded", str(payload.get("error", "empty payload")) if isinstance(payload, dict) else "invalid payload"
            return payload, "ok", None
        except Exception as exc:
            return fallback, "degraded", str(exc)

    valuation, valuation_status, valuation_error = collect("valuation", valuation_fn, {})
    domestic_rotation, domestic_status, domestic_error = collect("domestic_rotation", domestic_rotation_fn, {})
    global_rotation, global_status, global_error = collect("global_rotation", global_rotation_fn, {})

    source_status = {
        "valuation": valuation_status,
        "domestic_rotation": domestic_status,
        "global_rotation": global_status,
    }
    source_errors = {
        name: error
        for name, error in {
            "valuation": valuation_error,
            "domestic_rotation": domestic_error,
            "global_rotation": global_error,
        }.items()
        if error
    }

    return {
        "macro_decision": {"score": 50, "signal_en": "NEUTRAL"},
        "valuation": valuation,
        "domestic_rotation": domestic_rotation,
        "global_rotation": global_rotation,
        "source_status": source_status,
        "source_errors": source_errors,
    }


def build_institutional_allocation_model(
    portfolio: dict | None = None,
    data_quality: dict | None = None,
    allocation_builder=build_allocation_recommendation,
    market_context_builder=None,
) -> dict:
    portfolio = portfolio or build_institutional_portfolio()
    data_quality = data_quality or build_institutional_data_quality()
    market_context_builder = market_context_builder or build_institutional_market_context
    try:
        return allocation_builder(
            portfolio,
            data_quality=data_quality,
            market_context=market_context_builder(),
        )
    except Exception as exc:
        return build_allocation_model_degraded_packet(portfolio, data_quality, exc)


def build_allocation_model_degraded_packet(portfolio: dict, data_quality: dict, exc: Exception) -> dict:
    current_weights = {row["symbol"]: float(row["weight"]) for row in portfolio.get("positions", [])}
    drift = round(1.0 - sum(current_weights.values()), 6)
    if current_weights and drift:
        largest = max(current_weights, key=current_weights.get)
        current_weights[largest] = round(current_weights[largest] + drift, 6)
    return {
        "model_version": "allocation-v1",
        "model_hash": "",
        "status": "observe",
        "degraded": True,
        "degradation_reason": str(exc),
        "policy": allocation_policy_to_dict(get_default_allocation_policy()),
        "current_weights": current_weights,
        "target_weights": current_weights,
        "signals": [],
        "proposed_trades": [],
        "expected_effect": {
            "var_95_delta_pct": 0.0,
            "worst_scenario_delta_pct": 0.0,
            "turnover_pct": 0.0,
            "concentration_delta": 0.0,
        },
        "constraint_result": {
            "status": "block",
            "violations": ["allocation_model_unavailable"],
            "warnings": [],
            "repair_suggestions": ["Review runtime diagnostics before using allocation recommendations."],
        },
        "evidence_chain": [
            {
                "code": "allocation_model_unavailable",
                "message": str(exc),
                "severity": "warning",
            },
            {
                "code": "data_quality_snapshot",
                "message": f"data_quality={data_quality.get('status', 'unknown')}",
                "severity": "info",
            },
        ],
        "review_schedule": ["T+1", "T+5", "T+20"],
    }


def build_simulated_data_quality(request) -> dict:
    return {
        "score": request.data_quality_score,
        "status": "strong" if request.data_quality_score >= 80 else "weak",
        "flags": list(dict.fromkeys(request.data_quality_flags)),
        "source": "simulation",
    }


def build_institutional_what_if(portfolio: dict, adjustments: dict[str, float], portfolio_name: str | None = None) -> dict:
    what_if = run_what_if(portfolio, adjustments)
    data_quality = build_institutional_data_quality(portfolio_name)
    current_risk = calculate_portfolio_risk(portfolio)
    what_if["compliance"] = evaluate_pre_trade_compliance(
        portfolio,
        what_if["after"]["portfolio"],
        data_quality=data_quality,
        current_risk=current_risk,
    )
    return what_if
