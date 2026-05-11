# Institutional Decision Runbook

## Purpose

AlphaCore institutional decision mode produces an auditable portfolio decision packet for the configured ETF book. It combines portfolio exposure, data quality, risk budget, scenario stress, what-if improvement, recommended action, Audit Log, and Review Scheduler state.

## Portfolio Input

Set `PORTFOLIO_BOOK_PATH` to a UTF-8 JSON portfolio file. If the path is unset or missing, AlphaCore falls back to the deterministic sample portfolio and marks data quality with a `fallback` flag.

Current default file:

`data/institutional_portfolio.json`

## Core Endpoints

- `/api/institutional/portfolio`: current portfolio book, exposures, concentration.
- `/api/institutional/data_quality`: source, fallback flag, freshness score.
- `/api/institutional/policy`: active decision policy, thresholds, `policy_hash`.
- `/api/institutional/risk`: VaR, CVaR, risk contribution.
- `/api/institutional/scenarios`: scenario stress table and worst scenario.
- `/api/institutional/factors`: factor exposure and top portfolio factor.
- `/api/institutional/benchmark`: policy benchmark and `benchmark_hash`.
- `/api/institutional/active_risk`: active weights, tracking error proxy, and largest active exposures.
- `/api/institutional/attribution`: allocation, selection, currency, and decision attribution.
- `/api/institutional/compliance`: default pre-trade compliance result.
- `/api/institutional/compliance/check`: pre-trade compliance result for submitted adjustments.
- `/api/institutional/what_if`: default risk-reduction rebalance and risk delta.
- `/api/institutional/action`: execution recommendation.
- `/api/institutional/decision`: full decision packet.

## Policy Integrity

Every decision packet includes:

- `policy.version`
- `policy.policy_hash`
- `benchmark.benchmark_hash`
- `compliance.policy_hash`
- `decision_ticket.policy_version`
- `decision_ticket.policy_hash`
- `decision_explanation.policy_version`
- `decision_explanation.policy_hash`
- `evidence_chain.policy_hash`

`policy_hash` is a SHA-256 fingerprint over the active policy version and thresholds. Use it to prove which exact rule snapshot produced a ticket.

## Audit Log

Record a decision:

`POST /api/institutional/audit/decisions`

List recent decisions:

`GET /api/institutional/audit/decisions`

Verify payload integrity:

`GET /api/institutional/audit/verify`

Audit Log summaries include score, decision status, action status, `policy_version`, `policy_hash`, `benchmark_hash`, compliance status, primary driver, payload hash, and review schedule.

## Review Scheduler

Review Scheduler creates T+1, T+5, and T+20 windows for each recorded decision.

Operational endpoints:

- `/api/institutional/reviews/due`
- `/api/institutional/reviews/summary`
- `/api/institutional/reviews/queue`
- `/api/institutional/reviews/{ticket_id}/score`
- `/api/institutional/reviews/scores/due`

Use the queue endpoint first during daily operations, then persist review scores after validating action effectiveness, risk improvement, attribution effect, selection effect, and currency drag or tailwind.

## Verification

Run the automated suite:

`python -m pytest -q`

Run the browser-facing JavaScript syntax check:

`node --check static\main.js`

Run whitespace validation:

`git diff --check`

Run endpoint smoke checks against a live local server:

`python test_system.py`

For a non-default local port:

`python test_system.py http://127.0.0.1:8891`

The smoke runner includes institutional portfolio, policy, decision, what-if, action, audit verification, and review summary endpoints.
