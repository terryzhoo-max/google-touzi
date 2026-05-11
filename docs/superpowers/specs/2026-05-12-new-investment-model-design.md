# AlphaCore New Investment Model Design

Date: 2026-05-12

## Purpose

AlphaCore needs a new investment model that works like an institutional allocation assistant for the real ETF portfolio:

- CSI300_ETF
- CSI500_ETF
- STAR50_ETF
- HSTECH_ETF
- SP500_ETF
- NASDAQ_ETF
- NIKKEI225_ETF
- CHIP_ETF
- GOLD_ETF

The model must recommend target weights, rebalance actions, and review triggers. It must also explain why the recommendation exists, what constraints were applied, and how much risk changed.

AlphaCore remains a decision-support system. This design does not add automatic trading, broker integration, or unsupervised execution.

## Institutional Benchmark

The target operating model follows the common shape of institutional portfolio platforms:

- BlackRock Aladdin emphasizes full-cycle portfolio, performance, operations, data, and risk integration.
- Bloomberg PORT emphasizes unified positions, risk, performance, construction, factor models, scenarios, and reporting.
- MSCI BarraOne emphasizes multi-asset factor risk, VaR, stress testing, what-if analysis, attribution, and transparent risk-return views.
- Morningstar Direct emphasizes portfolio construction, holdings analysis, scenario stress, and attribution across portfolio decisions.

References:

- https://www.blackrock.com/aladdin/
- https://professional.bloomberg.com/products/bloomberg-terminal/portfolio-analytics/
- https://www.msci.com/data-and-analytics/portfolio-management/barra-one
- https://www.morningstar.com/business/products/direct/portfolio-management-tool

## Current Baseline

The project already has the right foundation:

- Real ETF portfolio input in `data/institutional_portfolio.json`.
- Portfolio exposure by asset class, region, strategy, and currency.
- Risk engine with daily volatility, VaR, CVaR, and risk contribution.
- Scenario engine with equity, rates, China, US technology, and technology drawdown shocks.
- Factor exposure registry for the nine ETF symbols.
- Benchmark and active risk snapshots.
- What-if engine for target weights and risk deltas.
- Trade constraints and compliance checks.
- Decision ticket, reason codes, evidence chain, audit log, review scheduler, and review scoring.
- Production health diagnostics added in the hardening phase.

The missing layer is a model that converts all of this into a single portfolio construction recommendation.

## Design Decision

Use a regime-aware constrained allocation model.

The model should not start as a predictive machine-learning system. The first production-grade version should be deterministic, explainable, testable, and auditable. It can later accept learned signals as one input, but the allocation engine itself should remain governed by explicit policy, constraints, and risk budgets.

### Considered Approaches

1. Rule-only allocation

Simple, transparent, and fast to ship. It is too rigid once multiple regions, themes, and macro states interact.

2. Pure optimizer

Useful for mathematical allocation, but fragile if expected returns are weak or noisy. Without policy and explanations, it can create overfit weights that look precise but are not decision-grade.

3. Regime-aware constrained allocation

Recommended. Combine macro regime scores, valuation, momentum, risk, scenario loss, factor concentration, and policy constraints into a target portfolio. This gives explainability and institutional controls while still producing concrete target weights.

## Model Name

`RegimeAwareETFAllocationModel`

Short label in UI: `ETF Allocation Model`.

## Model Responsibilities

The model must answer:

1. What is the current portfolio stance?
2. Which ETF weights should increase, decrease, or stay unchanged?
3. Which constraints prevent more aggressive changes?
4. How do VaR, worst scenario loss, concentration, and factor exposures change?
5. Which evidence supports the recommendation?
6. When should the decision be reviewed?

## Non-goals

- No trade execution.
- No brokerage API.
- No leverage, short selling, options, or derivatives.
- No minute-level trading.
- No opaque AI-generated weights.
- No external paid data dependency in the first implementation.
- No replacement of the existing institutional decision workflow.

## Inputs

### Portfolio Inputs

- Current positions from `build_portfolio_snapshot()`.
- Current weights and market values.
- Asset class, region, strategy, currency, and factor exposures.
- Benchmark active weights.

### Market Inputs

Use existing local providers and endpoints:

