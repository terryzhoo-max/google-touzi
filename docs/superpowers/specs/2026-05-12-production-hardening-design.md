# AlphaCore Production Hardening Design

Date: 2026-05-12

## Purpose

AlphaCore now has a complete institutional decision workflow. The next production-grade step is not to add more investment models. It is to make the existing system safer to start, easier to diagnose, and harder to break during daily operation.

This design covers runtime reliability, configuration checks, startup scripts, frontend rendering safety, and health observability.

## Goals

1. Make startup failures explicit before the server launches.
2. Make `/api/health` useful for production triage.
3. Prevent local scripts from hiding configuration or dependency problems.
4. Reduce unsafe frontend HTML rendering from API-derived data.
5. Keep all changes local-first and testable without paid external services.

## Non-goals

- No new investment decision model.
- No brokerage or trade execution integration.
- No authentication or multi-user permission system.
- No full frontend rewrite.
- No new external service dependency.

## Scope

### 1. Configuration Diagnostics

Add a small diagnostics layer that reports configuration status without blocking normal local usage.

Required checks:

- `PORTFOLIO_BOOK_PATH` exists and is readable.
- `ALLOWED_ORIGINS` does not include wildcard `*`.
- `ALLOW_CREDENTIALS` is not enabled with unsafe origins.
- `MAX_REQUESTS_PER_MINUTE` is positive and within a reasonable local range.
- Optional external keys are present or missing:
  - `FRED_API_KEY`
  - `DEEPSEEK_API_KEY`
  - `TUSHARE_TOKEN`
  - `SERVERCHAN_SENDKEY`

Missing optional keys should not fail startup. They should appear in health output as `optional_missing`.

### 2. Health Endpoint Upgrade

Extend `/api/health` to return a production triage block:

- Git commit and branch if available.
- Config diagnostics.
- Portfolio file status.
- Audit database status.
- Cache statistics.
- Rate-limit configuration.
- External data provider degradation state.

The endpoint must avoid leaking secret values. It may expose key presence, never key content.

### 3. Startup Script Hardening

Update `start_alphacore.bat` so it is reliable in local and server-like operation.

Required behavior:

- Allow environment variables to override:
  - `PROJECT_DIR`
  - `HOST`
  - `PORT`
  - `APP_MODULE`
- Support `--no-browser`.
- Check only runtime-critical dependencies:
  - `fastapi`
  - `uvicorn`
  - `pandas`
  - `numpy`
  - `requests`
- Print clear instructions when dependencies are missing.
- Detect occupied port and display the owning PID.
- Avoid destructive process kill unless the user explicitly confirms.

### 4. Frontend Rendering Safety

Reduce direct `innerHTML` usage where values come from API payloads.

Priority targets:

- Alert list rendering.
- Health/freshness indicator.
- Correlation insight.
- Scenario grid.
- Rotation panels.
- Valuation table.
- Global assets table.

Allowed uses:

- Static skeleton or fixed local markup with no API-derived interpolation.
- DOMPurify-sanitized AI markdown rendering.

Where table markup is needed, build DOM nodes with `textContent` instead of string interpolation.

### 5. Test Coverage

Add targeted tests:

- Config diagnostics cover safe defaults, wildcard rejection, optional missing keys, and portfolio path status.
- `/api/health` includes diagnostics and does not leak secret values.
- Startup script static contract covers env overrides, no-browser flag, dependency list, and port PID output.
- Frontend static contract catches unsafe API-derived `innerHTML` patterns.

## Proposed Architecture

Add one focused backend module:

- `core/runtime_diagnostics.py`

Responsibilities:

- Build config diagnostics.
- Build portfolio file diagnostics.
- Build audit database diagnostics.
- Build git metadata defensively.
- Return JSON-safe status payloads.

Modify:

- `data_engine.py`: include diagnostics in `/api/health`.
- `start_alphacore.bat`: startup hardening.
- `static/main.js`: safer rendering helpers.
- `tests/`: add focused production-hardening contracts.

## Error Handling

Diagnostics must never crash the health endpoint. If a check fails, return:

```json
{
  "status": "unknown",
  "error": "short non-secret reason"
}
```

The health endpoint can return `healthy`, `degraded`, or `misconfigured`:

- `healthy`: no degraded providers and no critical config issues.
- `degraded`: external data or optional service unavailable.
- `misconfigured`: local config prevents reliable institutional operation.

## Acceptance Criteria

The implementation is complete when:

1. `python -m pytest -q` passes.
2. `node --check static\main.js` passes.
3. `git diff --check` passes.
4. `/api/health` returns diagnostics with no secret leakage.
5. `start_alphacore.bat --no-browser` can start without opening the browser.
6. Frontend static tests prevent new unsafe API-derived `innerHTML` rendering.

## Rollout Notes

This is a production hardening layer. It should be implemented in small batches and should not change institutional decision outputs unless a health or safety issue is detected.
