from dataclasses import asdict, dataclass
import hashlib
import json


@dataclass(frozen=True)
class AllocationPolicy:
    version: str = "allocation_policy_v1"
    max_single_weight: float = 0.22
    max_region_weight: float = 0.55
    max_theme_weight: float = 0.45
    min_gold_weight: float = 0.08
    max_gold_weight: float = 0.22
    max_turnover: float = 0.16
    max_single_trade: float = 0.05
    min_trade_size: float = 0.01
    var_limit_pct: float = -2.4
    worst_scenario_limit_pct: float = -12.0
    data_quality_min_score: int = 80
    max_step_weight: float = 0.04


def allocation_policy_hash(policy: AllocationPolicy) -> str:
    payload = asdict(policy)
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def allocation_policy_to_dict(policy: AllocationPolicy) -> dict:
    payload = asdict(policy)
    payload["policy_hash"] = allocation_policy_hash(policy)
    return payload


def get_default_allocation_policy() -> AllocationPolicy:
    return AllocationPolicy()
