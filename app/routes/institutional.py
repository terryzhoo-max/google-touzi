import asyncio
import copy
import json
import os
import time
from uuid import uuid4
from collections.abc import Callable

from fastapi import APIRouter, FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

from app.schemas import (
    AllocationModelSimulateRequest,
    BlackLittermanRequest,
    CommitCustomDecisionRequest,
    CustomShockRequest,
    FrictionRequest,
    HistoricalCrisisRequest,
    RiskParityRequest,
    WhatIfRequest,
)
from core.allocation_policy import allocation_policy_to_dict, get_default_allocation_policy
from core.attribution_engine import build_attribution_snapshot
from core.audit_log import get_audit_store
from core.benchmark_book import benchmark_to_dict, build_active_risk_snapshot
from core.cache_store import ROUTE_TTL, cached, cached_async, invalidate
from core.compliance_engine import evaluate_pre_trade_compliance
from core.decision_explainer import build_decision_explanation
from core.decision_policy import get_default_decision_policy
from core.factor_risk import build_factor_risk_snapshot
from core.global_decision_hub import compute_decision_matrix
from core.llm_agent import generate_morning_brief
from core.portfolio_book import build_portfolio_snapshot, get_available_portfolios, load_portfolio_positions
from core.risk_engine import calculate_portfolio_risk
from core.scenario_engine import run_portfolio_scenarios
from core.strategy_lab import get_strategy_dashboard
from core.what_if_engine import build_default_risk_reduction_adjustments


BuildPortfolio = Callable[[str | None], dict]
BuildDataQuality = Callable[[str | None], dict]
BuildPayload = Callable[[str | None], dict]
BuildAllocationModel = Callable[[dict | None, dict | None], dict]
BuildSimulatedDataQuality = Callable[[AllocationModelSimulateRequest], dict]
BuildWhatIf = Callable[[dict, dict[str, float], str | None], dict]
AllocationBuilder = Callable[..., dict]


