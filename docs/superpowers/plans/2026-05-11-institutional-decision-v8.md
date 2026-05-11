# Institutional Decision v8 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend AlphaCore from the P0 decision packet into a benchmark-aware institutional workbench with factor risk, active risk, attribution, compliance, and evidence chains.

**Architecture:** Add focused pure-Python engines under `core/`, then compose them in `data_engine.py` beside the existing institutional endpoints. Keep calculations deterministic and local-first so the full suite runs without external data or paid providers.

**Tech Stack:** Python 3.10+, FastAPI, pytest, existing static HTML/CSS/JS.

---

## File Structure

- Create `core/factor_risk.py`: deterministic ETF factor exposure registry and portfolio factor aggregation.
- Create `core/benchmark_book.py`: default benchmark definition, benchmark hash, active weights, and tracking-error proxy.
- Create `core/compliance_engine.py`: production-grade pre-trade compliance rules over current and target snapshots.
- Create `core/attribution_engine.py`: deterministic review-window attribution for audited decisions.
- Create `core/evidence_chain.py`: structured evidence chain for decision packets.
- Modify `data_engine.py`: expose new endpoints and extend `/api/institutional/decision`.
- Modify `core/action_generator.py`: consume compliance status when present.
- Modify `core/audit_log.py`: store benchmark hash and compliance status summary columns.
- Modify `static/index.html`, `static/main.js`, `static/styles.css`: add compact Institutional Workbench tabs.
- Add/modify tests under `tests/` for each new engine, API contract, audit persistence, and frontend DOM contract.

## Tasks

### Task 1: Factor Risk Engine

**Files:**
- Create: `core/factor_risk.py`
- Test: `tests/test_factor_risk.py`

- [x] Write failing tests for ETF factor mapping and aggregate top factor.
- [x] Run `python -m pytest tests/test_factor_risk.py -q` and verify import failure.
- [x] Implement deterministic factor registry and aggregation.
- [x] Re-run `python -m pytest tests/test_factor_risk.py -q`.

### Task 2: Benchmark and Active Risk

**Files:**
- Create: `core/benchmark_book.py`
- Test: `tests/test_benchmark_book.py`

- [x] Write failing tests for benchmark hash stability, active weights, and tracking error proxy.
- [x] Run `python -m pytest tests/test_benchmark_book.py -q` and verify import failure.
- [x] Implement benchmark book, active risk, and largest active exposures.
- [x] Re-run `python -m pytest tests/test_benchmark_book.py -q`.

### Task 3: Pre-trade Compliance

**Files:**
- Create: `core/compliance_engine.py`
- Modify: `core/action_generator.py`
- Test: `tests/test_compliance_engine.py`

- [x] Write failing tests for pass, warn, block, defensive-only mode, and action downgrade.
- [x] Run `python -m pytest tests/test_compliance_engine.py -q tests/test_action_generator.py -q`.
- [x] Implement compliance policy rules and action-generator integration.
- [x] Re-run focused compliance and action tests.

### Task 4: Attribution Engine

**Files:**
- Create: `core/attribution_engine.py`
- Test: `tests/test_attribution_engine.py`

- [x] Write failing tests for allocation, selection, currency, and decision effect outputs.
- [x] Run `python -m pytest tests/test_attribution_engine.py -q`.
- [x] Implement deterministic attribution snapshots for T+1, T+5, and T+20 windows.
- [x] Re-run attribution tests.

### Task 5: Evidence Chain

**Files:**
- Create: `core/evidence_chain.py`
- Modify: `core/decision_explainer.py`
- Test: `tests/test_evidence_chain.py`

- [x] Write failing tests for metric, threshold, direction, source quality, and policy hash evidence.
- [x] Run `python -m pytest tests/test_evidence_chain.py -q`.
- [x] Implement evidence-chain builder and attach it to decision output.
- [x] Re-run evidence tests.

### Task 6: API Contract

**Files:**
- Modify: `data_engine.py`
- Modify: `test_system.py`
- Test: `tests/test_institutional_api_contract.py`

- [x] Write failing API tests for `/factors`, `/benchmark`, `/active_risk`, `/attribution`, `/compliance`, and decision extensions.
- [x] Run `python -m pytest tests/test_institutional_api_contract.py -q`.
- [x] Wire new core modules into FastAPI endpoints and decision packet builder.
- [x] Re-run API contract tests.

### Task 7: Audit Summary Extension

**Files:**
- Modify: `core/audit_log.py`
- Test: `tests/test_audit_log.py`

- [x] Write failing tests that recorded decisions expose benchmark hash and compliance status.
- [x] Run `python -m pytest tests/test_audit_log.py -q`.
- [x] Add summary columns with migration and verification checks.
- [x] Re-run audit tests.

### Task 8: Frontend Institutional Workbench

**Files:**
- Modify: `static/index.html`
- Modify: `static/main.js`
- Modify: `static/styles.css`
- Test: `tests/test_static_security.py`

- [x] Write failing static tests for required workbench DOM ids and `textContent` updates.
- [x] Run `python -m pytest tests/test_static_security.py -q` and `node --check static\main.js`.
- [x] Add compact workbench tabs and JS fetch rendering.
- [x] Re-run static and JS syntax checks.

### Task 9: Full Verification

**Files:**
- Modify: documentation only if endpoint names or contracts differ.

- [x] Run `python -m pytest -q`.
- [x] Run `node --check static\main.js`.
- [x] Run `git diff --check`.
- [x] Run institutional endpoint smoke checks against the local server.

## Self-Review

- Spec coverage: factor risk, benchmark, attribution, compliance, evidence chain, API, frontend, audit, and tests are covered.
- Scope control: multi-user permissions, broker execution, paid data, and full auth remain out of scope.
- Type consistency: core outputs use dict contracts to match existing AlphaCore modules and FastAPI JSON responses.
