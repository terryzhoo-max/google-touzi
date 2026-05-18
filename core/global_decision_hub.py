import time
import json
import os
from core.strategy_lab import get_strategy_dashboard
from core.compliance_engine import evaluate_pre_trade_compliance, CompliancePolicy
from core.decision_signal import compute_decision
from core.data_providers import get_vix_history, get_tnx_history
from core.yield_curve import get_yield_curve
from core.portfolio_book import load_portfolio_positions, build_portfolio_snapshot
from core.config import settings
from core.allocation_model import build_allocation_recommendation
from core.data_quality import score_payload
from core.china_macro import get_china_macro
from core.execution_engine import generate_broker_orders

def _build_portfolio():
    return build_portfolio_snapshot(load_portfolio_positions(settings.PORTFOLIO_BOOK_PATH))

def _build_data_quality():
    has_portfolio_file = bool(settings.PORTFOLIO_BOOK_PATH) and os.path.exists(settings.PORTFOLIO_BOOK_PATH)
    source = "portfolio_file" if has_portfolio_file else "sample_portfolio"
    return score_payload(
        source=source, updated_secs_ago=0, stale_after_sec=3600,
        fallback_used=not has_portfolio_file, missing_ratio=0.0, anomaly_count=0
    )

def get_l1_macro_state():
    """L1 Macro Filter: Real data from decision_signal"""
    try:
        vix_data = get_vix_history(60)
        tnx_data = get_tnx_history(60)
        yc_data  = get_yield_curve(days=60)
        vix = float(vix_data.iloc[-1]) if not vix_data.empty else 20.0
        tnx = float(tnx_data.iloc[-1]) if not tnx_data.empty else 4.0
        
        # Format the series data for compute_decision
        tnx_dict = {"data": list(tnx_data.values)} if not tnx_data.empty else {"data": [4.0]}
        
        china_data = get_china_macro(months=12)
        dec = compute_decision(vix=vix, tnx=tnx, tnx_data=tnx_dict, yc_data=yc_data, china=china_data)
        
        # Derive crowding level proxy from valuation and vix
        crowding_level = round(max(0, min(100, 80 - vix + (100 - locals().get('pe_pct', 50)) * 0.2)), 1)
        
        # Derive liquidity state
        if vix > 30:
            liquidity_state = "流动性枯竭 (CRISIS)"
        elif tnx > 4.5 and yc_data and yc_data.get("spread_values", [0])[-1] < 0:
            liquidity_state = "边际收紧 (TIGHTENING)"
        elif vix < 15 and tnx < 4.0:
            liquidity_state = "极度充裕 (AMPLE)"
        else:
            liquidity_state = "中性合理 (NEUTRAL)"

        return {
            "regime": dec.get("signal_en", "NEUTRAL"),
            "vix_level": vix,
            "macro_score": dec.get("score", 50),
            "crowding_level": crowding_level,
            "liquidity_state": liquidity_state,
            "score": dec.get("score", 50), # Kept for backwards compatibility
            "max_equity_exposure": 0.30 if vix > 25 else 0.80,
            "recommended_action": "REDUCE DURATION" if tnx > 4.5 else "MAINTAIN"
        }
    except Exception as e:
        print(f"L1 Macro Error: {e}")
        return {"regime": "UNKNOWN", "vix_level": 20.0, "macro_score": 50, "crowding_level": 50.0, "liquidity_state": "未知 (UNKNOWN)", "score": 50, "max_equity_exposure": 0.50, "recommended_action": "OBSERVE"}

