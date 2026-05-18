import math
from core.market_data import DATA_CACHE

# Dummy price cache for real-time order generation if we don't have fresh quotes
_FALLBACK_PRICES = {
    "510300.SH": 3.511,
    "510500.SH": 5.234,
    "513500.SH": 1.450,
    "513100.SH": 1.280,
    "512760.SH": 1.050,
    "518880.SH": 4.880,
    "512890.SH": 1.102,
}

def _get_live_price(symbol: str) -> float:
    """Fetch live price for lot sizing calculation."""
    # Attempt to fetch from real-time cache if available
    live = DATA_CACHE.get(symbol, {}).get("data")
    if live is not None and isinstance(live, (list, tuple)) and len(live) > 0:
        return float(live[-1])
    if hasattr(live, "iloc") and len(live) > 0:
        return float(live.iloc[-1])
        
    return _FALLBACK_PRICES.get(symbol, 1.0)


def generate_broker_orders(portfolio_snapshot: dict, execution_plan: list[dict]) -> list[dict]:
    """
    Translates percentage-based execution plans into discrete, broker-executable orders (FIX/QMT).
    Enforces A-share 100-share lot restrictions.
    """
    total_nav = portfolio_snapshot.get("total_market_value", 0.0)
    if total_nav <= 0:
        return []
        
    orders = []
    
    for plan in execution_plan:
        symbol = plan["symbol"]
        action = plan.get("action", "").upper() # INCREASE or DECREASE
        delta_weight = plan.get("delta_weight", 0.0)
        
        if delta_weight == 0.0:
            continue
            
        # Calculate raw cash required to fulfill the delta
        raw_capital_delta = abs(total_nav * delta_weight)
        
        # Get live price
        price = _get_live_price(symbol)
        
        # Calculate raw shares
        if price <= 0:
            continue
            
        raw_shares = raw_capital_delta / price
        
        # Enforce A-share trading rules (multiples of 100 shares)
        # We generally round down (floor) to prevent exceeding targeted cash or short-selling rules
        lots = math.floor(raw_shares / 100.0)
        executable_shares = lots * 100
        
        if executable_shares <= 0:
            # Order size too small for 1 lot
            continue
            
        # Slippage addition for limits (e.g. +1 tick for buy, -1 tick for sell)
        tick_size = 0.001
        limit_price = price + (tick_size * 2) if delta_weight > 0 else price - (tick_size * 2)
        limit_price = round(limit_price, 3)
        
        # Map our internal 'action' to standard broker verbs
        if delta_weight > 0:
            broker_side = "BUY"
        else:
            broker_side = "SELL"
            
        order = {
            "order_id": f"ORD_{symbol.replace('.', '')}_{broker_side}",
            "symbol": symbol,
            "side": broker_side,
            "order_type": "LIMIT",
            "quantity": int(executable_shares),
            "limit_price": limit_price,
            "estimated_value": round(executable_shares * limit_price, 2),
            "currency": "CNY",
            "time_in_force": "GFD" # Good For Day
        }
        
        orders.append(order)
        
    return orders
