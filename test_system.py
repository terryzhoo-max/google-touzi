import requests
import time
import sys

# Force UTF-8 encoding for stdout to avoid Windows charmap errors
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8888"

endpoints = {
    "ERP": "/api/macro/erp",
    "Spreads": "/api/macro/spread",
    "Yield Curve": "/api/macro/yield_curve",
    "Allocation": "/api/macro/allocation",
    "Correlation": "/api/macro/correlation",
    "Monte Carlo": "/api/macro/montecarlo",
    "Efficient Frontier": "/api/macro/efficient_frontier",
    "Scenario": "/api/macro/scenario",
    "Sector Rotation": "/api/macro/sector_rotation",
    "Theme Rotation": "/api/macro/theme_rotation",
    "Domestic ETF": "/api/macro/domestic_etf",
    "Global ETF": "/api/macro/global_etf",
    "China Macro": "/api/macro/china_macro",
    "Market Breadth": "/api/macro/market_breadth",
    "Signals": "/api/macro/signals",
    "AI CIO": "/api/macro/ai_insight",
    "Decision": "/api/macro/decision",
    "Backtest": "/api/macro/backtest"
}

print("="*50)
print("ALPHACORE V18.0 COMPREHENSIVE SYSTEM TEST")
print("="*50)

passed = 0
failed = 0

for name, path in endpoints.items():
    print(f"Testing [ {name} ] endpoint: {path} ... ", end="")
    try:
        t0 = time.time()
        response = requests.get(BASE_URL + path, timeout=60)
        duration = time.time() - t0
        
        if response.status_code == 200:
            data = response.json()
            if "error" in data:
                print(f"FAILED ❌ (Logic Error: {data['error']}) - {duration:.2f}s")
                failed += 1
            else:
                print(f"PASSED ✅ - {duration:.2f}s")
                passed += 1
                
                # Check specific keys to ensure payload integrity
                if name == "Backtest":
                    if "metrics" in data and "strat_cagr" in data["metrics"]:
                        print(f"   -> Backtest metrics found. CAGR: {data['metrics']['strat_cagr']}%")
                    else:
                        print(f"   -> WARNING: Missing metrics in Backtest payload.")
                elif name == "AI CIO":
                    if "insight" in data:
                        print(f"   -> AI Insight length: {len(data['insight'])} chars")
                    else:
                        print(f"   -> WARNING: Missing insight.")
        else:
            print(f"FAILED ❌ (HTTP {response.status_code}) - {duration:.2f}s")
            failed += 1
            
    except requests.exceptions.RequestException as e:
        print(f"FAILED ❌ (Network Error: {e})")
        failed += 1

print("="*50)
print(f"TEST SUMMARY: {passed} PASSED, {failed} FAILED")
print("="*50)
