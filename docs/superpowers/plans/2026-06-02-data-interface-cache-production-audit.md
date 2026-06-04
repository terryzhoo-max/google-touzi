# Data Interface and Cache Production Audit Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run an institution-grade production audit of AlphaCore data interfaces, cache behavior, rate-limit handling, and degradation paths before making code changes.

**Architecture:** Treat the system as three layers: route-result cache, provider-level cache/guard, and source-specific failover. First map every external call and cache boundary, then add focused tests for rate-limit and stale-cache behavior, then harden only the gaps that tests expose.

**Tech Stack:** Python 3.12, FastAPI, pytest, SQLite, urllib, pandas, Tushare, FRED, AKShare, DeepSeek API.

---

## Current Source Map

- Route cache: `core/cache_store.py`
  - L1 in-process `_store`
  - L2 SQLite `api_cache` via `core/db_layer.py`
  - sync/async decorators with per-key locks
  - stale serving on downstream refresh error
- Provider cache and guard: `core/data_providers.py`
  - `_provider_cache` for FRED and Tushare payloads
  - `_circuit` for `fred`, `tushare_fund`, `tushare_fx`, `tushare_index`
  - `_rate_limit()` serial spacing with jitter
  - `_sqlite_failover_series()` for local time-series fallback
- Macro memory cache: `core/market_data.py`
  - `DATA_CACHE` for `tnx`, `vix`, `dxy`, `csi300`, `correlation`
  - background refresh every 1800 seconds
- Health visibility: `app/routes/health.py`
  - provider stats, circuit state, route cache stats, runtime diagnostics
- App-level guard: `app/factory.py`
  - per-client API rate limit with HTTP 429 and `Retry-After: 30`
- FRED consumers:
  - `core/data_providers.py`: `VIXCLS`, `DTWEXBGS`, `DGS10`
  - `core/yield_curve.py`: `DGS2`, `DGS5`, `DGS10`, `DGS30`
  - `core/fed_prob.py`: `DFEDTARU`, `DFEDTARL`, `DFEDTAR`, `DGS2`
  - `core/global_assets.py`: `DGS10`
- Tushare consumers:
  - `core/data_providers.py`: `fund_daily`, `fx_daily`, `index_daily`, `index_global`, `sw_daily`
  - `core/china_macro.py`: `cn_cpi`, `cn_pmi`, `cn_m`, `cn_gdp`
  - `core/market_breadth.py`: `moneyflow_hsgt`
  - `core/margin_monitor.py`: `margin`
  - `core/dividend_yield.py`: `trade_cal`, `daily_basic`, `stock_basic`
  - `core/valuation.py`: `index_dailybasic`, `fund_daily`
  - `core/asset_rotation.py` and `core/sector_rotation.py`: shared multi-asset snapshot
- LLM consumers:
  - `core/llm_agent.py`: DeepSeek chat completions with deterministic local fallbacks

## Production Risks to Check

- P0: FRED rate-limit amplification. On HTTP 429, text containing `Too Many Requests`, or guard/circuit open, FRED must stop the current request immediately and use provider cache, SQLite failover, or deterministic empty-safe payloads. It must not sleep and retry inside the same request.
- P0: Cache stampede on cold start. Route-level background refresh avoids blocking, but compute functions can still fan out internally through `ThreadPoolExecutor`, especially `global_assets`, `calculate_correlation_matrix`, `run_montecarlo_sim`, and backtest paths.
- P0: SQLite cache freshness and corruption behavior. `api_cache` and `time_series` reads must not turn a bad JSON row, locked DB, or stale row into a broken route response.
- P1: Cross-provider shared HTTP helpers. `_http_get()` and `_http_post()` are generic; FRED-specific 429 stop logic must not disable ordinary transient retry behavior for Tushare or non-rate-limit FRED network errors.
- P1: Provider stats accuracy. `calls`, `hits`, `errors`, `last_ok`, `last_err`, and circuit state must match actual behavior so `/api/health` is operationally trustworthy.
- P1: AKShare fallback safety. Automatic AKShare fallback is disabled by default; tests must ensure disabled paths do not import or call AKShare.
- P1: Background daemon invalidation. `background_data_fetcher()` invalidates selected route keys after macro refresh; invalidation must not delete unrelated route cache or create repeated cold-start loops.
- P2: Encoding and user-facing degradation text. Several Chinese strings are mojibake in source output; this is not a data-interface outage, but degraded messages and alerts must remain machine-readable and not corrupt JSON.

