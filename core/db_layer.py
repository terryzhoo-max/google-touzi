import sqlite3
import pandas as pd
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'alphacore.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS time_series (
            symbol TEXT,
            date TEXT,
            close REAL,
            PRIMARY KEY (symbol, date)
        )
    ''')
    conn.commit()
    conn.close()

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
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.executemany('''
        INSERT OR REPLACE INTO time_series (symbol, date, close)
        VALUES (?, ?, ?)
    ''', records)
    conn.commit()
    conn.close()

def get_cached_timeseries(symbol, start_date, end_date):
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT date, close FROM time_series WHERE symbol = ? AND date >= ? AND date <= ? ORDER BY date ASC"
    df = pd.read_sql_query(query, conn, params=(symbol, start_date, end_date))
    conn.close()
    if df.empty:
        return None
    df['Date'] = pd.to_datetime(df['date'])
    df.set_index('Date', inplace=True)
    df.rename(columns={'close': 'Close'}, inplace=True)
    return df
