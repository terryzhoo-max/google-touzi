# AlphaCore Institutional Decision v8 Design

Date: 2026-05-11

## Purpose

AlphaCore should evolve from a macro and ETF dashboard into an institutional decision support system centered on the real portfolio. The system must help a portfolio owner answer four questions before any action:

1. What risks does the current portfolio actually carry?
2. Which factors, assets, regions, and themes explain those risks?
3. Would a proposed rebalance improve the portfolio after costs and constraints?
4. Can the decision be audited and reviewed later?

This design extends the current P0 foundation: portfolio book, data quality, risk engine, scenario engine, what-if engine, decision ticket, audit log, review scheduler, and frontend institutional panel.

AlphaCore remains an auxiliary decision system. It must not become an automatic trading system.

## Institutional Benchmark

The target shape follows the common operating model of institutional platforms such as BlackRock Aladdin, Bloomberg PORT, MSCI Barra PortfolioManager, SimCorp, State Street Alpha, and FactSet portfolio analytics:

- A shared portfolio view for PM, risk, and review workflows.
- Risk factor decomposition rather than only aggregate VaR.
- Benchmark-relative analysis and tracking error.
- Performance attribution across allocation, selection, currency, and strategy effects.
- Pre-trade compliance before execution.
- Decision evidence, policy versioning, audit logs, and scheduled review.

## Current Baseline

The system already includes:

- Real ETF holdings through `data/institutional_portfolio.json`.
- Portfolio exposures by asset class, region, strategy, and currency.
- Data quality checks with fallback flags.
- Portfolio VaR, CVaR, risk level, and contribution.
- Scenario stress testing and worst scenario detection.
- What-if rebalance simulation.
- Action recommendation generation.
- Versioned decision policy and SHA-256 policy hash.
- Decision tickets and reason-code explanations.
- SQLite audit log with payload integrity verification.
- T+1, T+5, and T+20 review scheduling and review scoring.
- Frontend institutional decision panel.

The next stage should not add isolated widgets. It should add institutional decision layers that make the existing decision packet more explainable, benchmark-aware, and governable.

## Recommended Path

Choose the operating-system path:

```text
Real Portfolio
-> Data Quality
-> Factor Risk
-> Benchmark and Active Risk
-> Scenario Stress
-> What-if Rebalance
-> Pre-trade Compliance
-> Decision Ticket
-> Audit Log
-> T+1 / T+5 / T+20 Review
-> Attribution and Policy Iteration
```

This path is preferred because it compounds the current P0 work instead of replacing it. It turns AlphaCore into a decision loop where every recommendation has a source, a policy, a constraint check, and a review outcome.

## Scope

### P1-A: Factor Risk and Benchmark

Add a factor layer that maps each ETF holding to interpretable exposures.

Required factor groups:

- Region: China, United States, Japan, Hong Kong, Global.
- Asset class: Equity, Gold, Cash, Fixed Income if later added.
- Strategy: broad market, small/mid cap, growth, technology, semiconductor, defensive, safe haven.
- Macro: equity beta, rate sensitivity, dollar sensitivity, inflation sensitivity, liquidity sensitivity.
- Theme: US technology, China equity, Hong Kong growth, Japan equity, semiconductor, gold hedge.

Add benchmark support:

- Configurable benchmark portfolio.
- Benchmark version and benchmark hash.
- Active weight by holding, region, strategy, and asset class.
- Tracking error proxy.
- Active risk contribution.
- Largest active exposures.

The output must explain whether risk is coming from absolute exposure or active deviation from the benchmark.

### P1-B: Performance Attribution

Add attribution for review and learning.

Required attribution views:

- Allocation contribution by asset class, region, strategy, and theme.
- Selection contribution by holding when a proxy benchmark exists.
- Currency contribution for USD, HKD, JPY, and CNY exposures.
- Decision attribution for each audited decision after T+1, T+5, and T+20.

The Review Scheduler should use attribution to score whether a decision improved the portfolio, not only whether risk metrics moved.

### P1-C: Pre-trade Compliance

Productionize constraints before action generation.

Required rules:

- Maximum single ETF weight.
- Maximum region weight.
- Maximum strategy or theme weight.
- Minimum liquidity or cash buffer when cash exists in the book.
- Maximum single rebalance turnover.
- Maximum proposed trade size.
- No new risk exposure when portfolio risk is already above policy limit.
- Defensive-only action mode when data quality is weak or fallback data is active.

Compliance output must include:

- Pass, warn, or block status.
- Violated rule ids.
- Human-readable reasons.
- Suggested repair when possible.
- Policy version and policy hash.

### P1-D: Decision Explainability 2.0

Extend the current explanation model from reason codes to evidence chains.

