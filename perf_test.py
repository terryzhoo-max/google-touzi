#!/usr/bin/env python
"""AlphaCore Performance Baseline Test
Measures cold/warm response times across all route categories.

Run: python perf_test.py
Requires: server running at http://127.0.0.1:8888
"""

import time
import urllib.request
import json

BASE = "http://127.0.0.1:8888"

ROUTES = {
    "Macro": [
        "/api/macro/erp",
        "/api/macro/spread",
        "/api/macro/yield_curve",
        "/api/macro/fed_prob",
        "/api/macro/china_macro",
        "/api/macro/surprise_index",
        "/api/macro/market_breadth",
    ],
    "Risk": [
        "/api/macro/correlation",
        "/api/macro/montecarlo",
        "/api/macro/scenario",
        "/api/macro/valuation",
    ],
    "Portfolio": [
        "/api/macro/allocation",
        "/api/macro/efficient_frontier",
        "/api/macro/backtest",
        "/api/macro/sector_rotation",
    ],
    "Global": [
        "/api/macro/global_assets",
        "/api/macro/signals",
        "/api/macro/decision",
    ],
    "Institutional": [
        "/api/institutional/decision",
    ],
}

def fetch(url, timeout=30):
    t0 = time.time()
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        t1 = time.time()
        cache = data.get("_cache", {})
        return round(t1 - t0, 2), cache.get("stale", False), cache.get("age_sec", 0)
    except Exception as e:
        return None, None, None

def main():
    print(f"{'='*60}")
    print(f"AlphaCore Performance Baseline")
    print(f"Server: {BASE}")
    print(f"{'='*60}\n")

    results = {}
    total_routes = sum(len(v) for v in ROUTES.values())

    for category, routes in ROUTES.items():
        print(f"\n{'─'*40}")
        print(f"  {category}")
        print(f"{'─'*40}")
        cat_times = []
        for route in routes:
            url = BASE + route
            t, stale, age = fetch(url)
            if t is not None:
                status = "stale" if stale else ("warm" if age > 0 else "COLD")
                print(f"  {t:6.2f}s  [{status:5s}]  {route}")
                cat_times.append(t)
                results[route] = t
            else:
                print(f"  FAILED         {route}")

    # Health endpoint
    print(f"\n{'─'*40}")
    print(f"  Health Check")
    print(f"{'─'*40}")
    t, _, _ = fetch(BASE + "/api/health")
    health_data = {}
    if t:
        print(f"  {t:6.2f}s  /api/health")
        try:
            req = urllib.request.Request(BASE + "/api/health")
            with urllib.request.urlopen(req, timeout=10) as resp:
                health_data = json.loads(resp.read())
        except: pass

    cache_stats = health_data.get("cache", {})
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Routes tested:    {len(results)}/{total_routes}")
    all_times = [t for t in results.values() if t is not None]
    if all_times:
        print(f"  Avg response:     {sum(all_times)/len(all_times):.2f}s")
        print(f"  Max response:     {max(all_times):.2f}s")
        print(f"  Min response:     {min(all_times):.2f}s")
    print(f"  Cache hits:       {cache_stats.get('hits', '?')}")
    print(f"  Cache misses:     {cache_stats.get('misses', '?')}")
    print(f"  Hit ratio:        {cache_stats.get('hit_ratio', '?')}")
    print(f"  Stale served:     {cache_stats.get('stale_served', '?')}")
    print(f"  Active entries:   {cache_stats.get('active_entries', '?')}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
