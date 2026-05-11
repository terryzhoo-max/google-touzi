import sys
import time
from dataclasses import dataclass

import requests


if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


DEFAULT_BASE_URL = "http://127.0.0.1:8888"

ENDPOINTS = {
    "Health": "/api/health",
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
    "Backtest": "/api/macro/backtest",
    "Institutional Portfolio": "/api/institutional/portfolio",
    "Institutional Policy": "/api/institutional/policy",
    "Institutional Decision": "/api/institutional/decision",
    "Institutional Factors": "/api/institutional/factors",
    "Institutional Benchmark": "/api/institutional/benchmark",
    "Institutional Active Risk": "/api/institutional/active_risk",
    "Institutional Attribution": "/api/institutional/attribution",
    "Institutional Compliance": "/api/institutional/compliance",
    "Institutional What-if": "/api/institutional/what_if",
    "Institutional Action": "/api/institutional/action",
    "Institutional Audit Verify": "/api/institutional/audit/verify",
    "Institutional Review Summary": "/api/institutional/reviews/summary",
}


@dataclass
class EndpointResult:
    name: str
    path: str
    ok: bool
    duration: float
    status_code: int | None = None
    error: str | None = None
    payload: dict | None = None


def check_endpoint(
    base_url: str,
    name: str,
    path: str,
    timeout: int = 60,
    get=requests.get,
) -> EndpointResult:
    try:
        t0 = time.time()
        response = get(base_url + path, timeout=timeout)
        duration = time.time() - t0

        if response.status_code != 200:
            return EndpointResult(
                name=name,
                path=path,
                ok=False,
                duration=duration,
                status_code=response.status_code,
                error=f"HTTP {response.status_code}",
            )

        data = response.json()
        if isinstance(data, dict) and "error" in data:
            return EndpointResult(
                name=name,
                path=path,
                ok=False,
                duration=duration,
                status_code=response.status_code,
                error=f"Logic Error: {data['error']}",
                payload=data,
            )

        return EndpointResult(
            name=name,
            path=path,
            ok=True,
            duration=duration,
            status_code=response.status_code,
            payload=data if isinstance(data, dict) else None,
        )
    except requests.exceptions.RequestException as exc:
        return EndpointResult(
            name=name,
            path=path,
            ok=False,
            duration=0.0,
            error=f"Network Error: {exc}",
        )


def run_endpoint_checks(
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 60,
    get=requests.get,
    endpoints: dict[str, str] | None = None,
) -> list[EndpointResult]:
    endpoints = endpoints or ENDPOINTS
    return [
        check_endpoint(base_url, name, path, timeout=timeout, get=get)
        for name, path in endpoints.items()
    ]


def print_result(result: EndpointResult) -> None:
    print(f"Testing [ {result.name} ] endpoint: {result.path} ... ", end="")
    if not result.ok:
        print(f"FAILED ❌ ({result.error}) - {result.duration:.2f}s")
        return

    print(f"PASSED ✅ - {result.duration:.2f}s")
    data = result.payload or {}
    if result.name == "Backtest":
        metrics = data.get("metrics", {})
        if "strat_cagr" in metrics:
            print(f"   -> Backtest metrics found. CAGR: {metrics['strat_cagr']}%")
        else:
            print("   -> WARNING: Missing metrics in Backtest payload.")
    elif result.name == "AI CIO":
        if "insight" in data:
            print(f"   -> AI Insight length: {len(data['insight'])} chars")
        else:
            print("   -> WARNING: Missing insight.")


def main() -> int:
    base_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE_URL
    print("=" * 50)
    print("ALPHACORE V18.0 COMPREHENSIVE SYSTEM TEST")
    print(f"BASE URL: {base_url}")
    print("=" * 50)

    results = run_endpoint_checks(base_url=base_url)
    for result in results:
        print_result(result)

    passed = sum(1 for result in results if result.ok)
    failed = len(results) - passed

    print("=" * 50)
    print(f"TEST SUMMARY: {passed} PASSED, {failed} FAILED")
    print("=" * 50)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
