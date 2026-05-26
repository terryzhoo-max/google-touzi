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


def check_qmt_portfolio_drift(portfolio_positions: list[dict]) -> dict:
    """Compare local portfolio positions with the last QMT export file to detect drifts."""
    drift_report = {"drift_detected": False, "mismatches": []}
    export_file = os.path.join(os.path.dirname(__file__), "..", "20260513资金股份查询.txt")
    if not os.path.exists(export_file):
        return drift_report
        
    try:
        content = ""
        for encoding in ("gbk", "utf-8", "utf-16"):
            try:
                with open(export_file, "r", encoding=encoding) as f:
                    content = f.read()
                break
            except Exception:
                continue
                
        if not content:
            return drift_report
            
        lines = content.splitlines()
        qmt_positions = {}
        for line in lines:
            tokens = [t.strip() for t in line.split() if t.strip()]
            if not tokens or len(tokens) < 3:
                continue
            code = tokens[0]
            if len(code) == 6 and code.isdigit():
                balance = 0
                for tok in tokens[2:]:
                    try:
                        clean_tok = tok.replace(",", "")
                        if clean_tok.isdigit():
                            balance = int(clean_tok)
                            break
                        elif "." in clean_tok:
                            balance = int(float(clean_tok))
                            break
                    except ValueError:
                        continue
                qmt_positions[code] = balance
                
        for pos in portfolio_positions:
            symbol = pos["symbol"].split(".")[0]
            if not symbol.isdigit():
                continue
            local_qty = int(pos.get("quantity", 0))
            qmt_qty = qmt_positions.get(symbol, 0)
            if local_qty != qmt_qty:
                drift_report["drift_detected"] = True
                drift_report["mismatches"].append({
                    "symbol": pos["symbol"],
                    "local_qty": local_qty,
                    "qmt_qty": qmt_qty,
                    "diff": local_qty - qmt_qty
                })
    except Exception as exc:
        print(f"[runtime_diagnostics] Failed to parse QMT query file: {exc}")
        
    return drift_report


def build_runtime_diagnostics(settings, cwd: str | Path | None = None) -> dict:
    base = Path(cwd) if cwd is not None else Path.cwd()
    config = _config_diagnostics(settings)
    optional_keys = _optional_keys(settings)
    portfolio = _portfolio_diagnostics(getattr(settings, "PORTFOLIO_BOOK_PATH", ""))
    audit_db = _audit_db_diagnostics(base)
    git = _git_diagnostics(base)

    # Heartbeat check for QMT Gateway
    qmt_status = "OFFLINE"
    status_file = base / "qmt_heartbeat.json"
    import time
    if status_file.exists():
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                heartbeat = json.load(f)
            if time.time() - heartbeat.get("timestamp", 0) < 30.0:
                qmt_status = "ONLINE"
        except Exception:
            pass

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
        "qmt_gateway": {
            "status": qmt_status,
        }
    }

