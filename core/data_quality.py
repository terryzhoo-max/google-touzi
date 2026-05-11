def classify_score(score: int) -> str:
    if score >= 80:
        return "strong"
    if score >= 60:
        return "usable"
    if score >= 40:
        return "weak"
    return "blocked"


def score_payload(
    source: str,
    updated_secs_ago: float | None,
    stale_after_sec: int,
    fallback_used: bool,
    missing_ratio: float,
    anomaly_count: int,
) -> dict:
    score = 100
    flags: list[str] = []

    if updated_secs_ago is None or updated_secs_ago > stale_after_sec:
        score -= 20
        flags.append("stale")
    if fallback_used:
        score -= 15
        flags.append("fallback")
    if missing_ratio > 0:
        score -= min(25, int(round(missing_ratio * 50)))
        flags.append("missing_values")
    if anomaly_count > 0:
        score -= min(20, anomaly_count * 10)
        flags.append("anomaly")

    score = max(0, score)
    return {
        "source": source,
        "score": score,
        "status": classify_score(score),
        "flags": flags,
        "updated_secs_ago": updated_secs_ago,
        "stale_after_sec": stale_after_sec,
    }
