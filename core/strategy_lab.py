import time
import hashlib
import json
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.backtest import get_symbol_data
from core.db_layer import init_db

# Strategy Configuration (Config-driven)
STRATEGY_POLICY_VERSION = "strategy_factory_policy_v1"
STRATEGY_CONFIG = {
    "barbell_weights": {
        "513500.SH": 0.40,  # SP500
        "510880.SH": 0.30,  # Dividend
        "510300.SH": 0.15,  # CSI300
        "512760.SH": 0.15   # Chip
    },
    "friction_daily": 0.00002
}


def _stable_hash(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_strategy_policy() -> dict:
    payload = {
        "version": STRATEGY_POLICY_VERSION,
        "barbell_weights": STRATEGY_CONFIG["barbell_weights"],
        "friction_daily": STRATEGY_CONFIG["friction_daily"],
        "backtest_window_years": 1,
        "benchmark": {"510300.SH": 0.60, "513500.SH": 0.40},
        "risk_parity_window_days": 30,
        "momentum_window_days": 200,
        "gold_trend_window_days": 60,
        "vix_panic_threshold": 25.0,
    }
    payload["strategy_policy_hash"] = _stable_hash(payload)
    return payload


def _data_quality(status: str = "ok", degraded_reason: str | None = None, source: str = "market_data_cache") -> dict:
    return {
        "status": status,
        "source": source,
        "degraded_reason": degraded_reason,
    }

# Universe Definition
ETF_UNIVERSE = {
    "A_SHARE_BROAD": [
        {"symbol": "510300.SH", "name": "沪深300ETF", "type": "A-Share Broad"},
        {"symbol": "159601.SZ", "name": "A50ETF", "type": "A-Share Broad"},
        {"symbol": "510880.SH", "name": "红利ETF", "type": "A-Share Broad"}
    ],
    "OVERSEAS_BROAD": [
        {"symbol": "513500.SH", "name": "标普500ETF", "type": "Overseas Broad"},
        {"symbol": "513100.SH", "name": "纳指100ETF", "type": "Overseas Broad"},
        {"symbol": "513520.SH", "name": "日经225ETF", "type": "Overseas Broad"}
    ],
    "15TH_FYP_THEME": [
        {"symbol": "512760.SH", "name": "芯片ETF", "type": "15th FYP Theme"},
        {"symbol": "159819.SZ", "name": "人工智能ETF", "type": "15th FYP Theme"},
        {"symbol": "159825.SZ", "name": "农业机械ETF", "type": "15th FYP Theme"},
        {"symbol": "512660.SH", "name": "军工ETF", "type": "15th FYP Theme"}
    ],
    "ALTERNATIVE_HEDGE": [
        {"symbol": "518880.SH", "name": "黄金ETF", "type": "Commodity/Hedge"}
    ]
}

# Global cache for the real backtest result to avoid recalculating on every API call
_CACHED_BACKTEST = None
_CACHED_TIME = 0

class VectorizedBacktester:
    def __init__(self, years=1):
        self.years = years
        self.trading_days = 252 * years
        self.symbols = list(STRATEGY_CONFIG["barbell_weights"].keys())
        self.data = pd.DataFrame()
        
    def fetch_data(self):
        init_db()
        results = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_symbol = {executor.submit(get_symbol_data, sym, self.years): sym for sym in self.symbols}
            for future in as_completed(future_to_symbol):
                sym = future_to_symbol[future]
                try:
                    df = future.result()
                    if not df.empty:
                        results[sym] = df['Close']
                except Exception as e:
                    print(f"Error fetching {sym} for Strategy Lab: {e}")
        
        if not results:
            return False
            
        # Align time series
        self.data = pd.DataFrame(results).sort_index().ffill().dropna()
        return not self.data.empty

    def run_strategy(self):
        df = self.data.copy()
        
        # Calculate daily returns
        for sym in self.symbols:
            if sym in df.columns:
                df[sym+'_Ret'] = df[sym].pct_change()
                
        df = df.dropna()
        if df.empty:
            return None
            
        # Calculate Strategy Returns dynamically from config
        df['Strat_Ret'] = 0.0
        for sym, weight in STRATEGY_CONFIG["barbell_weights"].items():
            ret_col = f'{sym}_Ret'
            if ret_col in df.columns:
                df['Strat_Ret'] += df[ret_col] * weight
                
        # Friction
        df['Strat_Ret'] -= STRATEGY_CONFIG["friction_daily"]
        
        # Benchmark: 60% CSI300 + 40% SP500
        df['Bench_Ret'] = (
            df.get('510300.SH_Ret', 0) * 0.60 +
            df.get('513500.SH_Ret', 0) * 0.40
        )
        
        df['Strat_Eq'] = (1 + df['Strat_Ret']).cumprod()
        df['Bench_Eq'] = (1 + df['Bench_Ret']).cumprod()
        
        # Metrics
        trading_days = 252
        years = len(df) / trading_days
        if years <= 0:
            return None
            
        strat_ytd = (df['Strat_Eq'].iloc[-1] - 1) * 100
        bench_ytd = (df['Bench_Eq'].iloc[-1] - 1) * 100
        
        strat_peak = df['Strat_Eq'].cummax()
        strat_dd = (df['Strat_Eq'] - strat_peak) / strat_peak
        max_dd = strat_dd.min() * 100
        
        strat_sharpe = (df['Strat_Ret'].mean() / (df['Strat_Ret'].std() + 1e-9)) * np.sqrt(trading_days)
        
        dates = df.index.strftime('%Y-%m-%d').tolist()
        strat_curve = ((df['Strat_Eq'] - 1) * 100).round(2).tolist()
        bench_curve = ((df['Bench_Eq'] - 1) * 100).round(2).tolist()
        
        return {
            "dates": dates,
            "strategy_returns": strat_curve,
            "benchmark_returns": bench_curve,
            "status": "ok",
            "data_quality": _data_quality(),
            "metrics": {
                "strategy_ytd": f"{strat_ytd:.2f}%",
                "benchmark_ytd": f"{bench_ytd:.2f}%",
                "max_drawdown": f"{max_dd:.2f}%",
                "sharpe_ratio": f"{strat_sharpe:.2f}",
                "win_rate": f"{(df['Strat_Ret'] > 0).mean() * 100:.1f}%"
            }
        }

def get_real_backtest():
    global _CACHED_BACKTEST, _CACHED_TIME
    # Cache for 1 hour
    if _CACHED_BACKTEST is not None and time.time() - _CACHED_TIME < 3600:
        return _CACHED_BACKTEST
        
    backtester = VectorizedBacktester(years=1)
    if backtester.fetch_data():
        res = backtester.run_strategy()
        if res:
            _CACHED_BACKTEST = res
            _CACHED_TIME = time.time()
            return res
            
    # Hard degradation: no synthetic fake data
    return {
        "status": "unavailable",
        "error": "Insufficient market data for backtest.",
        "data_quality": _data_quality("degraded", "insufficient_market_data"),
        "metrics": None,
        "dates": [],
        "strategy_returns": [],
        "benchmark_returns": [],
    }

def compute_global_risk_parity():
    # Fetch 30-day volatility dynamically
    try:
        csi = get_symbol_data("510300.SH", years=1)
        spy = get_symbol_data("513500.SH", years=1)
        
        csi_ret = csi['Close'].pct_change().tail(30)
        spy_ret = spy['Close'].pct_change().tail(30)
        
        csi_vol = csi_ret.std() * np.sqrt(252) if len(csi_ret) > 10 else 0.18
        spy_vol = spy_ret.std() * np.sqrt(252) if len(spy_ret) > 10 else 0.12
        
        # Inverse volatility weighting
        inv_csi = 1 / csi_vol if csi_vol > 0 else 0
        inv_spy = 1 / spy_vol if spy_vol > 0 else 0
        
        total_inv = inv_csi + inv_spy
        
        w_csi = inv_csi / total_inv if total_inv > 0 else 0.4
        w_spy = inv_spy / total_inv if total_inv > 0 else 0.6
        
        signal = "OVERWEIGHT OVERSEAS" if w_spy > w_csi else "OVERWEIGHT A-SHARE"
        status = "active"
        quality = _data_quality()
        
    except Exception as e:
        print(f"Risk Parity error: {e}")
        csi_vol, spy_vol = 0.185, 0.122
        w_csi, w_spy = 0.0, 0.0
        signal = "NO_SIGNAL"
        status = "degraded"
        quality = _data_quality("degraded", str(e))

    return {
        "id": "global_risk_parity",
        "name": "全球宏观风险平价",
        "name_en": "GLOBAL RISK PARITY",
        "status": status,
        "signal": signal,
        "color": "#3b82f6",
        "model_mode": "live" if status == "active" else "degraded",
        "tradeable": status == "active",
        "data_quality": quality,
        "description": "Volatility-inverse allocation across global broad indices.",
        "details": [
            {"label": "A-Share Vol (30d)", "value": f"{csi_vol*100:.1f}%", "color": "#ef4444" if csi_vol > 0.2 else "#22c55e"},
            {"label": "US-Share Vol (30d)", "value": f"{spy_vol*100:.1f}%", "color": "#ef4444" if spy_vol > 0.2 else "#22c55e"},
            {"label": "Target Weight A-Share", "value": f"{w_csi*100:.1f}%"},
            {"label": "Target Weight US/JP", "value": f"{w_spy*100:.1f}%"}
        ],
        "holdings": [
            {"symbol": "513500.SH", "name": "标普500ETF", "action": "BUY" if status == "active" and w_spy >= w_csi else "HOLD", "weight": f"{int(round(w_spy*100))}%"},
            {"symbol": "510300.SH", "name": "沪深300ETF", "action": "BUY" if status == "active" and w_csi > w_spy else "HOLD", "weight": f"{int(round(w_csi*100))}%"}
        ]
    }

def build_barbell_allocation():
    # Use weights from config
    weights = STRATEGY_CONFIG["barbell_weights"]
    core_weight = (
        weights.get("513500.SH", 0.0) +
        weights.get("510880.SH", 0.0) +
        weights.get("510300.SH", 0.0)
    )
    satellite_weight = weights.get("512760.SH", 0.0)
    w_div = STRATEGY_CONFIG["barbell_weights"].get("510880.SH", 0.3)
    w_chip = STRATEGY_CONFIG["barbell_weights"].get("512760.SH", 0.15)
    
    return {
        "id": "barbell_allocation",
        "name": "核心-卫星哑铃配置",
        "name_en": "BARBELL ALLOCATION",
        "status": "active",
        "signal": "DEFENSIVE TILT",
        "color": "#a855f7",
        "model_mode": "policy_static",
        "tradeable": True,
        "data_quality": _data_quality(source="strategy_policy"),
        "description": "Policy barbell allocation using configured broad, dividend, and 15th FYP theme weights.",
        "details": [
            {"label": "Core Allocation", "value": f"{core_weight*100:.1f}%"},
            {"label": "Satellite Allocation", "value": f"{satellite_weight*100:.1f}%"},
            {"label": "Dividend Yield (Core)", "value": "4.2%", "color": "#22c55e"},
            {"label": "Theme Beta (Satellite)", "value": "1.8x", "color": "#ef4444"}
        ],
        "holdings": [
            {"symbol": "510880.SH", "name": "红利ETF", "action": "BUY", "weight": f"{int(w_div*100)}%"},
            {"symbol": "512760.SH", "name": "芯片ETF", "action": "BUY", "weight": f"{int(w_chip*100)}%"}
        ]
    }

def analyze_absolute_momentum():
    try:
        csi = get_symbol_data("510300.SH", years=1)
        spy = get_symbol_data("513500.SH", years=1)
        
        csi_close = csi['Close'].iloc[-1] if not csi.empty else 0
        csi_ma200 = csi['Close'].rolling(window=200).mean().iloc[-1] if len(csi) >= 200 else csi_close
        
        spy_close = spy['Close'].iloc[-1] if not spy.empty else 0
        spy_ma200 = spy['Close'].rolling(window=200).mean().iloc[-1] if len(spy) >= 200 else spy_close
        
        csi_dist = ((csi_close / csi_ma200) - 1) * 100 if csi_ma200 > 0 else 0
        spy_dist = ((spy_close / spy_ma200) - 1) * 100 if spy_ma200 > 0 else 0
        
        csi_trend = "BULLISH" if csi_dist >= 0 else "BEARISH"
        csi_color = "#22c55e" if csi_dist >= 0 else "#ef4444"
        
        spy_trend = "BULLISH" if spy_dist >= 0 else "BEARISH"
        spy_color = "#22c55e" if spy_dist >= 0 else "#ef4444"
        
        action_csi = "HOLD" if csi_trend == "BULLISH" else "LIQUIDATE"
        weight_csi = "15%" if csi_trend == "BULLISH" else "0%"
        
        trigger = "TRIGGERED (A-SHARE)" if csi_trend == "BEARISH" else "SAFE"
        
    except Exception as e:
        print(f"Momentum error: {e}")
        csi_dist, spy_dist = 0, 0
        csi_trend, spy_trend = "UNKNOWN", "UNKNOWN"
        csi_color, spy_color = "#94a3b8", "#94a3b8"
        action_csi, weight_csi = "HOLD", "15%"
        trigger = "ERROR"
    quality = _data_quality("degraded", "momentum_data_unavailable") if trigger == "ERROR" else _data_quality()

    return {
        "id": "absolute_momentum",
        "name": "跨市场绝对动量防线",
        "name_en": "ABSOLUTE MOMENTUM",
        "status": "active",
        "signal": f"A-SHARE {'CAUTION' if csi_trend == 'BEARISH' else 'BULLISH'}",
        "color": "#f59e0b",
        "model_mode": "live_with_placeholder_theme",
        "tradeable": trigger != "ERROR",
        "data_quality": quality,
        "description": "200-day SMA trend filter. Liquidates assets in structural bear markets.",
        "details": [
            {"label": "CSI 300 Trend", "value": f"{csi_trend} ({csi_dist:+.1f}% vs 200MA)", "color": csi_color},
            {"label": "SP500 Trend", "value": f"{spy_trend} ({spy_dist:+.1f}% vs 200MA)", "color": spy_color},
            {"label": "AI Theme Trend", "value": "PLACEHOLDER (model inactive)", "color": "#94a3b8"},
            {"label": "Circuit Breaker", "value": trigger}
        ],
        "holdings": [
            {"symbol": "159601.SZ", "name": "A50ETF", "action": action_csi, "weight": weight_csi},
            {"symbol": "159819.SZ", "name": "人工智能ETF", "action": "HOLD", "weight": "15%"}
        ]
    }

def compute_beta_hedging():
    return {
        "id": "beta_hedging",
        "name": "动态贝塔中性化对冲",
        "name_en": "DYNAMIC BETA-HEDGING",
        "status": "standby",
        "signal": "PLACEHOLDER - NOT TRADEABLE",
        "color": "#10b981",
        "model_mode": "placeholder",
        "tradeable": False,
        "data_quality": _data_quality("degraded", "beta_hedging_model_not_connected", "placeholder"),
        "description": "Shorts Broad A-share ETF to isolate pure policy alpha of 15th FYP.",
        "details": [
            {"label": "Systemic Risk Level", "value": "PLACEHOLDER"},
            {"label": "Thematic Beta", "value": "PLACEHOLDER"},
            {"label": "Hedge Ratio", "value": "0.0%"},
            {"label": "Alpha Capture", "value": "NOT LIVE", "color": "#94a3b8"}
        ],
        "holdings": [
            {"symbol": "510300.SH", "name": "IF Index Futures", "action": "NEUTRAL", "weight": "0%"}
        ]
    }

def compute_gold_hedging():
    try:
        from core.data_providers import get_vix_history
        vix = get_vix_history(10)
        vix_current = float(vix.iloc[-1]) if not vix.empty else 15.0
        
        gold = get_symbol_data("518880.SH", years=1)
        if not gold.empty:
            gold_close = gold['Close'].iloc[-1]
            gold_ma60 = gold['Close'].rolling(window=60).mean().iloc[-1] if len(gold) >= 60 else gold_close
            trend_dist = ((gold_close / gold_ma60) - 1) * 100 if gold_ma60 > 0 else 0
            gold_trend = "BULLISH" if trend_dist > 0 else "BEARISH"
        else:
            gold_trend = "UNKNOWN"
            trend_dist = 0
            
        # Decision Logic: VIX spike or Gold upward trend
        trigger_vix = vix_current > 25.0
        signal = "BULLISH ON GOLD" if trigger_vix or gold_trend == "BULLISH" else "NEUTRAL ON GOLD"
        color = "#eab308" if signal == "BULLISH ON GOLD" else "#94a3b8"
        action = "BUY" if signal == "BULLISH ON GOLD" else "HOLD"
        weight = "15%" if signal == "BULLISH ON GOLD" else "0%"
        status = "active"
        quality = _data_quality()
        
    except Exception as e:
        print(f"Gold hedging error: {e}")
        vix_current = 0
        gold_trend = "ERROR"
        trend_dist = 0
        signal = "NO_SIGNAL"
        color = "#94a3b8"
        action = "HOLD"
        weight = "0%"
        status = "degraded"
        quality = _data_quality("degraded", str(e))

    return {
        "id": "gold_hedging",
        "name": "黄金避险择时引擎",
        "name_en": "GOLD SAFE-HAVEN TIMING",
        "status": status,
        "signal": signal,
        "color": color,
        "model_mode": "live" if status == "active" else "degraded",
        "tradeable": status == "active",
        "data_quality": quality,
        "description": "Monitors systemic panic (VIX) and monetary cycles to dynamically allocate to Gold.",
        "details": [
            {"label": "VIX Panic Index", "value": f"{vix_current:.1f}", "color": "#ef4444" if vix_current > 25 else "#22c55e"},
            {"label": "Gold Trend (60MA)", "value": f"{gold_trend} ({trend_dist:+.1f}%)", "color": "#eab308" if gold_trend == "BULLISH" else "#94a3b8"},
            {"label": "Systemic Hedge Need", "value": "HIGH" if vix_current > 25 else "LOW", "color": "#ef4444" if vix_current > 25 else "#22c55e"},
            {"label": "Allocation Target", "value": weight, "color": color}
        ],
        "holdings": [
            {"symbol": "518880.SH", "name": "黄金ETF", "action": action, "weight": weight}
        ]
    }

def get_strategy_dashboard() -> dict:
    """Aggregates all strategy data for the frontend dashboard."""
    policy = get_strategy_policy()
    backtest = get_real_backtest()
    engines = [
        compute_global_risk_parity(),
        build_barbell_allocation(),
        analyze_absolute_momentum(),
        compute_beta_hedging(),
        compute_gold_hedging()
    ]
    degraded_components = []
    if backtest.get("status") != "ok":
        degraded_components.append("backtest")
    degraded_components.extend(
        engine.get("id", "unknown_engine")
        for engine in engines
        if engine.get("data_quality", {}).get("status") != "ok"
    )
    dashboard_quality = _data_quality(
        status="degraded" if degraded_components else "ok",
        degraded_reason=";".join(degraded_components) if degraded_components else None,
        source="strategy_factory",
    )
    return {
        "status": "degraded" if degraded_components else "ok",
        "timestamp": int(time.time()),
        "strategy_policy": policy,
        "strategy_policy_hash": policy["strategy_policy_hash"],
        "data_quality": dashboard_quality,
        "universe": ETF_UNIVERSE,
        "backtest": backtest,
        "engines": engines
    }
