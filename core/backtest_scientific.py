import pandas as pd
import numpy as np
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.data_providers import get_global_index_history_long, get_vix_history, get_tnx_history
from core.aiae_backtest_signal import compute_aiae_signal

def run_scientific_backtest():
    """
    Runs the institutional scientific backtest for the AIAE Strategy.
    Assets: SPX (US), N225 (Japan), 000300.SH (China)
    """
    assets = ['SPX', 'N225', '000300.SH']
    
    # 1. Fetch long-term data
    results = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(get_global_index_history_long, sym, 10): sym for sym in assets}
        futures[executor.submit(get_vix_history, 3650)] = 'VIX'
        futures[executor.submit(get_tnx_history, 3650)] = 'TNX'
        
        for future in as_completed(futures):
            sym = futures[future]
            try:
                s = future.result()
                if not s.empty:
                    s.name = sym
                    results[sym] = s
            except Exception as e:
                print(f"Failed to fetch {sym}: {e}")

    df = pd.DataFrame(results).ffill().dropna()
    if df.empty:
        return {"error": "Insufficient data"}
    
    # 2. AIAE Signal Generation (uses strictly T-1)
    target_weights = compute_aiae_signal(df, assets)
    
    # 3. Apply execution logic: Signal of T applied to T+1 Returns
    # FIX: Timezone Look-Ahead Bias. US market closes at T+1 4AM CST, so Asian markets at T close (3PM CST) 
    # cannot know US T close. We MUST shift weights by 1. Signal from T-1 is executed at T close.
    exec_weights = target_weights.shift(1).fillna(0)
    
    returns = df[assets].pct_change().shift(-1) # return from T to T+1
    returns['CASH'] = df['TNX'] / 100 / 252 # Daily risk free rate
    
    # Apply 10bps round-trip friction on weight changes
    friction_bps = 0.0010
    weight_changes = exec_weights.diff().abs().sum(axis=1).fillna(0)
    transaction_costs = weight_changes * (friction_bps / 2.0)
    
    strat_returns = (exec_weights * returns).sum(axis=1) - transaction_costs
    # Shift back strat_returns by 1 because it contains return of T+1 at index T
    strat_returns = strat_returns.shift(1).fillna(0)
    
    # Equal weight benchmark
    eq_w = 1.0 / len(assets)
    bench_returns = returns[assets].mean(axis=1)
    bench_returns = bench_returns.shift(1).fillna(0)
    
    # 4. Out-of-Sample Split
    n_total = len(strat_returns)
    split_idx = int(n_total * 0.70)
    
    is_dates = strat_returns.index[:split_idx]
    oos_dates = strat_returns.index[split_idx:]
    
    # Function to calculate rigorous metrics
    def calc_metrics(ret_series, b_ret_series, signal_df):
        metrics = {}
        cum_ret = (1 + ret_series).cumprod()
        peak = cum_ret.cummax()
        drawdown = (cum_ret - peak) / peak
        
        # Ulcer Index (RMS of drawdowns)
        ulcer_index = np.sqrt(np.mean(drawdown**2))
        
        # CVaR (Expected Shortfall) at 5%
        cvar_5 = ret_series[ret_series <= ret_series.quantile(0.05)].mean()
        
        # Win-Rate (Days > Benchmark)
        win_rate = (ret_series > b_ret_series).mean()
        
        # Signal Hit Rate (Directional accuracy of active positions)
        # Hit: asset weight > 0 AND asset return > cash return
        hits, total_bets = 0, 0
        for dt, w in signal_df.iterrows():
            if dt in ret_series.index and dt != ret_series.index[-1]:
                next_dt = ret_series.index[ret_series.index.get_loc(dt) + 1]
                for a in assets:
                    if w[a] > 0.05:
                        total_bets += 1
                        if returns.loc[dt, a] > returns.loc[dt, 'CASH']:
                            hits += 1
        hit_rate = hits / total_bets if total_bets > 0 else 0
        
        # Sharpe & Calmar & Skewness
        ann_ret = ret_series.mean() * 252
        ann_vol = ret_series.std() * np.sqrt(252)
        sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
        mdd = drawdown.min()
        calmar = ann_ret / abs(mdd) if mdd < 0 else 0
        skewness = ret_series.skew()
        
        metrics['Annual_Return'] = round(ann_ret * 100, 2)
        metrics['Annual_Volatility'] = round(ann_vol * 100, 2)
        metrics['Sharpe_Ratio'] = round(sharpe, 2)
        metrics['Calmar_Ratio'] = round(calmar, 2)
        metrics['Max_Drawdown'] = round(mdd * 100, 2)
        metrics['Ulcer_Index'] = round(ulcer_index * 100, 2)
        metrics['CVaR_5'] = round(cvar_5 * 100, 2)
        metrics['Win_Rate'] = round(win_rate * 100, 2)
        metrics['Signal_Hit_Rate'] = round(hit_rate * 100, 2)
        metrics['Return_Skewness'] = round(skewness, 2)
        
        # --- Bootstrap Resampling (1000 simulations) ---
        # Group by month to preserve some autocorrelation
        try:
            monthly_rets = ret_series.resample('ME').apply(lambda x: (1 + x).prod() - 1)
            n_months = len(monthly_rets)
            if n_months > 12:
                sim_ann_rets = []
                sim_mdds = []
                for _ in range(1000):
                    idx = np.random.randint(0, n_months, n_months)
                    sim_path = monthly_rets.iloc[idx].values
                    sim_cum = np.cumprod(1 + sim_path)
                    sim_ann_rets.append((sim_cum[-1]**(12/n_months) - 1))
                    sim_mdds.append(np.min(sim_cum / np.maximum.accumulate(sim_cum) - 1))
                
                metrics['Bootstrap_Return_5th'] = round(np.percentile(sim_ann_rets, 5) * 100, 2)
                metrics['Bootstrap_Return_95th'] = round(np.percentile(sim_ann_rets, 95) * 100, 2)
                metrics['Bootstrap_MDD_5th'] = round(np.percentile(sim_mdds, 5) * 100, 2) # Worst 5% MDD
                metrics['Bootstrap_MDD_95th'] = round(np.percentile(sim_mdds, 95) * 100, 2) # Best 5% MDD
        except Exception:
            pass
            
        return metrics

    # IS vs OOS Metrics
    is_metrics = calc_metrics(strat_returns.loc[is_dates], bench_returns.loc[is_dates], exec_weights.loc[is_dates])
    oos_metrics = calc_metrics(strat_returns.loc[oos_dates], bench_returns.loc[oos_dates], exec_weights.loc[oos_dates])
    
    return {
        "status": "success",
        "data": {
            "dates": [d.strftime("%Y-%m-%d") for d in strat_returns.index],
            "strat_cum_return": (1 + strat_returns).cumprod().tolist(),
            "bench_cum_return": (1 + bench_returns).cumprod().tolist(),
            "drawdown": ((1 + strat_returns).cumprod() / (1 + strat_returns).cumprod().cummax() - 1).tolist()
        },
        "metrics": {
            "In_Sample": is_metrics,
            "Out_Of_Sample": oos_metrics
        }
    }

if __name__ == "__main__":
    res = run_scientific_backtest()
    import json
    print(json.dumps(res['metrics'], indent=2))
