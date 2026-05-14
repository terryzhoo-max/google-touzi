import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from core.db_layer import init_db, get_cached_timeseries, save_timeseries
from core.data_providers import get_us_etf_history_long, get_china_etf_history_long, get_vix_history, get_tnx_history

def get_symbol_data(symbol, years=5):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365 * years)
    
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')
    
    df = get_cached_timeseries(symbol, start_str, end_str)
    
    if df is None or len(df) < (years * 252 * 0.9):
        print(f"Downloading {symbol} ({years}y) via data_providers …")
        if symbol == "^VIX":
            s = get_vix_history(days=365 * years)
        elif symbol == "^TNX":
            s = get_tnx_history(days=365 * years)
        elif symbol.endswith(".SH") or symbol.endswith(".SZ"):
            s = get_china_etf_history_long(symbol, years=years)
        else:
            s = get_us_etf_history_long(symbol, years=years)

        if s.empty:
            return pd.DataFrame()

        df_save = pd.DataFrame({"Close": s})
        save_timeseries(symbol, df_save)
        df = get_cached_timeseries(symbol, start_str, end_str)
        
    return df

def run_backtest():
    init_db()
    
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    symbols = ['SPY', 'TLT', 'GLD', '^VIX', '^TNX']
    results = {}
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_symbol = {executor.submit(get_symbol_data, sym, 18): sym for sym in symbols}
        for future in as_completed(future_to_symbol):
            sym = future_to_symbol[future]
            try:
                results[sym] = future.result()
            except Exception as e:
                print(f"Error fetching {sym} for backtest: {e}")
                results[sym] = pd.DataFrame()
                
    spy = results.get('SPY', pd.DataFrame())
    tlt = results.get('TLT', pd.DataFrame())
    gld = results.get('GLD', pd.DataFrame())
    vix = results.get('^VIX', pd.DataFrame())
    tnx = results.get('^TNX', pd.DataFrame())
    
    if spy.empty or tlt.empty or vix.empty or tnx.empty or gld.empty:
        return {"error": "Missing data for backtest"}
        
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
    
    # Calculate 200-day moving average of TNX to determine long-term rate trend
    df['TNX_MA'] = df['TNX_prev'].rolling(window=200).mean()
    
    # Fill NA for MA with the current value to prevent dropping 200 days
    df['TNX_MA'] = df['TNX_MA'].fillna(df['TNX_prev'])
    
    # 动态调仓逻辑 (股/债/金/现金 4通道模型)
    df['W_SPY'] = 0.6
    df['W_TLT'] = 0.3
    df['W_GLD'] = 0.1
    df['W_CASH'] = 0.0
    
    # Regime 2: Deflationary Risk Off (VIX > 25, Rates Falling)
    mask_deflation = (df['VIX_prev'] > 25) & (df['TNX_prev'] < df['TNX_MA'])
    df.loc[mask_deflation, 'W_SPY'] = 0.0
    df.loc[mask_deflation, 'W_TLT'] = 0.8
    df.loc[mask_deflation, 'W_GLD'] = 0.2
    df.loc[mask_deflation, 'W_CASH'] = 0.0
    
    # Regime 3: Inflationary Risk Off (VIX > 25, Rates Rising -> 股债双杀)
    mask_inflation = (df['VIX_prev'] > 25) & (df['TNX_prev'] >= df['TNX_MA'])
    df.loc[mask_inflation, 'W_SPY'] = 0.0
    df.loc[mask_inflation, 'W_TLT'] = 0.0
    df.loc[mask_inflation, 'W_GLD'] = 0.4
    df.loc[mask_inflation, 'W_CASH'] = 0.6
    
    # Cash return is assumed 0% for simplicity (or we could use TNX/252, but 0 is more conservative)
    df['Strat_Ret'] = (df['W_SPY'] * df['SPY_Ret'] + 
                       df['W_TLT'] * df['TLT_Ret'] + 
                       df['W_GLD'] * df['GLD_Ret'] +
                       df['W_CASH'] * 0.0)
    
    df['Strat_Eq'] = (1 + df['Strat_Ret']).cumprod()
    df['Bench_Eq'] = (1 + df['SPY_Ret']).cumprod()
    
    df = df.dropna()
    
    trading_days = 252
    years = len(df) / trading_days
    
    strat_cagr = (df['Strat_Eq'].iloc[-1] ** (1/years) - 1) if years > 0 else 0
    bench_cagr = (df['Bench_Eq'].iloc[-1] ** (1/years) - 1) if years > 0 else 0
    
    strat_peak = df['Strat_Eq'].cummax()
    strat_dd = (df['Strat_Eq'] - strat_peak) / strat_peak
    strat_mdd = strat_dd.min()
    
    bench_peak = df['Bench_Eq'].cummax()
    bench_dd = (df['Bench_Eq'] - bench_peak) / bench_peak
    bench_mdd = bench_dd.min()
    
    strat_sharpe = (df['Strat_Ret'].mean() / df['Strat_Ret'].std()) * np.sqrt(trading_days)
    bench_sharpe = (df['SPY_Ret'].mean() / df['SPY_Ret'].std()) * np.sqrt(trading_days)
    
    df['W_SPY_diff'] = df['W_SPY'].diff()
    
    signals = []
    for date, row in df.iterrows():
        diff = row['W_SPY_diff']
        dt_str = date.strftime('%Y-%m-%d')
        if diff < 0:
            signals.append({
                "time": dt_str,
                "position": "aboveBar",
                "color": "#ef4444",
                "shape": "arrowDown",
                "text": "SELL"
            })
        elif diff > 0:
            signals.append({
                "time": dt_str,
                "position": "belowBar",
                "color": "#4ade80",
                "shape": "arrowUp",
                "text": "BUY"
            })
            
    dates = df.index.strftime('%Y-%m-%d').tolist()
    spy_close = df['SPY'].round(2).tolist()
    strat_eq = (df['Strat_Eq'] * 100).round(2).tolist()
    bench_eq = (df['Bench_Eq'] * 100).round(2).tolist()
    
    last_row = df.iloc[-1]
    current_state = {
        "date": last_row.name.strftime('%Y-%m-%d'),
        "vix": round(last_row['VIX'], 2),
        "w_spy": int(last_row['W_SPY'] * 100),
        "w_tlt": int(last_row['W_TLT'] * 100),
        "w_gld": int(last_row['W_GLD'] * 100),
        "w_cash": int(last_row['W_CASH'] * 100)
    }
    
    # Determine string representation of the regime
    if last_row['W_CASH'] > 0:
        regime_str = "通胀型恐慌 (极致防守)"
        regime_color = "#ef4444"
        asset_strategies = [
            {"asset": "SPY (标普500)", "weight": int(last_row['W_SPY'] * 100), "icon": "📈", "strategy": "波动率与利率双杀，右侧动能丧失，强制切断所有权益类风险敞口。"},
            {"asset": "TLT (长端美债)", "weight": int(last_row['W_TLT'] * 100), "icon": "🛡️", "strategy": "加息缩表导致债券熊市，长债失去避险属性，清仓规避久期风险。"},
            {"asset": "GLD (黄金)", "weight": int(last_row['W_GLD'] * 100), "icon": "🥇", "strategy": "保留基础比例对冲法币信用风险，但防范流动性危机下的无差别抛售。"},
            {"asset": "CASH (美元现金)", "weight": int(last_row['W_CASH'] * 100), "icon": "💵", "strategy": "宏观范式剧变期，现金为王。持有极短久期票据等待流动性恢复。"}
        ]
    elif last_row['W_TLT'] >= 0.7:
        regime_str = "通缩型恐慌 (美债避险)"
        regime_color = "#fbbf24"
        asset_strategies = [
            {"asset": "SPY (标普500)", "weight": int(last_row['W_SPY'] * 100), "icon": "📈", "strategy": "经济预期极速衰退，企业盈利下滑，规避所有高风险资产。"},
            {"asset": "TLT (长端美债)", "weight": int(last_row['W_TLT'] * 100), "icon": "🛡️", "strategy": "长端利率掉头向下，宏观进入衰退抢跑期，重仓长债吃足票息与资本利得。"},
            {"asset": "GLD (黄金)", "weight": int(last_row['W_GLD'] * 100), "icon": "🥇", "strategy": "维持标准抗通胀压舱石比例，对冲部分不确定性。"},
            {"asset": "CASH (美元现金)", "weight": int(last_row['W_CASH'] * 100), "icon": "💵", "strategy": "系统流动性尚可，长债已提供足够保护，无需持有绝对现金。"}
        ]
    else:
        regime_str = "常态扩张期 (均衡多头)"
        regime_color = "#4ade80"
        asset_strategies = [
            {"asset": "SPY (标普500)", "weight": int(last_row['W_SPY'] * 100), "icon": "📈", "strategy": "宏观波动率处于健康区间，重仓权益资产享受核心复利增长。"},
            {"asset": "TLT (长端美债)", "weight": int(last_row['W_TLT'] * 100), "icon": "🛡️", "strategy": "提供组合基础对冲，压平股市日常波动。"},
            {"asset": "GLD (黄金)", "weight": int(last_row['W_GLD'] * 100), "icon": "🥇", "strategy": "底仓配置以防范地缘政治黑天鹅。"},
            {"asset": "CASH (美元现金)", "weight": int(last_row['W_CASH'] * 100), "icon": "💵", "strategy": "市场处于上行周期，资金应最大化利用效率，无须囤积现金。"}
        ]
        
    current_state["regime"] = regime_str
    current_state["regime_color"] = regime_color
    current_state["asset_strategies"] = asset_strategies

    return {
        "dates": dates,
        "spy_close": spy_close,
        "signals": signals,
        "strat_eq": strat_eq,
        "bench_eq": bench_eq,
        "current_state": current_state,
        "metrics": {
            "strat_cagr": round(strat_cagr * 100, 2),
            "strat_mdd": round(strat_mdd * 100, 2),
            "strat_sharpe": round(strat_sharpe, 2),
            "bench_cagr": round(bench_cagr * 100, 2),
            "bench_mdd": round(bench_mdd * 100, 2),
            "bench_sharpe": round(bench_sharpe, 2)
        }
    }
