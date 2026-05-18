import os
import sys
import pandas as pd
import numpy as np
import time

# Ensure we can import from core
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.data_providers import get_china_etf_history_long

def run_erp_backtest():
    print("Fetching 8 years of data to ensure 5-year clean backtest window...")
    # Fetch 8 years so we have enough buffer for 250 MA + 500 rolling Z-score
    s = get_china_etf_history_long("510300.SH", years=8)
    if s.empty:
        print("Error: Failed to fetch data.")
        return
        
    df = pd.DataFrame({"Close": s})
    df = df.sort_index()
    
    # Calculate daily returns
    df['Ret'] = df['Close'].pct_change()
    
    # Calculate 250-day moving average
    df['MA250'] = df['Close'].rolling(window=250).mean()
    
    # Calculate Deviation
    df['Dev'] = df['Close'] / df['MA250'] - 1
    
    # Calculate Z-Score of Deviation over a 500-day rolling window
    dev_mean = df['Dev'].rolling(window=500).mean()
    dev_std = df['Dev'].rolling(window=500).std()
    
    # Synthetic ERP Z-Score (inverted, so positive means undervalued/oversold)
    df['ERP_Z'] = - (df['Dev'] - dev_mean) / dev_std
    
    # Filter to the last 5 years (approx 1250 trading days)
    df = df.dropna()
    df = df.tail(1250).copy()
    
    # State Machine for Position Sizing
    # 0 = Cash, 0.5 = Half Position, 1.0 = Full Position
    weights = []
    current_weight = 0.0
    
    for z in df['ERP_Z']:
        if z > 2.0:
            current_weight = 1.0
        elif z > 1.5 and current_weight == 0.0:
            current_weight = 0.5
        elif z < 0.0:
            current_weight = 0.0
            
        weights.append(current_weight)
        
    df['Weight'] = weights
    
    # Calculate turnover for friction (0.05% per trade)
    df['Turnover'] = df['Weight'].diff().abs().fillna(0)
    friction = 0.0005
    
    # Cash Yield 1.5% annualized
    cash_yield = 0.015 / 252
    
    # Portfolio Return (T-1 weight * T return)
    df['Strat_Ret'] = df['Weight'].shift(1) * df['Ret'] + (1 - df['Weight'].shift(1)) * cash_yield - df['Turnover'] * friction
    df['Strat_Ret'] = df['Strat_Ret'].fillna(0)
    
    # Equity Curves
    df['Strat_Eq'] = (1 + df['Strat_Ret']).cumprod()
    df['Bench_Eq'] = (1 + df['Ret']).cumprod()
    
    # Metrics calculation
    years = len(df) / 252
    
    strat_cagr = df['Strat_Eq'].iloc[-1] ** (1/years) - 1
    bench_cagr = df['Bench_Eq'].iloc[-1] ** (1/years) - 1
    
    strat_peak = df['Strat_Eq'].cummax()
    strat_dd = (df['Strat_Eq'] - strat_peak) / strat_peak
    strat_mdd = strat_dd.min()
    
    bench_peak = df['Bench_Eq'].cummax()
    bench_dd = (df['Bench_Eq'] - bench_peak) / bench_peak
    bench_mdd = bench_dd.min()
    
    strat_sharpe = (df['Strat_Ret'].mean() / df['Strat_Ret'].std()) * np.sqrt(252) if df['Strat_Ret'].std() != 0 else 0
    bench_sharpe = (df['Ret'].mean() / df['Ret'].std()) * np.sqrt(252)
    
    strat_calmar = strat_cagr / abs(strat_mdd) if strat_mdd != 0 else 0
    
    exposure_days = (df['Weight'] > 0).sum()
    
    print("\n" + "="*50)
    print(f"5-Year Synthetic ERP Backtest: 510300.SH")
    print(f"Period: {df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}")
    print("="*50)
    print(f"Strategy CAGR      : {strat_cagr*100:.2f}%")
    print(f"Benchmark CAGR     : {bench_cagr*100:.2f}%")
    print(f"Strategy Max DD    : {strat_mdd*100:.2f}%")
    print(f"Benchmark Max DD   : {bench_mdd*100:.2f}%")
    print(f"Strategy Sharpe    : {strat_sharpe:.2f}")
    print(f"Benchmark Sharpe   : {bench_sharpe:.2f}")
    print(f"Strategy Calmar    : {strat_calmar:.2f}")
    print(f"Market Exposure    : {exposure_days / len(df) * 100:.1f}% of days")
    print("="*50)

if __name__ == "__main__":
    run_erp_backtest()
