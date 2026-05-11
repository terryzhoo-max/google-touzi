from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dompurify_is_loaded_before_app_script():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")

    dompurify_index = html.index("purify.min.js")
    main_index = html.index('src="main.js')

    assert dompurify_index < main_index


def test_ai_markdown_is_sanitized_before_inner_html():
    js = (ROOT / "static" / "main.js").read_text(encoding="utf-8")

    assert "DOMPurify.sanitize" in js
    assert "ADD_ATTR: ['style']" not in js
    assert "tw.innerHTML = parsedHTML" not in js


def test_institutional_panel_static_contract():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "main.js").read_text(encoding="utf-8")

    assert 'id="institutional-decision-panel"' in html
    assert 'id="decision-score"' in html
    assert 'id="decision-action"' in html
    assert 'id="decision-risk-improvement"' in html
    assert 'id="decision-audit-count"' in html
    assert 'id="decision-audit-integrity"' in html
    assert 'id="decision-review-due"' in html
    assert 'id="decision-review-sla"' in html
    assert 'id="decision-review-priority"' in html
    assert 'id="decision-last-verdict"' in html
    assert 'id="decision-asset-exposure"' in html
    assert 'id="decision-region-exposure"' in html
    assert 'id="decision-strategy-exposure"' in html
    assert 'id="decision-currency-exposure"' in html
    assert 'id="decision-concentration"' in html
    assert 'id="decision-primary-driver"' in html
    assert 'id="decision-reason-codes"' in html
    assert 'id="decision-execution-readiness"' in html
    assert 'id="decision-policy-version"' in html
    assert 'id="decision-policy-hash"' in html
    assert "/api/institutional/decision" in js
    assert "/api/institutional/audit/verify?limit=10" in js
    assert "verified_rate" in js
    assert "asset_class_exposure" in js
    assert "region_exposure" in js
    assert "strategy_exposure" in js
    assert "currency_exposure" in js
    assert "concentration_level" in js
    assert "decision_explanation" in js
    assert "primary_driver" in js
    assert "reason_codes" in js
    assert "execution_readiness" in js
    assert "policy_version" in js
    assert "policy_hash" in js
    assert "decision-policy-version" in js
    assert "decision-policy-hash" in js
    assert "/api/institutional/reviews/summary" in js
    assert "/api/institutional/reviews/queue" in js
    assert "/api/institutional/reviews/scores?limit=1" in js
    assert "critical_due_count" in js
    assert "recommended_action" in js
    assert "initInstitutionalDecision" in js


def test_institutional_workbench_static_contract():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "main.js").read_text(encoding="utf-8")

    required_ids = [
        "institutional-workbench",
        "workbench-top-factor",
        "workbench-tracking-error",
        "workbench-largest-active",
        "workbench-compliance-status",
        "workbench-compliance-issues",
        "workbench-attribution",
        "workbench-evidence",
    ]
    for item_id in required_ids:
        assert f'id="{item_id}"' in html
        assert item_id in js

    assert "factor_risk" in js
    assert "active_risk" in js
    assert "compliance" in js
    assert "attribution" in js
    assert "evidence_chain" in js


def test_allocation_model_panel_static_contract():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "main.js").read_text(encoding="utf-8")

    required_ids = [
        "allocation-model-panel",
        "allocation-model-status",
        "allocation-model-version",
        "allocation-model-hash",
        "allocation-model-risk-delta",
        "allocation-model-stress-delta",
        "allocation-model-turnover",
        "allocation-model-constraint",
        "allocation-model-review",
        "allocation-model-weights",
        "allocation-model-trades",
        "allocation-model-evidence",
    ]
    for item_id in required_ids:
        assert f'id="{item_id}"' in html
        assert item_id in js

    assert "/api/institutional/allocation_model" in js
    assert "renderAllocationModel(data.allocation_model || data)" in js
    assert "renderAllocationWeightRows" in js
    assert "renderAllocationTradeRows" in js
    assert "renderAllocationEvidenceRows" in js
    assert "renderAllocationReviewSchedule" in js
    assert "current_weight" in js
    assert "target_weight" in js
    assert "allocationModelWeights.innerHTML" not in js
    assert "allocationModelTrades.innerHTML" not in js
    assert "allocationModelEvidence.innerHTML" not in js


def test_data_engine_uses_lifespan_instead_of_deprecated_on_event():
    source = (ROOT / "data_engine.py").read_text(encoding="utf-8")

    assert "@app.on_event" not in source
    assert "lifespan=" in source


def test_pytest_collection_is_scoped_to_tests_directory():
    pytest_ini = (ROOT / "pytest.ini").read_text(encoding="utf-8")

    assert "testpaths = tests" in pytest_ini
    assert "python_files = test_*.py" in pytest_ini


def test_start_script_supports_production_hardening_contract():
    script = (ROOT / "start_alphacore.bat").read_text(encoding="utf-8")

    assert "if not defined PROJECT_DIR" in script
    assert "if not defined HOST" in script
    assert "if not defined PORT" in script
    assert "if not defined APP_MODULE" in script
    assert "--no-browser" in script
    assert "import numpy" in script
    assert "import requests" in script
    assert "Occupied by PID" in script
    assert "start http://%HOST%:%PORT%" in script


def test_frontend_uses_safe_rendering_for_targeted_api_payloads():
    js = (ROOT / "static" / "main.js").read_text(encoding="utf-8")

    assert "renderAlertList(list, d.active_warnings)" in js
    assert "fi.textContent =" in js
    assert "ins.textContent = corrData.insight" in js
    assert "renderScenarioGrid(grid, data.scenarios)" in js
    assert "list.innerHTML = d.active_warnings.map" not in js
    assert "fi.innerHTML =" not in js
    assert "ins.innerHTML = corrData.insight" not in js
    assert "grid.innerHTML = data.scenarios.map" not in js
