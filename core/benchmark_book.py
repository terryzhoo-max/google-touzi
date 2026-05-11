from dataclasses import dataclass
import hashlib
import json


DEFAULT_BENCHMARK_WEIGHTS = {
    "CSI300_ETF": 0.16,
    "CSI500_ETF": 0.10,
    "STAR50_ETF": 0.08,
    "HSTECH_ETF": 0.08,
    "SP500_ETF": 0.16,
    "NASDAQ_ETF": 0.12,
    "NIKKEI225_ETF": 0.10,
    "CHIP_ETF": 0.08,
    "GOLD_ETF": 0.12,
}


@dataclass(frozen=True)
class BenchmarkBook:
    benchmark_id: str
    version: str
    positions: dict[str, float]


def _normalize(weights: dict[str, float]) -> dict[str, float]:
    total = sum(float(value) for value in weights.values())
    if total <= 0:
        raise ValueError("benchmark weights must have positive total")
    return {
        symbol: round(float(value) / total, 6)
        for symbol, value in sorted(weights.items())
    }


def _benchmark_hash(benchmark_id: str, version: str, positions: dict[str, float]) -> str:
    payload = {
        "benchmark_id": benchmark_id,
        "version": version,
        "positions": positions,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_default_benchmark(weights: dict[str, float] | None = None) -> BenchmarkBook:
    return BenchmarkBook(
        benchmark_id="alphacore_policy_benchmark",
        version="benchmark_v1",
        positions=_normalize(weights or DEFAULT_BENCHMARK_WEIGHTS),
    )


def benchmark_to_dict(benchmark: BenchmarkBook) -> dict:
    return {
        "benchmark_id": benchmark.benchmark_id,
        "version": benchmark.version,
        "benchmark_hash": _benchmark_hash(
            benchmark.benchmark_id,
            benchmark.version,
            benchmark.positions,
        ),
        "positions": benchmark.positions,
    }


def build_active_risk_snapshot(portfolio_snapshot: dict, benchmark: BenchmarkBook | None = None) -> dict:
    book = benchmark or build_default_benchmark()
    benchmark_payload = benchmark_to_dict(book)
    portfolio_weights = {
        position["symbol"]: float(position["weight"])
        for position in portfolio_snapshot["positions"]
    }
    symbols = sorted(set(portfolio_weights) | set(book.positions))
    active_weights = {
        symbol: round(portfolio_weights.get(symbol, 0.0) - book.positions.get(symbol, 0.0), 6)
        for symbol in symbols
    }
    risk_total = sum(value * value for value in active_weights.values()) or 1.0
    active_risk_contribution = {
        symbol: round((value * value) / risk_total, 6)
        for symbol, value in active_weights.items()
    }
    largest = sorted(
        [
            {
                "symbol": symbol,
                "portfolio_weight": round(portfolio_weights.get(symbol, 0.0), 6),
                "benchmark_weight": round(book.positions.get(symbol, 0.0), 6),
                "active_weight": active_weight,
                "active_risk_contribution": active_risk_contribution[symbol],
            }
            for symbol, active_weight in active_weights.items()
            if active_weight != 0
        ],
        key=lambda item: abs(item["active_weight"]),
        reverse=True,
    )
    return {
        "benchmark": benchmark_payload,
        "portfolio_weights": {
            symbol: round(value, 6)
            for symbol, value in sorted(portfolio_weights.items())
        },
        "benchmark_weights": book.positions,
        "active_weights": active_weights,
        "tracking_error_proxy_pct": round((risk_total ** 0.5) * 100, 4),
        "active_risk_contribution": active_risk_contribution,
        "largest_active_exposures": largest[:5],
        "unbenchmarked_symbols": [
            symbol
            for symbol in sorted(portfolio_weights)
            if symbol not in book.positions
        ],
    }
