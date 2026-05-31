import time
from collections.abc import Callable

from fastapi import APIRouter, FastAPI, Query
from fastapi.responses import JSONResponse

from core.audit_log import get_audit_store
from core.cache_store import ROUTE_TTL, cached, invalidate
from core.review_scheduler import build_review_queue, build_review_summary, list_due_reviews
from core.review_scoring import score_review


def register_audit_routes(app: FastAPI, *, build_payload: Callable[[str | None], dict]) -> None:
    router = APIRouter()

    @router.get("/api/audit_trail")
    def api_audit_trail(limit: int = 50, portfolio: str | None = None):
        try:
            from core.db_layer import get_recent_trades

            trades = get_recent_trades(limit=limit, portfolio_id=portfolio)
            return {"status": "success", "trades": trades}
        except Exception as exc:
            return JSONResponse(status_code=500, content={"error": str(exc)})

    @router.post("/api/institutional/audit/decisions")
    def api_record_institutional_decision(portfolio: str | None = None):
        payload = build_payload(portfolio)
        record = get_audit_store().record_decision(payload, source="api")
        invalidate("institutional_audit_log")
        invalidate("institutional_reviews_due")
        invalidate("institutional_reviews_summary")
        invalidate("institutional_review_scores")
        invalidate("institutional_review_outcomes")
        return {
            "record": {k: v for k, v in record.items() if k != "payload"},
            "payload": payload,
        }

    @router.get("/api/institutional/audit/decisions")
    def api_list_institutional_decisions(limit: int = 20):
        return {"decisions": get_audit_store().list_decisions(limit=limit)}

    @router.get("/api/institutional/audit/verify")
    def api_verify_institutional_audit(limit: int = Query(100, ge=1, le=500)):
        return get_audit_store().verify_recent_decisions(limit=limit)

    @router.get("/api/institutional/audit/decisions/{ticket_id}")
    def api_get_institutional_decision(ticket_id: str):
        record = get_audit_store().get_decision(ticket_id)
        if record is None:
            return JSONResponse(content={"error": "decision ticket not found"}, status_code=404)
        return record

    @router.get("/api/institutional/audit/decisions/{ticket_id}/verify")
    def api_verify_institutional_decision(ticket_id: str):
        verification = get_audit_store().verify_decision(ticket_id)
        if verification is None:
            return JSONResponse(content={"error": "decision ticket not found"}, status_code=404)
        return verification

    @router.get("/api/institutional/reviews/due")
    @cached(ttl=ROUTE_TTL["institutional_reviews_due"], key="institutional_reviews_due")
    def api_institutional_due_reviews():
        store = get_audit_store()
        rows = store.list_decisions(limit=100)
        review_scores = store.list_review_scores(limit=500)
        return {"reviews": list_due_reviews(rows, now=time.time(), review_scores=review_scores)}

    @router.get("/api/institutional/reviews/summary")
    @cached(ttl=ROUTE_TTL["institutional_reviews_summary"], key="institutional_reviews_summary")
    def api_institutional_review_summary():
        store = get_audit_store()
        rows = store.list_decisions(limit=100)
        review_scores = store.list_review_scores(limit=500)
        return {"summary": build_review_summary(rows, review_scores, now=time.time())}

    @router.get("/api/institutional/reviews/queue")
    def api_institutional_review_queue(priority: str | None = None, limit: int = Query(50, ge=1, le=100)):
        store = get_audit_store()
        rows = store.list_decisions(limit=100)
        review_scores = store.list_review_scores(limit=500)
        try:
            queue = build_review_queue(rows, review_scores, now=time.time(), priority=priority, limit=limit)
        except ValueError as exc:
            return JSONResponse(content={"error": str(exc)}, status_code=400)
        return {
            "queue": queue,
            "returned_count": len(queue),
            "filters": {
                "priority": priority,
                "limit": limit,
            },
        }

    @router.get("/api/institutional/reviews/{ticket_id}/score")
    def api_score_institutional_review(ticket_id: str, window: str = "T+1"):
        record = get_audit_store().get_decision(ticket_id)
        if record is None:
            return JSONResponse(content={"error": "decision ticket not found"}, status_code=404)
        return score_review(record, review_window=window)

    @router.post("/api/institutional/reviews/{ticket_id}/score")
    def api_record_institutional_review_score(ticket_id: str, window: str = "T+1"):
        store = get_audit_store()
        record = store.get_decision(ticket_id)
        if record is None:
            return JSONResponse(content={"error": "decision ticket not found"}, status_code=404)
        review_score = score_review(record, review_window=window)
        stored = store.record_review_score(review_score)
        invalidate("institutional_review_outcomes")
        invalidate("institutional_review_scores")
        invalidate("institutional_reviews_due")
        invalidate("institutional_reviews_summary")
        return {"recorded": True, "score": stored}

    @router.get("/api/institutional/reviews/scores")
    def api_list_institutional_review_scores(ticket_id: str | None = None, limit: int = 50):
        return {"scores": get_audit_store().list_review_scores(ticket_id=ticket_id, limit=limit)}

    @router.get("/api/institutional/reviews/scores/due")
    @cached(ttl=ROUTE_TTL["institutional_review_scores"], key="institutional_review_scores")
    def api_score_due_institutional_reviews():
        store = get_audit_store()
        review_scores = store.list_review_scores(limit=500)
        due = list_due_reviews(store.list_decisions(limit=100), now=time.time(), review_scores=review_scores)
        scored = []
        for item in due:
            record = store.get_decision(item["ticket_id"])
            if record is not None:
                scored.append(score_review(record, review_window=item["window"]))
        return {"scores": scored}

    @router.post("/api/institutional/reviews/scores/due")
    def api_record_due_institutional_review_scores():
        store = get_audit_store()
        review_scores = store.list_review_scores(limit=500)
        due = list_due_reviews(store.list_decisions(limit=100), now=time.time(), review_scores=review_scores)
        scored = []
        for item in due:
            record = store.get_decision(item["ticket_id"])
            if record is not None:
                scored.append(store.record_review_score(score_review(record, review_window=item["window"])))
        invalidate("institutional_review_scores")
        invalidate("institutional_review_outcomes")
        invalidate("institutional_reviews_due")
        invalidate("institutional_reviews_summary")
        return {"recorded_count": len(scored), "scores": scored}

    app.include_router(router)
