from core.data_quality import classify_score, score_payload


def test_score_payload_penalizes_stale_fallback_and_missing_values():
    score = score_payload(
        source="fred",
        updated_secs_ago=7200,
        stale_after_sec=3600,
        fallback_used=True,
        missing_ratio=0.2,
        anomaly_count=1,
    )

    assert score["source"] == "fred"
    assert score["score"] == 45
    assert score["status"] == "weak"
    assert "stale" in score["flags"]
    assert "fallback" in score["flags"]
    assert "missing_values" in score["flags"]
    assert "anomaly" in score["flags"]


def test_classify_score_boundaries():
    assert classify_score(85) == "strong"
    assert classify_score(70) == "usable"
    assert classify_score(55) == "weak"
    assert classify_score(30) == "blocked"
