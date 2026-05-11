ETF_CODE_MAP = {
    "CSI300_ETF": "510300.SH",
    "CSI500_ETF": "510500.SH",
    "STAR50_ETF": "588000.SH",
    "HSTECH_ETF": "513180.SH",
    "SP500_ETF": "513500.SH",
    "NASDAQ_ETF": "513100.SH",
    "NIKKEI225_ETF": "513520.SH",
    "CHIP_ETF": "512760.SH",
    "GOLD_ETF": "518880.SH",
}


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _macro_score(market_context: dict) -> float:
    return float((market_context.get("macro_decision") or {}).get("score", 50) or 50)


def _regime_fit(position: dict, macro_score: float) -> float:
    asset_class = position.get("asset_class")
    strategy = position.get("strategy")
    if asset_class == "gold":
        return 75 if macro_score < 55 else 58
    if strategy == "technology":
        return _clamp(macro_score - 8)
    if position.get("region") == "China":
        return _clamp(macro_score + 4)
    return _clamp(macro_score)


def _valuation_score(position: dict, market_context: dict) -> float:
    valuation = market_context.get("valuation") or {}
    indices = valuation.get("indices") or []
    pct_values = [
        float(item.get("pe_pct", item.get("price_pct", 50)) or 50)
        for item in indices
        if isinstance(item, dict)
    ]
    pe_pct = sum(pct_values) / len(pct_values) if pct_values else 50.0
    score = 100 - pe_pct
    if position.get("asset_class") == "gold":
        return 55
    if position.get("strategy") == "technology":
        return _clamp(score - 8)
    return _clamp(score)


def _rotation_items(market_context: dict) -> list[dict]:
    return list((market_context.get("domestic_rotation") or {}).get("items") or []) + list(
        (market_context.get("global_rotation") or {}).get("items") or []
    )


def _momentum_score(symbol: str, market_context: dict) -> float:
    code = ETF_CODE_MAP.get(symbol)
    for item in _rotation_items(market_context):
        if item.get("code") == code:
            ret_20d = float(item.get("ret_20d", 0) or 0)
            return _clamp(50 + ret_20d * 5)
    return 50


def _risk_diversification_score(position: dict, factor_risk: dict, scenarios: dict) -> float:
    top = factor_risk.get("top_factor") or {}
    top_name = top.get("factor_name")
    strategy = position.get("strategy")
    region = position.get("region")
    score = 62.0

    if top_name and str(top_name).lower() in {str(strategy).lower(), str(region).lower()}:
        score -= 14
    if position.get("asset_class") == "gold":
        score += 12

    worst = (scenarios.get("worst_scenario") or {}).get("id")
    if worst in {"technology_drawdown", "us_tech_shock"} and strategy == "technology":
        score -= 12
    if worst in {"equity_liquidity_shock", "china_equity_shock"} and position.get("asset_class") == "equity":
        score -= 8

    return _clamp(score)


def _data_confidence_score(data_quality: dict) -> float:
    score = float(data_quality.get("score", 0) or 0)
    if "fallback" in data_quality.get("flags", []):
        score = min(score, 60)
    return _clamp(score)


def _signal_reason(position: dict, components: dict) -> list[str]:
    best = max(components, key=components.get)
    worst = min(components, key=components.get)
    return [
        f"{position['symbol']} strongest input: {best}",
        f"{position['symbol']} weakest input: {worst}",
    ]


def build_etf_signals(
    portfolio: dict,
    factor_risk: dict,
    risk: dict,
    scenarios: dict,
    data_quality: dict,
    market_context: dict | None = None,
) -> list[dict]:
    context = market_context or {}
    macro = _macro_score(context)
    rows = []

    for position in portfolio["positions"]:
        components = {
            "regime_fit": round(_regime_fit(position, macro), 2),
            "valuation_score": round(_valuation_score(position, context), 2),
            "momentum_score": round(_momentum_score(position["symbol"], context), 2),
            "risk_diversification_score": round(_risk_diversification_score(position, factor_risk, scenarios), 2),
            "data_confidence_score": round(_data_confidence_score(data_quality), 2),
        }
        composite = round(
            components["regime_fit"] * 0.30
            + components["valuation_score"] * 0.25
            + components["momentum_score"] * 0.20
            + components["risk_diversification_score"] * 0.15
            + components["data_confidence_score"] * 0.10,
            2,
        )
        confidence = round(min(1.0, components["data_confidence_score"] / 100), 2)
        rows.append({
            "symbol": position["symbol"],
            "name": position["name"],
            "current_weight": float(position["weight"]),
            "component_scores": components,
            "composite_score": composite,
            "confidence": confidence,
            "reasons": _signal_reason(position, components),
        })

    return rows
