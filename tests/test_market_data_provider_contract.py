from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _python_sources(*roots: str):
    for root in roots:
        yield from (ROOT / root).rglob("*.py")


def test_no_runtime_yfinance_provider_usage():
    forbidden_markers = [
        "import yfinance",
        "from yfinance",
        "yf.download",
        "yf.Ticker",
        "yfinance.download",
        "yfinance.Ticker",
    ]

    offenders = []
    for path in _python_sources("core", "app"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for marker in forbidden_markers:
            if marker in text:
                offenders.append(f"{path.relative_to(ROOT)} contains {marker!r}")

    assert offenders == []


def test_production_code_uses_provider_neutral_market_data_entrypoint():
    offenders = []
    for path in _python_sources("core", "app"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "fetch_yfinance_data" in text:
            offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_fred_api_key_is_only_used_by_config_and_unified_provider():
    allowed = {
        "core/config.py",
        "core/data_providers.py",
        "core/runtime_diagnostics.py",
    }
    offenders = []
    for path in _python_sources("core", "app"):
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "FRED_API_KEY" in text and rel not in allowed:
            offenders.append(rel)

    assert offenders == []


def test_requirements_do_not_pull_yfinance_provider_extension():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-16")

    assert "yfinance" not in requirements.lower()
    assert "akshare" in requirements.lower()