def register_institutional_core_routes(
    app: FastAPI,
    *,
    build_portfolio: BuildPortfolio,
    build_data_quality: BuildDataQuality,
    build_payload: BuildPayload,
    build_allocation_model: BuildAllocationModel,
    build_simulated_data_quality: BuildSimulatedDataQuality,
    build_what_if: BuildWhatIf,
    allocation_builder: AllocationBuilder,
    settings,
    base_dir: str,
) -> None:
    router = APIRouter()

    @router.get("/api/institutional/portfolios")
    def api_institutional_portfolios():
        return {"portfolios": get_available_portfolios()}

    @router.get("/api/institutional/portfolio")
    @cached(ttl=ROUTE_TTL["institutional_portfolio"], key="institutional_portfolio")
    def api_institutional_portfolio(portfolio: str | None = None):
        return build_portfolio(portfolio)

    @router.get("/api/institutional/data_quality")
    @cached(ttl=ROUTE_TTL["institutional_data_quality"], key="institutional_data_quality")
    def api_institutional_data_quality(portfolio: str | None = None):
        return build_data_quality(portfolio)

    @router.get("/api/institutional/risk")
    @cached(ttl=ROUTE_TTL["institutional_risk"], key="institutional_risk")
    def api_institutional_risk(portfolio: str | None = None):
        return calculate_portfolio_risk(build_portfolio(portfolio))

    @router.get("/api/institutional/scenarios")
    @cached(ttl=ROUTE_TTL["institutional_scenarios"], key="institutional_scenarios")
    def api_institutional_scenarios(portfolio: str | None = None):
        return run_portfolio_scenarios(build_portfolio(portfolio))

    @router.get("/api/institutional/scenarios/historical")
    def api_historical_crisis_replication(
        portfolio: str | None = None,
        defense_trigger_drawdown: float = -0.05,
        defense_risk_cut_ratio: float = 0.50,
        stabilization_days: int = 10,
    ):
        return _run_historical_crisis_replication_internal(
            build_portfolio,
            portfolio,
            defense_trigger_drawdown,
            defense_risk_cut_ratio,
            stabilization_days,
        )

    @router.post("/api/institutional/scenarios/historical")
    def api_historical_crisis_replication_post(req: HistoricalCrisisRequest):
        return _run_historical_crisis_replication_internal(
            build_portfolio,
            req.portfolio,
            req.defense_trigger_drawdown,
            req.defense_risk_cut_ratio,
            req.stabilization_days,
        )

    @router.get("/api/institutional/global_risk_net")
    def api_institutional_global_risk_net():
        try:
            from core.scenario_engine import run_global_risk_net

            snapshots = []
            for book in get_available_portfolios():
                name = book["name"]
                positions = load_portfolio_positions(name)
                snapshot = build_portfolio_snapshot(positions)
                snapshot["portfolio_name"] = name
                snapshot["display_name"] = book.get("display_name", name)
                snapshots.append(snapshot)

            joint_stress = run_global_risk_net(snapshots)
            global_status = "NORMAL"
            worst = joint_stress.get("worst_scenario")
            if worst and worst.get("portfolio_loss_pct", 0.0) < -12.0:
                global_status = "CROSS_PORTFOLIO_WARNING"

            joint_stress["global_status"] = global_status
            return joint_stress
        except Exception as exc:
            return JSONResponse(status_code=500, content={"error": str(exc)})

    @router.get("/api/institutional/factors")
    @cached(ttl=ROUTE_TTL["institutional_factors"], key="institutional_factors")
    def api_institutional_factors(portfolio: str | None = None):
        return build_factor_risk_snapshot(build_portfolio(portfolio))

    @router.get("/api/institutional/benchmark")
    @cached(ttl=ROUTE_TTL["institutional_benchmark"], key="institutional_benchmark")
    def api_institutional_benchmark(portfolio: str | None = None):
        from core.benchmark_book import get_portfolio_benchmark

        return benchmark_to_dict(get_portfolio_benchmark(portfolio))

    @router.get("/api/institutional/active_risk")
    @cached(ttl=ROUTE_TTL["institutional_active_risk"], key="institutional_active_risk")
    def api_institutional_active_risk(portfolio: str | None = None):
        from core.benchmark_book import get_portfolio_benchmark

        portfolio_snapshot = build_portfolio(portfolio)
        return build_active_risk_snapshot(portfolio_snapshot, get_portfolio_benchmark(portfolio))

    @router.get("/api/institutional/attribution")
    @cached_async(ttl=ROUTE_TTL["institutional_attribution"], key="institutional_attribution")
    async def api_institutional_attribution(period: str = "T-1", portfolio: str | None = None):
        from core.benchmark_book import get_portfolio_benchmark
        from core.data_providers import get_attribution_returns

        portfolio_snapshot = build_portfolio(portfolio)
        benchmark = get_portfolio_benchmark(portfolio)
        port_symbols = [p["symbol"] for p in portfolio_snapshot.get("positions", [])]
        bench_symbols = list(benchmark.positions.keys())
        all_symbols = list(set(port_symbols + bench_symbols))
        returns = await asyncio.to_thread(get_attribution_returns, all_symbols, period)
        return build_attribution_snapshot(
            portfolio_snapshot,
            benchmark,
            period=period,
            asset_returns=returns,
            benchmark_returns=returns,
        )

    @router.get("/api/institutional/compliance")
    @cached(ttl=ROUTE_TTL["institutional_compliance"], key="institutional_compliance")
    def api_institutional_compliance(portfolio: str | None = None):
        portfolio_snapshot = build_portfolio(portfolio)
        what_if = build_what_if(
            portfolio_snapshot,
            build_default_risk_reduction_adjustments(portfolio_snapshot),
            portfolio,
        )
        return what_if["compliance"]

    @router.post("/api/institutional/compliance/check")
    def api_institutional_compliance_check(request: WhatIfRequest, portfolio: str | None = None):
        try:
            portfolio_snapshot = build_portfolio(portfolio)
            what_if = build_what_if(portfolio_snapshot, request.adjustments, portfolio)
            return what_if["compliance"]
        except ValueError as exc:
            return JSONResponse(content={"error": str(exc)}, status_code=400)

    @router.get("/api/institutional/decision")
    @cached(ttl=ROUTE_TTL["institutional_decision"], key="institutional_decision")
    def api_institutional_decision(portfolio: str | None = None):
        return build_payload(portfolio)

    @router.post("/api/institutional/import_tdx")
    async def api_import_tdx(file: UploadFile = File(...)):
        import shutil
        import tempfile

        fd, temp_path = tempfile.mkstemp(suffix=".txt")
        try:
            from core.tdx_parser import import_tdx_to_portfolio

            with os.fdopen(fd, "wb") as f:
                shutil.copyfileobj(file.file, f)
            import_tdx_to_portfolio(temp_path, settings.PORTFOLIO_BOOK_PATH)
            invalidate("institutional_decision")
            return {"status": "success", "message": "TDX portfolio imported"}
        except Exception as exc:
            return JSONResponse(content={"error": str(exc)}, status_code=400)
        finally:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass

    @router.get("/api/institutional/import_tdx")
    def api_import_tdx_get():
        return JSONResponse(content={"error": "Use POST"}, status_code=405)

    @router.get("/api/institutional/ai_compliance_review")
    @cached(ttl=ROUTE_TTL["institutional_compliance"], key="ai_compliance_review")
    def api_institutional_ai_compliance_review():
        try:
            from core.llm_agent import generate_portfolio_compliance_insight, generate_red_team_advisory

            payload = build_payload(None)
            comp_status = payload.get("compliance", {}).get("status", "unknown")
            active_risk = payload.get("active_risk", {})
            tracking_error = active_risk.get("tracking_error_proxy_pct", 0.0)
            factor_risk = payload.get("factor_risk", {})
            top_factor_name = "N/A"
            if "top_factor" in factor_risk and factor_risk["top_factor"]:
                top_factor_name = factor_risk["top_factor"].get("factor_name", "N/A")
            portfolio = payload.get("portfolio", {})
            concentration = portfolio.get("concentration_level", "low")
            var_95 = payload.get("risk", {}).get("var_95_pct", 0.0)
            worst_scenario = payload.get("scenarios", {}).get("worst_scenario", {})
            worst_scenario_name = worst_scenario.get("name_zh", "未知冲击")
            worst_loss = worst_scenario.get("portfolio_loss_pct", 0.0)
            cro_review = generate_portfolio_compliance_insight(
                comp_status,
                tracking_error,
                var_95,
                top_factor_name,
                concentration,
            )
            red_team = generate_red_team_advisory(
                comp_status,
                tracking_error,
                var_95,
                top_factor_name,
                concentration,
                worst_scenario_name,
                worst_loss,
            )
            return {"insight": cro_review.get("insight", ""), "red_team_advisory": red_team.get("insight", "")}
        except Exception as exc:
            import traceback

            traceback.print_exc()
            return JSONResponse(content={"error": str(exc)}, status_code=500)

    @router.get("/api/institutional/portfolio_raw")
    def api_institutional_portfolio_raw(portfolio: str | None = None):
        try:
            positions = load_portfolio_positions(portfolio)
            snapshot = build_portfolio_snapshot(positions)
            risk = calculate_portfolio_risk(snapshot)
            liquidity = risk.get("liquidity_metrics", {})
            dtl_dict = liquidity.get("days_to_liquidate", {})
            adv_dict = liquidity.get("adv_20d", {})
            mctr_dict = risk.get("mctr", {})
            actr_dict = risk.get("actr", {})
            norm_dict = risk.get("normalized_risk_contribution", {})
            raw_positions = []
            for pos in snapshot["positions"]:
                symbol = pos["symbol"]
                pos["days_to_liquidate"] = dtl_dict.get(symbol, 0.0)
                pos["adv_20d"] = adv_dict.get(symbol, 0.0)
                pos["mctr"] = mctr_dict.get(symbol, 0.0)
                pos["actr"] = actr_dict.get(symbol, 0.0)
                pos["normalized_risk_contribution"] = norm_dict.get(symbol, 0.0)
                raw_positions.append(pos)
            return {"positions": raw_positions}
        except Exception as exc:
            return JSONResponse(content={"error": str(exc)}, status_code=500)

    @router.get("/api/institutional/simulation/scenarios")
    async def api_simulation_scenarios():
        try:
            from core.scenario_engine import SCENARIO_SHOCKS

            return {"scenarios": SCENARIO_SHOCKS}
        except Exception as exc:
            return JSONResponse(status_code=500, content={"error": str(exc)})

    @router.post("/api/institutional/scenarios/custom")
    def api_custom_scenario_shock(request: CustomShockRequest, portfolio: str | None = None):
        try:
            from core.scenario_engine import run_custom_shock_analysis

            return run_custom_shock_analysis(build_portfolio(portfolio), request.dict())
        except Exception as exc:
            return JSONResponse(status_code=500, content={"error": str(exc)})

    @router.post("/api/institutional/portfolio_opt/black_litterman")
    def api_black_litterman_optimization(request: BlackLittermanRequest, portfolio: str | None = None):
        try:
            from core.benchmark_book import get_portfolio_benchmark
            from core.portfolio_opt import calculate_black_litterman

            portfolio_snapshot = build_portfolio(portfolio)
            benchmark = get_portfolio_benchmark(portfolio)
            return calculate_black_litterman(
                portfolio_snapshot,
                benchmark.positions,
                request.views,
                request.confidences,
            )
        except Exception as exc:
            return JSONResponse(status_code=500, content={"error": str(exc)})

    @router.post("/api/institutional/portfolio_opt/risk_parity")
    def api_risk_parity_optimization(request: RiskParityRequest, portfolio: str | None = None):
        try:
            from core.benchmark_book import get_portfolio_benchmark
            from core.portfolio_opt import calculate_risk_parity_allocation

            portfolio_snapshot = build_portfolio(portfolio)
            benchmark = get_portfolio_benchmark(portfolio)
            return calculate_risk_parity_allocation(portfolio_snapshot, benchmark.positions, request.budgets)
        except Exception as exc:
            return JSONResponse(status_code=500, content={"error": str(exc)})

    @router.post("/api/institutional/audit/commit_custom")
    def api_commit_custom_decision(request: CommitCustomDecisionRequest):
        try:
            payload = _build_custom_decision_payload(request, build_portfolio, build_data_quality)
            record = get_audit_store().record_decision(payload, source=request.source)
            invalidate("institutional_audit_log")
            invalidate("institutional_reviews_due")
            invalidate("institutional_reviews_summary")
            return {
                "status": "success",
                "ticket_id": record["ticket_id"],
                "record": {k: v for k, v in record.items() if k != "payload"},
            }
        except Exception as exc:
            import traceback

            traceback.print_exc()
            return JSONResponse(status_code=500, content={"error": str(exc)})

    @router.get("/api/institutional/strategies")
    def api_institutional_strategies():
        return get_strategy_dashboard()

    @router.get("/api/institutional/qmt_status")
    def api_institutional_qmt_status(portfolio: str | None = None):
        try:
            from core.runtime_diagnostics import check_qmt_portfolio_drift

            qmt_status = "OFFLINE"
            heartbeat_data = None
            status_file = os.path.join(base_dir, "qmt_heartbeat.json")
            if os.path.exists(status_file):
                try:
                    with open(status_file, "r", encoding="utf-8") as f:
                        heartbeat_data = json.load(f)
                    if time.time() - heartbeat_data.get("timestamp", 0) < 30.0:
                        qmt_status = "ONLINE"
                except Exception:
                    pass

            portfolio_snapshot = build_portfolio(portfolio)
            drift_report = check_qmt_portfolio_drift(portfolio_snapshot.get("positions", []))
            return {"status": qmt_status, "heartbeat": heartbeat_data, "drift_report": drift_report}
        except Exception as exc:
            return JSONResponse(status_code=500, content={"error": str(exc)})

    @router.get("/api/institutional/decision_hub")
    def api_institutional_decision_hub():
        return compute_decision_matrix()

    @router.get("/api/institutional/policy")
    @cached(ttl=ROUTE_TTL["institutional_policy"], key="institutional_policy")
    def api_institutional_policy():
        return get_default_decision_policy()

    @router.get("/api/institutional/aiae_backtest")
    async def api_aiae_backtest():
        try:
            from core.backtest_scientific import run_scientific_backtest

            res = await asyncio.to_thread(run_scientific_backtest)
            if "error" in res:
                return JSONResponse(status_code=500, content=res)
            return res
        except Exception as exc:
            return JSONResponse(status_code=500, content={"error": str(exc)})

    @router.get("/api/institutional/allocation_model")
    @cached(ttl=ROUTE_TTL["institutional_allocation_model"], key="institutional_allocation_model")
    def api_institutional_allocation_model(portfolio: str | None = None):
        portfolio_snapshot = build_portfolio(portfolio)
        data_quality = build_data_quality(portfolio)
        return build_allocation_model(portfolio_snapshot, data_quality)

    @router.get("/api/institutional/allocation_model/policy")
    @cached(ttl=ROUTE_TTL["institutional_allocation_model_policy"], key="institutional_allocation_model_policy")
    def api_institutional_allocation_model_policy():
        return allocation_policy_to_dict(get_default_allocation_policy())

    @router.post("/api/institutional/allocation_model/simulate")
    def api_institutional_allocation_model_simulate(
        request: AllocationModelSimulateRequest,
        portfolio: str | None = None,
    ):
        portfolio_snapshot = build_portfolio(portfolio)
        return allocation_builder(
            portfolio_snapshot,
            data_quality=build_simulated_data_quality(request),
            market_context=request.market_context,
        )

    @router.post("/api/institutional/allocation_model/audit")
    def api_record_institutional_allocation_model(portfolio: str | None = None):
        payload = build_payload(portfolio)
        record = get_audit_store().record_decision(payload, source="allocation_model_api")
        invalidate("institutional_audit_log")
        invalidate("institutional_reviews_due")
        invalidate("institutional_reviews_summary")
        invalidate("institutional_review_scores")
        invalidate("institutional_review_outcomes")
        return {"record": {k: v for k, v in record.items() if k != "payload"}, "payload": payload}

    @router.get("/api/institutional/what_if")
    @cached(ttl=ROUTE_TTL["institutional_what_if"], key="institutional_what_if")
    def api_institutional_what_if_default(portfolio: str | None = None):
        portfolio_snapshot = build_portfolio(portfolio)
        return build_what_if(
            portfolio_snapshot,
            build_default_risk_reduction_adjustments(portfolio_snapshot),
            portfolio,
        )

    @router.post("/api/institutional/what_if")
    def api_institutional_what_if(request: WhatIfRequest, portfolio: str | None = None):
        try:
            portfolio_snapshot = build_portfolio(portfolio)
            return build_what_if(portfolio_snapshot, request.adjustments, portfolio)
        except ValueError as exc:
            return JSONResponse(content={"error": str(exc)}, status_code=400)

    @router.post("/api/institutional/sandbox/friction")
    def api_institutional_sandbox_friction(request: FrictionRequest, portfolio: str | None = None):
        try:
            from core.trade_constraints import calculate_ex_ante_transaction_costs

            portfolio_snapshot = build_portfolio(portfolio)
            return calculate_ex_ante_transaction_costs(
                total_market_value=float(portfolio_snapshot["total_market_value"]),
                current_weights={p["symbol"]: float(p["weight"]) for p in portfolio_snapshot["positions"]},
                target_weights=request.target_weights,
            )
        except ValueError as exc:
            return JSONResponse(content={"error": str(exc)}, status_code=400)

    @router.get("/api/institutional/action")
    @cached(ttl=ROUTE_TTL["institutional_action"], key="institutional_action")
    def api_institutional_action(portfolio: str | None = None):
        payload = build_payload(portfolio)
        return payload["recommended_action"]

    @router.get("/api/institutional/morning_brief")
    async def api_institutional_morning_brief():
        try:
            portfolio = build_portfolio_snapshot(load_portfolio_positions("data/institutional_portfolio.json"))
            decision_matrix = compute_decision_matrix(portfolio=portfolio)
            factor_risk = build_factor_risk_snapshot(portfolio)
            scenarios = run_portfolio_scenarios(portfolio)

            from core.market_data import DATA_CACHE

            def get_last_val(key, default=0.0):
                d = DATA_CACHE.get(key, {}).get("data")
                if d is None:
                    return default
                vals = d.get("data", d) if isinstance(d, dict) else d
                if hasattr(vals, "iloc"):
                    return float(vals.iloc[-1]) if len(vals) > 0 else default
                if isinstance(vals, (list, tuple, str)):
                    return float(vals[-1]) if len(vals) > 0 else default
                return default

            macro_data = {"vix": get_last_val("vix", 20.0), "tnx": get_last_val("tnx", 4.0)}
            brief_result = generate_morning_brief(decision_matrix, scenarios, factor_risk, macro_data)
            return {"status": "ok", "timestamp": int(time.time()), "data": brief_result}
        except Exception as exc:
            import traceback

            traceback.print_exc()
            return JSONResponse(content={"error": str(exc)}, status_code=500)

    app.include_router(router)