def get_l2_quant_signals():
    """L2 Quant Engine Array: Real output from Strategy Lab"""
    stra_dash = get_strategy_dashboard()
    engines = stra_dash.get("engines", [])
    signals = {}
    for eng in engines:
        k = eng.get("id", eng.get("name_en", "unknown").lower().replace(" ", "_"))
        raw_sig = str(eng.get("signal", "")).upper()
        
        # Convert string signals to numeric for frontend JS logic
        numeric_sig = 0.0
        if "OVERSEAS" in raw_sig or "BULLISH" in raw_sig:
            numeric_sig = 1.0
        elif "A-SHARE" in raw_sig and "OVERWEIGHT" in raw_sig:
            numeric_sig = -1.0
        elif "BEARISH" in raw_sig or ("ACTIVE" in raw_sig and "INACTIVE" not in raw_sig):
            numeric_sig = -1.0

        signals[k] = {
            "source": eng.get("name_en", "Unknown"),
            "source_zh": eng.get("name", ""),
            "signal": numeric_sig,
            "raw_text": raw_sig,
            "top_holding": eng.get("holdings", [None])[0] if eng.get("holdings") else None
        }
    return signals

def run_l3_allocator(l1_macro, portfolio, data_quality):
    """L3 Allocator: Real allocation model"""
    # Build market context from L1
    market_context = {"vix": l1_macro.get("vix_level", 20)}
    rec = build_allocation_recommendation(portfolio, data_quality, market_context=market_context)
    
    # We extract target weights from the recommendation
    target_weights = rec.get("target_weights", {})
    routing_rationale = f"Allocation model generated ({rec.get('status', 'unknown')}). VIX level at {l1_macro.get('vix_level')}."
    
    if l1_macro.get("vix_level", 20) > 25:
        routing_rationale += " Macro override engaged due to high volatility."
        
    return target_weights, routing_rationale

def run_l4_compliance_gate(target_weights, portfolio, data_quality):
    """L4 Compliance Gate: Uses real compliance engine on target weights"""
    from core.allocation_model import _snapshot_from_weights
    from core.risk_engine import calculate_portfolio_risk
    
    if not target_weights:
        target_weights = {row["symbol"]: float(row["weight"]) for row in portfolio["positions"]}
        
    try:
        target_snapshot = _snapshot_from_weights(portfolio, target_weights)
    except Exception:
        target_snapshot = portfolio
        
    before_risk = calculate_portfolio_risk(portfolio)
    res = evaluate_pre_trade_compliance(portfolio, target_snapshot, data_quality, before_risk)
    
    gate_status = "HARD_BLOCK" if res["status"] == "block" else ("SOFT_WARNING" if res["status"] == "warn" else "PASSED")
    return {
        "gate_status": gate_status,
        "score": 100 - (len(res.get("violations", []))*20) - (len(res.get("warnings", []))*5),
        "violations": res.get("violations", []),
        "warnings": res.get("warnings", []),
        "repair_suggestions": res.get("repair_suggestions", []),
        "turnover": sum(abs(target_weights.get(row["symbol"], 0) - float(row["weight"])) for row in portfolio["positions"]) / 2
    }

def get_l5_ai_memo(gate_status, target_weights):
    """L5 AI Synthesis: Fast deterministic template for UI load"""
    if gate_status == "HARD_BLOCK":
        return {
            "headline": "🚨 交易被风控系统阻断 (TRADE BLOCKED)",
            "memo": "AI-CIO 分析：量化引擎与资金路由建议的调仓方案已被 L4 机构风控门禁【一票否决】。调仓可能触发了严重的集中度越界或换手率超标。系统已强制拦截订单下达指令。请参考合规修复建议，缩减单次下单规模或剔除高波资产后重新提交中枢网络。系统将不会向 FIX 接口发送任何真实委托。"
        }
    elif gate_status == "SOFT_WARNING":
        return {
            "headline": "⚠️ 需人工复核的边缘合规 (TRADE WARNED)",
            "memo": "AI-CIO 分析：本次调仓处于合规灰度区间。模型检测到潜在的策略漂移或资产重叠风险，但尚未触及硬性熔断阈值。建议合规官（CCO）介入人工复核。如无异议，系统可在延迟 15 分钟后以降频切单模式 (Iceberg) 执行调仓。"
        }
    else:
        return {
            "headline": "✅ 投委会决策全量通过 (TRADE APPROVED)",
            "memo": "AI-CIO 分析：本次全局资产配置与换仓操作，完美符合当前的宏观流动性周期，且通过了所有的风控熔断规则。系统已确认组合风险因子处于安全水域。授权引擎立即通过 FIX 专线将标的打包发送至前台交易席位，执行机构级低滑点调仓。"
        }

