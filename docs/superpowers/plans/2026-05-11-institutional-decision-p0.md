# Institutional Decision P0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the P0 institutional decision foundation: portfolio book, data quality scoring, portfolio risk engine, scenario stress interface, and decision ticket output.

**Architecture:** Add focused backend modules under `core/` and expose read-only API endpoints from `data_engine.py`. Keep the first release deterministic and local-first: use a sample portfolio provider and pure calculation functions so tests do not require network data. Frontend integration is a minimal dashboard section after backend contracts are stable.

**Tech Stack:** Python 3.10+, FastAPI, pandas, numpy, pytest, existing AlphaCore cache/data-provider conventions.

---

## File Structure

- Create `core/portfolio_book.py`: portfolio position models, sample portfolio, weight/exposure calculations.
- Create `core/data_quality.py`: source-level and payload-level quality scoring.
- Create `core/risk_engine.py`: portfolio risk metrics and risk contribution calculations.
- Create `core/scenario_engine.py`: current-holding stress test calculations using scenario shocks.
- Create `core/decision_ticket.py`: decision scorecard and structured decision ticket.
- Modify `data_engine.py`: add institutional API routes under `/api/institutional/*`.
- Modify `core/cache_store.py`: add route TTL keys for new institutional endpoints.
- Modify `static/index.html`: add a compact institutional decision panel.
- Modify `static/main.js`: fetch and render the new institutional endpoints.
- Modify `static/styles.css`: style the institutional decision panel.
- Create tests:
  - `tests/test_portfolio_book.py`
  - `tests/test_data_quality.py`
  - `tests/test_risk_engine.py`
  - `tests/test_scenario_engine.py`
  - `tests/test_decision_ticket.py`
  - `tests/test_institutional_api_contract.py`

## Task 1: Portfolio Book

**Files:**
- Create: `core/portfolio_book.py`
- Test: `tests/test_portfolio_book.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_portfolio_book.py
from core.portfolio_book import Position, build_portfolio_snapshot, get_sample_portfolio


def test_sample_portfolio_weights_sum_to_one():
    snapshot = build_portfolio_snapshot(get_sample_portfolio())

    assert snapshot["total_market_value"] == 1000000.0
    assert round(sum(item["weight"] for item in snapshot["positions"]), 6) == 1.0
    assert snapshot["asset_class_exposure"]["equity"] == 0.45
    assert snapshot["asset_class_exposure"]["bond"] == 0.25
    assert snapshot["asset_class_exposure"]["gold"] == 0.15
    assert snapshot["asset_class_exposure"]["cash"] == 0.15


def test_position_rejects_negative_market_value():
    try:
        Position("SPY", "SPDR S&P 500 ETF", "equity", "USD", -1.0)
    except ValueError as exc:
        assert "market_value must be non-negative" in str(exc)
    else:
        raise AssertionError("negative market value was accepted")
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
pytest tests/test_portfolio_book.py -q
```

Expected: FAIL because `core.portfolio_book` does not exist.

- [ ] **Step 3: Implement the minimal module**

```python
# core/portfolio_book.py
from dataclasses import dataclass
from collections import defaultdict


@dataclass(frozen=True)
class Position:
    symbol: str
    name: str
    asset_class: str
    currency: str
    market_value: float
    quantity: float = 0.0
    cost_basis: float = 0.0

    def __post_init__(self):
        if self.market_value < 0:
            raise ValueError("market_value must be non-negative")


def get_sample_portfolio() -> list[Position]:
    return [
        Position("SPY", "SPDR S&P 500 ETF", "equity", "USD", 450000.0),
        Position("TLT", "20+ Year Treasury ETF", "bond", "USD", 250000.0),
        Position("GLD", "Gold ETF", "gold", "USD", 150000.0),
        Position("CASH", "Cash", "cash", "USD", 150000.0),
    ]


def build_portfolio_snapshot(positions: list[Position]) -> dict:
    total = round(sum(p.market_value for p in positions), 2)
    if total <= 0:
        raise ValueError("portfolio market value must be positive")

    exposure = defaultdict(float)
    rows = []
    for p in positions:
        weight = round(p.market_value / total, 6)
        exposure[p.asset_class] += weight
        rows.append({
            "symbol": p.symbol,
            "name": p.name,
            "asset_class": p.asset_class,
            "currency": p.currency,
            "market_value": round(p.market_value, 2),
            "weight": weight,
            "quantity": p.quantity,
            "cost_basis": p.cost_basis,
        })

    return {
        "total_market_value": total,
        "positions": rows,
        "asset_class_exposure": {k: round(v, 6) for k, v in exposure.items()},
        "position_count": len(rows),
    }
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```powershell
pytest tests/test_portfolio_book.py -q
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```powershell
git add core/portfolio_book.py tests/test_portfolio_book.py
git commit -m "feat: add institutional portfolio book"
```

