"""
Custom Alert Rule Engine.
6 predefined rules with configurable thresholds.
Persisted to alert_rules.json in project root.

Evaluated every 5 minutes by background daemon.
On trigger: writes to alert_state → Dashboard banner + ServerChan push.
"""

import json
import os
import time
from core.alert_state import set_alert, clear_alert
from core.db import trigger_emergency_alert

RULES_FILE = os.path.join(os.path.dirname(__file__), "..", "alert_rules.json")

DEFAULT_RULES = [
    {
        "id": "vix_spike",
        "name": "VIX 飙升",
        "enabled": True,
        "source": "vix",
        "field": "current",
        "operator": "gt",
        "threshold": 30.0,
        "severity": "danger",
        "push_wx": True,
        "message": "VIX 飙升至 {value}，超过阈值 {threshold}",
        "last_triggered": 0,
    },
    {
        "id": "tnx_tight",
        "name": "利率紧缩",
        "enabled": True,
        "source": "tnx",
        "field": "current",
        "operator": "gt",
        "threshold": 4.5,
        "severity": "warning",
        "push_wx": False,
        "message": "10Y 美债收益率 {value}% 超过阈值 {threshold}%",
        "last_triggered": 0,
    },
    {
        "id": "curve_invert",
        "name": "利率倒挂",
        "enabled": True,
        "source": "yield_curve",
        "field": "spread",
        "operator": "lt",
        "threshold": -50.0,
        "severity": "danger",
        "push_wx": True,
        "message": "2s10s 利差深度倒挂 {value}bp，阈值 {threshold}bp",
        "last_triggered": 0,
    },
    {
        "id": "dual_kill",
        "name": "股债双杀",
        "enabled": True,
        "source": "correlation",
        "field": "spy_tlt",
        "operator": "gt",
        "threshold": 0.3,
        "severity": "danger",
        "push_wx": True,
        "message": "SPY-TLT 相关性 {value}，股债双杀风险",
        "last_triggered": 0,
    },
    {
        "id": "valuation_extreme",
        "name": "估值极端",
        "enabled": True,
        "source": "valuation",
        "field": "max_pe_pct",
        "operator": "gt",
        "threshold": 90.0,
        "severity": "warning",
        "push_wx": False,
        "message": "PE 分位 {value}% 超过阈值 {threshold}%，估值极端",
        "last_triggered": 0,
    },
    {
        "id": "flow_outflow",
        "name": "北向大幅流出",
        "enabled": True,
        "source": "market_breadth",
        "field": "flow_5d",
        "operator": "lt",
        "threshold": -100.0,
        "severity": "warning",
        "push_wx": False,
        "message": "北向资金 5 日净流出 {value} 亿，超阈值 {threshold} 亿",
        "last_triggered": 0,
    },
]


def _load_rules() -> list[dict]:
    if os.path.exists(RULES_FILE):
        try:
            with open(RULES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return [dict(r) for r in DEFAULT_RULES]


def _save_rules(rules: list[dict]):
    os.makedirs(os.path.dirname(RULES_FILE), exist_ok=True)
    with open(RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)


def get_rules() -> list[dict]:
    return _load_rules()


def update_rules(rules: list[dict]) -> list[dict]:
    _save_rules(rules)
    return rules


def _evaluate_rule(rule: dict, data: dict) -> bool:
    """Return True if rule condition is met."""
    val = data.get(rule["field"], None)
    if val is None:
        return False
    op = rule["operator"]
    th = rule["threshold"]
    if op == "gt":
        return val > th
    if op == "lt":
        return val < th
    if op == "gte":
        return val >= th
    if op == "lte":
        return val <= th
    return False


def evaluate_all_rules():
    """Called by background daemon. Fetches current data and checks rules."""
    from core.market_data import DATA_CACHE
    from core.yield_curve import get_yield_curve
    from core.valuation import get_valuation
    from core.market_breadth import get_market_breadth
    from core.quant_engine import calculate_correlation_matrix

    rules = _load_rules()
    now = time.time()
    triggered = False

    # ── aggregate current data ──
    data = {}

    # VIX
    vix_cache = DATA_CACHE.get("vix", {}).get("data")
    if vix_cache:
        vix_vals = vix_cache.get("data", [])
        data["current"] = float(vix_vals[-1]) if vix_vals else 20.0

    # TNX
    tnx_cache = DATA_CACHE.get("tnx", {}).get("data")
    if tnx_cache:
        tnx_vals = tnx_cache.get("data", [])
        tnx_cur = float(tnx_vals[-1]) if tnx_vals else 4.0
    else:
        tnx_cur = 4.0
    data["current"] = tnx_cur  # override for tnx rules

    # Yield curve
    try:
        yc = get_yield_curve(days=5)
        spread = yc.get("spread_values", [0])
        data["spread"] = float(spread[-1]) if spread else 0
    except Exception:
        data["spread"] = 0

    # Correlation
    try:
        corr = calculate_correlation_matrix()
        if corr.get("matrix"):
            for item in corr["matrix"]:
                if (item[0] == 0 and item[1] == 1) or (item[0] == 1 and item[1] == 0):
                    data["spy_tlt"] = float(item[2])
                    break
    except Exception:
        data["spy_tlt"] = 0

    # Valuation
    try:
        val = get_valuation()
        pe_pcts = [i.get("pe_pct", 0) for i in val.get("indices", [])]
        data["max_pe_pct"] = max(pe_pcts) if pe_pcts else 50
    except Exception:
        data["max_pe_pct"] = 50

    # Market breadth
    try:
        mb = get_market_breadth()
        data["flow_5d"] = float(mb.get("today", {}).get("flow_5d", 0))
    except Exception:
        data["flow_5d"] = 0

    # ── evaluate each rule ──
    changed = False
    for rule in rules:
        if not rule.get("enabled", True):
            continue

        # route data to the right field
        rule_data = {}
        if rule["source"] == "vix":
            vix_vals2 = DATA_CACHE.get("vix", {}).get("data", {}).get("data", [])
            rule_data["current"] = float(vix_vals2[-1]) if vix_vals2 else 20.0
        elif rule["source"] == "tnx":
            tnx_vals2 = DATA_CACHE.get("tnx", {}).get("data", {}).get("data", [])
            rule_data["current"] = float(tnx_vals2[-1]) if tnx_vals2 else 4.0
        elif rule["source"] == "yield_curve":
            rule_data["spread"] = data["spread"]
        elif rule["source"] == "correlation":
            rule_data["spy_tlt"] = data.get("spy_tlt", 0)
        elif rule["source"] == "valuation":
            rule_data["max_pe_pct"] = data.get("max_pe_pct", 50)
        elif rule["source"] == "market_breadth":
            rule_data["flow_5d"] = data.get("flow_5d", 0)

        if _evaluate_rule(rule, rule_data):
            val = rule_data.get(rule["field"], "?")
            msg = rule["message"].format(value=val, threshold=rule["threshold"])
            set_alert(rule["id"], rule["severity"], msg)
            if rule.get("push_wx") and now - rule.get("last_triggered", 0) > 1800:
                trigger_emergency_alert(f'[AlphaCore Alert] {rule["name"]}', msg)
                rule["last_triggered"] = now
                changed = True
            triggered = True
        else:
            clear_alert(rule["id"])

    if changed:
        _save_rules(rules)
    return triggered
