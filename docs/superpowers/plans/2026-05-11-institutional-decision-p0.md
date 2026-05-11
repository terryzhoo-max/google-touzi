# Institutional Decision P0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the P0 institutional decision foundation: portfolio book, data quality scoring, portfolio risk engine, scenario stress interface, and decision ticket output.

**Architecture:** Add focused backend modules under `core/` and expose read-only API endpoints from `data_engine.py`. Keep the first release deterministic and local-first: use a sample portfolio provider and pure calculation functions so tests do not require network data.

**Tech Stack:** Python 3.10+, FastAPI, pandas, numpy, pytest, existing AlphaCore cache/data-provider conventions.

---

## Tasks

1. Portfolio Book: create `core/portfolio_book.py` and tests.
2. Data Quality: create `core/data_quality.py` and tests.
3. Risk Engine: create `core/risk_engine.py` and tests.
4. Scenario Engine: create `core/scenario_engine.py` and tests.
5. Decision Ticket: create `core/decision_ticket.py` and tests.
6. Institutional API: expose `/api/institutional/decision`.
7. Frontend Panel: add a compact institutional decision panel.
8. Verification: run focused tests, static checks, and endpoint smoke checks.

## Contracts

The backend endpoint `/api/institutional/decision` returns:

```json
{
  "portfolio": {},
  "data_quality": {},
  "risk": {},
  "scenarios": {},
  "decision_ticket": {}
}
```

The first release uses a deterministic sample portfolio:

```text
SPY 45%, TLT 25%, GLD 15%, CASH 15%
```

Execution note: this worktree may not have Python on PATH. If `python` or `pytest` is unavailable, continue implementation with static checks and report the blocked runtime verification explicitly.
