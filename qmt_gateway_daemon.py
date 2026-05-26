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
    from core.db_layer import record_trade, is_order_processed, update_trade_execution
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
    
    # Proactively subscribe quotes for fast Tick protection
    if HAS_XTQUANT and not DRY_RUN:
        try:
            subscribe_symbols = ["510050.SH", "510300.SH", "510500.SH", "159915.SZ", "159919.SZ", "511880.SH"]
            for sym in subscribe_symbols:
                xtdata.subscribe_quote(sym, period='1m', callback=None)
            logger.info(f"Proactively subscribed quote feeds: {subscribe_symbols}")
        except Exception as e:
            logger.warning(f"Proactive quote subscription failure: {e}")
            
    return xt_trader

import threading
import random

class TwapExecutionThread(threading.Thread):
    """Institutional TWAP Iceberg Order Placement Engine with Market Impact Protection."""
    def __init__(self, xt_trader, order_data: dict, interval_sec: int = 5, duration_minutes: int = 1):
        super().__init__()
        self.xt_trader = xt_trader
        self.order_data = order_data
        self.symbol = order_data.get("symbol", "")
        self.side = order_data.get("side", "BUY")
        self.total_qty = int(order_data.get("quantity", 0))
        self.limit_price = float(order_data.get("limit_price", 0.0))
        self.order_id = order_data.get("order_id")
        
        # Unique date-prefixed ID
        today_str = datetime.date.today().strftime("%Y%m%d")
        self.unique_id = f"{today_str}_{self.order_id}"
        
        self.interval = interval_sec
        # Split into lots
        self.total_intervals = max(1, int((duration_minutes * 60) / interval_sec))
        self.qty_per_interval = max(100, (self.total_qty // self.total_intervals) // 100 * 100)
        
        if self.qty_per_interval <= 0:
            self.qty_per_interval = self.total_qty
            self.total_intervals = 1
            
        self.executed_qty = 0
        self.price_sum = 0.0
        self.trade_count = 0
        self.running = True

    def run(self):
        logger.info(f"[ALGO_EXEC] Starting TWAP for {self.side} {self.total_qty} {self.symbol}. Lots: {self.total_intervals}, Qty/lot: {self.qty_per_interval}")
        
        # 1. Initialize record as EXECUTING
        record_trade(self.unique_id, self.symbol, self.side, self.total_qty, self.limit_price, "EXECUTING",
                     execution_algo="TWAP", benchmark_price=self.limit_price, executed_qty=0, avg_executed_price=0.0)
                     
        interval_count = 0
        while self.running and self.executed_qty < self.total_qty and interval_count < self.total_intervals:
            remaining = self.total_qty - self.executed_qty
            lot_qty = self.qty_per_interval if remaining > self.qty_per_interval else remaining
            
            # Downward lot rounding to 100 A-share units
            if lot_qty > 100 and remaining > 100:
                lot_qty = (lot_qty // 100) * 100
                
            if lot_qty <= 0:
                break
                
            # 2. Market Impact / L1 Tick Protection
            execution_price = self.limit_price
            qmt_symbol = self.symbol
            if len(qmt_symbol) == 6:
                qmt_symbol += ".SH" if qmt_symbol.startswith("6") or qmt_symbol.startswith("5") else ".SZ"
                
            if not DRY_RUN and HAS_XTQUANT:
                try:
                    tick = xtdata.get_full_tick([qmt_symbol])
                    if qmt_symbol in tick:
                        ask_price = tick[qmt_symbol].get("askPrice", [self.limit_price])[0]
                        bid_price = tick[qmt_symbol].get("bidPrice", [self.limit_price])[0]
                        
                        # Apply passive micro limit adjust
                        if self.side == "BUY" and ask_price > 0:
                            execution_price = min(self.limit_price, ask_price)
                        elif self.side == "SELL" and bid_price > 0:
                            execution_price = max(self.limit_price, bid_price)
                except Exception as e:
                    logger.warning(f"Failed to pull tick protection data: {e}")
            
            # 3. Placement
            trade_price = 0.0
            if DRY_RUN:
                logger.info(f"[DRY-RUN] [TWAP_LOT] {self.side} {lot_qty} of {qmt_symbol} @ {execution_price:.2f} ({interval_count+1}/{self.total_intervals})")
                # Generate realistic slippage noise (+- 5 Bps)
                slip_pct = random.uniform(-0.0005, 0.0005)
                trade_price = execution_price * (1.0 + slip_pct)
            else:
                try:
                    from xtquant.xttype import StockAccount  # type: ignore
                    acc = StockAccount(QMT_ACCOUNT_ID)
                    xt_side = xtconstant.STOCK_BUY if self.side == "BUY" else xtconstant.STOCK_SELL
                    xt_type = xtconstant.FIX_WEIGHT
                    
                    seq = self.xt_trader.order_stock(
                        account=acc,
                        stock_code=qmt_symbol,
                        order_type=xt_side,
                        order_volume=lot_qty,
                        price_type=xt_type,
                        price=execution_price,
                        strategy_name="AlphaCore_TWAP",
                        order_remark=f"{self.unique_id}_lot_{interval_count}"
                    )
                    logger.info(f"[TWAP_LOT] Placed sequence: {seq}")
                    trade_price = execution_price
                except Exception as e:
                    logger.error(f"TWAP placement failure: {e}")
                    
            if trade_price > 0:
                self.executed_qty += lot_qty
                self.price_sum += trade_price * lot_qty
                self.trade_count += 1
                
                avg_p = self.price_sum / self.executed_qty
                current_status = "FILLED" if self.executed_qty >= self.total_qty else "EXECUTING"
                
                # Update progress and slippage in SQLite
                update_trade_execution(self.unique_id, self.executed_qty, avg_p, current_status)
                
            interval_count += 1
            time.sleep(self.interval)
            
        # 4. Finish
        if self.executed_qty >= self.total_qty:
            logger.info(f"[ALGO_EXEC] Algorithmic Order {self.unique_id} FILLED SUCCESSFULLY.")
            update_trade_execution(self.unique_id, self.executed_qty, self.price_sum/self.executed_qty, "FILLED")
        else:
            avg_p = self.price_sum / self.executed_qty if self.executed_qty > 0 else self.limit_price
            logger.info(f"[ALGO_EXEC] Algorithmic Order {self.unique_id} PARTIALLY FILLED ({self.executed_qty}/{self.total_qty}).")
            update_trade_execution(self.unique_id, self.executed_qty, avg_p, "FILLED")

def place_order(xt_trader, order_data: dict):
    """Execute order via QMT or print dry-run simulation (DIRECT limit order fallback)."""
    symbol = order_data.get("symbol")
    side = order_data.get("side")
    qty = order_data.get("quantity")
    price = order_data.get("limit_price")
    order_id = order_data.get("order_id")
    
    qmt_symbol = symbol 
    if len(qmt_symbol) == 6:
        qmt_symbol += ".SH" if qmt_symbol.startswith("6") or qmt_symbol.startswith("5") else ".SZ"

    if DRY_RUN:
        logger.info(f"[DRY-RUN] > SENDING DIRECT ORDER: {side} {qty} of {qmt_symbol} @ {price:.3f} (ID: {order_id})")
        time.sleep(0.3)
        logger.info(f"[DRY-RUN] < DIRECT ORDER {order_id} SUBMITTED")
        return

    try:
        from xtquant.xttype import StockAccount  # type: ignore
        acc = StockAccount(QMT_ACCOUNT_ID)
        xt_side = xtconstant.STOCK_BUY if side == "BUY" else xtconstant.STOCK_SELL
        xt_type = xtconstant.FIX_WEIGHT
        
        logger.info(f"Executing LIVE Direct Order: {side} {qty} of {qmt_symbol} @ {price}")
        
        seq = xt_trader.order_stock(
            account=acc,
            stock_code=qmt_symbol,
            order_type=xt_side,
            order_volume=qty,
            price_type=xt_type,
            price=price,
            strategy_name="AlphaCore_Direct",
            order_remark=order_id
        )
        logger.info(f"Direct order Seq: {seq}")
    except Exception as e:
        logger.error(f"Failed to execute direct QMT order: {e}")

def poll_hub_decisions(xt_trader) -> bool:
    """Poll Decision Hub for directives and spin up execution threads.
    Returns:
        bool: True if execution succeeded (no connection failures), False otherwise.
    """
    try:
        response = requests.get(HUB_API_URL, timeout=5)
        if response.status_code != 200:
            logger.warning(f"Failed to fetch decision hub data: HTTP {response.status_code}")
            return False
            
        data = response.json()
        
        # 1. Compliance Lock
        global_status = data.get("global_status", "")
        if global_status == "HARD_BLOCK":
            if DRY_RUN:
                logger.warning("SYSTEM LOCKED BY COMPLIANCE (HARD_BLOCK). Bypassing lock for local simulation dry-run test.")
            else:
                logger.warning("SYSTEM LOCKED BY COMPLIANCE (HARD_BLOCK). Skipping order execution.")
                return True
            
        # 2. Extract Directives
        orders = data.get("broker_orders", [])
        if not orders:
            return True
            
        # 3. Process Trades
        new_orders = 0
        for order in orders:
            order_id = order.get("order_id")
            today_str = datetime.date.today().strftime("%Y%m%d")
            unique_id = f"{today_str}_{order_id}"
            
            if is_order_processed(unique_id):
                continue
                
            new_orders += 1
            execution_algo = order.get("execution_algo", "DIRECT")
            
            if execution_algo == "TWAP":
                # Spin up TWAP execution engine thread
                thread = TwapExecutionThread(xt_trader, order)
                thread.start()
            else:
                # Direct Place Order Fallback
                place_order(xt_trader, order)
                record_trade(unique_id, order.get("symbol", ""), order.get("side", ""), int(order.get("quantity", 0)), float(order.get("limit_price", 0.0)), "FILLED",
                             execution_algo="DIRECT", benchmark_price=order.get("limit_price", 0.0), executed_qty=order.get("quantity", 0), avg_executed_price=order.get("limit_price", 0.0))
            
        if new_orders > 0:
            logger.info(f"Processed {new_orders} new execution directives successfully.")
        return True
            
    except requests.exceptions.RequestException as e:
        logger.warning(f"Connection to AlphaCore API failed: {e}")
        return False

def _write_heartbeat_status(retry_count: int = 0, backoff_sec: float = 0.0, gateway_status: str = "HEALTHY"):
    status_file = os.path.join(os.path.dirname(__file__), "qmt_heartbeat.json")
    try:
        payload = {
            "timestamp": time.time(),
            "has_xtquant": HAS_XTQUANT,
            "dry_run": DRY_RUN,
            "account_id": QMT_ACCOUNT_ID,
            "data_dir": QMT_DATA_DIR,
            "status": "ONLINE" if gateway_status == "HEALTHY" else "OFFLINE",
            "gateway_resilience_status": gateway_status,
            "retry_count": retry_count,
            "backoff_sec": round(backoff_sec, 2)
        }
        with open(status_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to write heartbeat status: {e}")

def main():
    logger.info(f"Starting AlphaCore QMT Algorithmic Gateway with Exponential Backoff Resilience.")
    logger.info(f"Target API: {HUB_API_URL}")
    logger.info(f"Default Interval: {POLL_INTERVAL_SEC} seconds")
    
    xt_trader = init_qmt_trader()
    
    retry_count = 0
    backoff_sec = 0.0
    gateway_status = "HEALTHY"
    
    # Initialize heartbeat file
    _write_heartbeat_status(retry_count, backoff_sec, gateway_status)
    
    try:
        while True:
            success = poll_hub_decisions(xt_trader)
            if success:
                if retry_count > 0:
                    logger.info("AlphaCore API connection restored. Resilience stats reset to healthy.")
                retry_count = 0
                backoff_sec = 0.0
                gateway_status = "HEALTHY"
                _write_heartbeat_status(retry_count, backoff_sec, gateway_status)
                time.sleep(POLL_INTERVAL_SEC)
            else:
                retry_count += 1
                gateway_status = "RECONNECTING" if retry_count <= 3 else "DEGRADED"
                # Exponential backoff: min(60, 5 * (2 ** retry_count)) with random jitter
                backoff_sec = min(60.0, 5.0 * (2.0 ** retry_count)) + random.uniform(0.0, 2.0)
                logger.warning(f"API Connection lost. Entering backoff state (retry={retry_count}, sleep={backoff_sec:.2f}s, status={gateway_status})")
                _write_heartbeat_status(retry_count, backoff_sec, gateway_status)
                time.sleep(backoff_sec)
    except KeyboardInterrupt:
        logger.info("Algorithmic Gateway daemon stopped by user.")
        if xt_trader:
            xt_trader.stop()
        status_file = os.path.join(os.path.dirname(__file__), "qmt_heartbeat.json")
        try:
            if os.path.exists(status_file):
                os.remove(status_file)
        except Exception:
            pass


if __name__ == "__main__":
    main()
