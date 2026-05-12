# AlphaCore New Investment Model v2 Design

Date: 2026-05-12

## Purpose

The first investment model is now working as a deterministic, auditable allocation assistant. It produces ETF target weights, proposed trades, constraints, evidence, audit records, and review scores for the real nine-ETF portfolio.

The next phase should not replace that model. It should add a second layer that makes the allocation process more scientific:

1. A predictive signal layer that estimates relative opportunity.
2. A constrained optimizer that converts signals into target weights.
3. A walk-forward backtest that proves whether the model improves risk-adjusted outcomes.
4. A model governance layer that tracks versions, parameter changes, and review outcomes.

This design keeps AlphaCore as a decision-support system. It does not add automatic trading or broker execution.

## Current Baseline

Implemented v1 capabilities:

- `core/allocation_policy.py`: versioned allocation policy and policy hash.
- `core/etf_signal_model.py`: deterministic ETF component scores.
- `core/allocation_model.py`: bounded target-weight deltas, constraints, risk deltas, and evidence.
- `/api/institutional/allocation_model`: standalone model endpoint.
- `/api/institutional/allocation_model/policy`: policy endpoint.
- `/api/institutional/allocation_model/simulate`: simulation endpoint.
- `/api/institutional/allocation_model/audit`: audit endpoint.
- `/api/institutional/decision`: embeds allocation model output.
- Audit log stores allocation model status and model hash.
- Review scoring includes allocation model status, constraints, risk change, turnover, and evidence count.
- Frontend panel shows current vs target weights, trades, risk deltas, constraints, evidence, and review schedule.
- Market context now uses valuation, domestic ETF rotation, and global ETF rotation with defensive source-status handling.

The main limitation is that v1 still maps scores to fixed target deltas. It does not yet estimate expected returns, solve a true constrained optimization problem, or validate decisions through historical walk-forward tests.

## Design Decision

Build v2 as an additive model layer named `PredictiveConstrainedAllocationModel`.

V2 will sit above v1:

```text
Real Portfolio
-> Data Quality
-> Market Context
-> Predictive Signals
-> Expected Return / Risk Inputs
-> Constrained Optimizer
-> Backtest Gate
-> Allocation Recommendation
-> Audit / Review
```

V1 remains the fallback path. If v2 has insufficient data, unstable optimization, or failed backtest gates, the system returns the existing v1 recommendation with a clear `v2_status = "fallback_to_v1"`.

## Considered Approaches

### Approach A: Improve Rule Weights Only

This would tune the current component weights and thresholds. It is easy to ship but does not answer whether the model is better historically. It also keeps the target weights tied to coarse score buckets.

### Approach B: Add Predictive Signals Without Optimization

This improves signal quality but still uses fixed deltas. It is useful as an intermediate step, but it does not fully use risk budgets, correlations, or turnover constraints.

### Approach C: Predictive Signals + Constrained Optimizer + Walk-forward Backtest

Recommended. This is closest to institutional portfolio construction: separate alpha views from risk and constraints, solve for weights, then prove the process through repeatable historical tests.

## V2 Responsibilities

V2 must answer:

1. Which ETFs have the best forward-looking relative opportunity?
2. How confident is each signal?
3. What target weights maximize risk-adjusted opportunity under policy constraints?
4. Does the proposed target improve expected return without breaching risk limits?
5. Would the method have worked in walk-forward historical tests?
6. When should v2 defer to v1?

## Non-goals

- No automatic trade execution.
- No black-box AI-generated weights.
- No intraday or high-frequency model.
- No leverage, derivatives, shorting, or margin.
- No dependence on paid external data for the first v2 implementation.
- No replacement of v1 fallback behavior.

## Inputs

### Portfolio Inputs

- Current weights.
- Market values.
- Asset class, region, strategy, currency, and factor exposure.
- Benchmark and active risk.

### Market Inputs

Use existing local sources first:

- ETF rotation returns: 5-day, 20-day, 60-day.
- Valuation percentiles.
- Macro decision score.
- China macro data.
- Market breadth.
- Cross-asset correlation.
- Scenario stress loss.
- Data quality score and source status.

### Historical Inputs

Use local provider/cache functions where available:

- ETF close prices for the nine ETF proxies.
- Rebalance dates.
- Benchmark weights.
- Existing scenario shocks.
- Transaction cost assumptions.

If a series is unavailable, v2 must mark the symbol as `insufficient_history` and exclude it from optimizer alpha until data quality recovers.

## Output Contract

V2 returns a model packet:

```json
{
  "model_version": "allocation-v2",
  "v1_model_version": "allocation-v1",
  "model_hash": "sha256...",
  "status": "allow|limited|observe|fallback_to_v1",
  "alpha_signals": [],
  "optimizer": {
    "method": "constrained_mean_variance",
    "objective_value": 0.0,
    "solver_status": "optimal|repaired|fallback",
    "constraint_bindings": []
  },
  "current_weights": {},
  "target_weights": {},
  "proposed_trades": [],
  "expected_effect": {},
  "backtest_gate": {
    "status": "pass|warn|fail|not_enough_data",
    "lookback_months": 0,
    "summary": {}
  },
  "governance": {
    "policy_hash": "sha256...",
    "signal_version": "signal_v1",
    "optimizer_version": "optimizer_v1",
    "fallback_reason": null
  },
  "evidence_chain": [],
  "review_schedule": ["T+1", "T+5", "T+20"]
}
```

## Signal Layer

Create `core/predictive_signals.py`.

Each ETF receives an `AlphaSignal`:

