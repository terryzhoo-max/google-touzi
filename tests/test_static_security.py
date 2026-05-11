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


def test_data_engine_uses_lifespan_instead_of_deprecated_on_event():
    source = (ROOT / "data_engine.py").read_text(encoding="utf-8")

    assert "@app.on_event" not in source
    assert "lifespan=" in source


def test_pytest_collection_is_scoped_to_tests_directory():
    pytest_ini = (ROOT / "pytest.ini").read_text(encoding="utf-8")

    assert "testpaths = tests" in pytest_ini
    assert "python_files = test_*.py" in pytest_ini