## Acceptance Criteria

- FRED 429 or `Too Many Requests` produces zero sleep calls, at most one outbound FRED attempt for that logical request, increments FRED error stats once, opens or records guard state according to threshold rules, and returns stale provider cache or SQLite fallback when present.
- FRED circuit open produces zero outbound FRED attempts.
- Repeated concurrent requests for the same route key produce one refresh task per key and serve stale or `syncing` payloads without blocking the caller.
- Repeated concurrent provider requests for the same source key do not exceed the configured provider budget in one route invocation.
- `/api/health` shows degraded source state when provider error rate is above threshold or circuit state is not closed.
- No test logs or API responses expose raw API keys or bearer tokens.
- Existing tests continue passing after any future hardening patch.

## Tasks

### Task 1: FRED 429 and Guard Contract

**Files:**
- Modify tests only first: `tests/test_data_provider_fred_guard.py`
- Potential implementation target after failing tests: `core/data_providers.py`

- [x] Add a test where `urllib.request.urlopen` raises an HTTP 429 error and `time.sleep` is patched to fail if called.
- [x] Assert `_fred_series("DGS10", limit=5)` returns stale `_provider_cache["fred:DGS10:5"]` when present.
- [x] Assert FRED stats record one call and one error, and the captured `last_error` contains no API key.
- [x] Add a test where `_circuit["fred"]["state"] = "open"` and `opened_at` is current.
- [x] Assert `_fred_series()` does not call `urlopen` and returns stale provider cache when present.
- [x] Add a no-cache variant and assert it returns an empty `pd.Series` with the requested series name.
- [x] Run `python -m pytest tests/test_data_provider_fred_guard.py -q`.
- [x] If tests fail, update FRED-specific handling in `core/data_providers.py` so 429 and `Too Many Requests` bypass local retry and fall through to stale/failover logic.

### Task 2: Shared HTTP Retry Boundary

**Files:**
- Modify tests only first: `tests/test_data_provider_http_retry.py`
- Potential implementation target after failing tests: `core/data_providers.py`

- [x] Add a test proving non-429 transient FRED failures still use bounded retry with exponential waits.
- [x] Add a test proving Tushare `_http_post()` retains bounded retry for transient connection errors.
- [x] Add a test proving FRED 429 does not consume all retry attempts.
- [x] Run `python -m pytest tests/test_data_provider_http_retry.py -q`.
- [x] If tests fail, split source-aware GET behavior into a FRED wrapper or pass a `stop_on_rate_limit=True` option only from `_fred_series()`.

### Task 3: Route Cache and SQLite L2 Contract

**Files:**
- Extend: `tests/test_cache_store.py`
- Potential implementation target after failing tests: `core/cache_store.py`
- Potential implementation target after failing tests: `core/db_layer.py`

- [x] Add a sync cached route test that returns fresh L1 data with `_cache.stale == False`.
- [x] Add a stale route test where refresh raises and stale L1 is returned with `_stale == True`.
- [x] Add a SQLite L2 rehydration test using a saved `api_cache` payload.
- [x] Add a corrupted JSON row test and assert `get_api_cache()` returns `(None, 0.0)` without raising.
- [x] Add an `invalidate(key)` test that deletes only the requested key and keeps other keys intact.
- [x] Run `python -m pytest tests/test_cache_store.py -q`.
- [x] If tests fail, harden stale serving, JSON handling, and targeted invalidation without changing route payload contracts.

### Task 4: Provider Fan-Out and Budget Audit

**Files:**
- Add: `tests/test_provider_fanout_budget.py`
- Potential implementation target after failing tests: `core/data_providers.py`
- Potential implementation target after failing tests: `core/global_assets.py`
- Potential implementation target after failing tests: `core/quant_engine.py`

- [x] Instrument `_tushare_items` and `_fred_series` with counters in tests.
- [x] Run `get_global_assets()` and record FRED/Tushare logical call count.
- [x] Run `calculate_correlation_matrix()` and `run_montecarlo_sim()` with mocked series and record duplicate SPY/TLT/GLD requests.
- [x] Assert each function stays within an explicit budget documented in the test.
- [x] Run `python -m pytest tests/test_provider_fanout_budget.py -q`.
- [x] If tests fail, add provider-level in-flight coalescing or reduce worker counts for same-provider calls while preserving route latency.

