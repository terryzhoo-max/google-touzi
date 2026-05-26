import sqlite3
import pandas as pd
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'alphacore.db')

def init_db():
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    cursor = conn.cursor()
    cursor.execute('PRAGMA journal_mode=WAL;')
    cursor.execute('PRAGMA synchronous=NORMAL;')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS time_series (
            symbol TEXT,
            date TEXT,
            close REAL,
            PRIMARY KEY (symbol, date)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_cache (
            endpoint_key TEXT PRIMARY KEY,
            payload_json TEXT,
            updated_at REAL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trade_journal (
            order_id TEXT PRIMARY KEY,
            symbol TEXT,
            side TEXT,
            quantity INTEGER,
            price REAL,
            status TEXT,
            timestamp REAL
        )
    ''')
    conn.commit()
    conn.close()

import json
import time

def save_api_cache(endpoint_key: str, payload: dict):
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    cursor = conn.cursor()
    payload_str = json.dumps(payload, ensure_ascii=False)
    cursor.execute('''
        INSERT OR REPLACE INTO api_cache (endpoint_key, payload_json, updated_at)
        VALUES (?, ?, ?)
    ''', (endpoint_key, payload_str, time.time()))
    conn.commit()
    conn.close()

def get_api_cache(endpoint_key: str) -> tuple[dict | None, float]:
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    cursor = conn.cursor()
    cursor.execute('SELECT payload_json, updated_at FROM api_cache WHERE endpoint_key = ?', (endpoint_key,))
    row = cursor.fetchone()
    conn.close()
    if row:
        try:
            return json.loads(row[0]), row[1]
        except Exception:
            return None, 0.0
    return None, 0.0

def save_timeseries(symbol, df):
    if df.empty: return
    
    df_reset = df.reset_index()
    if 'Date' in df_reset.columns:
        date_col = 'Date'
    else:
        date_col = df_reset.columns[0]
        
    records = []
    for _, row in df_reset.iterrows():
        dt_str = pd.to_datetime(row[date_col]).strftime('%Y-%m-%d')
        close_val = float(row['Close'])
        records.append((symbol, dt_str, close_val))
        
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    cursor = conn.cursor()
    cursor.executemany('''
        INSERT OR REPLACE INTO time_series (symbol, date, close)
        VALUES (?, ?, ?)
    ''', records)
    conn.commit()
    conn.close()

def get_cached_timeseries(symbol, start_date, end_date):
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    query = "SELECT date, close FROM time_series WHERE symbol = ? AND date >= ? AND date <= ? ORDER BY date ASC"
    df = pd.read_sql_query(query, conn, params=(symbol, start_date, end_date))
    conn.close()
    if df.empty:
        return None
    df['Date'] = pd.to_datetime(df['date'])
    df.set_index('Date', inplace=True)
    df.rename(columns={'close': 'Close'}, inplace=True)
    return df

def _migrate_schema(cursor):
    """Idempotently migrate database schema to add institutional algorithmic columns."""
    for col, col_type in [
        ("execution_algo", "TEXT DEFAULT 'DIRECT'"),
        ("benchmark_price", "REAL DEFAULT 0.0"),
        ("executed_qty", "INTEGER DEFAULT 0"),
        ("avg_executed_price", "REAL DEFAULT 0.0"),
        ("slippage_bps", "REAL DEFAULT 0.0"),
        ("portfolio_id", "TEXT DEFAULT 'institutional_portfolio'")
    ]:
        try:
            cursor.execute(f"ALTER TABLE trade_journal ADD COLUMN {col} {col_type};")
        except sqlite3.OperationalError:
            # Field already exists
            pass

def record_trade(order_id: str, symbol: str, side: str, quantity: int, price: float, status: str,
                 execution_algo: str = 'DIRECT', benchmark_price: float = 0.0,
                 executed_qty: int = 0, avg_executed_price: float = 0.0, slippage_bps: float = 0.0,
                 portfolio_id: str = 'institutional_portfolio'):
    """Persist an executed or dry-run trade into the audit journal, including algorithm logs."""
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    cursor = conn.cursor()
    # Auto-ensure table exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trade_journal (
            order_id TEXT PRIMARY KEY,
            symbol TEXT,
            side TEXT,
            quantity INTEGER,
            price REAL,
            status TEXT,
            timestamp REAL
        )
    ''')
    _migrate_schema(cursor)
    cursor.execute('''
        INSERT OR REPLACE INTO trade_journal (
            order_id, symbol, side, quantity, price, status, timestamp,
            execution_algo, benchmark_price, executed_qty, avg_executed_price, slippage_bps, portfolio_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (order_id, symbol, side, int(quantity), float(price), status, time.time(),
          execution_algo, float(benchmark_price), int(executed_qty), float(avg_executed_price), float(slippage_bps), portfolio_id))
    conn.commit()
    conn.close()

def update_trade_execution(order_id: str, executed_qty: int, avg_executed_price: float, status: str, portfolio_id: str = 'institutional_portfolio') -> bool:
    """Update execution progression of an algorithmic order and compute slippage dynamically in Bps."""
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    cursor = conn.cursor()
    # Ensure schema is valid
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trade_journal (
            order_id TEXT PRIMARY KEY,
            symbol TEXT,
            side TEXT,
            quantity INTEGER,
            price REAL,
            status TEXT,
            timestamp REAL
        )
    ''')
    _migrate_schema(cursor)
    
    cursor.execute('SELECT side, price, benchmark_price FROM trade_journal WHERE order_id = ?', (order_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
        
    side, limit_price, benchmark_price = row
    if not benchmark_price or benchmark_price <= 0:
        benchmark_price = limit_price if limit_price > 0 else avg_executed_price
        
    # Calculate Slippage (Bps)
    # Buy slippage = (AvgPrice - BenchPrice) / BenchPrice * 10000
    # Sell slippage = (BenchPrice - AvgPrice) / BenchPrice * 10000
    slippage_bps = 0.0
    if benchmark_price > 0 and avg_executed_price > 0:
        if side == "BUY":
            slippage_bps = (avg_executed_price - benchmark_price) / benchmark_price * 10000.0
        else:
            slippage_bps = (benchmark_price - avg_executed_price) / benchmark_price * 10000.0
            
    cursor.execute('''
        UPDATE trade_journal
        SET executed_qty = ?, avg_executed_price = ?, slippage_bps = ?, status = ?, timestamp = ?, portfolio_id = ?
        WHERE order_id = ?
    ''', (int(executed_qty), float(avg_executed_price), float(slippage_bps), status, time.time(), portfolio_id, order_id))
    conn.commit()
    conn.close()
    return True

def is_order_processed(order_id: str, portfolio_id: str = None) -> bool:
    """Check if an order_id has already been processed and journaled."""
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    cursor = conn.cursor()
    # Ensure table exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trade_journal (
            order_id TEXT PRIMARY KEY,
            symbol TEXT,
            side TEXT,
            quantity INTEGER,
            price REAL,
            status TEXT,
            timestamp REAL
        )
    ''')
    _migrate_schema(cursor)
    if portfolio_id:
        cursor.execute('SELECT status FROM trade_journal WHERE order_id = ? AND portfolio_id = ?', (order_id, portfolio_id))
    else:
        cursor.execute('SELECT status FROM trade_journal WHERE order_id = ?', (order_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0] in ("EXECUTING", "FILLED", "EXECUTED")
    return False

def get_recent_trades(limit: int = 10, portfolio_id: str = None) -> list[dict]:
    """Fetch the most recent executed/journaled trades, enriched with algo statistics."""
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    cursor = conn.cursor()
    # Ensure table and columns exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trade_journal (
            order_id TEXT PRIMARY KEY,
            symbol TEXT,
            side TEXT,
            quantity INTEGER,
            price REAL,
            status TEXT,
            timestamp REAL
        )
    ''')
    _migrate_schema(cursor)
    
    if portfolio_id:
        cursor.execute('''
            SELECT order_id, symbol, side, quantity, price, status, timestamp,
                   execution_algo, benchmark_price, executed_qty, avg_executed_price, slippage_bps
            FROM trade_journal
            WHERE portfolio_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (portfolio_id, limit))
    else:
        cursor.execute('''
            SELECT order_id, symbol, side, quantity, price, status, timestamp,
                   execution_algo, benchmark_price, executed_qty, avg_executed_price, slippage_bps
            FROM trade_journal
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))
        
    rows = cursor.fetchall()
    conn.close()
    
    trades = []
    for row in rows:
        trades.append({
            "order_id": row[0],
            "symbol": row[1],
            "side": row[2],
            "quantity": row[3],
            "limit_price": row[4],
            "status": row[5],
            "timestamp": row[6],
            "execution_algo": row[7] if row[7] is not None else 'DIRECT',
            "benchmark_price": row[8] if row[8] is not None else row[4],
            "executed_qty": row[9] if row[9] is not None else 0,
            "avg_executed_price": row[10] if row[10] is not None else 0.0,
            "slippage_bps": row[11] if row[11] is not None else 0.0
        })
    return trades