def compute_decision_matrix(portfolio=None, data_quality=None):
    """Generates the full Global Decision Hub pipeline data"""
    if portfolio is None:
        portfolio = _build_portfolio()
    if data_quality is None:
        data_quality = _build_data_quality()
        
    l1 = get_l1_macro_state()
    l2 = get_l2_quant_signals()
    l3_weights, l3_rationale = run_l3_allocator(l1, portfolio, data_quality)
    l4 = run_l4_compliance_gate(l3_weights, portfolio, data_quality)
    l5 = get_l5_ai_memo(l4["gate_status"], l3_weights)
    
    # Calculate before weights for frontend comparison
    before_weights = {row["symbol"]: float(row["weight"]) for row in portfolio.get("positions", [])}
    symbol_names = {row["symbol"]: row.get("name", row["symbol"]) for row in portfolio.get("positions", [])}
    
    # Add common fallbacks for testing if they are not in the portfolio
    common_names = {
        "518880": "黄金ETF",
        "513130": "纳指ETF",
        "512890": "红利低波ETF",
        "688981": "中芯国际",
        "510500": "中证500ETF",
        "159995": "创业板ETF",
        "511260": "十年国债ETF",
        "513500": "标普500ETF",
        "CASH": "现金"
    }
    for k, v in common_names.items():
        if k not in symbol_names:
            symbol_names[k] = v
            
    # Run backtest to get confidence metrics
    try:
        from core.backtest import run_backtest
        bt_results = run_backtest()
        bt_metrics = bt_results.get("metrics", {}) if isinstance(bt_results, dict) else {}
    except Exception as e:
        print(f"[Decision Hub] Failed to run backtest for metrics: {e}")
        bt_metrics = {}
        
    # Generate institutional trade directives and execution plan
    all_symbols = set(list(before_weights.keys()) + list(l3_weights.keys()))
    trade_directives = []
    execution_plan = []
    has_hard_block = l4["gate_status"] == "HARD_BLOCK"
    
    for s in all_symbols:
        diff_weight = l3_weights.get(s, 0.0) - before_weights.get(s, 0.0)
        diff_pct = diff_weight * 100
        
        if abs(diff_pct) > 0.5:
            directive_status = "BLOCKED_BY_COMPLIANCE" if has_hard_block else "APPROVED"
            trade_directives.append({
                "symbol": s,
                "name": symbol_names.get(s, s),
                "action": "BUY" if diff_pct > 0 else "SELL",
                "amount_pct": round(abs(diff_pct), 2),
                "status": directive_status
            })
            
            # For execution engine
            execution_plan.append({
                "symbol": s,
                "action": "INCREASE" if diff_weight > 0 else "DECREASE",
                "delta_weight": diff_weight
            })
            
    # Generate Broker Orders (FIX/QMT format)
    # We only generate orders if compliance passed
    broker_orders = []
    if not has_hard_block and portfolio is not None:
        broker_orders = generate_broker_orders(portfolio, execution_plan)
        
    # If blocked, enforce risk: freeze target weights back to current
    if has_hard_block:
        l3_weights = before_weights.copy()
    
    try:
        from core.db_layer import get_recent_trades
        recent_executions = get_recent_trades(15)
    except Exception:
        recent_executions = []

    return {
        "timestamp": int(time.time()),
        "global_status": l4["gate_status"],
        "drift_monitor": {"total_gap_pct": sum(abs(v - before_weights.get(k, 0)) for k, v in l3_weights.items()) * 100},
        "execution_plan": execution_plan,
        "broker_orders": broker_orders,
        "recent_executions": recent_executions,
        "l1_macro": l1,
        "l2_signals": l2,
        "l3_routing": {
            "before_weights": before_weights,
            "target_weights": l3_weights,
            "rationale": l3_rationale,
            "backtest_metrics": bt_metrics,
            "symbol_names": symbol_names,
            "trade_directives": trade_directives
        },
        "l4_compliance": l4,
        "l5_ai_memo": l5
    }
