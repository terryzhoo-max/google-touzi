SECONDS_PER_DAY = 24 * 60 * 60

REVIEW_WINDOWS = [
    ("T+1", 1),
    ("T+5", 5),
    ("T+20", 20),
]

PRIORITY_RANK = {
    "critical": 0,
    "elevated": 1,
    "due": 2,
    "normal": 3,
}

QUEUE_PRIORITIES = {"critical", "elevated", "due"}


def _completed_windows(review_scores: list[dict] | None = None) -> dict[str, set[str]]:
    completed: dict[str, set[str]] = {}
    for score in review_scores or []:
        completed.setdefault(score["ticket_id"], set()).add(score["review_window"])
    return completed


def _review_status(ticket_id: str, window: str, due_at: float, now: float | None, completed: dict[str, set[str]]) -> str:
    if window in completed.get(ticket_id, set()):
        return "recorded"
    if now is not None and due_at <= now:
        return "due"
    return "pending"


def _review_sla(due_at: float, now: float | None) -> dict:
    if now is None or due_at > now:
        return {"overdue_days": 0, "priority": "normal"}

    overdue_days = int((now - due_at) // SECONDS_PER_DAY)
    if overdue_days >= 3:
        priority = "critical"
    elif overdue_days >= 1:
        priority = "elevated"
    else:
        priority = "due"
    return {"overdue_days": overdue_days, "priority": priority}


def build_review_schedule(
    ticket_id: str,
    created_at: float,
    now: float | None = None,
    review_scores: list[dict] | None = None,
) -> list[dict]:
    completed = _completed_windows(review_scores)
    schedule = []
    for window, days in REVIEW_WINDOWS:
        due_at = created_at + days * SECONDS_PER_DAY
        schedule.append({
            "ticket_id": ticket_id,
            "window": window,
            "due_at": due_at,
            "status": _review_status(ticket_id, window, due_at, now, completed),
            **_review_sla(due_at, now),
        })
    return schedule


def list_due_reviews(audit_rows: list[dict], now: float, review_scores: list[dict] | None = None) -> list[dict]:
    due = []
    for row in audit_rows:
        schedule = build_review_schedule(
            row["ticket_id"],
            float(row["created_at"]),
            now=now,
            review_scores=review_scores,
        )
        for item in schedule:
            if item["status"] == "due":
                due.append({
                    **item,
                    "score": row.get("score"),
                    "decision_status": row.get("decision_status"),
                    "action_status": row.get("action_status"),
                })
    return sorted(due, key=lambda item: item["due_at"])


def build_review_queue(
    audit_rows: list[dict],
    review_scores: list[dict],
    now: float,
    priority: str | None = None,
    limit: int = 50,
) -> list[dict]:
    if priority is not None and priority not in QUEUE_PRIORITIES:
        raise ValueError(f"unsupported review priority: {priority}")

    due = list_due_reviews(audit_rows, now=now, review_scores=review_scores)
    if priority:
        due = [item for item in due if item["priority"] == priority]

    ordered = sorted(
        due,
        key=lambda item: (
            PRIORITY_RANK.get(item["priority"], 99),
            item["due_at"],
            item["ticket_id"],
            item["window"],
        ),
    )
    return [
        {
            **item,
            "queue_rank": index,
        }
        for index, item in enumerate(ordered[:max(0, limit)], start=1)
    ]


def build_review_summary(audit_rows: list[dict], review_scores: list[dict], now: float) -> dict:
    schedules = []
    for row in audit_rows:
        schedules.extend(build_review_schedule(
            row["ticket_id"],
            float(row["created_at"]),
            now=now,
            review_scores=review_scores,
        ))

    due_items = [item for item in schedules if item["status"] == "due"]
    pending_items = [item for item in schedules if item["status"] == "pending"]
    recorded_items = [item for item in schedules if item["status"] == "recorded"]
    return {
        "tickets_count": len(audit_rows),
        "due_count": len(due_items),
        "pending_count": len(pending_items),
        "recorded_count": len(recorded_items),
        "critical_due_count": len([item for item in due_items if item["priority"] == "critical"]),
        "elevated_due_count": len([item for item in due_items if item["priority"] == "elevated"]),
        "oldest_due_at": min((item["due_at"] for item in due_items), default=None),
        "next_due_at": min((item["due_at"] for item in pending_items), default=None),
    }
