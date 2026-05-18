import time
import datetime
import requests
import json
import logging
from typing import Set

# Configure Institutional Logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("QMT_GATEWAY")

# QMT xtquant API stub
try:
    from xtquant import xtdata  # type: ignore
    from xtquant import xtconstant  # type: ignore
    from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback  # type: ignore
    HAS_XTQUANT = True
    DRY_RUN = False
    logger.info("Detected xtquant module. Gateway operating in LIVE EXECUTION mode.")
except ImportError:
    HAS_XTQUANT = False
    DRY_RUN = True
    logger.warning("xtquant module not found. Gateway operating in DRY-RUN (Paper) mode.")

# Configuration
HUB_API_URL = "http://127.0.0.1:8888/api/institutional/decision_hub"
POLL_INTERVAL_SEC = 10
QMT_ACCOUNT_ID = "YOUR_ACCOUNT_ID" # e.g. "88888888"
QMT_DATA_DIR = r"D:\迅投极速交易终端睿智版\userdata_mini" 

# DB Imports
import sys
import os
sys.path.append(os.path.dirname(__file__))
try:
    from core.db_layer import record_trade, is_order_processed
except ImportError:
    logger.error("Failed to import core.db_layer.")
    sys.exit(1)

def init_qmt_trader():
    """Initialize QMT Trader if xtquant is available."""
    global DRY_RUN
    if DRY_RUN:
        return None
        
    session_id = int(time.time())
    xt_trader = XtQuantTrader(QMT_DATA_DIR, session_id)
    # Define a simple callback handler
    class MyXtQuantTraderCallback(XtQuantTraderCallback):
        def on_disconnected(self):
            logger.error("xtquant trader disconnected.")
        def on_order_msg(self, order):
            logger.info(f"Order Msg: {order.order_remark} | Status: {order.order_status}")
        def on_trade_msg(self, trade):
            logger.info(f"Trade Msg: {trade.order_remark} | Volume: {trade.traded_volume}")
            
    xt_trader.register_callback(MyXtQuantTraderCallback())
    xt_trader.start()
    
    # Connect
    res = xt_trader.connect()
    if res != 0:
        logger.error("Failed to connect to QMT terminal. Downgrading to DRY-RUN mode.")
        DRY_RUN = True
        return None
        
    from xtquant.xttype import StockAccount  # type: ignore
    acc = StockAccount(QMT_ACCOUNT_ID)
    res = xt_trader.subscribe_a_account(acc)
    logger.info(f"Connected to QMT. Subscribed account: {QMT_ACCOUNT_ID}")
    return xt_trader

def place_order(xt_trader, order_data: dict):
    """Execute order via QMT or print dry-run simulation."""
    symbol = order_data.get("symbol")
    side = order_data.get("side")
    qty = order_data.get("quantity")
    price = order_data.get("limit_price")
    order_id = order_data.get("order_id")
    
    # QMT requires market suffix (e.g. 510300.SH)
    qmt_symbol = symbol 
    if len(qmt_symbol) == 6:
        # Simple heuristic, backend engine should ideally provide suffix
        if qmt_symbol.startswith("6") or qmt_symbol.startswith("5"):
            qmt_symbol += ".SH"
        else:
            qmt_symbol += ".SZ"

    if DRY_RUN:
        logger.info(f"[DRY-RUN] > SENDING ORDER: {side} {qty} LOTS of {qmt_symbol} @ {price:.3f} (ID: {order_id})")
        time.sleep(0.5) # Simulate network delay
        logger.info(f"[DRY-RUN] < ORDER {order_id} SUBMITTED SUCCESSFULLY")
        return

    # Real Execution
    try:
        from xtquant.xttype import StockAccount  # type: ignore
        acc = StockAccount(QMT_ACCOUNT_ID)
        
        xt_side = xtconstant.STOCK_BUY if side == "BUY" else xtconstant.STOCK_SELL
        xt_type = xtconstant.FIX_WEIGHT # Limit order
        
        # order_volume in QMT is total shares (so if qty is 100 shares, pass 100)
        # Note: AlphaCore outputs 'quantity' as shares. 
        # (Assuming backend output is shares e.g. 100, 200)
        
        logger.info(f"Executing LIVE Order: {side} {qty} of {qmt_symbol} @ {price}")
        
        seq = xt_trader.order_stock(
            account=acc,
            stock_code=qmt_symbol,
            order_type=xt_side,
            order_volume=qty,
            price_type=xt_type,
            price=price,
            strategy_name="AlphaCore",
            order_remark=order_id
        )
        logger.info(f"Order submitted. QMT Seq: {seq}")
        
    except Exception as e:
        logger.error(f"Failed to execute order via xtquant: {e}")

def poll_hub_decisions(xt_trader):
    """Poll the AlphaCore API for decisions and orders."""
    try:
        response = requests.get(HUB_API_URL, timeout=5)
        if response.status_code != 200:
            logger.warning(f"Failed to fetch decision hub data: HTTP {response.status_code}")
            return
            
        data = response.json()
        
        # 1. Check Compliance Hardware Lock
        global_status = data.get("global_status", "")
        if global_status == "HARD_BLOCK":
            logger.warning("SYSTEM LOCKED BY COMPLIANCE (HARD_BLOCK). Skipping order execution.")
            return
            
        # 2. Extract Broker Orders
        orders = data.get("broker_orders", [])
        if not orders:
            # logger.info("No pending orders from Decision Hub.")
            return
            
        # 3. Process Orders idempotently
        new_orders = 0
        for order in orders:
            order_id = order.get("order_id")
            # Today's date prefix prevents cross-day replay bugs
            today_str = datetime.date.today().strftime("%Y%m%d")
            unique_id = f"{today_str}_{order_id}"
            
            if is_order_processed(unique_id):
                continue
                
            new_orders += 1
            # Execute
            place_order(xt_trader, order)
            # Mark as processed in SQLite Audit Trail
            record_trade(unique_id, order.get("symbol", ""), order.get("side", ""), int(order.get("quantity", 0)), float(order.get("limit_price", 0.0)), "SUBMITTED")
            
        if new_orders > 0:
            logger.info(f"Processed {new_orders} new orders successfully.")
            
    except requests.exceptions.RequestException as e:
        logger.warning(f"Connection to AlphaCore API failed: {e}")

def main():
    logger.info(f"Starting AlphaCore QMT Execution Gateway.")
    logger.info(f"Target API: {HUB_API_URL}")
    logger.info(f"Poll Interval: {POLL_INTERVAL_SEC} seconds")
    
    xt_trader = init_qmt_trader()
    
    try:
        while True:
            # Simple terminal heartbeat
            print(".", end="", flush=True)
            poll_hub_decisions(xt_trader)
            time.sleep(POLL_INTERVAL_SEC)
    except KeyboardInterrupt:
        logger.info("Gateway daemon stopped by user.")
        if xt_trader:
            xt_trader.stop()

if __name__ == "__main__":
    main()