- Macro decision score from `/api/macro/decision`.
- China macro data.
- Valuation percentiles.
- Domestic ETF rotation.
- Global ETF rotation.
- Correlation matrix.
- Scenario stress results.
- Portfolio risk and factor risk.
- Data quality and fallback flags.

### Policy Inputs

Add a versioned allocation policy:

- Max single ETF weight.
- Max China equity exposure.
- Max US equity exposure.
- Max technology theme exposure.
- Min and max gold weight.
- Max turnover per rebalance.
- Min trade size threshold.
- Risk budget for VaR and worst scenario loss.
- Data quality minimum score.
- Defensive mode rules when data is stale, fallback, or degraded.

## Outputs

The model returns an allocation packet:

```json
{
  "model_version": "allocation-v1",
  "model_hash": "sha256...",
  "as_of": "2026-05-12T00:00:00+08:00",
  "status": "allow|limited|observe",
  "current_weights": {},
  "target_weights": {},
  "proposed_trades": [],
  "expected_effect": {
    "var_95_delta_pct": 0.0,
    "worst_scenario_delta_pct": 0.0,
    "turnover_pct": 0.0,
    "concentration_delta": 0.0
  },
  "constraint_result": {},
  "evidence_chain": [],
  "review_schedule": ["T+1", "T+5", "T+20"]
}
```

## Signal Architecture

The model uses four signal families. Each returns `score`, `confidence`, and `reason`.

### 1. Regime Signal

Measures whether the portfolio should be risk-on, balanced, or defensive.

Inputs:

- VIX score.
- TNX and rate trend.
- Yield curve.
- Cross-asset correlation.
- China macro score.
- Valuation percentile.

Output:

- `risk_budget_multiplier`: lower in stress, higher in healthy expansion.
- `defensive_bias`: increases gold and reduces high-beta technology.

### 2. Valuation Signal

Measures where exposure is cheap or expensive relative to policy.

Inputs:

- Existing valuation endpoint.
- China broad-market valuation.
- Technology valuation proxy if available.
- Global equity valuation proxy if available.

Output:

- Positive score for cheap broad-market exposure.
- Negative score for overheated growth or technology exposure.
- Neutral score when data quality is weak.

### 3. Momentum and Breadth Signal

Measures market participation and trend quality.

Inputs:

- Domestic ETF rotation.
- Global ETF rotation.
- Market breadth.
- Recent return windows already used by rotation panels.

Output:

- Tilt toward ETFs with positive trend and broad participation.
- Penalize narrow, crowded, high-volatility leadership.

### 4. Risk and Diversification Signal

Measures whether the target improves portfolio durability.

Inputs:

- Portfolio VaR and CVaR.
- Scenario worst loss.
- Factor concentration.
- Active risk versus benchmark.
- Correlation matrix.

Output:

- Penalize trades that increase worst scenario loss.
- Reward trades that reduce dominant factor concentration without violating return signals.

## Allocation Engine

The allocation engine has five deterministic steps.

### Step 1: Build Base Weights

Start from current weights rather than a theoretical model portfolio. This reduces churn and keeps the recommendation anchored to the real portfolio.

### Step 2: Compute ETF Scores

For each ETF:

```text
raw_score =
  0.30 * regime_fit +
  0.25 * valuation_score +
  0.20 * momentum_score +
  0.15 * risk_diversification_score +
  0.10 * data_confidence_score
```

Scores are relative, not absolute forecasts.

### Step 3: Convert Scores to Target Deltas

Map ETF scores into target changes with bounded deltas:

- Strong positive: add up to policy max step.
- Mild positive: add half step.
- Neutral: no change.
- Mild negative: reduce half step.
- Strong negative: reduce up to policy max step.

### Step 4: Apply Constraints

Run the target through policy constraints:

- Weight caps.
- Exposure caps.
- Turnover cap.
- Minimum gold floor.
- Scenario loss guardrail.
- Data quality guardrail.
- Minimum trade size.

Blocked changes become repair suggestions instead of disappearing silently.

### Step 5: Run What-if and Evidence

Use existing what-if, risk, scenario, factor, compliance, and audit modules to produce:

- Before and after risk.
- Before and after scenario loss.
- Factor exposure changes.
- Constraint pass/warn/block.
- Evidence chain.
- Review schedule.

## Data Model

### AllocationPolicy

Fields:

- `version`
- `max_single_weight`
- `max_region_weight`
- `max_theme_weight`
- `min_gold_weight`
- `max_gold_weight`
- `max_turnover`
- `max_single_trade`
- `min_trade_size`
- `var_limit_pct`
- `worst_scenario_limit_pct`
- `data_quality_min_score`
- `policy_hash`

### ETFSignal

Fields:

- `symbol`
- `regime_fit`
- `valuation_score`
- `momentum_score`
- `risk_diversification_score`
- `data_confidence_score`
- `composite_score`
- `confidence`
- `reasons`

### AllocationRecommendation

Fields:

- `model_version`
- `model_hash`
- `status`
- `current_weights`
- `target_weights`
- `proposed_trades`
- `expected_effect`
- `constraint_result`
- `evidence_chain`
- `review_schedule`

## API Design

Add:

- `GET /api/institutional/allocation_model`
- `GET /api/institutional/allocation_model/policy`
- `POST /api/institutional/allocation_model/simulate`
- `POST /api/institutional/allocation_model/audit`

Extend:

- `GET /api/institutional/decision`

The decision endpoint should include an `allocation_model` block, but the standalone endpoint remains available for focused testing and UI panels.

## Frontend Design

Add one institutional panel after the current decision workbench:

### Panel: ETF Allocation Model

Show:

- Current vs target weight table.
- Proposed trade list.
- Expected risk delta.
- Worst scenario delta.
- Constraint status.
- Top three evidence reasons.
- Model version and policy hash.
- Review due schedule.

The panel should use existing dashboard styles and safe DOM rendering helpers. It should not render API-derived strings with raw `innerHTML`.

## Error Handling

The model must return a controlled packet even when some data is missing.

Status rules:

- `allow`: data quality is strong, constraints pass, and risk does not worsen.
- `limited`: data is usable but one or more warnings require staged or reduced trades.
- `observe`: data quality is weak, constraints block the target, or stress risk worsens.

No exception should crash `/api/institutional/decision`. If the model cannot compute a full recommendation, return an `observe` packet with clear degradation reasons.

## Testing Strategy

Add tests before implementation:

1. Policy hashing is stable and changes when policy changes.
2. ETF signal builder returns one signal per real ETF.
3. Target weights sum to 1.0.
4. Target weights never breach single ETF, region, theme, gold, or turnover constraints.
5. Weak data quality forces `observe` or `limited`.
6. Worst scenario loss guardrail blocks risk-increasing recommendations.
7. Allocation endpoint includes model version, policy hash, target weights, trades, evidence, and constraint result.
8. Decision endpoint embeds the allocation model block.
9. Frontend static tests verify panel IDs and safe rendering.

## Rollout Plan

### Phase 1: Backend Model Core

Create:

- `core/allocation_policy.py`
- `core/etf_signal_model.py`
- `core/allocation_model.py`

Integrate with existing portfolio, risk, scenario, factor, what-if, and compliance modules.

### Phase 2: API Integration

Add standalone allocation model endpoints and embed the model packet in institutional decision output.

### Phase 3: Frontend Panel

Add a compact institutional panel for current vs target weights, proposed trades, evidence, and constraints.

### Phase 4: Audit and Review

Record allocation model decisions into the audit log and connect review scoring to the target-versus-outcome analysis.

## Acceptance Criteria

The implementation is ready when:

1. `python -m pytest -q` passes.
2. `node --check static\main.js` passes.
3. `git diff --check` passes.
4. Allocation model endpoint returns deterministic output for the real nine-ETF portfolio.
5. Target weights sum to 1.0.
6. Constraint result explains every block or warning.
7. Decision endpoint includes allocation model output.
8. Frontend panel renders current weights, target weights, risk deltas, and evidence safely.
9. Audit log can store and verify an allocation model recommendation.

## Scope Control

This design is one implementation unit. It deliberately excludes:

- Predictive ML.
- Real trade execution.
- New paid data providers.
- Full portfolio accounting.
- Mobile UI redesign.

Those can be later phases after the deterministic allocation model is working, tested, and reviewed.

## Self-Review

- No unresolved markers remain.
- The design fits the current AlphaCore modules instead of replacing them.
- The model is deterministic and auditable.
- The first version can be implemented and tested locally.
- Risk, scenario, compliance, evidence, audit, and review workflows remain first-class.
