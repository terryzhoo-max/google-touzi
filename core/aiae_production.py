import pandas as pd
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.data_providers import _tushare_items, _ts_items_to_series, get_vix_history, get_tnx_history
from core.aiae_backtest_signal import compute_aiae_signal

# 映射名称用于前端显示
ASSET_METADATA = {
    '510300.SH': {'name': '沪深300ETF', 'icon': '🇨🇳'},
    '588000.SH': {'name': '科创50ETF', 'icon': '🚀'},
    '513500.SH': {'name': '标普500ETF', 'icon': '🇺🇸'},
    '513180.SH': {'name': '恒生科技ETF', 'icon': '💻'},
    '513520.SH': {'name': '日经225ETF', 'icon': '🇯🇵'},
    '518880.SH': {'name': '黄金ETF', 'icon': '🪙'}
}

def fetch_fund_fast(code: str, days_back: int = 400) -> pd.Series:
    """Fast fetch for production (only recent data)"""
    end = datetime.date.today()
    start = end - datetime.timedelta(days=days_back)
    try:
        items = _tushare_items(
            'fund_daily',
            params={
                "ts_code": code,
                "start_date": start.strftime("%Y%m%d"),
                "end_date": end.strftime("%Y%m%d"),
            },
            fields="trade_date,close",
        )
        s = _ts_items_to_series(items, date_col=0, val_col=1, name=code)
        return s
    except Exception as e:
        print(f"[AIAE_PROD] Failed to fetch {code}: {e}")
        return pd.Series(dtype=float)

def get_current_aiae_allocation() -> dict:
    """
    Production entry point: Fetches latest data, runs the AIAE signal logic,
    and formats the latest target weights for the AlphaCore UI.
    """
    assets = list(ASSET_METADATA.keys())
    
    # 1. Fetch recent data (400 days covers 200 trading days for TNX MA easily)
    results = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fetch_fund_fast, sym, 400): sym for sym in assets}
        futures[executor.submit(get_vix_history, 400)] = 'VIX'
        futures[executor.submit(get_tnx_history, 400)] = 'TNX'
        
        for future in as_completed(futures):
            sym = futures[future]
            try:
                s = future.result()
                if not s.empty:
                    s.name = sym
                    results[sym] = s
            except Exception as e:
                print(f"[AIAE_PROD] Error reading future for {sym}: {e}")

    df = pd.DataFrame(results).ffill().dropna()
    if df.empty or len(df) < 200:
        raise ValueError("Insufficient data to compute 200-day MA or momentum in production.")
        
    # 2. Compute Signals using exactly the same logic as the scientific backtest
    # This prevents any discrepancy between backtest and production
    target_weights = compute_aiae_signal(df, assets)
    
    # 3. Extract the very last row (the current actionable signal)
    current_weights = target_weights.iloc[-1]
    
    # Determine the current macro regime for UI explanation
    vix = df['VIX'].iloc[-1]
    tnx = df['TNX'].iloc[-1]
    tnx_ma = df['TNX'].rolling(window=200).mean().fillna(df['TNX']).iloc[-1]
    
    if vix > 25 and tnx < tnx_ma:
        regime = "衰退防御期 (Deflationary Risk-Off)"
        strategy_reason = "恐慌突破25且利率下行，避险至黄金或现金"
    elif vix > 25 and tnx >= tnx_ma:
        regime = "滞胀紧缩期 (Inflationary Risk-Off)"
        strategy_reason = "股债双杀预警，无差别抛售转入现金"
    else:
        regime = "动量轮动期 (Normal Regime)"
        strategy_reason = "恐慌可控，追随各宽基ETF跨月截面动量"

    # 4. Format for UI
    alloc = []
    for asset, weight in current_weights.items():
        if weight > 0:
            val = round(weight * 100, 2)
            if asset == 'CASH':
                alloc.append({
                    "value": val,
                    "name": "战略现金 (货币基金)",
                    "icon": "💵",
                    "strategy": "宏观防御安全垫"
                })
            else:
                meta = ASSET_METADATA.get(asset, {})
                alloc.append({
                    "value": val,
                    "name": meta.get('name', asset),
                    "icon": meta.get('icon', '📈'),
                    "strategy": strategy_reason if "动量" not in strategy_reason else "AIAE动量强推"
                })
                
    # Sort descending by weight
    alloc = sorted(alloc, key=lambda x: x['value'], reverse=True)

    return {
        "regime": regime,
        "vix_ref": round(vix, 2),
        "tnx_ref": round(tnx, 2),
        "dxy_ref": 100.0, # Not strictly used in this model, placeholder for UI
        "allocation": alloc
    }

if __name__ == "__main__":
    import json
    res = get_current_aiae_allocation()
    print(json.dumps(res, indent=2, ensure_ascii=False))