def _run_historical_crisis_replication_internal(
    build_portfolio: BuildPortfolio,
    portfolio: str | None = None,
    defense_trigger_drawdown: float = -0.05,
    defense_risk_cut_ratio: float = 0.50,
    stabilization_days: int = 10,
):
    try:
        from core.benchmark_book import get_portfolio_benchmark
        from core.market_data import fetch_market_data
        from core.portfolio_opt import calculate_risk_parity_allocation
        from core.scenario_engine import run_historical_replication_analysis

        try:
            vix_data = fetch_market_data("^VIX", "vix")
            vix = float(vix_data["data"][-1]) if vix_data.get("data") else 20.0
        except Exception:
            vix = 20.0

        portfolio_snapshot = build_portfolio(portfolio)
        benchmark = get_portfolio_benchmark(portfolio)
        rp_res = calculate_risk_parity_allocation(portfolio_snapshot, benchmark.positions, None)
        return run_historical_replication_analysis(
            portfolio_snapshot,
            benchmark.positions,
            rp_res["optimized_weights"],
            vix=vix,
            defense_trigger_drawdown=defense_trigger_drawdown,
            defense_risk_cut_ratio=defense_risk_cut_ratio,
            stabilization_days=stabilization_days,
        )
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


def _build_custom_decision_payload(
    request: CommitCustomDecisionRequest,
    build_portfolio: BuildPortfolio,
    build_data_quality: BuildDataQuality,
) -> dict:
    portfolio_snapshot = build_portfolio(request.portfolio)
    data_quality = build_data_quality(request.portfolio)
    policy = get_default_decision_policy()
    risk = calculate_portfolio_risk(portfolio_snapshot)
    scenarios = run_portfolio_scenarios(portfolio_snapshot)

    if request.source == "bayesian_rebalance":
        from core.benchmark_book import get_portfolio_benchmark
        from core.portfolio_opt import calculate_black_litterman

        bench = get_portfolio_benchmark(request.portfolio)
        bl_res = calculate_black_litterman(portfolio_snapshot, bench.positions, request.views, request.confidences)
        simulated_portfolio = _simulate_reweighted_portfolio(portfolio_snapshot, bl_res["optimized_weights"])
        compliance = evaluate_pre_trade_compliance(
            portfolio_snapshot,
            simulated_portfolio,
            data_quality=data_quality,
            current_risk=risk,
        )
        explanation = build_decision_explanation(
            decision_ticket={"score": 85, "decision_status": "observe"},
            data_quality=data_quality,
            risk=risk,
            scenarios=scenarios,
            portfolio=portfolio_snapshot,
            what_if={"compliance": compliance, "before": {"portfolio": portfolio_snapshot}, "after": {"portfolio": simulated_portfolio}},
            recommended_action={"status": "executed", "action_en": "Rebalance via Bayesian Opt", "action_zh": "执行贝叶斯再平衡"},
            policy=policy,
        )
    elif request.source == "risk_parity_rebalance":
        from core.benchmark_book import get_portfolio_benchmark
        from core.portfolio_opt import calculate_risk_parity_allocation

        bench = get_portfolio_benchmark(request.portfolio)
        rp_res = calculate_risk_parity_allocation(portfolio_snapshot, bench.positions, request.budgets)
        simulated_portfolio = _simulate_reweighted_portfolio(portfolio_snapshot, rp_res["optimized_weights"])
        compliance = evaluate_pre_trade_compliance(
            portfolio_snapshot,
            simulated_portfolio,
            data_quality=data_quality,
            current_risk=risk,
        )
        explanation = build_decision_explanation(
            decision_ticket={"score": 92, "decision_status": "pass"},
            data_quality=data_quality,
            risk=risk,
            scenarios=scenarios,
            portfolio=portfolio_snapshot,
            what_if={"compliance": compliance, "before": {"portfolio": portfolio_snapshot}, "after": {"portfolio": simulated_portfolio}},
            recommended_action={"status": "executed", "action_en": "Rebalance via Risk Parity", "action_zh": "执行风险平价再平衡"},
            policy=policy,
        )
    else:
        from core.scenario_engine import run_custom_shock_analysis

        shock_res = run_custom_shock_analysis(portfolio_snapshot, request.shocks)
        compliance = {
            "status": "warning" if shock_res["status"] == "yellow" else "block" if shock_res["status"] == "red" else "pass",
            "violations": ["custom_black_swan_limit_exceeded"] if shock_res["status"] == "red" else [],
            "warnings": ["custom_black_swan_alert"] if shock_res["status"] == "yellow" else [],
            "repair_suggestions": ["Rebalance portfolio or purchase options to hedge risk."] if shock_res["status"] != "green" else [],
        }
        explanation = {
            "verdict_zh": f"自定义因子压测已归档，预计组合损益 {shock_res['custom_loss_pct']}%",
            "verdict_en": f"Custom factor stress test triggered. Estimated portfolio loss: {shock_res['custom_loss_pct']}%",
            "primary_driver": {"code": "custom_stress_testing", "desc_zh": "自定义冲击沙盘", "desc_en": "Custom Shock Sandbox"},
        }

    ticket = {
        "ticket_id": f"dt_{uuid4().hex[:12]}",
        "score": 75 if compliance["status"] != "pass" else 90,
        "decision_status": "block" if compliance["status"] == "block" else "warning" if compliance["status"] == "warning" else "pass",
        "policy_version": policy.get("version", "v1"),
        "review_schedule": ["T+1", "T+5", "T+20"],
    }

    return {
        "policy": policy,
        "portfolio": portfolio_snapshot,
        "data_quality": data_quality,
        "risk": risk,
        "scenarios": scenarios,
        "compliance": compliance,
        "decision_ticket": ticket,
        "decision_explanation": explanation,
        "recommended_action": {"status": "executed", "action_en": "Custom Sandbox Archiving", "action_zh": "归档自定义压测"},
        "views": request.views,
        "confidences": request.confidences,
        "shocks": request.shocks,
        "budgets": request.budgets,
    }


def _simulate_reweighted_portfolio(portfolio_snapshot: dict, optimized_weights: dict[str, float]) -> dict:
    simulated_positions = []
    for position in portfolio_snapshot.get("positions", []):
        symbol = position["symbol"]
        new_weight = optimized_weights.get(symbol, position["weight"])
        cloned = copy.deepcopy(position)
        cloned["weight"] = new_weight
        cloned["market_value"] = round(new_weight * portfolio_snapshot["total_market_value"], 2)
        simulated_positions.append(cloned)

    simulated_portfolio = copy.deepcopy(portfolio_snapshot)
    simulated_portfolio["positions"] = simulated_positions
    return simulated_portfolio
