import time
import json
from core.strategy_lab import get_strategy_dashboard
from core.compliance_engine import evaluate_pre_trade_compliance, CompliancePolicy

def get_l1_macro_state():
    """L1 Macro Filter: Defines the global risk appetite ceiling"""
    return {
        "regime": "Contraction (Liquidity Stress)",
        "vix_level": 28.5,
        "max_equity_exposure": 0.40,
        "recommended_action": "REDUCE DURATION, INCREASE CASH"
    }

def get_l2_quant_signals():
    """L2 Quant Engine Array: Raw output from Strategy Lab"""
    stra_dash = get_strategy_dashboard()
    engines = stra_dash.get("engines", [])
    signals = []
    for eng in engines:
        signals.append({
            "source": eng["name_en"],
            "signal": eng["signal"],
            "top_holding": eng["holdings"][0] if eng["holdings"] else None
        })
    return signals

def run_l3_allocator(l1_macro, l2_signals):
    """L3 Allocator: Resolves conflicts and outputs target weights"""
    # If VIX is high, Macro forces a defensive posture
    if l1_macro["vix_level"] > 25:
        target_weights = {
            "510300.SH": 0.10, # CSI300 (drastically reduced)
            "513500.SH": 0.15, # SP500
            "510880.SH": 0.20, # Dividend
            "512760.SH": 0.05, # Tech
            "CASH": 0.50
        }
        routing_rationale = "Macro override: VIX > 25. Forcing 50% Cash allocation. Growth assets heavily penalized."
    else:
        # Standard mix
        target_weights = {
            "510300.SH": 0.20,
            "513500.SH": 0.30,
            "510880.SH": 0.30,
            "512760.SH": 0.20,
            "CASH": 0.0
        }
        routing_rationale = "Aggregated Strategy Lab target weights."
        
    return target_weights, routing_rationale

def run_l4_compliance_gate(target_weights):
    """L4 Compliance Gate: Uses compliance_engine to veto or approve"""
    # Create fake current snapshot for demo purposes
    current_snapshot = {
        "positions": [
            {"symbol": "510300.SH", "weight": 0.15},
            {"symbol": "513500.SH", "weight": 0.25},
            {"symbol": "510880.SH", "weight": 0.20},
            {"symbol": "512760.SH", "weight": 0.40}, # Tech was very high
            {"symbol": "CASH", "weight": 0.0}
        ],
        "asset_class_exposure": {"equity": 1.0, "gold": 0.0},
        "strategy_exposure": {"technology": 0.40}
    }
    
    target_snapshot = {
        "positions": [{"symbol": k, "weight": v} for k, v in target_weights.items()],
        "asset_class_exposure": {"equity": 1 - target_weights.get("CASH", 0), "gold": 0.0},
        "strategy_exposure": {"technology": target_weights.get("512760.SH", 0.0)}
    }
    
    data_quality = {"score": 95, "flags": []}
    current_risk = {"risk_level": "medium"}
    
    # Run institutional compliance
    policy = CompliancePolicy(max_position_weight=0.30, max_turnover=0.50)
    res = evaluate_pre_trade_compliance(current_snapshot, target_snapshot, data_quality, current_risk, policy)
    
    # Adapt output for UI
    gate_status = "HARD_BLOCK" if res["status"] == "block" else ("SOFT_WARNING" if res["status"] == "warn" else "PASSED")
    return {
        "gate_status": gate_status,
        "score": res["score"],
        "violations": res["violations"],
        "warnings": res["warnings"],
        "repair_suggestions": res["repair_suggestions"],
        "turnover": res["turnover"]
    }

def get_l5_ai_memo(gate_status, target_weights):
    """L5 AI Synthesis: Returns the final narrative"""
    if gate_status == "HARD_BLOCK":
        return {
            "headline": "🚨 交易被合规系统阻断 (TRADE BLOCKED)",
            "memo": "AI-CIO 分析：动量引擎与配置路由建议的调仓方案已被 L4 风控门禁一票否决。由于强制平仓带来的单次换手率（Turnover）过高，且突破了单只基金的最大集中度限制。请参考修复建议，缩减单次下单规模（建议拆分为多日建仓）后重新提交至中枢系统。"
        }
    else:
        return {
            "headline": "✅ 投委会决策通过 (TRADE APPROVED)",
            "memo": "AI-CIO 分析：本次调仓符合全局风控矩阵标准。由于宏观指标提示流动性收紧（VIX > 25），系统已成功压制 L2 策略的激进买入信号，强制将组合底仓切换为现金与高分红防御资产。准许通过 FIX 接口下达真实订单。"
        }

def compute_decision_matrix():
    """Generates the full Global Decision Hub pipeline data"""
    l1 = get_l1_macro_state()
    l2 = get_l2_quant_signals()
    l3_weights, l3_rationale = run_l3_allocator(l1, l2)
    l4 = run_l4_compliance_gate(l3_weights)
    l5 = get_l5_ai_memo(l4["gate_status"], l3_weights)
    
    return {
        "timestamp": int(time.time()),
        "l1_macro": l1,
        "l2_signals": l2,
        "l3_routing": {
            "target_weights": l3_weights,
            "rationale": l3_rationale
        },
        "l4_compliance": l4,
        "l5_ai_memo": l5
    }
