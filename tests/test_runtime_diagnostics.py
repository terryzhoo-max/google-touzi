from pathlib import Path
from types import SimpleNamespace

from core.runtime_diagnostics import build_runtime_diagnostics


def _settings(tmp_path, **overrides):
    values = {
        "PORTFOLIO_BOOK_PATH": str(tmp_path / "portfolio.json"),
        "ALLOWED_ORIGINS": ["http://127.0.0.1:8888"],
        "ALLOW_CREDENTIALS": False,
        "MAX_REQUESTS_PER_MINUTE": 240,
        "FRED_API_KEY": "",
        "DEEPSEEK_API_KEY": "secret-deepseek",
        "TUSHARE_TOKEN": "",
        "SERVERCHAN_SENDKEY": "",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_runtime_diagnostics_reports_safe_config_without_leaking_secret_values(tmp_path):
    portfolio = tmp_path / "portfolio.json"
    portfolio.write_text('{"positions":[]}', encoding="utf-8")

    diagnostics = build_runtime_diagnostics(_settings(tmp_path), cwd=tmp_path)

    assert diagnostics["status"] == "degraded"
    assert diagnostics["config"]["status"] == "ok"
    assert diagnostics["portfolio"]["status"] == "ok"
    assert diagnostics["optional_keys"]["DEEPSEEK_API_KEY"] == "present"
    assert diagnostics["optional_keys"]["FRED_API_KEY"] == "optional_missing"
    assert "secret-deepseek" not in str(diagnostics)


def test_runtime_diagnostics_marks_unsafe_origin_and_credentials_as_misconfigured(tmp_path):
    diagnostics = build_runtime_diagnostics(
        _settings(
            tmp_path,
            ALLOWED_ORIGINS=["*"],
            ALLOW_CREDENTIALS=True,
            MAX_REQUESTS_PER_MINUTE=0,
        ),
        cwd=tmp_path,
    )

    assert diagnostics["status"] == "misconfigured"
    assert "wildcard_origin" in diagnostics["config"]["issues"]
    assert "credentials_with_wildcard_origin" in diagnostics["config"]["issues"]
    assert "invalid_rate_limit" in diagnostics["config"]["issues"]


def test_runtime_diagnostics_reports_missing_portfolio_and_audit_db(tmp_path):
    diagnostics = build_runtime_diagnostics(_settings(tmp_path), cwd=tmp_path)

    assert diagnostics["portfolio"]["status"] == "missing"
    assert diagnostics["audit_db"]["status"] == "missing"


def test_runtime_diagnostics_git_metadata_is_defensive(tmp_path):
    diagnostics = build_runtime_diagnostics(_settings(tmp_path), cwd=Path("Z:/path/that/does/not/exist"))

    assert diagnostics["git"]["status"] == "unknown"
    assert "error" in diagnostics["git"]