## Task 2: Data Quality Scoring

**Files:**
- Create: `core/data_quality.py`
- Test: `tests/test_data_quality.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_data_quality.py
from core.data_quality import score_payload, classify_score


def test_score_payload_penalizes_stale_fallback_and_missing_values():
    score = score_payload(
        source="fred",
        updated_secs_ago=7200,
        stale_after_sec=3600,
        fallback_used=True,
        missing_ratio=0.2,
        anomaly_count=1,
    )

    assert score["source"] == "fred"
    assert score["score"] == 45
    assert score["status"] == "weak"
    assert "stale" in score["flags"]
    assert "fallback" in score["flags"]
    assert "missing_values" in score["flags"]
    assert "anomaly" in score["flags"]


def test_classify_score_boundaries():
    assert classify_score(85) == "strong"
    assert classify_score(70) == "usable"
    assert classify_score(55) == "weak"
    assert classify_score(30) == "blocked"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
pytest tests/test_data_quality.py -q
```

Expected: FAIL because `core.data_quality` does not exist.

- [ ] **Step 3: Implement scoring**

```python
# core/data_quality.py
def classify_score(score: int) -> str:
    if score >= 80:
        return "strong"
    if score >= 60:
        return "usable"
    if score >= 40:
        return "weak"
    return "blocked"


def score_payload(
    source: str,
    updated_secs_ago: float | None,
    stale_after_sec: int,
    fallback_used: bool,
    missing_ratio: float,
    anomaly_count: int,
) -> dict:
    score = 100
    flags: list[str] = []

    if updated_secs_ago is None or updated_secs_ago > stale_after_sec:
        score -= 20
        flags.append("stale")
    if fallback_used:
        score -= 15
        flags.append("fallback")
    if missing_ratio > 0:
        score -= min(25, int(round(missing_ratio * 50)))
        flags.append("missing_values")
    if anomaly_count > 0:
        score -= min(20, anomaly_count * 10)
        flags.append("anomaly")

    score = max(0, score)
    return {
        "source": source,
        "score": score,
        "status": classify_score(score),
        "flags": flags,
        "updated_secs_ago": updated_secs_ago,
        "stale_after_sec": stale_after_sec,
    }
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```powershell
pytest tests/test_data_quality.py -q
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```powershell
git add core/data_quality.py tests/test_data_quality.py
git commit -m "feat: add data quality scoring"
```

## Task 3: Risk Engine

**Files:**
- Create: `core/risk_engine.py`
- Test: `tests/test_risk_engine.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_risk_engine.py
from core.portfolio_book import build_portfolio_snapshot, get_sample_portfolio
from core.risk_engine import calculate_portfolio_risk


def test_calculate_portfolio_risk_from_asset_class_shocks():
    snapshot = build_portfolio_snapshot(get_sample_portfolio())
    risk = calculate_portfolio_risk(snapshot)

    assert risk["risk_level"] == "medium"
    assert risk["var_95_pct"] == -4.75
    assert risk["cvar_95_pct"] == -6.41
    assert risk["max_single_position_weight"] == 0.45
    assert risk["risk_contribution"]["equity"] > risk["risk_contribution"]["cash"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
pytest tests/test_risk_engine.py -q
```

Expected: FAIL because `core.risk_engine` does not exist.

- [ ] **Step 3: Implement deterministic risk calculations**

