# Production Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add production diagnostics, startup-script hardening, and safer frontend rendering without changing institutional decision outputs.

**Architecture:** Add a focused runtime diagnostics module and expose it through `/api/health`. Harden `start_alphacore.bat` with env overrides and no-browser mode, then replace selected API-derived `innerHTML` updates with `textContent`/DOM helpers.

**Tech Stack:** Python 3.10+, FastAPI, pytest, Windows batch, browser DOM APIs.

---

## File Structure

- Create `core/runtime_diagnostics.py`: config, portfolio, audit DB, and git metadata checks.
- Modify `data_engine.py`: include production diagnostics in `/api/health`.
- Modify `start_alphacore.bat`: env overrides, `--no-browser`, dependency list, clearer port handling.
- Modify `static/main.js`: safe text helpers for alert list, health status, correlation insight, and scenario grid.
- Add tests:
  - `tests/test_runtime_diagnostics.py`
  - extend `tests/test_institutional_api_contract.py`
  - extend `tests/test_static_security.py`

## Tasks

### Task 1: Runtime Diagnostics

**Files:**
- Create: `core/runtime_diagnostics.py`
- Test: `tests/test_runtime_diagnostics.py`

- [x] Write failing tests for safe config diagnostics, optional key presence, portfolio path status, audit DB status, and git metadata.
- [x] Run `python -m pytest tests/test_runtime_diagnostics.py -q` and verify missing module failure.
- [x] Implement `build_runtime_diagnostics(settings, cwd=None)`.
- [x] Re-run diagnostics tests.

### Task 2: Health Endpoint Diagnostics

**Files:**
- Modify: `data_engine.py`
- Test: `tests/test_institutional_api_contract.py`

- [x] Write failing health endpoint assertions for `diagnostics`, `config`, `portfolio`, `audit_db`, `git`, and secret non-leakage.
- [x] Run the focused API contract test and verify failure.
- [x] Wire `build_runtime_diagnostics()` into `/api/health`.
- [x] Re-run API contract tests.

### Task 3: Startup Script Hardening

**Files:**
- Modify: `start_alphacore.bat`
- Test: `tests/test_static_security.py`

- [x] Write failing static assertions for env overrides, `--no-browser`, required dependencies, and explicit PID output.
- [x] Run static security tests and verify failure.
- [x] Update the batch script.
- [x] Re-run static security tests.

### Task 4: Frontend Safe Rendering

**Files:**
- Modify: `static/main.js`
- Test: `tests/test_static_security.py`

- [x] Write failing static assertions that health/freshness, alert list, correlation insight, and scenario grid avoid API-derived `innerHTML`.
- [x] Run static security tests and verify failure.
- [x] Add small DOM helper functions and replace the targeted unsafe rendering.
- [x] Re-run static security tests and `node --check static\main.js`.

### Task 5: Full Verification

**Files:**
- None unless documentation needs a correction.

- [x] Run `python -m pytest -q`.
- [x] Run `node --check static\main.js`.
- [x] Run `git diff --check`.
- [x] Run a focused `/api/health` smoke check against the local server if available.

## Self-Review

- Spec coverage: diagnostics, health, startup script, frontend safety, and tests are covered.
- Scope control: no new investment model, no auth, no broker integration, no new dependency.
- Type consistency: diagnostics return plain JSON dictionaries matching existing API style.
