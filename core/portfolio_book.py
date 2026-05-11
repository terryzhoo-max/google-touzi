from collections import defaultdict
from dataclasses import dataclass
import json
import os


@dataclass(frozen=True)
class Position:
    symbol: str
    name: str
    asset_class: str
    currency: str
    market_value: float
    quantity: float = 0.0
    cost_basis: float = 0.0
    region: str = "Global"
    strategy: str = "core"

    def __post_init__(self):
        if self.market_value < 0:
            raise ValueError("market_value must be non-negative")


def get_sample_portfolio() -> list[Position]:
    return [
        Position("SPY", "SPDR S&P 500 ETF", "equity", "USD", 450000.0),
        Position("TLT", "20+ Year Treasury ETF", "bond", "USD", 250000.0),
        Position("GLD", "Gold ETF", "gold", "USD", 150000.0),
        Position("CASH", "Cash", "cash", "USD", 150000.0),
    ]


def _position_from_dict(item: dict) -> Position:
    return Position(
        symbol=str(item["symbol"]),
        name=str(item.get("name") or item["symbol"]),
        asset_class=str(item["asset_class"]),
        currency=str(item.get("currency", "USD")),
        market_value=float(item["market_value"]),
        quantity=float(item.get("quantity", 0.0)),
        cost_basis=float(item.get("cost_basis", 0.0)),
        region=str(item.get("region", "Global")),
        strategy=str(item.get("strategy", "core")),
    )


def load_portfolio_positions(path: str | None = None) -> list[Position]:
    if not path:
        return get_sample_portfolio()
    if not os.path.exists(path):
        return get_sample_portfolio()

    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    rows = payload.get("positions", payload if isinstance(payload, list) else [])
    positions = [_position_from_dict(item) for item in rows]
    if not positions:
        raise ValueError("portfolio file must contain at least one position")
    return positions


def build_portfolio_snapshot(positions: list[Position]) -> dict:
    total = round(sum(p.market_value for p in positions), 2)
    if total <= 0:
        raise ValueError("portfolio market value must be positive")

    exposure = defaultdict(float)
    region_exposure = defaultdict(float)
    strategy_exposure = defaultdict(float)
    currency_exposure = defaultdict(float)
    rows = []
    for p in positions:
        weight = round(p.market_value / total, 6)
        exposure[p.asset_class] += weight
        region_exposure[p.region] += weight
        strategy_exposure[p.strategy] += weight
        currency_exposure[p.currency] += weight
        rows.append({
            "symbol": p.symbol,
            "name": p.name,
            "asset_class": p.asset_class,
            "region": p.region,
            "strategy": p.strategy,
            "currency": p.currency,
            "market_value": round(p.market_value, 2),
            "weight": weight,
            "quantity": p.quantity,
            "cost_basis": p.cost_basis,
        })

    sorted_rows = sorted(rows, key=lambda item: item["weight"], reverse=True)
    largest_position = {
        "symbol": sorted_rows[0]["symbol"],
        "name": sorted_rows[0]["name"],
        "weight": sorted_rows[0]["weight"],
    }
    top_3_weight = round(sum(item["weight"] for item in sorted_rows[:3]), 6)
    if largest_position["weight"] >= 0.5 or top_3_weight >= 0.8:
        concentration_level = "high"
    elif largest_position["weight"] >= 0.25 or top_3_weight >= 0.6:
        concentration_level = "medium"
    else:
        concentration_level = "low"

    return {
        "total_market_value": total,
        "positions": rows,
        "asset_class_exposure": {k: round(v, 6) for k, v in exposure.items()},
        "region_exposure": {k: round(v, 6) for k, v in region_exposure.items()},
        "strategy_exposure": {k: round(v, 6) for k, v in strategy_exposure.items()},
        "currency_exposure": {k: round(v, 6) for k, v in currency_exposure.items()},
        "largest_position": largest_position,
        "top_3_weight": top_3_weight,
        "concentration_level": concentration_level,
        "position_count": len(rows),
    }
