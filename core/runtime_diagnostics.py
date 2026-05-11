import os
import sqlite3
import subprocess
from pathlib import Path

from core.audit_log import DEFAULT_AUDIT_DB_PATH


OPTIONAL_KEYS = [
    "FRED_API_KEY",
    "DEEPSEEK_API_KEY",
    "TUSHARE_TOKEN",
    "SERVERCHAN_SENDKEY",
]


def _config_diagnostics(settings) -> dict:
    issues = []
    origins = list(getattr(settings, "ALLOWED_ORIGINS", []) or [])
    allow_credentials = bool(getattr(settings, "ALLOW_CREDENTIALS", False))
    rate_limit = int(getattr(settings, "MAX_REQUESTS_PER_MINUTE", 0) or 0)

    if "*" in origins:
        issues.append("wildcard_origin")
    if allow_credentials and "*" in origins:
        issues.append("credentials_with_wildcard_origin")
    if rate_limit <= 0 or rate_limit > 10000:
        issues.append("invalid_rate_limit")

    return {
        "status": "misconfigured" if issues else "ok",
        "issues": issues,
        "allowed_origins_count": len(origins),
        "allow_credentials": allow_credentials,
        "max_requests_per_minute": rate_limit,
    }


def _optional_keys(settings) -> dict:
    return {
        key: "present" if bool(getattr(settings, key, "")) else "optional_missing"
        for key in OPTIONAL_KEYS
    }


def _portfolio_diagnostics(path: str) -> dict:
    if not path:
        return {"status": "missing", "path_configured": False, "readable": False}
    candidate = Path(path)
    if not candidate.exists():
        return {"status": "missing", "path_configured": True, "readable": False}
    readable = os.access(candidate, os.R_OK)
    return {
        "status": "ok" if readable else "unreadable",
        "path_configured": True,
        "readable": readable,
        "size_bytes": candidate.stat().st_size if readable else None,
    }


def _audit_db_diagnostics(cwd: Path | None) -> dict:
    db_path = cwd / "alphacore_audit.db" if cwd is not None else Path(DEFAULT_AUDIT_DB_PATH)
    if not db_path.exists():
        return {"status": "missing", "readable": False}
    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
        return {"status": "ok", "readable": True, "size_bytes": db_path.stat().st_size}
    except sqlite3.Error as exc:
        return {"status": "unreadable", "readable": False, "error": str(exc)}


def _git_value(args: list[str], cwd: Path) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=str(cwd),
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=2,
    ).strip()


def _git_diagnostics(cwd: Path | None) -> dict:
    try:
        if cwd is None or not cwd.exists():
            raise FileNotFoundError("working directory is unavailable")
        return {
            "status": "ok",
            "commit": _git_value(["rev-parse", "--short", "HEAD"], cwd),
            "branch": _git_value(["branch", "--show-current"], cwd),
        }
    except Exception as exc:
        return {"status": "unknown", "error": str(exc)}


def build_runtime_diagnostics(settings, cwd: str | Path | None = None) -> dict:
    base = Path(cwd) if cwd is not None else Path.cwd()
    config = _config_diagnostics(settings)
    optional_keys = _optional_keys(settings)
    portfolio = _portfolio_diagnostics(getattr(settings, "PORTFOLIO_BOOK_PATH", ""))
    audit_db = _audit_db_diagnostics(base)
    git = _git_diagnostics(base)

    if config["status"] == "misconfigured" or portfolio["status"] in {"missing", "unreadable"}:
        status = "misconfigured"
    elif any(value == "optional_missing" for value in optional_keys.values()):
        status = "degraded"
    else:
        status = "healthy"

    return {
        "status": status,
        "config": config,
        "optional_keys": optional_keys,
        "portfolio": portfolio,
        "audit_db": audit_db,
        "git": git,
    }
