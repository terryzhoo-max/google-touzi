import time
import requests
import json
import sqlite3
import os

API_SIGN_OFF = "http://127.0.0.1:8888/api/institutional/sign_off_orders"
API_AUDIT = "http://127.0.0.1:8888/api/audit_trail"
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "alphacore.db")

def test_flow():
    print("--- STEP 1: 验证 QMT 实盘网关心跳状态 ---")
    try:
        res = requests.get("http://127.0.0.1:8888/api/gateway/status", timeout=5)
        print("Gateway status response:", json.dumps(res.json(), ensure_ascii=False, indent=2))
    except Exception as e:
        print("Failed to get gateway status:", e)
        return

    print("\n--- STEP 2: 模拟交易员向网关签发一笔机构级 TWAP 拆单 ---")
    payload = {
        "orders": [
            {
                "symbol": "510300.SH",
                "side": "BUY",
                "quantity": 1000,
                "price": 3.511,
                "execution_algo": "TWAP"
            }
        ]
    }
    try:
        res = requests.post(API_SIGN_OFF, json=payload, timeout=5)
        print("Sign-off response:", json.dumps(res.json(), ensure_ascii=False, indent=2))
        res_data = res.json()
        if res_data.get("status") != "success":
            print("Failed to sign off orders!")
            return
        order_id = res_data["signed_orders"][0]["order_id"]
        print(f"Successfully generated signed PENDING order with ID: {order_id}")
    except Exception as e:
        print("Failed to sign off orders:", e)
        return

    print("\n--- STEP 3: 循环监测网关的多线程拆单执行进度与实时滑点漂移 ---")
    print("等待网关抓取订单并在后台执行 (每 2 秒轮询一次，共轮询 15 次)...")
    for i in range(15):
        time.sleep(2)
        try:
            # Query from FastAPI audit trail
            res = requests.get(API_AUDIT, timeout=5)
            trades = res.json().get("trades", [])
            target_trade = None
            for t in trades:
                if t["order_id"] == order_id:
                    target_trade = t
                    break
            
            if target_trade:
                progress = (target_trade['executed_qty'] / target_trade['quantity']) * 100
                print(f"[{i+1}/15] 订单状态: {target_trade['status']} | 进度: {progress:.1f}% ({target_trade['executed_qty']}/{target_trade['quantity']} 股) | 均价: {target_trade['avg_executed_price']:.4f} | 滑点: {target_trade['slippage_bps']:.2f} Bps")
                if target_trade['status'] == 'FILLED':
                    print("\n🎉 成功！订单已完全成交并归档！")
                    break
            else:
                print(f"[{i+1}/15] 暂未在流水中检测到该订单，等待网关同步中...")
        except Exception as e:
            print("Sync failed:", e)

if __name__ == "__main__":
    test_flow()