```python
# core/risk_engine.py
ASSET_CLASS_DAILY_VOL = {
    "equity": 0.015,
    "bond": 0.007,
    "gold": 0.012,
    "cash": 0.0001,
}


def calculate_portfolio_risk(snapshot: dict) -> dict:
    positions = snapshot["positions"]
    risk_contribution = {}
    variance = 0.0
    max_weight = 0.0

    for p in positions:
        weight = float(p["weight"])
        asset_class = p["asset_class"]
        vol = ASSET_CLASS_DAILY_VOL.get(asset_class, 0.01)
        contribution = (weight * vol) ** 2
        variance += contribution
        risk_contribution[asset_class] = risk_contribution.get(asset_class, 0.0) + contribution
        max_weight = max(max_weight, weight)

    daily_vol = variance ** 0.5
    var_95 = round(-1.65 * daily_vol * 100, 2)
    cvar_95 = round(var_95 * 1.35, 2)
    risk_total = sum(risk_contribution.values()) or 1.0
    normalized = {
        k: round(v / risk_total, 4)
        for k, v in risk_contribution.items()
    }

    if var_95 <= -6 or max_weight > 0.5:
        level = "high"
    elif var_95 <= -3:
        level = "medium"
    else:
        level = "low"

    return {
        "daily_vol_pct": round(daily_vol * 100, 2),
        "var_95_pct": var_95,
        "cvar_95_pct": cvar_95,
        "max_single_position_weight": round(max_weight, 4),
        "risk_contribution": normalized,
        "risk_level": level,
    }
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```powershell
pytest tests/test_risk_engine.py -q
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```powershell
git add core/risk_engine.py tests/test_risk_engine.py
git commit -m "feat: add portfolio risk engine"
```

## Task 4: Scenario Engine

**Files:**
- Create: `core/scenario_engine.py`
- Test: `tests/test_scenario_engine.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_scenario_engine.py
from core.portfolio_book import build_portfolio_snapshot, get_sample_portfolio
from core.scenario_engine import run_portfolio_scenarios


def test_run_portfolio_scenarios_applies_asset_class_shocks():
    snapshot = build_portfolio_snapshot(get_sample_portfolio())
    result = run_portfolio_scenarios(snapshot)

    assert result["worst_scenario"]["id"] == "equity_liquidity_shock"
    assert result["worst_scenario"]["portfolio_loss_pct"] == -6.75
    assert len(result["scenarios"]) == 3
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
pytest tests/test_scenario_engine.py -q
```

Expected: FAIL because `core.scenario_engine` does not exist.

- [ ] **Step 3: Implement scenario calculations**

```python
# core/scenario_engine.py
SCENARIO_SHOCKS = [
    {
        "id": "equity_liquidity_shock",
        "name": "Equity liquidity shock",
        "shocks": {"equity": -0.15, "bond": -0.02, "gold": 0.02, "cash": 0.0},
    },
    {
        "id": "rate_shock",
        "name": "Rate shock",
        "shocks": {"equity": -0.06, "bond": -0.10, "gold": -0.03, "cash": 0.0},
    },
    {
        "id": "risk_on",
        "name": "Risk-on recovery",
        "shocks": {"equity": 0.08, "bond": -0.02, "gold": -0.01, "cash": 0.0},
    },
]


def _scenario_loss(snapshot: dict, shocks: dict[str, float]) -> float:
    loss = 0.0
    for p in snapshot["positions"]:
        loss += float(p["weight"]) * shocks.get(p["asset_class"], 0.0)
    return round(loss * 100, 2)


def run_portfolio_scenarios(snapshot: dict) -> dict:
    rows = []
    for scenario in SCENARIO_SHOCKS:
        rows.append({
            "id": scenario["id"],
            "name": scenario["name"],
            "portfolio_loss_pct": _scenario_loss(snapshot, scenario["shocks"]),
            "shocks": scenario["shocks"],
        })

    worst = min(rows, key=lambda row: row["portfolio_loss_pct"])
    return {
        "scenarios": rows,
        "worst_scenario": worst,
    }
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```powershell
pytest tests/test_scenario_engine.py -q
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```powershell
git add core/scenario_engine.py tests/test_scenario_engine.py
git commit -m "feat: add institutional scenario engine"
```

