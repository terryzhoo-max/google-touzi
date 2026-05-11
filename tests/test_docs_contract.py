from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_institutional_runbook_covers_operational_controls():
    runbook = (ROOT / "docs" / "institutional_decision_runbook.md").read_text(encoding="utf-8")

    assert "/api/institutional/decision" in runbook
    assert "/api/institutional/policy" in runbook
    assert "policy_hash" in runbook
    assert "Audit Log" in runbook
    assert "Review Scheduler" in runbook
    assert "PORTFOLIO_BOOK_PATH" in runbook
    assert "python -m pytest -q" in runbook
    assert "python test_system.py" in runbook
