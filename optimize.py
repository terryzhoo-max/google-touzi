import pandas as pd
import numpy as np
from core.db_layer import init_db, get_cached_timeseries

def get_symbol_data_local(symbol, years=18):
    # Just fetch from db, do not download to save time
    import datetime
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=365 * years)
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')
    df = get_cached_timeseries(symbol, start_str, end_str)
    return df

def evaluate_params(vix_thresh, tnx_ma_window, w_norm, w_def, w_inf):
    spy = get_symbol_data_local('SPY')
    tlt = get_symbol_data_local('TLT')
    gld = get_symbol_data_local('GLD')
    vix = get_symbol_data_local('^VIX')
    tnx = get_symbol_data_local('^TNX')
    
    if spy is None or spy.empty: return None

    df = pd.DataFrame({
        'SPY': spy['Close'],
        'TLT': tlt['Close'],
        'GLD': gld['Close'],
        'VIX': vix['Close'],
        'TNX': tnx['Close']
    }).dropna()
    
    df['SPY_Ret'] = df['SPY'].pct_change()
    df['TLT_Ret'] = df['TLT'].pct_change()
    df['GLD_Ret'] = df['GLD'].pct_change()
    
    df['VIX_prev'] = df['VIX'].shift(1)
    df['TNX_prev'] = df['TNX'].shift(1)
    
    df['TNX_MA'] = df['TNX_prev'].rolling(window=tnx_ma_window).mean()
    df['TNX_MA'] = df['TNX_MA'].fillna(df['TNX_prev'])
    
    df['W_SPY'] = w_norm[0]
    df['W_TLT'] = w_norm[1]
    df['W_GLD'] = w_norm[2]
    df['W_CASH'] = w_norm[3]
    
    mask_deflation = (df['VIX_prev'] > vix_thresh) & (df['TNX_prev'] < df['TNX_MA'])
    df.loc[mask_deflation, 'W_SPY'] = w_def[0]
    df.loc[mask_deflation, 'W_TLT'] = w_def[1]
    df.loc[mask_deflation, 'W_GLD'] = w_def[2]
    df.loc[mask_deflation, 'W_CASH'] = w_def[3]
    
    mask_inflation = (df['VIX_prev'] > vix_thresh) & (df['TNX_prev'] >= df['TNX_MA'])
    df.loc[mask_inflation, 'W_SPY'] = w_inf[0]
    df.loc[mask_inflation, 'W_TLT'] = w_inf[1]
    df.loc[mask_inflation, 'W_GLD'] = w_inf[2]
    df.loc[mask_inflation, 'W_CASH'] = w_inf[3]
    
    df['Strat_Ret'] = (df['W_SPY'] * df['SPY_Ret'] + 
                       df['W_TLT'] * df['TLT_Ret'] + 
                       df['W_GLD'] * df['GLD_Ret'] +
                       df['W_CASH'] * 0.0)
    
    df['Strat_Eq'] = (1 + df['Strat_Ret']).cumprod()
    
    df = df.dropna()
    trading_days = 252
    years = len(df) / trading_days
    if years == 0: return None
    
    cagr = (df['Strat_Eq'].iloc[-1] ** (1/years) - 1) * 100
    peak = df['Strat_Eq'].cummax()
    mdd = ((df['Strat_Eq'] - peak) / peak).min() * 100
    sharpe = (df['Strat_Ret'].mean() / df['Strat_Ret'].std()) * np.sqrt(trading_days)
    
    return {'cagr': round(cagr, 2), 'mdd': round(mdd, 2), 'sharpe': round(sharpe, 3)}

init_db()

# Baseline (Backtest defaults)
print("Baseline (25, 200, [0.6,0.3,0.1,0], [0.0,0.8,0.2,0], [0,0,0.4,0.6]):")
print(evaluate_params(25, 200, [0.6, 0.3, 0.1, 0.0], [0.0, 0.8, 0.2, 0.0], [0.0, 0.0, 0.4, 0.6]))

# Grid Search
vix_list = [20, 22, 25, 28]
tnx_ma_list = [20, 50, 100, 200]
best_sharpe = 0
best_params = None

print("\nRunning Grid Search...")
for v in vix_list:
    for ma in tnx_ma_list:
        # Tweak Normal weights: maybe 70/20/10 or 60/40/0
        norm = [0.6, 0.3, 0.1, 0.0]
        # Deflation: 0 SPY, 80 TLT, 20 GLD
        def_w = [0.0, 0.8, 0.2, 0.0]
        # Inflation: 0 SPY, 0 TLT, 40 GLD, 60 CASH
        inf_w = [0.0, 0.0, 0.4, 0.6]
        
        res = evaluate_params(v, ma, norm, def_w, inf_w)
        if res and res['sharpe'] > best_sharpe:
            best_sharpe = res['sharpe']
            best_params = (v, ma, norm, def_w, inf_w, res)

print(f"\nBest Sharpe Config:")
print(f"VIX: {best_params[0]}, TNX_MA: {best_params[1]}")
print(f"Norm: {best_params[2]}, Deflation: {best_params[3]}, Inflation: {best_params[4]}")
print(f"Result: {best_params[5]}")