## Task 5: Decision Ticket

**Files:**
- Create: `core/decision_ticket.py`
- Test: `tests/test_decision_ticket.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_decision_ticket.py
from core.decision_ticket import build_decision_ticket


def test_build_decision_ticket_downgrades_when_data_quality_is_weak():
    ticket = build_decision_ticket(
        data_quality={"score": 55, "status": "weak"},
        risk={"risk_level": "medium", "var_95_pct": -4.75},
        scenarios={"worst_scenario": {"portfolio_loss_pct": -6.75}},
    )

    assert ticket["decision_status"] == "observe"
    assert ticket["score"] == 58
    assert ticket["suggested_action"] == "Hold risk steady until data quality improves."
    assert "data_quality_weak" in ticket["gates_failed"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
pytest tests/test_decision_ticket.py -q
```

Expected: FAIL because `core.decision_ticket` does not exist.

- [ ] **Step 3: Implement ticket builder**

```python
# core/decision_ticket.py
def build_decision_ticket(data_quality: dict, risk: dict, scenarios: dict) -> dict:
    score = 100
    gates_failed: list[str] = []

    if data_quality["score"] < 60:
        score -= 25
        gates_failed.append("data_quality_weak")
    if risk["risk_level"] == "high":
        score -= 25
        gates_failed.append("risk_budget_exceeded")
    if scenarios["worst_scenario"]["portfolio_loss_pct"] < -8:
        score -= 20
        gates_failed.append("scenario_loss_high")

    if score >= 80 and not gates_failed:
        status = "allow"
        action = "Proceed with constrained execution."
    elif score >= 60:
        status = "limited"
        action = "Use staged execution and keep cash buffer."
    else:
        status = "observe"
        action = "Hold risk steady until data quality improves."

    return {
        "decision_status": status,
        "score": score,
        "suggested_action": action,
        "gates_failed": gates_failed,
        "risk_summary": {
            "var_95_pct": risk["var_95_pct"],
            "worst_scenario_loss_pct": scenarios["worst_scenario"]["portfolio_loss_pct"],
        },
        "review_schedule": ["T+1", "T+5", "T+20"],
        "invalidates_when": [
            "data quality score changes materially",
            "VaR breaches the configured risk budget",
            "worst scenario loss breaches the configured loss limit",
        ],
    }
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```powershell
pytest tests/test_decision_ticket.py -q
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```powershell
git add core/decision_ticket.py tests/test_decision_ticket.py
git commit -m "feat: add decision ticket builder"
```

## Task 6: Institutional API Contracts

**Files:**
- Modify: `core/cache_store.py`
- Modify: `data_engine.py`
- Test: `tests/test_institutional_api_contract.py`

- [ ] **Step 1: Write the failing API contract test**

```python
# tests/test_institutional_api_contract.py
from fastapi.testclient import TestClient

from data_engine import app


client = TestClient(app)


def test_institutional_decision_endpoint_returns_ticket():
    response = client.get("/api/institutional/decision")

    assert response.status_code == 200
    payload = response.json()
    assert payload["portfolio"]["total_market_value"] == 1000000.0
    assert "risk" in payload
    assert "scenarios" in payload
    assert payload["decision_ticket"]["review_schedule"] == ["T+1", "T+5", "T+20"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
pytest tests/test_institutional_api_contract.py -q
```

Expected: FAIL with HTTP 404 for `/api/institutional/decision`.

- [ ] **Step 3: Add route TTL keys**

Modify `ROUTE_TTL` in `core/cache_store.py`:

```python
    "institutional_portfolio": 300,
    "institutional_data_quality": 300,
    "institutional_risk": 300,
    "institutional_scenarios": 300,
    "institutional_decision": 300,
```

- [ ] **Step 4: Add institutional route assembly**

Add imports to `data_engine.py`:

```python
from core.portfolio_book import build_portfolio_snapshot, get_sample_portfolio
from core.data_quality import score_payload
from core.risk_engine import calculate_portfolio_risk
from core.scenario_engine import run_portfolio_scenarios
from core.decision_ticket import build_decision_ticket
```

Add helper and route before `app.mount(...)`:

```python
def _build_institutional_payload() -> dict:
    portfolio = build_portfolio_snapshot(get_sample_portfolio())
    data_quality = score_payload(
        source="sample_portfolio",
        updated_secs_ago=0,
        stale_after_sec=3600,
        fallback_used=False,
        missing_ratio=0.0,
        anomaly_count=0,
    )
    risk = calculate_portfolio_risk(portfolio)
    scenarios = run_portfolio_scenarios(portfolio)
    ticket = build_decision_ticket(data_quality, risk, scenarios)
    return {
        "portfolio": portfolio,
        "data_quality": data_quality,
        "risk": risk,
        "scenarios": scenarios,
        "decision_ticket": ticket,
    }


@app.get("/api/institutional/decision")
@cached_async(ttl=ROUTE_TTL["institutional_decision"], key="institutional_decision")
async def api_institutional_decision():
    return _build_institutional_payload()
```

- [ ] **Step 5: Run the API contract test**

Run:

```powershell
pytest tests/test_institutional_api_contract.py -q
```

Expected: 1 passed.

- [ ] **Step 6: Commit**

```powershell
git add core/cache_store.py data_engine.py tests/test_institutional_api_contract.py
git commit -m "feat: expose institutional decision API"
```

## Task 7: Frontend Institutional Panel

**Files:**
- Modify: `static/index.html`
- Modify: `static/main.js`
- Modify: `static/styles.css`
- Test: `tests/test_static_security.py`

- [ ] **Step 1: Add static contract assertions**

Append to `tests/test_static_security.py`:

```python
def test_institutional_panel_static_contract():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "main.js").read_text(encoding="utf-8")

    assert 'id="institutional-decision-panel"' in html
    assert 'id="decision-score"' in html
    assert 'id="decision-action"' in html
    assert "/api/institutional/decision" in js
    assert "initInstitutionalDecision" in js
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
pytest tests/test_static_security.py::test_institutional_panel_static_contract -q
```

Expected: FAIL because the institutional panel is not in the static files.

- [ ] **Step 3: Add panel markup**

Add this block below the dashboard cards in `static/index.html`:

```html
<section id="institutional-decision-panel" class="institutional-panel glass-card">
    <header class="terminal-panel-header">
        <div>
            <div class="panel-kicker">INSTITUTIONAL DECISION</div>
            <h3>科学决策门禁</h3>
            <p>组合风险、场景压力、数据质量与决策票据的机构级汇总。</p>
        </div>
        <span id="decision-status" class="status-indicator">计算中...</span>
    </header>
    <div class="institutional-grid">
        <div><span>决策评分</span><strong id="decision-score">--</strong></div>
        <div><span>建议动作</span><strong id="decision-action">--</strong></div>
        <div><span>VaR 95%</span><strong id="decision-var">--</strong></div>
        <div><span>最坏场景</span><strong id="decision-worst">--</strong></div>
    </div>
    <p id="decision-review" class="flow-insight">等待机构决策引擎输出。</p>
</section>
```

- [ ] **Step 4: Add frontend loader**

Add `initInstitutionalDecision` to the initializer list in `static/main.js`:

```javascript
[initInstitutionalDecision, 520],
```

Add the function near other dashboard loaders:

```javascript
async function initInstitutionalDecision() {
    const panel = document.getElementById('institutional-decision-panel');
    if (!panel) return;

    try {
        const response = await fetch('/api/institutional/decision');
        const data = await response.json();
        const ticket = data.decision_ticket || {};
        const risk = data.risk || {};
        const worst = data.scenarios?.worst_scenario || {};

        setFlowText('decision-score', `${ticket.score ?? '--'} / 100`);
        setFlowText('decision-action', ticket.suggested_action || '--');
        setFlowText('decision-var', `${risk.var_95_pct ?? '--'}%`);
        setFlowText('decision-worst', `${worst.portfolio_loss_pct ?? '--'}%`);
        setFlowText('decision-review', `复盘计划: ${(ticket.review_schedule || []).join(' / ')}`);

        const status = document.getElementById('decision-status');
        if (status) {
            status.innerText = ticket.decision_status || 'unknown';
            status.classList.toggle('is-ok', ticket.decision_status === 'allow');
            status.classList.toggle('is-error', ticket.decision_status === 'observe');
        }
    } catch (error) {
        console.error('Institutional decision failed:', error);
        setFlowText('decision-action', '决策引擎暂不可用');
    }
}
```