- `symbol`
- `expected_return_score`
- `momentum_score`
- `valuation_score`
- `macro_fit_score`
- `risk_penalty_score`
- `confidence`
- `expected_return_annualized`
- `reason_codes`
- `source_status`

### Signal Formula

The first implementation should be deterministic:

```text
expected_return_score =
  0.35 * momentum_score
  + 0.25 * valuation_score
  + 0.20 * macro_fit_score
  + 0.10 * breadth_score
  + 0.10 * risk_penalty_score
```

Convert the score to a conservative annualized expected return:

```text
expected_return_annualized =
  base_return_by_asset_class
  + score_tilt
  - risk_penalty
```

The output is a portfolio-construction input, not a forecast guarantee.

## Optimizer Layer

Create `core/allocation_optimizer.py`.

The optimizer should use a deterministic constrained objective:

```text
maximize:
  sum(weight_i * expected_return_i)
  - risk_aversion * portfolio_variance_proxy
  - turnover_penalty * turnover

subject to:
  sum(weights) = 1
  weight_i between min and max position bounds
  region exposure <= policy max
  technology exposure <= policy max
  gold exposure between min and max
  turnover <= policy max
  single trade <= policy max
  scenario loss >= policy limit
```

Implementation should start with a simple grid/repair optimizer using existing Python dependencies. Do not add a heavy solver until the deterministic contract is stable.

## Backtest Layer

Create `core/allocation_backtest.py`.

The first backtest must be local, deterministic, and cheap enough for tests.

### Backtest Design

- Monthly rebalance.
- Rolling lookback for signals.
- Compare v2 target against:
  - current v1 allocation process.
  - equal-weight portfolio.
  - policy benchmark if available.
- Include turnover cost.
- Report annualized return, volatility, max drawdown, Sharpe proxy, hit rate, turnover, and worst month.

### Backtest Gate

V2 can be marked production-ready only if:

- Data coverage is above policy minimum.
- Max drawdown is not materially worse than baseline.
- Turnover is within policy.
- Risk-adjusted return improves or risk is reduced at similar return.

If the gate fails, v2 must return `fallback_to_v1`.

## Governance Layer

Create `core/model_registry.py`.

Responsibilities:

- Register model version.
- Hash model parameters.
- Store signal version and optimizer version.
- Compare v1 and v2 recommendation differences.
- Expose model readiness:
  - `experimental`
  - `paper`
  - `approved`
  - `disabled`

V2 starts as `paper`. The UI can show v2 output, but the primary recommendation remains v1 until the backtest gate passes.

## API Design

Add:

- `GET /api/institutional/allocation_model/v2`
- `GET /api/institutional/allocation_model/v2/signals`
- `GET /api/institutional/allocation_model/v2/backtest`
- `POST /api/institutional/allocation_model/v2/simulate`

Extend:

- `GET /api/institutional/allocation_model`
  - include `next_model_preview` if v2 is available.
- `GET /api/institutional/decision`
  - include `allocation_model_v2` only as a preview until governance status is `approved`.

## Frontend Design

Add a compact v2 preview section inside the existing ETF Allocation Model panel.

Show:

- v2 status.
- v2 vs v1 target-weight difference.
- top alpha signals.
- optimizer constraint bindings.
- backtest gate status.
- governance status.

Do not create a separate marketing-style page. This remains an institutional work surface.

## Error Handling

V2 must degrade conservatively:

- Missing prices: exclude the symbol from alpha and keep current weight.
- Missing valuation: neutral valuation score.
- Missing macro data: neutral macro score.
- Optimizer infeasible: repair to nearest policy-compliant v1 target.
- Backtest unavailable: `backtest_gate.status = "not_enough_data"`.
- Any v2 exception: return `fallback_to_v1` with a non-secret degradation reason.

No v2 failure may break v1 endpoints.

## Testing Strategy

Add tests before implementation:

1. Predictive signals return one signal per eligible ETF.
2. Missing data lowers confidence and marks source status.
3. Optimizer target weights sum to 1.0.
4. Optimizer respects position, region, theme, gold, turnover, and single-trade limits.
5. Infeasible optimizer returns a repaired or fallback result.
6. Backtest returns deterministic metrics for a small fixture price matrix.
7. Backtest gate fails when drawdown or turnover breaches policy.
8. V2 endpoint returns preview output without changing v1 output.
9. Decision endpoint embeds v2 preview only when available.
10. Audit log can store v2 preview hash without replacing v1 audit behavior.
11. Frontend static tests verify safe rendering for v2 preview.

## Rollout Plan

### Phase 1: Predictive Signal Layer

Build deterministic signals and expose `/v2/signals`.

### Phase 2: Optimizer

Build constrained optimizer using policy bounds and existing risk/scenario functions.

### Phase 3: Backtest Gate

Add fixture-based tests first, then wire real local ETF histories when available.

### Phase 4: V2 Preview API

Expose v2 as preview beside v1. Do not make it primary.

### Phase 5: Governance and UI

Add governance status and v1-vs-v2 comparison in the existing allocation panel.

## Acceptance Criteria

V2 design is ready for implementation when:

1. The v2 output contract is stable.
2. V1 remains the production fallback.
3. No v2 failure can break `/api/institutional/decision`.
4. Signal, optimizer, backtest, governance, API, audit, and frontend slices are testable independently.
5. The first implementation can run locally without paid services.
6. Model governance can keep v2 in paper mode until evidence supports promotion.

## Self-Review

- No open markers remain.
- The design is additive and does not replace v1.
- The model remains auditable and deterministic.
- Predictive signals, optimizer, backtest, governance, API, UI, and fallback behavior are explicitly scoped.
- Implementation should be split into multiple tasks and should start with tests.
