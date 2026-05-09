"""
L1 Route-result cache — decorator-based, per-route TTL.

Usage:
    from core.cache_store import cached
    @cached(ttl=300, key="decision")
    async def expensive_route():
        ...

The first call computes and caches; subsequent calls within TTL return
the cached result immediately, skipping ALL downstream data fetching.
"""

import time
import json
import functools
import asyncio

_store: dict[str, tuple[float, dict]] = {}
_stats: dict[str, int] = {"hits": 0, "misses": 0}

ROUTE_TTL: dict[str, int] = {
    "decision":          300,
    "erp":              1800,
    "spread":            600,
    "yield_curve":      1800,
    "allocation":        600,
    "correlation":      3600,
    "montecarlo":       1800,
    "efficient_frontier":3600,
    "scenario":          600,
    "signals":          3600,
    "backtest":        86400,
    "ai_insight":        600,
    "sector_rotation":  3600,
    "china_macro":     86400,
    "market_breadth":   3600,
    "fed_prob":         3600,
    "global_assets":    3600,
    "valuation":       43200,
    "theme_rotation":   3600,
    "domestic_etf":     3600,
    "global_etf":       3600,
    "health":            120,
}


def cached(ttl: int, key: str):
    """Decorator for synchronous functions."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            now = time.time()
            if key in _store:
                ts, val = _store[key]
                if now - ts < ttl:
                    _stats["hits"] += 1
                    return val
            _stats["misses"] += 1
            try:
                result = fn(*args, **kwargs)
                if isinstance(result, dict) and "error" in result:
                    if key in _store:
                        print(f"[cache_store] {key} returned logic error, serving stale cache.")
                        stale_val = _store[key][1]
                        if isinstance(stale_val, dict): stale_val["_stale"] = True
                        return stale_val
                    # cache the error briefly (1 minute) to avoid spamming the backend
                    _store[key] = (now - ttl + 60, result)
                    return result

                _store[key] = (now, result)
                return result
            except Exception as e:
                print(f"[cache_store] Exception in {key}: {e}")
                if key in _store:
                    stale_val = _store[key][1]
                    if isinstance(stale_val, dict): stale_val["_stale"] = True
                    return stale_val
                raise e
        return wrapper
    return decorator


def cached_async(ttl: int, key: str):
    """Decorator for async functions (FastAPI routes)."""
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            now = time.time()
            if key in _store:
                ts, val = _store[key]
                if now - ts < ttl:
                    _stats["hits"] += 1
                    return val
            _stats["misses"] += 1
            try:
                result = await fn(*args, **kwargs)
                if isinstance(result, dict) and "error" in result:
                    if key in _store:
                        print(f"[cache_store] {key} returned logic error, serving stale cache.")
                        stale_val = _store[key][1]
                        if isinstance(stale_val, dict): stale_val["_stale"] = True
                        return stale_val
                    _store[key] = (now - ttl + 60, result)
                    return result

                _store[key] = (now, result)
                return result
            except Exception as e:
                print(f"[cache_store] Exception in {key}: {e}")
                if key in _store:
                    stale_val = _store[key][1]
                    if isinstance(stale_val, dict): stale_val["_stale"] = True
                    return stale_val
                raise e
        return wrapper
    return decorator


def get_cache_stats() -> dict:
    total = _stats["hits"] + _stats["misses"]
    return {
        "hits": _stats["hits"],
        "misses": _stats["misses"],
        "hit_ratio": round(_stats["hits"] / max(total, 1), 2),
        "active_entries": len(_store),
    }


def invalidate(key: str = None):
    """Clear specific or all cached results."""
    if key:
        _store.pop(key, None)
    else:
        _store.clear()
