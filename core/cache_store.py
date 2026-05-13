"""
In-process route-result cache for AlphaCore API routes.

Design goals:
- L1 cache sits above route handlers and avoids repeated expensive work.
- Per-key locks prevent thundering-herd refreshes on concurrent page loads.
- Stale values are served on transient downstream errors when available.
- Cache metadata is attached to dict payloads for health/debug visibility.
"""

import asyncio
import copy
import functools
import threading
import time
from collections import defaultdict
from typing import Any


_store: dict[str, dict[str, Any]] = {}
_stats: dict[str, int] = {
    "hits": 0,
    "misses": 0,
    "refreshes": 0,
    "stale_served": 0,
    "errors": 0,
}
_sync_locks: defaultdict[str, threading.Lock] = defaultdict(threading.Lock)
_async_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


ROUTE_TTL: dict[str, int] = {
    "decision": 300,
    "erp": 1800,
    "spread": 600,
    "yield_curve": 1800,
    "allocation": 600,
    "correlation": 3600,
    "montecarlo": 1800,
    "efficient_frontier": 3600,
    "scenario": 600,
    "signals": 3600,
    "backtest": 86400,
    "ai_insight": 600,
    "sector_rotation": 3600,
    "china_macro": 86400,
    "market_breadth": 3600,
    "fed_prob": 3600,
    "global_assets": 3600,
    "valuation": 43200,
    "theme_rotation": 3600,
    "domestic_etf": 3600,
    "global_etf": 3600,
    "surprise_index": 43200,
    "health": 120,
    "institutional_portfolio": 300,
    "institutional_data_quality": 300,
    "institutional_risk": 300,
    "institutional_scenarios": 300,
    "institutional_factors": 300,
    "institutional_benchmark": 300,
    "institutional_active_risk": 300,
    "institutional_attribution": 300,
    "institutional_compliance": 300,
    "institutional_decision": 300,
    "institutional_policy": 300,
    "institutional_what_if": 300,
    "institutional_action": 300,
    "institutional_allocation_model": 300,
    "institutional_allocation_model_policy": 300,
    "institutional_audit_log": 120,
    "institutional_reviews_due": 120,
    "institutional_reviews_summary": 120,
    "institutional_review_scores": 120,
    "institutional_review_outcomes": 120,
}


def _is_fresh(entry: dict[str, Any], now: float) -> bool:
    return now - float(entry["ts"]) < int(entry["ttl"])


def _with_cache_meta(value: Any, key: str, entry: dict[str, Any], stale: bool = False) -> Any:
    if not isinstance(value, dict):
        return value

    payload = copy.deepcopy(value)
    age = max(0.0, time.time() - float(entry["ts"]))
    payload["_cache"] = {
        "key": key,
        "age_sec": round(age, 1),
        "ttl_sec": int(entry["ttl"]),
        "stale": stale,
    }
    if stale:
        payload["_stale"] = True
    return payload


def _safe_copy(value: Any) -> Any:
    try:
        return copy.deepcopy(value)
    except Exception:
        return value


def _get_fresh(key: str, now: float) -> Any | None:
    entry = _store.get(key)
    if entry and _is_fresh(entry, now):
        _stats["hits"] += 1
        return _with_cache_meta(entry["value"], key, entry)
    return None


def _store_value(key: str, ttl: int, value: Any, ts: float | None = None) -> Any:
    entry = {"ts": ts or time.time(), "ttl": ttl, "value": _safe_copy(value)}
    _store[key] = entry
    from core.db_layer import save_api_cache
    save_api_cache(key, value)
    return _with_cache_meta(value, key, entry)


def _serve_stale(key: str) -> Any | None:
    entry = _store.get(key)
    if not entry:
        return None
    _stats["stale_served"] += 1
    print(f"[cache_store] Serving stale cache for {key}.")
    return _with_cache_meta(entry["value"], key, entry, stale=True)


def _is_logic_error(value: Any) -> bool:
    if isinstance(value, dict) and bool(value.get("error")):
        return True
    status_code = getattr(value, "status_code", None)
    return isinstance(status_code, int) and status_code >= 400


from core.db_layer import save_api_cache, get_api_cache

def cached(ttl: int, key: str):
    """Decorator for synchronous functions.
    Uses SQLite as a L2 Data Lake to separate API reads from data fetching.
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            now = time.time()
            
            # Check SQLite L2 cache
            payload, updated_at = get_api_cache(key)
            if payload and (now - updated_at < ttl):
                _stats["hits"] += 1
                return payload
            
            _stats["misses"] += 1
            
            # If stale or missing, we want to return STALE data immediately
            # and trigger a background thread to update the cache
            def background_refresh():
                with _sync_locks[key]:
                    # Double check if someone else updated it
                    _, last_update = get_api_cache(key)
                    if time.time() - last_update < ttl: return
                    try:
                        result = fn(*args, **kwargs)
                        if not _is_logic_error(result):
                            _stats["refreshes"] += 1
                            save_api_cache(key, result)
                    except Exception as exc:
                        _stats["errors"] += 1
                        print(f"[cache_store] Async Sync Exception {key}: {exc}")
                        
            # Spin up a thread to fetch it without blocking the API request!
            threading.Thread(target=background_refresh, daemon=True).start()
            
            if payload:
                _stats["stale_served"] += 1
                return payload
                
            return {"status": "syncing", "message": "Initial data sync in progress. Please refresh."}
        return wrapper
    return decorator


def cached_async(ttl: int, key: str):
    """Decorator for async route functions. True Cold/Hot separation."""
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            now = time.time()
            fresh = _get_fresh(key, now)
            if fresh is not None:
                return fresh

            _stats["misses"] += 1

            async def background_refresh():
                async with _async_locks[key]:
                    if _get_fresh(key, time.time()) is not None:
                        return
                    try:
                        result = await fn(*args, **kwargs)
                        if _is_logic_error(result):
                            if isinstance(result, dict):
                                _store_value(key, 60, result)
                        else:
                            _stats["refreshes"] += 1
                            _store_value(key, ttl, result)
                    except Exception as exc:
                        _stats["errors"] += 1
                        print(f"[cache_store] Exception in async background {key}: {exc}")

            # Fire and forget
            asyncio.create_task(background_refresh())

            stale = _serve_stale(key)
            if stale is not None:
                return stale

            return {"status": "syncing", "message": "Initial data sync in progress. Please wait."}
        return wrapper
    return decorator


def get_cache_stats() -> dict:
    total = _stats["hits"] + _stats["misses"]
    now = time.time()
    entries = {}
    for key, entry in _store.items():
        age = max(0.0, now - float(entry["ts"]))
        ttl = int(entry["ttl"])
        entries[key] = {
            "age_sec": round(age, 1),
            "ttl_sec": ttl,
            "expires_in_sec": max(0, round(ttl - age, 1)),
            "fresh": age < ttl,
        }
    return {
        **_stats,
        "hit_ratio": round(_stats["hits"] / max(total, 1), 2),
        "active_entries": len(_store),
        "entries": entries,
    }


def invalidate(key: str | None = None):
    """Clear specific or all cached route results."""
    import sqlite3
    from core.db_layer import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if key:
        cursor.execute('DELETE FROM api_cache WHERE endpoint_key = ?', (key,))
    else:
        cursor.execute('DELETE FROM api_cache')
    conn.commit()
    conn.close()
