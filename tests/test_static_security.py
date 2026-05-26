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

    assert 'id="view-institutional"' in html
    assert 'id="audit-log-table-body"' in html
    assert 'id="ai-cro-status"' in html
    assert 'id="ai-cro-text"' in html
    assert 'id="ai-cro-status"' in html
    assert 'id="ai-cro-text"' in html
    
    assert "/api/institutional/decision" in js
    assert "/api/institutional/audit/decisions" in js
    assert "initInstitutionalDecision" in js


def test_institutional_workbench_static_contract():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "main.js").read_text(encoding="utf-8")

    required_ids = [
        "workbench-top-factor",
        "workbench-tracking-error",
        "workbench-largest-active",
    ]
    for item_id in required_ids:
        assert f'id="{item_id}"' in html
        assert item_id in js

    assert "factor" in js or "active" in js


def test_allocation_model_panel_static_contract():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "main.js").read_text(encoding="utf-8")

    # This tests the upgraded pre-trade simulation workbench (SIMU)
    required_ids = [
        "simu-proj-mv",
        "simu-post-cash",
        "simu-compliance",
        "simu-cli-input",
        "simu-trades-body",
        "chart-simu-allocation",
    ]
    for item_id in required_ids:
        assert f'id="{item_id}"' in html
        assert item_id in js

    assert 'id="view-portfolio"' in html

    assert "executeSimuCLI" in js
    assert "resetSimuSandbox" in js


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
