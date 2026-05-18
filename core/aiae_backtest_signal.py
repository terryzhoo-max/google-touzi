import pandas as pd
import numpy as np
from core.config import settings

def compute_aiae_signal(history_df: pd.DataFrame, asset_cols: list) -> pd.DataFrame:
    """
    AIAE (Asymmetric Information Allocation Engine) Signal Generator
    Uses rigorous T-1 macro conditions to avoid look-ahead bias.
    Includes institutional features: dynamic thresholds, continuous deleveraging, and turnover control.
    """
    df = history_df.copy()
    
    # 1. Macro Features & Dynamic Thresholds
    df['VIX_val'] = df['VIX'].fillna(20.0)
    df['TNX_val'] = df['TNX'].fillna(4.0)
    df['TNX_MA'] = df['TNX_val'].rolling(window=200).mean().fillna(df['TNX_val'])
    
    # Dynamic VIX Threshold (85th percentile of 1-year rolling, fallback to 25)
    vix_thresh_base = getattr(settings, 'AIAE_VIX_THRESHOLD', 25.0)
    df['VIX_THRESH'] = df['VIX_val'].rolling(window=252).quantile(0.85).fillna(vix_thresh_base)
    # Cap the threshold to not be too high or too low
    df['VIX_THRESH'] = df['VIX_THRESH'].clip(lower=20.0, upper=35.0)
    
    weights = pd.DataFrame(index=df.index, columns=asset_cols + ['CASH'], dtype=float).fillna(0.0)
    
    # 2. Multi-Factor Scoring (Vectorized)
    momentum = pd.DataFrame(index=df.index, columns=asset_cols)
    inv_vol = pd.DataFrame(index=df.index, columns=asset_cols)
    
    for col in asset_cols:
        ret_1m = df[col] / df[col].shift(21) - 1
        ret_3m = df[col] / df[col].shift(63) - 1
        momentum[col] = (ret_1m * 0.4 + ret_3m * 0.6).fillna(0)
        
        # 20-day volatility (annualized)
        vol_20d = df[col].pct_change().rolling(20).std() * np.sqrt(252)
        inv_vol[col] = 1.0 / vol_20d.replace(0, np.nan).fillna(0.15) # avoid div by zero
        
    # Rank scoring (0.0 to 1.0) cross-sectionally
    mom_score = momentum.rank(axis=1, pct=True).fillna(0)
    vol_score = inv_vol.rank(axis=1, pct=True).fillna(0)
    
    weights.loc[:, 'CASH'] = 1.0
    
    # Turnover Threshold (e.g., 5% per asset, meaning we don't trade unless target deviates by > 5%)
    turnover_threshold = getattr(settings, 'AIAE_TURNOVER_THRESHOLD', 0.05)
    last_weights = np.zeros(len(asset_cols) + 1)
    last_weights[-1] = 1.0 # start with 100% cash
    
    for i in range(len(df)):
        vix = df['VIX_val'].iloc[i]
        vix_t = df['VIX_THRESH'].iloc[i]
        tnx = df['TNX_val'].iloc[i]
        tnx_ma = df['TNX_MA'].iloc[i]
        
        # Continuous Deleveraging Multiplier (0.0 to 1.0)
        if vix <= vix_t:
            risk_multiplier = 1.0
        elif vix >= vix_t + 5.0:
            risk_multiplier = 0.0
        else:
            risk_multiplier = 1.0 - (vix - vix_t) / 5.0
            
        is_deflation = (vix > vix_t) and (tnx < tnx_ma)
        is_inflation = (vix > vix_t) and (tnx >= tnx_ma)
        is_normal = not (is_deflation or is_inflation)
        
        target = np.zeros(len(asset_cols) + 1)
        base_target = np.zeros(len(asset_cols))
        base_cash = 1.0
        
        # Macro Regime Defense Boost
        macro_score = pd.Series(0.0, index=asset_cols)
        if is_deflation and risk_multiplier < 1.0:
            for safe_asset in ['518880.SH', 'GLD', '512890.SH']: # Gold, Dividend
                if safe_asset in asset_cols:
                    macro_score[safe_asset] = 1.0 # Max boost for defense
        
        if is_normal or risk_multiplier > 0:
            # Composite Score (40% Mom, 30% Vol, 30% Macro)
            comp_score = (mom_score.iloc[i] * 0.4) + (vol_score.iloc[i] * 0.3) + (macro_score * 0.3)
            
            # Absolute filter: Never buy negative momentum assets (falling knives)
            comp_score = comp_score[momentum.iloc[i] > 0]
            
            if len(comp_score) > 0:
                # Top 3 asset selection
                top_k = min(3, len(comp_score))
                top_assets = comp_score.nlargest(top_k)
                total_score = top_assets.sum()
                
                if total_score > 0:
                    for asset, score in top_assets.items():
                        idx = asset_cols.index(asset)
                        base_target[idx] = (score / total_score) * risk_multiplier
                    base_cash = 1.0 - risk_multiplier
                
            # If deflation and we still have unallocated cash from risk_multiplier
            if is_deflation and risk_multiplier < 1.0:
                allocated_defense = False
                for safe_asset in ['518880.SH', 'GLD']:
                    if safe_asset in asset_cols and momentum.iloc[i][safe_asset] > 0:
                        idx = asset_cols.index(safe_asset)
                        base_target[idx] += (1.0 - risk_multiplier)
                        base_cash -= (1.0 - risk_multiplier)
                        allocated_defense = True
                        break
                        
            target[:len(asset_cols)] = base_target
            target[-1] = base_cash
            
        elif is_deflation: # risk_multiplier == 0
            allocated_defense = False
            for safe_asset in ['518880.SH', 'GLD']:
                if safe_asset in asset_cols and momentum.iloc[i][safe_asset] > 0:
                    idx = asset_cols.index(safe_asset)
                    target[idx] = 1.0
                    target[-1] = 0.0
                    allocated_defense = True
                    break
            if not allocated_defense:
                target[-1] = 1.0
        else: # is_inflation and risk_multiplier == 0
            target[-1] = 1.0
            
        # Apply Turnover Friction Control
        diff = np.abs(target - last_weights)
        if np.max(diff) < turnover_threshold:
            # Skip trading, keep old weights
            weights.iloc[i] = last_weights
        else:
            weights.iloc[i] = target
            last_weights = target

    return weights
