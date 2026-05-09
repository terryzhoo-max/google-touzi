"""
Global alert state — a module-level registry that each engine writes to
when it detects a warning condition.  The decision-signal endpoint
aggregates these into the active_warnings array shown on the dashboard.
"""

from dataclasses import dataclass, field
from typing import Dict, List

@dataclass
class Alert:
    source: str       # "yield_curve", "correlation", "scenario", "backtest" …
    level: str        # "danger" | "warning" | "info"
    text: str

_alerts: Dict[str, Alert] = {}

def set_alert(source: str, level: str, text: str):
    """Write or overwrite an alert for a given source."""
    _alerts[source] = Alert(source=source, level=level, text=text)

def clear_alert(source: str):
    _alerts.pop(source, None)

def get_active_alerts() -> List[dict]:
    """Return all current alerts sorted by severity (danger > warning > info)."""
    order = {"danger": 0, "warning": 1, "info": 2}
    sorted_alerts = sorted(_alerts.values(), key=lambda a: order.get(a.level, 99))
    return [{"source": a.source, "level": a.level, "text": a.text} for a in sorted_alerts]
