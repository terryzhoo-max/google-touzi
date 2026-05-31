from fastapi import APIRouter, FastAPI
from pydantic import BaseModel

from core.alert_rules import get_rules, update_rules


class RulesUpdate(BaseModel):
    rules: list[dict]


def register_alert_routes(app: FastAPI) -> None:
    router = APIRouter()

    @router.get("/api/alerts/rules")
    def api_get_rules():
        return {"rules": get_rules()}

    @router.put("/api/alerts/rules")
    def api_update_rules(req: RulesUpdate):
        return {"rules": update_rules(req.rules)}

    app.include_router(router)
