from dataclasses import asdict, dataclass
import hashlib
import json

from core.config import settings


def _policy_hash(policy_payload: dict) -> str:
    body = json.dumps(policy_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DecisionPolicy:
    version: str = "institutional_policy_v1"
    data_quality_min_score: int = 60
    data_quality_strong_score: int = 80
    scenario_loss_limit_pct: float = -8.0
    scenario_loss_watch_pct: float = -6.0
    scenario_loss_info_pct: float = -3.0
    # ── calibrated defaults from 18-year backtest, overridable via config ──
    allow_min_score: int = getattr(settings, 'CALIBRATED_ALLOW_MIN', 80)
    limited_min_score: int = getattr(settings, 'CALIBRATED_LIMITED_MIN', 60)
    technology_exposure_watch: float = 0.35
    china_complex_exposure_watch: float = 0.40

    def to_dict(self) -> dict:
        values = asdict(self)
        version = values.pop("version")
        payload = {
            "version": version,
            "thresholds": values,
        }
        payload["policy_hash"] = _policy_hash(payload)
        return payload


DEFAULT_DECISION_POLICY = DecisionPolicy()


def as_policy(policy: DecisionPolicy | dict | None = None) -> DecisionPolicy:
    if policy is None:
        return DEFAULT_DECISION_POLICY
    if isinstance(policy, DecisionPolicy):
        return policy
    thresholds = dict(policy.get("thresholds", {}))
    if "version" in policy:
        thresholds["version"] = policy["version"]
    return DecisionPolicy(**thresholds)


def get_default_decision_policy() -> dict:
    return DEFAULT_DECISION_POLICY.to_dict()
