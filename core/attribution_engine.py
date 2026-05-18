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

def build_attribution_snapshot(
    portfolio_snapshot: dict,
    benchmark: BenchmarkBook | None = None,
    period: str = "T+1",
    asset_returns: dict[str, float] | None = None,
    benchmark_returns: dict[str, float] | None = None,
    currency_returns: dict[str, float] | None = None,
) -> dict:
    
    # 机构级容错：允许部分数据缺失，默认补 0.0，但必须是由外部注入的真实数据字典
    if asset_returns is None or benchmark_returns is None:
        return {
            "period": period,
            "error": "Missing real market data for attribution calculations. Hard degradation triggered.",
            "availability": {
                "status": "error",
                "source": "missing_data"
            }
        }

    book = benchmark or build_default_benchmark()
    portfolio_weights = _portfolio_weights(portfolio_snapshot)
    asset_ret = asset_returns or {}
    bench_ret = benchmark_returns or {}
    currency_ret = currency_returns or {}
    symbols = sorted(set(portfolio_weights) | set(book.positions))

    by_symbol = []
    allocation_effect = 0.0
    selection_effect = 0.0
    portfolio_return = 0.0
    benchmark_return = 0.0

    for symbol in symbols:
        portfolio_weight = portfolio_weights.get(symbol, 0.0)
        benchmark_weight = book.positions.get(symbol, 0.0)
        symbol_return = float(asset_ret.get(symbol, 0.0))
        symbol_benchmark_return = float(bench_ret.get(symbol, symbol_return))
        symbol_allocation = (portfolio_weight - benchmark_weight) * symbol_benchmark_return
        symbol_selection = portfolio_weight * (symbol_return - symbol_benchmark_return)
        allocation_effect += symbol_allocation
        selection_effect += symbol_selection
        portfolio_return += portfolio_weight * symbol_return
        benchmark_return += benchmark_weight * symbol_benchmark_return
        by_symbol.append({
            "symbol": symbol,
            "portfolio_weight": round(portfolio_weight, 6),
            "benchmark_weight": round(benchmark_weight, 6),
            "asset_return": round(symbol_return, 6),
            "benchmark_return": round(symbol_benchmark_return, 6),
            "allocation_effect": round(symbol_allocation, 6),
            "selection_effect": round(symbol_selection, 6),
        })

    currency_effect = sum(
        weight * float(currency_ret.get(currency, 0.0))
        for currency, weight in _currency_weights(portfolio_snapshot).items()
    )
    decision_effect = portfolio_return - benchmark_return

    return {
        "period": period,
        "portfolio_return": round(portfolio_return, 6),
        "benchmark_return": round(benchmark_return, 6),
        "allocation_effect": round(allocation_effect, 6),
        "selection_effect": round(selection_effect, 6),
        "currency_effect": round(currency_effect, 6),
        "decision_effect": round(decision_effect, 6),
        "by_symbol": by_symbol,
        "benchmark": benchmark_to_dict(book),
        "availability": {
            "status": "provided",
            "source": "provided_returns",
        },
    }
