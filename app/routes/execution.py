import json
import os
import time
import datetime
import uuid

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import JSONResponse

from app.schemas import ExecuteTradeRequest, ForceReleaseRequest, SignOffOrdersRequest


def register_execution_routes(app: FastAPI, *, settings, base_dir: str) -> None:
    router = APIRouter()

    @router.get("/api/institutional/execution/status")
    def api_execution_status():
        status_file = os.path.join(base_dir, "qmt_heartbeat.json")
        if not os.path.exists(status_file):
            return {
                "status": "OFFLINE",
                "gateway_resilience_status": "NOT_RUNNING",
                "has_xtquant": False,
                "dry_run": True,
                "retry_count": 0,
                "backoff_sec": 0,
                "timestamp": 0,
            }
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            return {
                "status": "ERROR",
                "gateway_resilience_status": "ERROR",
                "error": str(exc),
            }

    @router.get("/api/gateway/status")
    def api_gateway_status():
        try:
            status_file = os.path.join(base_dir, "qmt_heartbeat.json")
            if not os.path.exists(status_file):
                return {"status": "OFFLINE", "reason": "Heartbeat file not found"}

            with open(status_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            heartbeat_time = data.get("timestamp", 0)
            if time.time() - heartbeat_time > 25.0:
                return {"status": "OFFLINE", "reason": "Heartbeat timeout"}

            return {
                "status": "ONLINE",
                "has_xtquant": data.get("has_xtquant", False),
                "dry_run": data.get("dry_run", True),
                "account_id": data.get("account_id", ""),
                "data_dir": data.get("data_dir", ""),
                "timestamp": heartbeat_time,
            }
        except Exception as exc:
            return JSONResponse(status_code=500, content={"error": str(exc)})

    @router.post("/api/institutional/sign_off_orders")
    def api_sign_off_orders(req: SignOffOrdersRequest):
        try:
            from core.db_layer import record_trade

            today_str = datetime.date.today().strftime("%Y%m%d")
            signed_orders = []

            for ord_req in req.orders:
                order_uuid = str(uuid.uuid4())[:8].upper()
                unique_id = f"{today_str}_{order_uuid}"
                record_trade(
                    order_id=unique_id,
                    symbol=ord_req.symbol,
                    side=ord_req.side.upper(),
                    quantity=int(ord_req.quantity),
                    price=float(ord_req.price),
                    status="PENDING",
                    execution_algo=ord_req.execution_algo,
                    benchmark_price=float(ord_req.price),
                )
                signed_orders.append({
                    "order_id": unique_id,
                    "symbol": ord_req.symbol,
                    "execution_algo": ord_req.execution_algo,
                })

            return {"status": "success", "signed_orders": signed_orders}
        except Exception as exc:
            return JSONResponse(status_code=500, content={"error": str(exc)})

    @router.post("/api/execute")
    def api_execute_trade(req: ExecuteTradeRequest, portfolio: str | None = None):
        try:
            from core.db_layer import record_trade

            order_id = str(uuid.uuid4())[:8].upper()
            price = 100.0
            portfolio_id = portfolio or "institutional_portfolio"
            record_trade(
                order_id,
                req.ticker,
                req.action.upper(),
                int(req.qty),
                price,
                "EXECUTED",
                portfolio_id=portfolio_id,
            )
            return {
                "status": "success",
                "order_id": order_id,
                "message": f"{req.action} {req.qty} {req.ticker} executed",
            }
        except Exception as exc:
            return JSONResponse(status_code=500, content={"error": str(exc)})

    @router.post("/api/institutional/execution/force_release")
    def api_force_release(req: ForceReleaseRequest):
        from core.db_layer import record_trade

        if req.auth_key != settings.CCO_AUTH_KEY:
            raise HTTPException(status_code=403, detail="Invalid CCO authorization key")

        try:
            order_id = f"cco_force_{int(time.time())}"
            record_trade(
                order_id=order_id,
                symbol=req.symbol,
                side=req.side.upper(),
                quantity=int(req.quantity),
                price=float(req.limit_price),
                status="PENDING",
                execution_algo=req.execution_algo,
                benchmark_price=float(req.limit_price),
                portfolio_id=req.portfolio_id,
            )
            return {
                "status": "success",
                "order_id": order_id,
                "message": f"CCO manual release approved. Order {order_id} queued as PENDING.",
            }
        except Exception as exc:
            return JSONResponse(status_code=500, content={"error": str(exc)})

    app.include_router(router)
