import math
from dataclasses import dataclass


@dataclass(frozen=True)
class TradeConstraints:
    max_turnover: float = 0.2
    min_cash_weight: float = 0.05
    max_position_weight: float = 0.6
    cost_bps_per_turnover: float = 10.0


LIQUIDITY_DB = {
    "CSI300_ETF": {"adv": 2500000000.0, "sigma_daily": 0.010},
    "CSI500_ETF": {"adv": 1500000000.0, "sigma_daily": 0.012},
    "STAR50_ETF": {"adv": 800000000.0, "sigma_daily": 0.015},
    "HSTECH_ETF": {"adv": 1200000000.0, "sigma_daily": 0.016},
    "SP500_ETF": {"adv": 500000000.0, "sigma_daily": 0.009},
    "NASDAQ_ETF": {"adv": 300000000.0, "sigma_daily": 0.011},
    "GOLD_ETF": {"adv": 600000000.0, "sigma_daily": 0.008},
}

DEFAULT_LIQUIDITY = {"adv": 200000000.0, "sigma_daily": 0.012}
COMMISSION_RATE = 0.0003  # 万三佣金
IMPACT_GAMMA = 0.5       # 冲击系数


def _get_liquidity_params(symbol: str) -> dict:
    sym = symbol.upper().split(".")[0]  # 去除后缀
    return LIQUIDITY_DB.get(sym, DEFAULT_LIQUIDITY)


def calculate_ex_ante_transaction_costs(
    total_market_value: float,
    current_weights: dict[str, float],
    target_weights: dict[str, float],
) -> dict:
    """
    计算事前交易执行摩擦与非线性市场冲击（滑点）成本。
    基于 Almgren-Chriss 平方根法则 (Square-Root Law) 和万三双向券商佣金。
    CASH 视为 0 摩擦。
    """
    symbols = set(current_weights.keys()) | set(target_weights.keys())
    details = []
    total_commission = 0.0
    total_impact_cost = 0.0

    for symbol in symbols:
        if symbol == "CASH":
            continue

        w_curr = current_weights.get(symbol, 0.0)
        w_target = target_weights.get(symbol, 0.0)
        delta_w = w_target - w_curr
        trade_value = total_market_value * abs(delta_w)

        if trade_value <= 0.0001:
            continue

        # 获取标的流动性参数
        liq = _get_liquidity_params(symbol)
        adv = liq["adv"]
        sigma_daily = liq["sigma_daily"]

        # 1. 规费佣金 (Fixed Commission)
        commission = trade_value * COMMISSION_RATE

        # 2. 非线性市场冲击成本 (Market Impact Cost)
        participation_rate = trade_value / adv
        impact_cost = trade_value * IMPACT_GAMMA * sigma_daily * math.sqrt(participation_rate)

        # 3. 流动性警告与拆单建议 (Liquidity Warning & Split Advice)
        warning_level = "NORMAL"
        warning_msg = ""
        if participation_rate > 0.05:
            warning_level = "RED"
            suggested_days = math.ceil(participation_rate / 0.015)
            suggested_days = max(2, suggested_days)
            warning_msg = f"单日交易额占比达 {participation_rate * 100:.2f}%，已突破 5% 流动性红线！建议将订单拆分为 {suggested_days} 天分批执行，单日交易量控制在 1.5% ADV 以内。"
        elif participation_rate > 0.02:
            warning_level = "YELLOW"
            warning_msg = f"交易额占比达 {participation_rate * 100:.2f}%，建议拉长交易窗口执行。"

        total_commission += commission
        total_impact_cost += impact_cost

        details.append({
            "symbol": symbol,
            "trade_value": round(trade_value, 2),
            "delta_weight": round(delta_w, 6),
            "commission": round(commission, 2),
            "impact_cost": round(impact_cost, 2),
            "total_cost": round(commission + impact_cost, 2),
            "participation_rate": round(participation_rate, 6),
            "warning_level": warning_level,
            "warning_msg": warning_msg,
        })

    total_cost = total_commission + total_impact_cost
    total_cost_bps = (total_cost / total_market_value * 10000.0) if total_market_value > 0 else 0.0
    net_projected_aum = total_market_value - total_cost

    # 按照名义交易金额降序排列
    details.sort(key=lambda x: x["trade_value"], reverse=True)

    return {
        "total_market_value": round(total_market_value, 2),
        "total_commission": round(total_commission, 2),
        "total_impact_cost": round(total_impact_cost, 2),
        "total_cost": round(total_cost, 2),
        "total_cost_bps": round(total_cost_bps, 2),
        "net_projected_aum": round(net_projected_aum, 2),
        "details": details,
    }


def evaluate_trade_constraints(
    target_weights: dict[str, float],
    current_weights: dict[str, float],
    constraints: TradeConstraints | None = None,
) -> dict:
    limits = constraints or TradeConstraints()
    violations: list[str] = []

    turnover = round(
        sum(abs(target_weights.get(symbol, 0.0) - current_weights.get(symbol, 0.0))
            for symbol in set(target_weights) | set(current_weights)) / 2,
        6,
    )

    if turnover > limits.max_turnover:
        violations.append("turnover_exceeded")
    if "CASH" in current_weights or "CASH" in target_weights:
        cash_weight = target_weights.get("CASH", 0.0)
    else:
        cash_weight = limits.min_cash_weight

    if cash_weight < limits.min_cash_weight:
        violations.append("cash_below_minimum")

    for symbol, weight in target_weights.items():
        if weight < 0:
            violations.append(f"negative_weight:{symbol}")
        if weight > limits.max_position_weight:
            violations.append(f"position_limit_exceeded:{symbol}")

    return {
        "passed": not violations,
        "violations": violations,
        "turnover": round(turnover, 4),
        "estimated_cost_bps": round(turnover * limits.cost_bps_per_turnover, 2),
        "limits": {
            "max_turnover": limits.max_turnover,
            "min_cash_weight": limits.min_cash_weight,
            "max_position_weight": limits.max_position_weight,
        },
    }

def evaluate_portfolio_funding_drag(portfolio_snapshot: dict) -> dict:
    """
    Evaluate institutional funding drag and leverage compliance.
    Flags warning if the estimated T+1 clearing lock capital exceeds 80% of portfolio.
    """
    total = portfolio_snapshot.get("total_market_value", 1.0)
    cash_t1_locked = portfolio_snapshot.get("cash_t1_locked", 0.0)
    
    lock_ratio = cash_t1_locked / total if total > 0 else 0.0
    passed = lock_ratio < 0.80
    violations = []
    if not passed:
        violations.append("funding_drag_leverage_exceeded")
        
    return {
        "passed": passed,
        "violations": violations,
        "cash_t1_locked": cash_t1_locked,
        "lock_ratio": round(lock_ratio, 4),
        "warning_threshold": 0.80,
        "status": "passed" if passed else "warning"
    }

