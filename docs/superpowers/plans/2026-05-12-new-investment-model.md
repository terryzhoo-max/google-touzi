# New Investment Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build a deterministic regime-aware ETF allocation model that recommends target weights, trades, constraints, evidence, and review schedule for the real nine-ETF portfolio.

**Architecture:** Add focused backend modules for allocation policy, ETF signals, and allocation construction. Wire the model into `/api/institutional/allocation_model`, embed it in `/api/institutional/decision`, and render a compact safe-DOM frontend panel.

**Tech Stack:** Python 3.10+, FastAPI, pytest, existing AlphaCore portfolio/risk/scenario/factor/compliance modules, browser DOM APIs.

---

## File Structure

- Create `core/allocation_policy.py`: versioned allocation policy, stable hash, and JSON serialization.
- Create `core/etf_signal_model.py`: one deterministic signal packet per real ETF.
- Create `core/allocation_model.py`: target-weight construction, constraints, what-if, evidence, and recommendation packet.
- Modify `data_engine.py`: API endpoints and decision payload embedding.
- Modify `core/cache_store.py`: TTL entries for allocation model routes.
- Modify `static/index.html`: ETF allocation model panel.
- Modify `static/main.js`: safe rendering of target weights, trades, and evidence.
- Add `tests/test_allocation_model.py`: backend model contract tests.
- Extend `tests/test_institutional_api_contract.py`: API contract tests.
- Extend `tests/test_static_security.py`: frontend static contract tests.

## Tasks

### Task 1: Allocation Policy

**Files:**
- Create: `core/allocation_policy.py`
- Test: `tests/test_allocation_model.py`

- [x] Write failing tests for default policy version, stable 64-char policy hash, and hash change when one field changes.
- [x] Run `python -m pytest tests/test_allocation_model.py::test_allocation_policy_hash_is_stable_and_sensitive -q` and verify import failure.
- [x] Implement `AllocationPolicy`, `get_default_allocation_policy()`, `allocation_policy_hash()`, and `allocation_policy_to_dict()`.
- [x] Re-run the focused test.

### Task 2: ETF Signals

**Files:**
- Create: `core/etf_signal_model.py`
- Test: `tests/test_allocation_model.py`

- [x] Write failing tests that the signal builder returns one signal per real ETF with component scores, composite score, confidence, and reasons.
- [x] Run the focused test and verify missing function failure.
- [x] Implement deterministic ETF signal scoring using region, strategy, asset class, risk score, scenario score, and data quality.
- [x] Re-run the focused test.

### Task 3: Allocation Recommendation

**Files:**
- Create: `core/allocation_model.py`
- Test: `tests/test_allocation_model.py`

- [x] Write failing tests that target weights sum to 1.0, constraints are present, trades are thresholded, and risk deltas are included.
- [x] Write failing tests that weak data quality returns `observe` or `limited`.
- [x] Implement `build_allocation_recommendation()` with bounded deltas, policy caps, what-if, compliance, evidence, and review schedule.
- [x] Re-run backend model tests.

### Task 4: API Integration

**Files:**
- Modify: `data_engine.py`
- Modify: `core/cache_store.py`
- Test: `tests/test_institutional_api_contract.py`

- [x] Write failing tests for `GET /api/institutional/allocation_model`, `GET /api/institutional/allocation_model/policy`, and embedded `allocation_model` in `/api/institutional/decision`.
- [x] Run the focused API tests and verify route/key failures.
- [x] Add imports, builder helper, endpoints, cache TTL keys, and decision payload embedding.
- [x] Re-run API tests.

### Task 5: Frontend Panel

**Files:**
- Modify: `static/index.html`
- Modify: `static/main.js`
- Test: `tests/test_static_security.py`

- [x] Write failing static assertions for allocation panel IDs, API usage, and safe rendering helpers.
- [x] Run static tests and verify failure.
- [x] Add a compact allocation model panel and safe DOM renderer.
- [x] Re-run static tests and `node --check static\main.js`.

### Task 6: Full Verification and Delivery

**Files:**
- None unless verification exposes a defect.

- [x] Run `python -m pytest -q`.
- [x] Run `node --check static\main.js`.
- [x] Run `git diff --check`.
- [x] Run a temporary local `/api/institutional/allocation_model` smoke check if possible.
- [x] Commit with `feat: add regime-aware ETF allocation model`.
- [x] Push `main` to `origin`.

## Self-Review

- Spec coverage: policy, signals, allocation recommendation, API, frontend, audit-ready evidence, and tests are covered.
- Scope control: no automatic trading, no broker API, no paid data dependency, no ML black box.
- Type consistency: policy hash, model hash, target weights, proposed trades, constraint result, evidence chain, and review schedule are named consistently across backend, API, and frontend.
