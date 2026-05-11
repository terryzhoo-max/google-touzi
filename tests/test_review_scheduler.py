from core.review_scheduler import (
    SECONDS_PER_DAY,
    build_review_queue,
    build_review_schedule,
    build_review_summary,
    list_due_reviews,
)
import pytest


def test_build_review_schedule_creates_standard_windows():
    schedule = build_review_schedule(ticket_id="dt_abc", created_at=1_700_000_000.0)

    assert [item["window"] for item in schedule] == ["T+1", "T+5", "T+20"]
    assert schedule[0]["due_at"] == 1_700_086_400.0
    assert schedule[1]["due_at"] == 1_700_432_000.0
    assert schedule[2]["due_at"] == 1_701_728_000.0
    assert all(item["status"] == "pending" for item in schedule)


def test_list_due_reviews_filters_pending_reviews():
    audit_rows = [
        {"ticket_id": "dt_old", "created_at": 1_700_000_000.0, "score": 80},
        {"ticket_id": "dt_new", "created_at": 1_700_200_000.0, "score": 70},
    ]

    due = list_due_reviews(audit_rows, now=1_700_100_000.0)

    assert len(due) == 1
    assert due[0]["ticket_id"] == "dt_old"
    assert due[0]["window"] == "T+1"


def test_list_due_reviews_excludes_already_recorded_windows():
    audit_rows = [
        {"ticket_id": "dt_old", "created_at": 1_700_000_000.0, "score": 80},
    ]
    review_scores = [
        {"ticket_id": "dt_old", "review_window": "T+1", "score": 90},
    ]

    due = list_due_reviews(audit_rows, now=1_700_500_000.0, review_scores=review_scores)

    assert [item["window"] for item in due] == ["T+5"]
    assert all(item["status"] == "due" for item in due)


def test_list_due_reviews_adds_sla_priority_and_overdue_days():
    created_at = 1_700_000_000.0
    audit_rows = [
        {"ticket_id": "dt_old", "created_at": created_at, "score": 80},
    ]

    due = list_due_reviews(audit_rows, now=created_at + 9 * SECONDS_PER_DAY)

    assert [item["window"] for item in due] == ["T+1", "T+5"]
    assert due[0]["overdue_days"] == 8
    assert due[0]["priority"] == "critical"
    assert due[1]["overdue_days"] == 4
    assert due[1]["priority"] == "critical"


def test_build_review_summary_counts_due_pending_and_recorded_windows():
    audit_rows = [
        {"ticket_id": "dt_old", "created_at": 1_700_000_000.0, "score": 80},
        {"ticket_id": "dt_new", "created_at": 1_700_400_000.0, "score": 70},
    ]
    review_scores = [
        {"ticket_id": "dt_old", "review_window": "T+1", "score": 90},
    ]

    summary = build_review_summary(audit_rows, review_scores, now=1_700_500_000.0)

    assert summary["tickets_count"] == 2
    assert summary["recorded_count"] == 1
    assert summary["due_count"] == 2
    assert summary["pending_count"] == 3
    assert summary["oldest_due_at"] == 1_700_432_000.0


def test_build_review_summary_counts_sla_breaches():
    created_at = 1_700_000_000.0
    audit_rows = [
        {"ticket_id": "dt_old", "created_at": created_at, "score": 80},
    ]

    summary = build_review_summary(audit_rows, review_scores=[], now=created_at + 9 * SECONDS_PER_DAY)

    assert summary["due_count"] == 2
    assert summary["critical_due_count"] == 2
    assert summary["elevated_due_count"] == 0


def test_build_review_queue_sorts_by_operational_priority():
    now = 1_700_000_000.0 + 9 * SECONDS_PER_DAY
    audit_rows = [
        {"ticket_id": "dt_recent", "created_at": 1_700_000_000.0 + 8 * SECONDS_PER_DAY, "score": 82},
        {"ticket_id": "dt_old", "created_at": 1_700_000_000.0, "score": 74},
    ]

    queue = build_review_queue(audit_rows, review_scores=[], now=now)

    assert queue[0]["ticket_id"] == "dt_old"
    assert queue[0]["priority"] == "critical"
    assert queue[0]["queue_rank"] == 1
    assert queue[-1]["priority"] == "due"


def test_build_review_queue_filters_priority_and_limits_results():
    now = 1_700_000_000.0 + 9 * SECONDS_PER_DAY
    audit_rows = [
        {"ticket_id": "dt_recent", "created_at": 1_700_000_000.0 + 8 * SECONDS_PER_DAY, "score": 82},
        {"ticket_id": "dt_old", "created_at": 1_700_000_000.0, "score": 74},
    ]

    queue = build_review_queue(audit_rows, review_scores=[], now=now, priority="critical", limit=1)

    assert len(queue) == 1
    assert queue[0]["priority"] == "critical"
    assert queue[0]["queue_rank"] == 1


def test_build_review_queue_rejects_unknown_priority_filter():
    with pytest.raises(ValueError, match="unsupported review priority"):
        build_review_queue([], review_scores=[], now=1_700_000_000.0, priority="urgent")
