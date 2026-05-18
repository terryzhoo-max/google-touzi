import os
import sys
import pandas as pd
import numpy as np

# Ensure we can import from core
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.data_providers import get_china_etf_history_long, get_us_etf_history_long, get_vix_history, get_dxy_history

def fetch_data():
    days = 8 * 365
    print("Fetching CSI300...")
    csi = get_china_etf_history_long("510300.SH", years=8)
    
    print("Fetching SP500...")
    spy = get_us_etf_history_long("SPY", years=8)
    
    print("Fetching VIX...")
    vix = get_vix_history(days=days)
    
    print("Fetching DXY...")
    dxy = get_dxy_history(days=days)
    
    df = pd.DataFrame({
        "CSI": csi,
        "SPY": spy,
        "VIX": vix,
        "DXY": dxy
    })
    
    # Forward fill to align dates, limit to 5 days ffill to drop totally stale data
    df = df.ffill(limit=5).dropna()
    return df

def run_v2_backtest():
    df = fetch_data()
    if df.empty or len(df) < 500:
        print("Error: Failed to fetch synchronized cross-market data.")
        return
        
    # Calculate daily returns
    df['CSI_Ret'] = df['CSI'].pct_change()
    df['SPY_Ret'] = df['SPY'].pct_change()
    
    # 1. A-Share Synthetic ERP
    df['CSI_MA250'] = df['CSI'].rolling(window=250).mean()
    df['Dev'] = df['CSI'] / df['CSI_MA250'] - 1
    dev_mean = df['Dev'].rolling(window=500).mean()
    dev_std = df['Dev'].rolling(window=500).std()
    df['ERP_Z'] = - (df['Dev'] - dev_mean) / dev_std
    
    # 2. DXY Liquidity Filter
    df['DXY_MA60'] = df['DXY'].rolling(window=60).mean()
    
    # 3. SP500 Trend Filter
    df['SPY_MA200'] = df['SPY'].rolling(window=200).mean()
    
    # Filter to last 5 years (approx 1250 days)
    df = df.dropna().tail(1250).copy()
    
    w_csi = np.zeros(len(df))
    w_spy = np.zeros(len(df))
    
    a_share_buy = (df['ERP_Z'] > 1.5) & (df['DXY'] < df['DXY_MA60'])
    us_share_buy = (df['VIX'] < 25) & (df['SPY'] > df['SPY_MA200'])
    
    for i in range(len(df)):
        if a_share_buy.iloc[i]:
            w_csi[i] = 1.0
            w_spy[i] = 0.0
        elif us_share_buy.iloc[i]:
            w_csi[i] = 0.0
            w_spy[i] = 1.0
        else:
            w_csi[i] = 0.0
            w_spy[i] = 0.0
            
    df['W_CSI'] = w_csi
    df['W_SPY'] = w_spy
    
    df['Turnover'] = df['W_CSI'].diff().abs() + df['W_SPY'].diff().abs()
    
    # Base friction (commissions + standard slippage)
    base_friction = 0.001 
    # Dynamic slippage multiplier based on VIX (proxy for market depth/spreads)
    df['Slippage_Mult'] = np.where(df['VIX'] > 30, 2.5, np.where(df['VIX'] > 20, 1.5, 1.0))
    df['Execution_Cost'] = df['Turnover'].fillna(0) * base_friction * df['Slippage_Mult']
    
    cash_yield = 0.015 / 252
    
    # T+1 Execution Proxy: 
    # Signal generated at T (based on T's close).
    # Executed at T+1 Close (safest proxy without intraday data).
    # Returns begin accruing from T+2. Thus, shift weights by 2.
    exec_shift = 2
    
    df['Strat_Ret'] = (
        df['W_CSI'].shift(exec_shift) * df['CSI_Ret'] + 
        df['W_SPY'].shift(exec_shift) * df['SPY_Ret'] + 
        (1 - df['W_CSI'].shift(exec_shift) - df['W_SPY'].shift(exec_shift)) * cash_yield - 
        df['Execution_Cost'].shift(exec_shift - 1).fillna(0) # Cost incurred on the day of execution (T+1)
    )
    df['Strat_Ret'] = df['Strat_Ret'].fillna(0)
    
    df['Bench_Ret'] = 0.6 * df['CSI_Ret'] + 0.4 * df['SPY_Ret']
    
    df['Strat_Eq'] = (1 + df['Strat_Ret']).cumprod()
    df['Bench_Eq'] = (1 + df['Bench_Ret']).cumprod()
    
    years = len(df) / 252
    
    strat_cagr = df['Strat_Eq'].iloc[-1] ** (1/years) - 1
    bench_cagr = df['Bench_Eq'].iloc[-1] ** (1/years) - 1
    
    strat_mdd = (df['Strat_Eq'] / df['Strat_Eq'].cummax() - 1).min()
    bench_mdd = (df['Bench_Eq'] / df['Bench_Eq'].cummax() - 1).min()
    
    strat_sharpe = (df['Strat_Ret'].mean() / df['Strat_Ret'].std()) * np.sqrt(252) if df['Strat_Ret'].std() != 0 else 0
    bench_sharpe = (df['Bench_Ret'].mean() / df['Bench_Ret'].std()) * np.sqrt(252)
    
    strat_calmar = strat_cagr / abs(strat_mdd) if strat_mdd != 0 else 0
    
    csi_exposure = (df['W_CSI'] > 0).sum() / len(df)
    spy_exposure = (df['W_SPY'] > 0).sum() / len(df)
    cash_exposure = ((df['W_CSI'] == 0) & (df['W_SPY'] == 0)).sum() / len(df)
    
    print("\n" + "="*50)
    print(f"V2 Global Macro Rotation Backtest")
    print(f"Period: {df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}")
    print("="*50)
    print(f"Strategy CAGR      : {strat_cagr*100:.2f}%")
    print(f"Benchmark CAGR     : {bench_cagr*100:.2f}%")
    print(f"Strategy Max DD    : {strat_mdd*100:.2f}%")
    print(f"Benchmark Max DD   : {bench_mdd*100:.2f}%")
    print(f"Strategy Sharpe    : {strat_sharpe:.2f}")
    print(f"Benchmark Sharpe   : {bench_sharpe:.2f}")
    print(f"Strategy Calmar    : {strat_calmar:.2f}")
    print(f"A-Share Exposure   : {csi_exposure*100:.1f}%")
    print(f"US-Share Exposure  : {spy_exposure*100:.1f}%")
    print(f"Cash Exposure      : {cash_exposure*100:.1f}%")
    print("="*50)

if __name__ == "__main__":
    run_v2_backtest()
