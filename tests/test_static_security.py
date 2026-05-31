from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _frontend_js() -> str:
    files = [
        ROOT / "static" / "main.js",
        ROOT / "static" / "js" / "core" / "api.js",
        ROOT / "static" / "js" / "core" / "dom.js",
        ROOT / "static" / "js" / "core" / "charts.js",
        ROOT / "static" / "js" / "core" / "portfolio.js",
        ROOT / "static" / "js" / "core" / "status.js",
        ROOT / "static" / "js" / "core" / "events.js",
        ROOT / "static" / "js" / "core" / "bootstrap.js",
        ROOT / "static" / "js" / "panels" / "custom_shock.js",
        ROOT / "static" / "js" / "panels" / "portfolio_workbench.js",
        ROOT / "static" / "js" / "panels" / "risk.js",
        ROOT / "static" / "js" / "panels" / "stress.js",
        ROOT / "static" / "js" / "panels" / "strategy.js",
        ROOT / "static" / "js" / "panels" / "decision_hub.js",
        ROOT / "static" / "js" / "panels" / "audit_trail.js",
        ROOT / "static" / "js" / "panels" / "optimizers.js",
        ROOT / "static" / "js" / "panels" / "historical_scenarios.js",
        ROOT / "static" / "js" / "panels" / "execution_monitor.js",
        ROOT / "static" / "js" / "panels" / "brinson_attribution.js",
        ROOT / "static" / "js" / "panels" / "crisis_controls.js",
        ROOT / "static" / "js" / "panels" / "cco_release.js",
    ]
    return "\n".join(path.read_text(encoding="utf-8") for path in files)


def test_dompurify_is_loaded_before_app_script():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")

    dompurify_index = html.index("purify.min.js")
    main_index = html.index('src="main.js')

    assert dompurify_index < main_index


def test_frontend_modules_load_in_dependency_order():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")

    ordered_scripts = [
        "js/core/namespace.js",
        "js/core/state.js",
        "js/core/api.js",
        "js/core/dom.js",
        "js/core/charts.js",
        "js/core/portfolio.js",
        "js/core/status.js",
        "js/core/events.js",
        "main.js",
        "js/panels/custom_shock.js",
        "js/panels/portfolio_workbench.js",
        "js/panels/risk.js",
        "js/panels/stress.js",
        "js/panels/strategy.js",
        "js/panels/decision_hub.js",
        "js/panels/audit_trail.js",
        "js/panels/optimizers.js",
        "js/panels/historical_scenarios.js",
        "js/panels/execution_monitor.js",
        "js/panels/brinson_attribution.js",
        "js/panels/crisis_controls.js",
        "js/panels/cco_release.js",
        "js/core/bootstrap.js",
    ]
    positions = [html.index(script) for script in ordered_scripts]

    assert positions == sorted(positions)


def test_static_html_uses_declarative_actions_not_inline_handlers():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")

    assert " onclick=" not in html
    assert " onchange=" not in html
    assert " onsubmit=" not in html
    assert 'data-action="switch-view"' in html
    assert 'data-action="import-tdx"' in html
    assert 'data-action="execute-simu-cli"' in html
    assert 'data-action="submit-cco-force-release"' in html


def test_generated_panel_templates_use_declarative_actions():
    js = _frontend_js()

    assert "onclick=" not in js
    assert "onchange=" not in js
    assert 'data-action="open-action-modal"' in js
    assert 'data-action="sign-off-single-order"' in js
    assert 'data-action="remove-simu-trade"' in js


def test_freshness_indicator_uses_central_status_writer_without_mojibake():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    main_js = (ROOT / "static" / "main.js").read_text(encoding="utf-8")
    bootstrap_js = (ROOT / "static" / "js" / "core" / "bootstrap.js").read_text(encoding="utf-8")
    status_js = (ROOT / "static" / "js" / "core" / "status.js").read_text(encoding="utf-8")
    freshness_sources = "\n".join([main_js, bootstrap_js, status_js])

    assert html.index("js/core/status.js") < html.index("js/core/events.js")
    assert "function setFreshnessStatus" in status_js
    assert "setFreshnessStatus({" in main_js
    assert "app.status.setFreshnessStatus({" in bootstrap_js
    assert "document.getElementById('freshness-indicator')" not in main_js
    assert "document.getElementById('freshness-indicator')" not in bootstrap_js
    assert "Healthy | cache hit" in main_js
    assert "Degraded:" in main_js
    assert "Circuit open:" in main_js
    assert "Panels loaded" in bootstrap_js

    for marker in ["\u951f", "\u95ff", "\u923f", "\u9983", "\ufffd"]:
        assert marker not in freshness_sources


def test_frontend_sources_do_not_contain_common_mojibake_markers():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    scanned = html + "\n" + _frontend_js()

    mojibake_markers = [
        "\u951f",  # ?
        "\u95ff",  # ?
        "\u923f",  # ?
        "\u9983",  # ?
        "\ufffd",  # replacement character
        "\u6722",  # ?
        "\u51e2",  # ?
        "\u6762",  # ?
        "\u9722",  # ?
        "\ue045",  # private-use residue from misdecoded Chinese names
        "\ue161",  # private-use residue from misdecoded Chinese names
        "\ufe3d",  # presentation-form residue from misdecoded Chinese names
    ]

    for marker in mojibake_markers:
        assert marker not in scanned