### Task 5: Health Endpoint Production Signals

**Files:**
- Extend: `tests/test_institutional_api_contract.py`
- Extend: `tests/test_runtime_diagnostics.py`
- Potential implementation target after failing tests: `app/routes/health.py`
- Potential implementation target after failing tests: `core/runtime_diagnostics.py`

- [x] Add `/api/health` assertions for provider `sources`, `circuit`, `cache`, `diagnostics`, `rate_limit`, and `degraded_sources`.
- [x] Add a test where FRED circuit is open and `/api/health` status becomes `degraded`.
- [x] Add a test proving optional key status is `present` or `optional_missing`, never raw secret content.
- [x] Run `python -m pytest tests/test_institutional_api_contract.py tests/test_runtime_diagnostics.py -q`.
- [x] If tests fail, normalize health status calculation and secret redaction.

### Task 6: Background Refresh and Invalidation

**Files:**
- Add: `tests/test_background_data_refresh.py`
- Potential implementation target after failing tests: `core/market_data.py`
- Potential implementation target after failing tests: `core/cache_store.py`

- [x] Mock `fetch_fred_10y`, `fetch_macro_indicator`, `fetch_tushare_csi300`, and `invalidate`.
- [x] Run one controlled background refresh cycle by setting `shutdown_event` after the first pass.
- [x] Assert only `erp`, `spread`, `yield_curve`, `decision`, `signals`, and `allocation` are invalidated.
- [x] Assert failed alert-rule evaluation does not fail the refresh cycle.
- [x] Run `python -m pytest tests/test_background_data_refresh.py -q`.
- [x] If tests fail, isolate one-cycle refresh behavior and tighten invalidation keys.

### Task 7: End-to-End Degradation Smoke

**Files:**
- Add: `tests/test_data_degradation_smoke.py`
- Potential implementation target after failing tests: `core/market_data.py`
- Potential implementation target after failing tests: `core/data_providers.py`

- [x] Mock FRED, Tushare, AKShare, and DeepSeek outages.
- [x] Call macro routes through FastAPI test client for ERP, spread, yield curve, decision, global assets, valuation, and AI insight.
- [x] Assert each route returns HTTP 200 or the existing documented `syncing` response, not an unhandled exception.
- [x] Assert stale responses include `_cache` metadata when served by `cache_store`.
- [x] Run `python -m pytest tests/test_data_degradation_smoke.py -q`.
- [x] If tests fail, patch the narrowest failing degradation path.

### Task 8: Final Verification

**Files:**
- None unless earlier tasks require source changes.

- [x] Run `python -m pytest tests/test_cache_store.py tests/test_institutional_resilience.py tests/test_runtime_diagnostics.py -q`.
- [x] Run all new provider and degradation tests from Tasks 1 through 7.
- [x] Run `python -m pytest -q` if focused tests are green.
- [x] Run `git diff --check`.
- [x] Review `/api/health` payload manually or via test client for no secret leakage and correct degraded source reporting.

## Execution Order

1. Lock FRED 429 and guard behavior first because it is the highest blast-radius failure.
2. Verify shared HTTP retry boundaries before editing generic helpers.
3. Verify route cache and SQLite L2, because they are the fallback surface after provider failure.
4. Measure fan-out budgets and only then reduce concurrency or add coalescing.
5. Tighten health signals and background refresh after the source behaviors are deterministic.
6. Run end-to-end degradation smoke last.

## Rollback Rules

- If a hardening patch changes investment signal values under healthy provider responses, revert that patch and keep only tests.
- If a coalescing patch increases route latency beyond existing route timeouts, reduce scope to source-specific serialization for FRED first.
- If SQLite cache behavior changes payload shape, keep existing route contract and attach metadata only through `cache_store`.
- If AKShare import becomes reachable while `ENABLE_AKSHARE_FALLBACK` is false, stop and fix before continuing.

## Self-Review

- Spec coverage: FRED rate-limit amplification, guard open behavior, route cache, provider cache, SQLite fallback, fan-out, health visibility, background refresh, and end-to-end degradation are covered.
- Placeholder scan: every task has concrete files, commands, and expected assertions.
- Scope control: this is an audit-and-hardening plan; no investment model change, no new external provider, no frontend redesign, and no API key changes.
