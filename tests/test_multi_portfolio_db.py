import pytest
import sqlite3
import os
import uuid
import time
from core.db_layer import record_trade, get_recent_trades, is_order_processed

def test_multi_portfolio_db_isolation():
    """Verify trade_journal isolation and query bounds under multi-portfolio schema."""
    p1 = "portfolio_a"
    p2 = "portfolio_b"
    
    order1 = f"ord_{uuid.uuid4().hex[:6]}"
    order2 = f"ord_{uuid.uuid4().hex[:6]}"
    
    # 1. Record trades to isolated portfolios
    record_trade(order1, "510300", "BUY", 1000, 4.0, "FILLED", portfolio_id=p1)
    record_trade(order2, "510500", "SELL", 2000, 6.0, "FILLED", portfolio_id=p2)
    
    # 2. Check individual order processing status
    assert is_order_processed(order1, portfolio_id=p1) is True
    assert is_order_processed(order2, portfolio_id=p2) is True
    # Order 1 should not exist in Portfolio B
    assert is_order_processed(order1, portfolio_id=p2) is False
    
    # 3. Retrieve recent trades and check bounds
    trades_p1 = get_recent_trades(limit=10, portfolio_id=p1)
    trades_p2 = get_recent_trades(limit=10, portfolio_id=p2)
    
    # Extract order ids
    ids_p1 = [t["order_id"] for t in trades_p1]
    ids_p2 = [t["order_id"] for t in trades_p2]
    
    assert order1 in ids_p1
    assert order2 not in ids_p1
    
    assert order2 in ids_p2
    assert order1 not in ids_p2