def test_dashboard_allocation_card_uses_chinese_visual_copy():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    main_js = (ROOT / "static" / "main.js").read_text(encoding="utf-8")

    alloc_start = html.index('id="dash-alloc"')
    alloc_end = html.index("</div>", html.index('id="alloc-detail"', alloc_start))
    alloc_markup = html[alloc_start:alloc_end]

    assert "目标仓位分布" in alloc_markup
    assert "基于宏观信号的建议配置" in alloc_markup
    assert "TARGET ALLOCATION" not in alloc_markup
    assert "权益资产" in main_js
    assert "固收资产" in main_js
    assert "黄金" in main_js
    assert "现金" in main_js
    assert "EQ " not in main_js


def test_rotation_page_uses_chinese_institutional_titles():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    main_js = (ROOT / "static" / "main.js").read_text(encoding="utf-8")

    rotation_start = html.index('id="view-rotation"')
    rotation_end = html.index('id="view-risk"', rotation_start)
    rotation_html = html[rotation_start:rotation_end]

    expected_titles = [
        "资产轮动监控",
        "A股行业轮动",
        "政策主题动量",
        "境内ETF资金流向",
        "全球ETF轮动",
    ]
    for title in expected_titles:
        assert title in rotation_html

    expected_copy = [
        "申万一级行业强弱与资金偏好",
        "政策主题与高端制造动量跟踪",
        "宽基ETF相对强弱与资金承接观察",
        "美股、日股、港股与中概风险偏好",
        "强势前三",
        "弱势后三",
    ]
    combined = rotation_html + "\n" + main_js
    for text in expected_copy:
        assert text in combined

    forbidden = [
        "ASSET ROTATION HEATMAPS",
        "A-SHARE SECTOR ROTATION",
        "POLICY THEME MOMENTUM",
        "DOMESTIC ETF FLOWS",
        "GLOBAL ETF ROTATION",
        "Top Strength",
        "Bottom Weakness",
    ]
    for text in forbidden:
        assert text not in rotation_html


def test_stress_page_uses_chinese_institutional_risk_governance_copy():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    stress_js = (ROOT / "static" / "js" / "panels" / "stress.js").read_text(encoding="utf-8")
    historical_js = (ROOT / "static" / "js" / "panels" / "historical_scenarios.js").read_text(encoding="utf-8")

    stress_start = html.index('id="view-stress"')
    stress_end = html.index('id="view-institutional"', stress_start)
    stress_html = html[stress_start:stress_end]

    expected_copy = [
        "极限压测与情景治理",
        "历史危机复盘 / 黑天鹅冲击 / 回撤韧性 / 防御动作评估",
        "当前组合最脆弱的压力来源",
        "预计最大组合损失",
        "评级越高代表压力下净值修复能力越强",
        "情景损益分布",
        "按组合损益从最不利到最有利排序",
        "自定义冲击沙盘",
        "机构假设输入",
        "压力动作建议",
        "冲击传导矩阵",
        "组合损益",
        "区域与风格暴露",
    ]
    combined = "\n".join([stress_html, stress_js, historical_js])
    for text in expected_copy:
        assert text in combined

    forbidden = [
        "INSTITUTIONAL STRESS GOVERNANCE",
        "Historical Scenario Stress Testing",
        "Black Swan Events / Drawdown VaR / Shock Propagation",
        "SCENARIO IMPACT DISTRIBUTION",
        "INTERACTIVE BLACK SWAN SANDBOX",
        "SHOCK PROPAGATION MATRIX",
        "Worst Case",
        "Max Drawdown VaR",
        "Resiliency Grade",
        "PREDICTED PORTFOLIO LOSS",
    ]
    for text in forbidden:
        assert text not in stress_html


def test_ai_markdown_is_sanitized_before_inner_html():
    js = _frontend_js()

    assert "DOMPurify.sanitize" in js
    assert "ADD_ATTR: ['style']" not in js
    assert "tw.innerHTML = parsedHTML" not in js


def test_institutional_panel_static_contract():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    js = _frontend_js()

    assert 'id="view-institutional"' in html
    assert 'id="audit-log-table-body"' in html
    assert 'id="ai-cro-status"' in html
    assert 'id="ai-cro-text"' in html
    assert 'id="ai-cro-status"' in html
    assert 'id="ai-cro-text"' in html
    
    assert "/api/institutional/decision" in js
    assert "/api/institutional/audit/decisions" in js
    assert "initInstitutionalDecision" in js


def test_institutional_panel_uses_chinese_title_and_contains_all_static_modules():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")

    institutional_start = html.index('id="view-institutional"')
    portfolio_start = html.index('id="view-portfolio"')

    assert "机构合规审计" in html[institutional_start:portfolio_start]
    assert "组合治理、主动风险、交易审计" in html[institutional_start:portfolio_start]
    assert "Brinson 业绩归因" in html[institutional_start:portfolio_start]


def test_institutional_panel_static_text_has_no_visible_mojibake():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    institutional_start = html.index('id="view-institutional"')
    portfolio_start = html.index('id="view-portfolio"')
    institutional_html = html[institutional_start:portfolio_start]

    mojibake_fragments = [
        "鍚",
        "璺",
        "瀹",
        "鏃",
        "瑁",
        "涓",
        "澶",
        "缁",
        "閰",
        "浜",
    ]

    for fragment in mojibake_fragments:
        assert fragment not in institutional_html


def test_institutional_workbench_static_contract():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    js = _frontend_js()

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
    js = _frontend_js()

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
    js = _frontend_js()

    assert "renderAlertList(list, d.active_warnings)" in js
    assert "setFreshnessStatus({" in js
    assert "ins.textContent = corrData.insight" in js
    assert "renderScenarioGrid(grid, data.scenarios)" in js
    assert "list.innerHTML = d.active_warnings.map" not in js
    assert "fi.textContent =" not in js
    assert "fi.innerHTML =" not in js
    assert "ins.innerHTML = corrData.insight" not in js
    assert "grid.innerHTML = data.scenarios.map" not in js
