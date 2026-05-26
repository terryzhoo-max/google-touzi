from core.benchmark_book import BenchmarkBook, build_default_benchmark, benchmark_to_dict

def _portfolio_weights(snapshot: dict) -> dict[str, float]:
    return {
        position["symbol"]: float(position["weight"])
        for position in snapshot["positions"]
    }

def _currency_weights(snapshot: dict) -> dict[str, float]:
    weights: dict[str, float] = {}
    for position in snapshot["positions"]:
        currency = position.get("currency", "USD")
        weights[currency] = weights.get(currency, 0.0) + float(position["weight"])
    return weights

def get_symbol_asset_class(symbol: str) -> str:
    symbol_upper = symbol.upper()
    if "SPY" in symbol_upper or "CSI300" in symbol_upper or "300" in symbol_upper or "500" in symbol_upper or "芯片" in symbol_upper or "半导体" in symbol_upper or "科创" in symbol_upper or "159" in symbol_upper or "510" in symbol_upper or "512" in symbol_upper or "513" in symbol_upper or "588" in symbol_upper or "002851" in symbol_upper:
        return "equity"
    elif "TLT" in symbol_upper or "IEF" in symbol_upper or "SHY" in symbol_upper:
        return "bond"
    elif "GLD" in symbol_upper or "IAU" in symbol_upper or "518880" in symbol_upper or "GOLD" in symbol_upper:
        return "gold"
    elif "CASH" in symbol_upper or "MONEY" in symbol_upper:
        return "cash"
    return "equity" # Default fallback


def build_attribution_snapshot(
    portfolio_snapshot: dict,
    benchmark: BenchmarkBook | None = None,
    period: str = "T+1",
    asset_returns: dict[str, float] | None = None,
    benchmark_returns: dict[str, float] | None = None,
    currency_returns: dict[str, float] | None = None,
) -> dict:
    
    # 机构级容错：允许部分数据缺失，默认补 0.0，但必须是由外部注入的真实数据字典
    is_proxy = False
    if asset_returns is None or benchmark_returns is None:
        is_proxy = True
        asset_returns = {}
        benchmark_returns = {}
        currency_returns = currency_returns or {}

    book = benchmark or build_default_benchmark()
    portfolio_weights = _portfolio_weights(portfolio_snapshot)
    asset_ret = asset_returns or {}
    bench_ret = benchmark_returns or {}
    currency_ret = currency_returns or {}
    symbols = sorted(set(portfolio_weights) | set(book.positions))

    # Build symbol to asset class map
    symbol_to_class = {}
    for p in portfolio_snapshot.get("positions", []):
        symbol_to_class[p["symbol"]] = p["asset_class"]
    for s in symbols:
        if s not in symbol_to_class:
            symbol_to_class[s] = get_symbol_asset_class(s)

    # Aggregate weights and returns by asset class
    class_weights_p = {}
    class_weights_b = {}
    class_ret_weighted_p = {}
    class_ret_weighted_b = {}

    for symbol in symbols:
        w_p = portfolio_weights.get(symbol, 0.0)
        w_b = book.positions.get(symbol, 0.0)
        r_p = float(asset_ret.get(symbol, 0.0))
        r_b = float(bench_ret.get(symbol, r_p))
        
        ac = symbol_to_class[symbol]
        
        class_weights_p[ac] = class_weights_p.get(ac, 0.0) + w_p
        class_weights_b[ac] = class_weights_b.get(ac, 0.0) + w_b
        class_ret_weighted_p[ac] = class_ret_weighted_p.get(ac, 0.0) + (w_p * r_p)
        class_ret_weighted_b[ac] = class_ret_weighted_b.get(ac, 0.0) + (w_b * r_b)

    # Compute total portfolio and benchmark returns
    total_portfolio_return = sum(class_ret_weighted_p.values())
    total_benchmark_return = sum(class_ret_weighted_b.values())
    total_active_return = total_portfolio_return - total_benchmark_return

    # Compute asset class returns and Brinson effects
    asset_classes = sorted(set(class_weights_p.keys()) | set(class_weights_b.keys()))
    by_class = []
    
    total_alloc_effect = 0.0
    total_select_effect = 0.0
    total_inter_effect = 0.0

    for ac in asset_classes:
        w_p = class_weights_p.get(ac, 0.0)
        w_b = class_weights_b.get(ac, 0.0)
        
        r_p = class_ret_weighted_p.get(ac, 0.0) / w_p if w_p > 0 else 0.0
        r_b = class_ret_weighted_b.get(ac, 0.0) / w_b if w_b > 0 else 0.0
        
        # If active weight and benchmark weight are both 0, skip
        if w_p == 0.0 and w_b == 0.0:
            continue
            
        # Brinson-Fachler Model calculations:
        # Allocation Effect: (w_p - w_b) * (r_b - R_benchmark_total)
        alloc_effect = (w_p - w_b) * (r_b - total_benchmark_return)
        # Selection Effect: w_b * (r_p - r_b)
        select_effect = w_b * (r_p - r_b)
        # Interaction Effect: (w_p - w_b) * (r_p - r_b)
        inter_effect = (w_p - w_b) * (r_p - r_b)
        
        total_alloc_effect += alloc_effect
        total_select_effect += select_effect
        total_inter_effect += inter_effect
        
        by_class.append({
            "asset_class": ac,
            "portfolio_weight": round(w_p, 6),
            "benchmark_weight": round(w_b, 6),
            "portfolio_return": round(r_p, 6),
            "benchmark_return": round(r_b, 6),
            "allocation_effect": round(alloc_effect, 6),
            "selection_effect": round(select_effect, 6),
            "interaction_effect": round(inter_effect, 6),
            "active_return": round((w_p * r_p) - (w_b * r_b), 6),
        })

    # Individual symbol details (for security-level transparency)
    by_symbol = []
    for symbol in symbols:
        w_p = portfolio_weights.get(symbol, 0.0)
        w_b = book.positions.get(symbol, 0.0)
        r_p = float(asset_ret.get(symbol, 0.0))
        r_b = float(bench_ret.get(symbol, r_p))
        
        # Symbol-level Brinson effects
        alloc_effect = (w_p - w_b) * (r_b - total_benchmark_return)
        select_effect = w_b * (r_p - r_b)
        inter_effect = (w_p - w_b) * (r_p - r_b)
        
        by_symbol.append({
            "symbol": symbol,
            "portfolio_weight": round(w_p, 6),
            "benchmark_weight": round(w_b, 6),
            "asset_return": round(r_p, 6),
            "benchmark_return": round(r_b, 6),
            "allocation_effect": round(alloc_effect, 6),
            "selection_effect": round(select_effect, 6),
            "interaction_effect": round(inter_effect, 6),
        })

    currency_effect = sum(
        weight * float(currency_ret.get(currency, 0.0))
        for currency, weight in _currency_weights(portfolio_snapshot).items()
    )

    return {
        "period": period,
        "portfolio_return": round(total_portfolio_return, 6),
        "benchmark_return": round(total_benchmark_return, 6),
        "active_return": round(total_active_return, 6),
        "allocation_effect": round(total_alloc_effect, 6),
        "selection_effect": round(total_select_effect, 6),
        "interaction_effect": round(total_inter_effect, 6),
        "currency_effect": round(currency_effect, 6),
        "decision_effect": round(total_active_return, 6), # kept for compatibility
        "by_class": by_class,
        "by_symbol": by_symbol,
        "benchmark": benchmark_to_dict(book),
        "availability": {
            "status": "proxy" if is_proxy else "provided",
            "source": "proxy_returns" if is_proxy else "provided_returns",
        },
    }