- [ ] **Step 5: Add CSS**

Append to `static/styles.css` near the flow panel styles:

```css
.institutional-panel {
    margin: 16px auto 0;
    max-width: 1200px;
    padding: 18px;
}

.institutional-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 1px;
    margin-top: 14px;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 4px;
    background: rgba(255,255,255,0.06);
}

.institutional-grid div {
    min-width: 0;
    padding: 12px;
    background: rgba(15, 23, 42, 0.72);
}

.institutional-grid span {
    display: block;
    margin-bottom: 5px;
    color: #64748b;
    font-size: 0.66rem;
}

.institutional-grid strong {
    display: block;
    color: #e5e7eb;
    font-family: var(--font-mono);
    font-size: 0.84rem;
    overflow: hidden;
    text-overflow: ellipsis;
}
```

- [ ] **Step 6: Run static and JS checks**

Run:

```powershell
pytest tests/test_static_security.py -q
node --check static\main.js
```

Expected: pytest passes and `node --check` exits 0.

- [ ] **Step 7: Commit**

```powershell
git add static/index.html static/main.js static/styles.css tests/test_static_security.py
git commit -m "feat: add institutional decision panel"
```

## Task 8: End-to-End Verification

**Files:**
- No new files.

- [ ] **Step 1: Run focused tests**

Run:

```powershell
pytest tests/test_portfolio_book.py tests/test_data_quality.py tests/test_risk_engine.py tests/test_scenario_engine.py tests/test_decision_ticket.py tests/test_institutional_api_contract.py tests/test_static_security.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run project smoke contract tests**

Run:

```powershell
pytest tests/test_smoke_contract.py -q
```

Expected: all smoke contract tests pass.

- [ ] **Step 3: Run frontend syntax check**

Run:

```powershell
node --check static\main.js
```

Expected: exits 0 with no syntax errors.

- [ ] **Step 4: Start local server**

Run:

```powershell
python -m uvicorn data_engine:app --host 127.0.0.1 --port 8888
```

Expected: server starts and logs Uvicorn running on `http://127.0.0.1:8888`.

- [ ] **Step 5: Run endpoint smoke script in another terminal**

Run:

```powershell
python test_system.py
```

Expected: `/api/health`, `/api/institutional/decision`, and existing macro endpoints return HTTP 200 or report explicit upstream-data errors.

- [ ] **Step 6: Final commit**

```powershell
git status --short
git add .
git commit -m "feat: build institutional decision p0"
```

## Self-Review

Spec coverage:

- Data gate is covered by Task 2 and Task 6.
- Risk gate is covered by Task 3 and Task 6.
- Scenario gate is covered by Task 4 and Task 6.
- Decision ticket is covered by Task 5 and Task 6.
- Initial UI visibility is covered by Task 7.
- End-to-end verification is covered by Task 8.

Type consistency:

- `build_portfolio_snapshot()` returns `positions`, `total_market_value`, and `asset_class_exposure`.
- `calculate_portfolio_risk()` consumes that snapshot and returns `var_95_pct`, `cvar_95_pct`, `risk_contribution`, and `risk_level`.
- `run_portfolio_scenarios()` consumes that snapshot and returns `scenarios` plus `worst_scenario`.
- `build_decision_ticket()` consumes `data_quality`, `risk`, and `scenarios`.
- `/api/institutional/decision` returns all four sections under stable keys.

Execution note:

- The current machine previously did not have `python` or `pytest` in PATH. Before implementing this plan, install Python 3.10+ and project dependencies with `pip install -r requirements.txt`, then run the focused tests from Task 8.