Each recommendation should include:

- Triggering metric.
- Current value.
- Policy threshold.
- Direction of breach or improvement.
- Related scenario or factor.
- Effect of the proposed action.
- Whether the evidence is based on live, stale, fallback, or sample data.

AI text may summarize the evidence, but rules and numeric outputs remain the source of truth.

## Data Model

Add these core entities:

### FactorExposure

Fields:

- `symbol`
- `factor_group`
- `factor_name`
- `exposure`
- `source`
- `as_of`
- `confidence`

### BenchmarkBook

Fields:

- `benchmark_id`
- `version`
- `policy_hash`
- `positions`
- `created_at`

### ActiveRiskSnapshot

Fields:

- `portfolio_weight`
- `benchmark_weight`
- `active_weight`
- `tracking_error_proxy`
- `active_risk_contribution`
- `largest_active_exposures`

### AttributionSnapshot

Fields:

- `period`
- `portfolio_return`
- `benchmark_return`
- `allocation_effect`
- `selection_effect`
- `currency_effect`
- `decision_effect`

### ComplianceResult

Fields:

- `status`
- `score`
- `violations`
- `warnings`
- `repair_suggestions`
- `policy_version`
- `policy_hash`

## API Design

Add these endpoints after the current institutional endpoints:

- `GET /api/institutional/factors`
- `GET /api/institutional/benchmark`
- `GET /api/institutional/active_risk`
- `GET /api/institutional/attribution`
- `GET /api/institutional/compliance`
- `POST /api/institutional/compliance/check`

Extend:

- `GET /api/institutional/decision`
- `GET /api/institutional/action`
- `GET /api/institutional/reviews/{ticket_id}/score`

The extended decision packet should include:

- `factor_risk`
- `benchmark`
- `active_risk`
- `compliance`
- `evidence_chain`

## Frontend Design

The frontend should remain operational and dense, not marketing-oriented.

Add an Institutional Workbench section with four compact tabs:

- Risk: factor exposure, risk contribution, active risk.
- Benchmark: benchmark weights, active weights, tracking error proxy.
- Compliance: rule status, violations, repair suggestions.
- Review: attribution, decision effectiveness, due reviews.

Avoid large hero sections and decorative cards. This is a repeated-use decision surface.

## Error Handling

The system must degrade conservatively:

- Missing benchmark: show absolute risk, disable active risk conclusions.
- Missing factor exposure: mark exposure as unknown, lower confidence, do not infer precision.
- Fallback portfolio data: allow observation and weak recommendations only.
- Failed attribution data: preserve review schedule but mark attribution unavailable.
- Compliance block: action generation must downgrade to observe, reduce risk, or repair.

No endpoint should fail because one optional institutional layer is unavailable. The decision packet should carry availability flags.

## Testing Strategy

Add focused unit tests before implementation:

- Factor exposure mapping from the real ETF book.
- Benchmark loading, hash stability, and active weight math.
- Tracking error proxy and active risk contribution.
- Attribution math for deterministic sample returns.
- Compliance pass, warn, and block cases.
- Decision packet extension contract.
- Frontend static contract for required DOM ids.

Add integration tests:

- Institutional API contract covers all new endpoints.
- Audit log stores new policy, benchmark, compliance, and evidence fields.
- Review scoring can consume attribution outputs.

Verification commands:

```powershell
python -m pytest -q
node --check static\main.js
git diff --check
python test_system.py
```

## Acceptance Criteria

The v8 implementation is complete when AlphaCore can answer:

1. Which factor explains the largest current risk?
2. Which exposure is the largest deviation from benchmark?
3. What is the expected risk improvement from the proposed rebalance?
4. Which compliance rule allows, warns, or blocks the action?
5. Which evidence chain supports the decision?
6. Did the decision improve return, risk, or drawdown at T+1, T+5, and T+20?
7. Can an auditor verify the policy, benchmark, data quality, and payload hash used at decision time?

## Non-goals

- No automatic trade execution.
- No brokerage integration.
- No unrestricted AI-generated trading instructions.
- No multi-user permission system in this phase.
- No external paid data dependency requirement for local tests.
- No large frontend redesign before the core institutional layer is stable.

## Implementation Order

1. Factor exposure registry and tests.
2. Benchmark book and active risk engine.
3. Compliance engine production rules.
4. Decision packet extension.
5. Attribution engine for review windows.
6. Audit log schema extension.
7. Frontend Institutional Workbench tabs.
8. Smoke and regression verification.

## Open Risk

The current ETF book has limited historical and look-through data in local mode. The first implementation should use deterministic proxy mappings and clearly mark confidence. Later data integrations can replace proxy exposures without changing the API contract.

