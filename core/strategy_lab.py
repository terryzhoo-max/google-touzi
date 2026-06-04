import time
import hashlib
import json
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.backtest import get_symbol_data
from core.db_layer import init_db
from core.portfolio_book import build_portfolio_snapshot, load_portfolio_positions

# Strategy Configuration (Config-driven)
STRATEGY_POLICY_VERSION = "strategy_factory_policy_v1"
STRATEGY_CONFIG = {
    "barbell_weights": {
        "513500.SH": 0.40,  # SP500
        "510880.SH": 0.30,  # Dividend
        "510300.SH": 0.15,  # CSI300
        "512760.SH": 0.15   # Chip
    },
    "friction_daily": 0.00002,
    "barbell": {
        "rebalance_threshold": 0.03,
        "max_single_trade_weight": 0.10,
        "max_total_trade_weight": 0.20,
        "satellite_cap": 0.15,
    },
    "risk_parity": {
        "symbols": ["510300.SH", "513500.SH"],
        "policy_weights": {"510300.SH": 0.50, "513500.SH": 0.50},
        "risk_budgets": {"510300.SH": 0.50, "513500.SH": 0.50},
        "weight_bounds": {"510300.SH": [0.30, 0.65], "513500.SH": [0.20, 0.60]},
        "rebalance_threshold": 0.03,
        "max_single_trade_weight": 0.10,
        "vol_windows": {"short": 30, "medium": 60, "long": 120},
    },
    "absolute_momentum": {
        "market_symbols": {"a_share": "510300.SH", "overseas": "513500.SH"},
        "target_symbols": {"a_share": "159601.SZ", "theme": "159819.SZ"},
        "policy_weights": {"159601.SZ": 0.15, "159819.SZ": 0.15},
        "current_weights": {"159601.SZ": 0.15, "159819.SZ": 0.15},
        "required_history_days": 220,
        "trend_window_days": 200,
        "entry_buffer_pct": 2.0,
        "exit_buffer_pct": -2.0,
        "confirm_days": 3,
        "recovery_confirm_days": 5,
        "risk_off_equity_multiplier": 0.50,
        "theme_model_connected": False,
    },
    "beta_hedging": {
        "theme_weights": {
            "512760.SH": 0.40,
            "159819.SZ": 0.30,
            "159825.SZ": 0.15,
            "512660.SH": 0.15,
        },
        "benchmark_symbol": "510300.SH",
        "theme_target_weight": 0.30,
        "windows": {"short": 30, "primary": 60, "long": 120},
        "max_hedge_ratio": 0.60,
        "min_observations": 120,
        "paper_observation_days_required": 40,
    },
    "gold_hedging": {
        "symbol": "518880.SH",
        "trend_window": 60,
        "min_price_points": 60,
        "rebalance_threshold": 0.02,
        "max_single_trade_weight": 0.03,
        "score_bands": [
            {"min_score": 85, "target_weight": 0.15, "signal": "EXTREME_GOLD_HEDGE", "confidence": "HIGH"},
            {"min_score": 70, "target_weight": 0.12, "signal": "BULLISH_ON_GOLD", "confidence": "HIGH"},
            {"min_score": 55, "target_weight": 0.08, "signal": "BULLISH_ON_GOLD", "confidence": "MEDIUM"},
            {"min_score": 40, "target_weight": 0.03, "signal": "WATCH_GOLD_HEDGE", "confidence": "MEDIUM"},
            {"min_score": 0, "target_weight": 0.00, "signal": "NEUTRAL_ON_GOLD", "confidence": "LOW"},
        ],
    },
}


def _stable_hash(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_strategy_policy() -> dict:
    payload = {
        "version": STRATEGY_POLICY_VERSION,
        "barbell_weights": STRATEGY_CONFIG["barbell_weights"],
        "barbell": STRATEGY_CONFIG["barbell"],
        "friction_daily": STRATEGY_CONFIG["friction_daily"],
        "risk_parity": STRATEGY_CONFIG["risk_parity"],
        "absolute_momentum": STRATEGY_CONFIG["absolute_momentum"],
        "backtest_window_years": 1,
        "benchmark": {"510300.SH": 0.60, "513500.SH": 0.40},
        "risk_parity_window_days": 30,
        "momentum_window_days": 200,
        "gold_trend_window_days": 60,
        "vix_panic_threshold": 25.0,
        "beta_hedging": STRATEGY_CONFIG["beta_hedging"],
        "gold_hedging": STRATEGY_CONFIG["gold_hedging"],
    }
    payload["strategy_policy_hash"] = _stable_hash(payload)
    return payload


def _data_quality(
    status: str = "ok",
    degraded_reason: str | None = None,
    source: str = "market_data_cache",
    **extra,
) -> dict:
    payload = {
        "status": status,
        "source": source,
        "degraded_reason": degraded_reason,
    }
    payload.update(extra)
    return payload

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

STRATEGY_SYMBOL_ALIASES = {
    "510300.SH": ["510300"],
    "513500.SH": ["513500"],
    "510880.SH": ["510880", "512890", "159545"],
    "512760.SH": ["512760", "159995"],
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

def _compute_global_risk_parity_legacy():
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
    policy = get_strategy_policy()
    weights = {sym: round(float(weight), 6) for sym, weight in STRATEGY_CONFIG["barbell_weights"].items()}
    symbols = list(weights)
    barbell_policy = STRATEGY_CONFIG["barbell"]
    current_weights, current_weight_meta = _resolve_current_strategy_weights(symbols, weights)
    if current_weight_meta["fallback_used"]:
        decision_state = "blocked"
        execution = [
            {
                "symbol": sym,
                "current_weight": round(float(current_weights.get(sym, 0.0)), 6),
                "target_weight": weights[sym],
                "drift_weight": 0.0,
                "trade_weight": 0.0,
                "action": "HOLD",
            }
            for sym in symbols
        ]
        status = "degraded"
        tradeable = False
        quality = _data_quality(
            "degraded",
            current_weight_meta.get("reason") or "current_portfolio_weights_unavailable",
            "portfolio_book",
            fallback_used=True,
            current_weights_source=current_weight_meta["source"],
        )
    else:
        decision_state, execution = _execution_plan(
            weights,
            current_weights,
            float(barbell_policy["rebalance_threshold"]),
            float(barbell_policy["max_single_trade_weight"]),
            float(barbell_policy["max_total_trade_weight"]),
        )
        status = "active"
        tradeable = True
        quality = _data_quality(
            source="strategy_policy+portfolio_book",
            fallback_used=False,
            current_weights_source=current_weight_meta["source"],
            total_market_value=current_weight_meta.get("total_market_value"),
            symbol_aliases_applied=current_weight_meta.get("symbol_aliases_applied", False),
        )

    core_weight = (
        weights.get("513500.SH", 0.0) +
        weights.get("510880.SH", 0.0) +
        weights.get("510300.SH", 0.0)
    )
    satellite_weight = weights.get("512760.SH", 0.0)
    symbol_names = {
        asset["symbol"]: asset["name"]
        for assets in ETF_UNIVERSE.values()
        for asset in assets
    }
    execution_by_symbol = {item["symbol"]: item for item in execution}
    holdings = []
    for sym in symbols:
        item = execution_by_symbol[sym]
        target_weight = float(item["target_weight"])
        current_weight = float(item["current_weight"])
        drift_weight = float(item["drift_weight"])
        trade_weight = float(item["trade_weight"])
        holdings.append({
            "symbol": sym,
            "name": symbol_names.get(sym, sym),
            "action": item["action"],
            "weight": f"{int(round(target_weight * 100))}%",
            "target_weight": round(target_weight, 6),
            "current_weight": round(current_weight, 6),
            "drift_weight": round(drift_weight, 6),
            "trade_weight": round(trade_weight, 6),
        })
    
    return {
        "id": "barbell_allocation",
        "name": "核心-卫星哑铃配置",
        "name_en": "BARBELL ALLOCATION",
        "status": status,
        "signal": "REVIEW REQUIRED" if not tradeable else "DEFENSIVE TILT",
        "color": "#a855f7",
        "model_mode": "policy_static",
        "tradeable": tradeable,
        "decision_state": decision_state,
        "policy_version": policy["version"],
        "strategy_policy_hash": policy["strategy_policy_hash"],
        "target_weights": weights,
        "current_weights": current_weights,
        "execution_plan": execution,
        "risk_controls": {
            "rebalance_threshold": float(barbell_policy["rebalance_threshold"]),
            "max_single_trade_weight": float(barbell_policy["max_single_trade_weight"]),
            "max_total_trade_weight": float(barbell_policy["max_total_trade_weight"]),
            "satellite_cap": float(barbell_policy["satellite_cap"]),
        },
        "data_quality": quality,
        "description": "Policy barbell allocation using configured broad, dividend, and 15th FYP theme weights.",
        "details": [
            {"label": "Core Allocation", "value": f"{core_weight*100:.1f}%"},
            {"label": "Satellite Allocation", "value": f"{satellite_weight*100:.1f}%"},
            {"label": "Execution State", "value": decision_state},
            {"label": "Max Single Trade", "value": f"{float(barbell_policy['max_single_trade_weight']) * 100:.1f}%"},
            {"label": "Max Total Trade", "value": f"{float(barbell_policy['max_total_trade_weight']) * 100:.1f}%"},
            {"label": "Dividend Yield (Core)", "value": "DATA REQUIRED", "color": "#f59e0b"},
            {"label": "Theme Beta (Satellite)", "value": "DATA REQUIRED", "color": "#f59e0b"}
        ],
        "holdings": holdings
    }

def _analyze_absolute_momentum_legacy():
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


def _close_series_for_momentum(frame: pd.DataFrame, symbol: str, required_days: int) -> pd.Series:
    if frame is None or "Close" not in frame:
        raise ValueError(f"missing close series for {symbol}")
    close = frame["Close"].astype(float).dropna()
    if len(close) < required_days:
        raise ValueError(f"insufficient market history for {symbol}: {len(close)} < {required_days}")
    return close


def _momentum_trend_snapshot(close: pd.Series, policy: dict) -> dict:
    window = int(policy["trend_window_days"])
    entry_buffer = float(policy["entry_buffer_pct"])
    exit_buffer = float(policy["exit_buffer_pct"])
    confirm_days = int(policy["confirm_days"])
    recovery_days = int(policy["recovery_confirm_days"])
    ma = close.rolling(window=window).mean()
    distance = ((close / ma) - 1.0) * 100.0
    valid_distance = distance.dropna()
    if len(valid_distance) < recovery_days:
        raise ValueError("insufficient rolling trend observations")

    latest_distance = float(valid_distance.iloc[-1])
    recent_exit = valid_distance.tail(confirm_days)
    recent_entry = valid_distance.tail(recovery_days)
    if bool((recent_exit <= exit_buffer).all()):
        trend = "BEARISH"
        regime = "bearish_confirmed"
        color = "#ef4444"
    elif bool((recent_entry >= entry_buffer).all()):
        trend = "BULLISH"
        regime = "bullish_confirmed"
        color = "#22c55e"
    else:
        trend = "NEUTRAL"
        regime = "transition"
        color = "#f59e0b"

    return {
        "trend": trend,
        "regime": regime,
        "distance_pct": latest_distance,
        "color": color,
        "as_of": str(close.index[-1]) if len(close.index) else None,
        "sample_days": int(len(close)),
    }


def _blocked_momentum_result(policy: dict, reason: str) -> dict:
    target_symbols = policy["target_symbols"]
    required_days = int(policy["required_history_days"])
    current_weights = dict(policy["current_weights"])
    execution = [
        {
            "symbol": target_symbols["a_share"],
            "current_weight": round(float(current_weights.get(target_symbols["a_share"], 0.0)), 6),
            "target_weight": 0.0,
            "drift_weight": 0.0,
            "trade_weight": 0.0,
            "action": "HOLD",
            "blocking_reason": reason,
        },
        {
            "symbol": target_symbols["theme"],
            "current_weight": round(float(current_weights.get(target_symbols["theme"], 0.0)), 6),
            "target_weight": 0.0,
            "drift_weight": 0.0,
            "trade_weight": 0.0,
            "action": "BLOCKED",
            "blocking_reason": "theme_model_not_connected",
        },
    ]
    return {
        "id": "absolute_momentum",
        "name": "跨市场绝对动量防线",
        "name_en": "ABSOLUTE MOMENTUM",
        "status": "degraded",
        "signal": "NO_SIGNAL",
        "color": "#f59e0b",
        "model_mode": "degraded",
        "tradeable": False,
        "decision_state": "blocked",
        "regime_state": "unavailable",
        "blocking_reason": reason,
        "target_weights": {target_symbols["a_share"]: 0.0, target_symbols["theme"]: 0.0},
        "current_weights": current_weights,
        "risk_action": {"equity_budget_multiplier": 0.0, "theme_cap_pct": 0.0, "cash_buffer_pct": 100.0},
        "execution_plan": execution,
        "data_quality": _data_quality(
            "degraded",
            reason,
            fallback_used=True,
            required_history_days=required_days,
        ),
        "description": "200-day SMA trend filter. Liquidates assets in structural bear markets.",
        "details": [
            {"label": "CSI 300 Trend", "value": "UNKNOWN", "color": "#94a3b8"},
            {"label": "SP500 Trend", "value": "UNKNOWN", "color": "#94a3b8"},
            {"label": "AI Theme Trend", "value": "PLACEHOLDER (model inactive)", "color": "#94a3b8"},
            {"label": "Circuit Breaker", "value": "ERROR"},
        ],
        "holdings": [
            {"symbol": target_symbols["a_share"], "name": "A50ETF", "action": "HOLD", "weight": "0%"},
            {"symbol": target_symbols["theme"], "name": "人工智能ETF", "action": "BLOCKED", "weight": "0%"},
        ],
    }


def _momentum_execution_plan(policy: dict, target_weights: dict[str, float], theme_blocked: bool) -> list[dict]:
    current_weights = dict(policy["current_weights"])
    plan = []
    for symbol, target_weight in target_weights.items():
        current_weight = float(current_weights.get(symbol, 0.0))
        drift = float(target_weight) - current_weight
        action = "HOLD"
        trade_weight = drift
        blocking_reason = None
        if theme_blocked and symbol == policy["target_symbols"]["theme"]:
            action = "BLOCKED"
            trade_weight = 0.0
            blocking_reason = "theme_model_not_connected"
        elif target_weight <= 0.0 and current_weight > 0.0:
            action = "LIQUIDATE"
        elif abs(drift) >= 0.01:
            action = "BUY" if drift > 0.0 else "REDUCE"
        else:
            trade_weight = 0.0
        item = {
            "symbol": symbol,
            "current_weight": round(current_weight, 6),
            "target_weight": round(float(target_weight), 6),
            "drift_weight": round(drift, 6),
            "trade_weight": round(float(trade_weight), 6),
            "action": action,
        }
        if blocking_reason:
            item["blocking_reason"] = blocking_reason
        plan.append(item)
    return plan


def analyze_absolute_momentum():
    policy = STRATEGY_CONFIG["absolute_momentum"]
    market_symbols = policy["market_symbols"]
    target_symbols = policy["target_symbols"]
    required_days = int(policy["required_history_days"])

    try:
        csi_close = _close_series_for_momentum(
            get_symbol_data(market_symbols["a_share"], years=2),
            market_symbols["a_share"],
            required_days,
        )
        spy_close = _close_series_for_momentum(
            get_symbol_data(market_symbols["overseas"], years=2),
            market_symbols["overseas"],
            required_days,
        )
        csi_snapshot = _momentum_trend_snapshot(csi_close, policy)
        spy_snapshot = _momentum_trend_snapshot(spy_close, policy)
    except Exception as e:
        print(f"Momentum error: {e}")
        return _blocked_momentum_result(policy, "insufficient_market_history")

    csi_trend = csi_snapshot["trend"]
    spy_trend = spy_snapshot["trend"]
    csi_dist = csi_snapshot["distance_pct"]
    spy_dist = spy_snapshot["distance_pct"]
    trigger = "TRIGGERED (A-SHARE)" if csi_snapshot["regime"] == "bearish_confirmed" else "SAFE"
    decision_state = "risk_off" if trigger != "SAFE" else "risk_on"
    target_a_share = 0.0 if decision_state == "risk_off" else float(policy["policy_weights"][target_symbols["a_share"]])
    theme_connected = bool(policy["theme_model_connected"])
    target_theme = float(policy["policy_weights"][target_symbols["theme"]]) if theme_connected and decision_state == "risk_on" else 0.0
    target_weights = {target_symbols["a_share"]: round(target_a_share, 6), target_symbols["theme"]: round(target_theme, 6)}
    risk_multiplier = float(policy["risk_off_equity_multiplier"]) if decision_state == "risk_off" else 1.0
    theme_cap_pct = target_theme * 100.0 if theme_connected else 0.0
    execution = _momentum_execution_plan(policy, target_weights, theme_blocked=not theme_connected)
    quality = _data_quality(
        as_of=csi_snapshot["as_of"],
        fallback_used=False,
        required_history_days=required_days,
        sample_days=min(csi_snapshot["sample_days"], spy_snapshot["sample_days"]),
    )

    return {
        "id": "absolute_momentum",
        "name": "跨市场绝对动量防线",
        "name_en": "ABSOLUTE MOMENTUM",
        "status": "active",
        "signal": f"A-SHARE {'CAUTION' if decision_state == 'risk_off' else 'BULLISH'}",
        "color": "#f59e0b",
        "model_mode": "live_with_placeholder_theme",
        "tradeable": True,
        "decision_state": decision_state,
        "regime_state": csi_snapshot["regime"],
        "blocking_reason": None,
        "target_weights": target_weights,
        "current_weights": dict(policy["current_weights"]),
        "risk_action": {
            "equity_budget_multiplier": risk_multiplier,
            "theme_cap_pct": round(theme_cap_pct, 2),
            "cash_buffer_pct": 0.0 if decision_state == "risk_on" else 50.0,
        },
        "execution_plan": execution,
        "data_quality": quality,
        "description": "200-day SMA trend filter. Liquidates assets in structural bear markets.",
        "details": [
            {"label": "CSI 300 Trend", "value": f"{csi_trend} ({csi_dist:+.1f}% vs 200MA)", "color": csi_snapshot["color"]},
            {"label": "SP500 Trend", "value": f"{spy_trend} ({spy_dist:+.1f}% vs 200MA)", "color": spy_snapshot["color"]},
            {"label": "AI Theme Trend", "value": "PLACEHOLDER (model inactive)", "color": "#94a3b8"},
            {"label": "Circuit Breaker", "value": trigger},
        ],
        "holdings": [
            {"symbol": target_symbols["a_share"], "name": "A50ETF", "action": execution[0]["action"], "weight": f"{int(round(target_a_share*100))}%"},
            {"symbol": target_symbols["theme"], "name": "人工智能ETF", "action": execution[1]["action"], "weight": f"{int(round(target_theme*100))}%"},
        ],
    }


def _legacy_compute_beta_hedging_placeholder():
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


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _symbol_returns(symbol: str, years: int = 1) -> pd.Series:
    df = get_symbol_data(symbol, years=years)
    if df is None or df.empty or "Close" not in df:
        raise ValueError(f"missing close series for {symbol}")
    close = pd.to_numeric(df["Close"], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if len(close) < 2:
        raise ValueError(f"insufficient close series for {symbol}")
    return close.pct_change().dropna().rename(symbol)


def _weighted_theme_returns(theme_weights: dict[str, float]) -> pd.Series:
    returns = [_symbol_returns(symbol) for symbol in theme_weights]
    aligned = pd.concat(returns, axis=1, join="inner").dropna()
    if aligned.empty:
        raise ValueError("theme returns unavailable")
    weights = pd.Series(theme_weights, dtype=float)
    weights = weights / weights.sum()
    return aligned.mul(weights, axis=1).sum(axis=1).rename("theme")


def _beta_stats(theme_returns: pd.Series, benchmark_returns: pd.Series, window: int) -> dict:
    aligned = pd.concat(
        [theme_returns.rename("theme"), benchmark_returns.rename("benchmark")],
        axis=1,
        join="inner",
    ).dropna()
    if len(aligned) < window:
        raise ValueError("insufficient beta observations")
    sample = aligned.tail(window)
    benchmark_var = float(sample["benchmark"].var())
    if benchmark_var <= 1e-12:
        raise ValueError("benchmark variance too low")
    covariance = float(sample["theme"].cov(sample["benchmark"]))
    beta = covariance / benchmark_var
    correlation = float(sample["theme"].corr(sample["benchmark"]))
    r_squared = 0.0 if np.isnan(correlation) else correlation * correlation
    residual = sample["theme"] - (beta * sample["benchmark"])
    return {
        "beta": beta,
        "r_squared": r_squared,
        "residual_volatility": float(residual.std() * np.sqrt(252)),
        "observations": int(len(sample)),
    }


def _downside_beta(theme_returns: pd.Series, benchmark_returns: pd.Series, window: int) -> float:
    aligned = pd.concat(
        [theme_returns.rename("theme"), benchmark_returns.rename("benchmark")],
        axis=1,
        join="inner",
    ).dropna().tail(window)
    downside = aligned[aligned["benchmark"] < 0]
    if len(downside) < 20:
        return np.nan
    benchmark_var = float(downside["benchmark"].var())
    if benchmark_var <= 1e-12:
        return np.nan
    return float(downside["theme"].cov(downside["benchmark"]) / benchmark_var)


def compute_beta_hedging():
    config = STRATEGY_CONFIG["beta_hedging"]
    windows = config["windows"]
    benchmark_symbol = config["benchmark_symbol"]
    target_theme_weight = float(config["theme_target_weight"])

    try:
        theme_returns = _weighted_theme_returns(config["theme_weights"])
        benchmark_returns = _symbol_returns(benchmark_symbol)
        aligned_count = len(pd.concat([theme_returns, benchmark_returns], axis=1, join="inner").dropna())
        if aligned_count < int(config["min_observations"]):
            raise ValueError("insufficient beta observations")

        short_stats = _beta_stats(theme_returns, benchmark_returns, int(windows["short"]))
        primary_stats = _beta_stats(theme_returns, benchmark_returns, int(windows["primary"]))
        long_stats = _beta_stats(theme_returns, benchmark_returns, int(windows["long"]))
        downside = _downside_beta(theme_returns, benchmark_returns, int(windows["long"]))
        stress_beta = max(
            primary_stats["beta"],
            long_stats["beta"],
            downside if not np.isnan(downside) else primary_stats["beta"],
        )
        hedge_ratio = _clamp(
            max(stress_beta, 0.0) * target_theme_weight,
            0.0,
            float(config["max_hedge_ratio"]),
        )
        beta_exposure_before = max(primary_stats["beta"], 0.0) * target_theme_weight
        net_beta_after_hedge = max(beta_exposure_before - hedge_ratio, 0.0)
        beta_drift = abs(short_stats["beta"] - long_stats["beta"])
        confidence = _clamp(
            0.25 + primary_stats["r_squared"] * 0.55 - min(beta_drift, 1.0) * 0.20,
            0.0,
            1.0,
        )
        risk_state = "high_beta_watch" if net_beta_after_hedge > 0.10 else "paper_observe"
        blockers = ["paper_mode_not_approved_for_live", "execution_not_enabled"]
        quality = _data_quality(status="ok", source="paper_beta_engine", observations=aligned_count)
        status = "standby"
        mode = "paper"
        signal = "PAPER HEDGE - NOT TRADEABLE"
        details = [
            {"label": "Systemic Risk Level", "value": risk_state.upper(), "color": "#f59e0b" if risk_state == "high_beta_watch" else "#10b981"},
            {"label": "Thematic Beta", "value": f"{primary_stats['beta']:.2f}"},
            {"label": "Downside Beta", "value": "N/A" if np.isnan(downside) else f"{downside:.2f}"},
            {"label": "Hedge Ratio", "value": f"{hedge_ratio*100:.1f}%"},
            {"label": "Net Beta", "value": f"{net_beta_after_hedge:.2f}"},
            {"label": "Model Confidence", "value": f"{confidence*100:.0f}%"},
            {"label": "Alpha Capture", "value": "PAPER ONLY", "color": "#94a3b8"},
        ]
        target_exposure = {
            "theme_weight": round(target_theme_weight, 4),
            "beta_before_hedge": round(beta_exposure_before, 4),
            "hedge_ratio": round(hedge_ratio, 4),
            "net_beta_after_hedge": round(net_beta_after_hedge, 4),
            "hedge_instrument": benchmark_symbol,
            "rebalance_band": "8%",
        }
        risk_metrics = {
            "short_beta": round(short_stats["beta"], 4),
            "primary_beta": round(primary_stats["beta"], 4),
            "long_beta": round(long_stats["beta"], 4),
            "downside_beta": None if np.isnan(downside) else round(downside, 4),
            "r_squared": round(primary_stats["r_squared"], 4),
            "residual_volatility_pct": round(primary_stats["residual_volatility"] * 100, 2),
            "model_confidence": round(confidence, 4),
            "observations": aligned_count,
            "paper_observation_days_required": int(config["paper_observation_days_required"]),
        }
    except Exception as exc:
        hedge_ratio = 0.0
        risk_state = "blocked"
        blockers = ["market_source_unavailable", "beta_model_not_approved_for_live"]
        quality = _data_quality(
            "degraded",
            "beta_hedging_market_data_unavailable",
            "paper_beta_engine",
            error=str(exc),
        )
        status = "degraded"
        mode = "blocked"
        signal = "BETA HEDGE BLOCKED"
        target_exposure = {
            "theme_weight": round(target_theme_weight, 4),
            "beta_before_hedge": None,
            "hedge_ratio": 0.0,
            "net_beta_after_hedge": None,
            "hedge_instrument": benchmark_symbol,
            "rebalance_band": "8%",
        }
        risk_metrics = {
            "short_beta": None,
            "primary_beta": None,
            "long_beta": None,
            "downside_beta": None,
            "r_squared": None,
            "residual_volatility_pct": None,
            "model_confidence": 0.0,
            "observations": 0,
            "paper_observation_days_required": int(config["paper_observation_days_required"]),
        }
        details = [
            {"label": "Systemic Risk Level", "value": "BLOCKED", "color": "#ef4444"},
            {"label": "Thematic Beta", "value": "UNAVAILABLE"},
            {"label": "Downside Beta", "value": "UNAVAILABLE"},
            {"label": "Hedge Ratio", "value": "0.0%"},
            {"label": "Net Beta", "value": "UNAVAILABLE"},
            {"label": "Model Confidence", "value": "0%"},
            {"label": "Alpha Capture", "value": "NOT LIVE", "color": "#94a3b8"},
        ]

    return {
        "id": "beta_hedging",
        "name": "动态贝塔中性化对冲",
        "name_en": "DYNAMIC BETA-HEDGING",
        "status": status,
        "signal": signal,
        "color": "#10b981" if status == "standby" else "#ef4444",
        "model_mode": mode,
        "tradeable": False,
        "decision_state": "paper_blocked" if mode == "paper" else "blocked",
        "risk_state": risk_state,
        "blockers": blockers,
        "target_exposure": target_exposure,
        "risk_metrics": risk_metrics,
        "data_quality": quality,
        "description": "Paper beta hedge observes broad-index exposure before any live approval.",
        "details": details,
        "holdings": [
            {
                "symbol": benchmark_symbol,
                "name": "CSI 300 ETF Hedge Leg",
                "action": "PAPER_HEDGE" if mode == "paper" else "NEUTRAL",
                "weight": f"{hedge_ratio*100:.1f}%",
            }
        ],
    }


def _clip_score(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 2)


def _select_gold_band(score: float, bands: list[dict]) -> dict:
    for band in sorted(bands, key=lambda item: item["min_score"], reverse=True):
        if score >= float(band["min_score"]):
            return dict(band)
    return dict(bands[-1])


def _format_weight(weight: float) -> str:
    return f"{int(round(float(weight) * 100))}%"


def compute_gold_hedging():
    policy = STRATEGY_CONFIG["gold_hedging"]
    symbol = policy["symbol"]
    current_weights, current_weight_meta = _resolve_current_strategy_weights(symbols=[symbol], fallback_weights={symbol: 0.0})
    current_weight = float(current_weights.get(symbol, 0.0))

    try:
        from core.data_providers import get_vix_history
        vix = get_vix_history(10)
        if vix is None or len(vix) == 0:
            raise ValueError("vix history unavailable")
        vix_series = pd.Series(vix).dropna().astype(float)
        if vix_series.empty:
            raise ValueError("vix history unavailable")
        vix_current = float(vix_series.iloc[-1])
        vix_previous = float(vix_series.iloc[0]) if len(vix_series) > 1 else vix_current
        vix_change = vix_current - vix_previous

        gold = get_symbol_data(symbol, years=1)
        if gold is None or "Close" not in gold or len(gold) < int(policy["min_price_points"]):
            raise ValueError(f"insufficient close series for {symbol}")
        close = gold["Close"].dropna().astype(float)
        if len(close) < int(policy["min_price_points"]):
            raise ValueError(f"insufficient close series for {symbol}")

        trend_window = int(policy["trend_window"])
        gold_close = float(close.iloc[-1])
        gold_ma60 = float(close.rolling(window=trend_window).mean().iloc[-1])
        if gold_ma60 <= 0:
            raise ValueError("invalid gold moving average")
        trend_dist = ((gold_close / gold_ma60) - 1.0) * 100.0
        gold_trend = "BULLISH" if trend_dist > 0 else "BEARISH"
        gold_vol = float(close.pct_change().dropna().tail(20).std() * np.sqrt(252.0) * 100.0)

        panic_score = _clip_score(((vix_current - 12.0) / 23.0) * 70.0 + max(0.0, vix_change) * 6.0)
        trend_score = _clip_score(50.0 + trend_dist * 5.0)
        monetary_score = 50.0
        hedge_score = _clip_score(35.0 + (panic_score * 0.25) + (trend_score * 0.35) - max(0.0, gold_vol - 25.0))
        liquidity_score = 80.0
        total_score = _clip_score(
            panic_score * 0.30
            + trend_score * 0.25
            + monetary_score * 0.20
            + hedge_score * 0.15
            + liquidity_score * 0.10
        )

        band = _select_gold_band(total_score, policy["score_bands"])
        target_weight = round(float(band["target_weight"]), 6)
        signal = str(band["signal"])
        confidence = str(band["confidence"])
        color = "#ef4444" if signal == "EXTREME_GOLD_HEDGE" else ("#eab308" if target_weight > 0 else "#94a3b8")
        decision_state, execution = _execution_plan(
            {symbol: target_weight},
            {symbol: current_weight},
            float(policy["rebalance_threshold"]),
            float(policy["max_single_trade_weight"]),
        )
        status = "active"
        quality = _data_quality(
            as_of=str(close.index[-1]) if len(close.index) else None,
            fallback_used=current_weight_meta["fallback_used"],
            current_weights_source=current_weight_meta["source"],
            current_weights_reason=current_weight_meta.get("reason"),
        )

        drivers = [
            {"name": "Panic Score", "score": panic_score, "impact": "positive" if panic_score >= 55 else "negative"},
            {"name": "Trend Score", "score": trend_score, "impact": "positive" if trend_score >= 55 else "negative"},
            {"name": "Monetary Score", "score": monetary_score, "impact": "neutral"},
            {"name": "Hedge Effectiveness", "score": hedge_score, "impact": "positive" if hedge_score >= 55 else "neutral"},
            {"name": "Liquidity Score", "score": liquidity_score, "impact": "positive"},
        ]
        guards = [
            {"name": "VIX Data Check", "passed": True},
            {"name": "Gold Close Series Check", "passed": True},
            {"name": "Single-Day Trade Cap", "passed": abs(execution[0]["trade_weight"]) <= float(policy["max_single_trade_weight"])},
        ]

    except Exception as e:
        print(f"Gold hedging error: {e}")
        vix_current = 0.0
        vix_change = 0.0
        trend_dist = 0.0
        gold_vol = 0.0
        gold_trend = "ERROR"
        panic_score = 0.0
        trend_score = 0.0
        monetary_score = 0.0
        hedge_score = 0.0
        liquidity_score = 0.0
        total_score = 0.0
        target_weight = 0.0
        signal = "NO_SIGNAL"
        confidence = "LOW"
        color = "#94a3b8"
        decision_state = "blocked"
        execution = [{
            "symbol": symbol,
            "current_weight": round(current_weight, 6),
            "target_weight": 0.0,
            "drift_weight": 0.0,
            "trade_weight": 0.0,
            "action": "HOLD",
        }]
        status = "degraded"
        quality = _data_quality(
            "degraded",
            str(e),
            fallback_used=False,
            current_weights_source=current_weight_meta["source"],
            current_weights_reason=current_weight_meta.get("reason"),
        )
        drivers = [
            {"name": "Panic Score", "score": 0.0, "impact": "blocked"},
            {"name": "Trend Score", "score": 0.0, "impact": "blocked"},
            {"name": "Hedge Effectiveness", "score": 0.0, "impact": "blocked"},
        ]
        guards = [
            {"name": "VIX Data Check", "passed": "vix" not in str(e).lower()},
            {"name": "Gold Close Series Check", "passed": "close series" not in str(e).lower()},
        ]

    action = execution[0]["action"] if execution else "HOLD"
    return {
        "id": "gold_hedging",
        "name": "黄金避险择时引擎",
        "name_en": "GOLD SAFE-HAVEN TIMING",
        "status": status,
        "signal": signal,
        "color": color,
        "model_mode": "live" if status == "active" else "degraded",
        "tradeable": status == "active",
        "decision_state": decision_state,
        "hedge_score": total_score,
        "confidence": confidence,
        "target_weight": target_weight,
        "current_weight": round(current_weight, 6),
        "rebalance_delta": round(target_weight - current_weight, 6),
        "drivers": drivers,
        "guards": guards,
        "execution_plan": execution,
        "risk_metrics": {
            "vix_current": round(vix_current, 2),
            "vix_change": round(vix_change, 2),
            "gold_trend_distance_pct": round(trend_dist, 2),
            "gold_volatility_pct": round(gold_vol, 2),
        },
        "data_quality": quality,
        "description": "Monitors systemic panic (VIX), gold trend, and execution guards before allocating to Gold.",
        "details": [
            {"label": "Gold Hedge Score", "value": f"{total_score:.0f}/100", "color": color},
            {"label": "VIX Panic Index", "value": f"{vix_current:.1f}", "color": "#ef4444" if vix_current > 25 else "#22c55e"},
            {"label": "VIX 10d Change", "value": f"{vix_change:+.1f}", "color": "#ef4444" if vix_change > 3 else "#94a3b8"},
            {"label": "Gold Trend (60MA)", "value": f"{gold_trend} ({trend_dist:+.1f}%)", "color": "#eab308" if gold_trend == "BULLISH" else "#94a3b8"},
            {"label": "Signal Confidence", "value": confidence, "color": "#22c55e" if confidence == "HIGH" else "#94a3b8"},
            {"label": "Allocation Target", "value": _format_weight(target_weight), "color": color},
        ],
        "holdings": [
            {"symbol": symbol, "name": "黄金ETF", "action": action, "weight": _format_weight(target_weight)}
        ]
    }

def _bounded_two_asset_weights(raw_weights: dict[str, float], bounds: dict[str, list[float]]) -> dict[str, float]:
    symbols = list(raw_weights.keys())
    first, second = symbols
    first_min, first_max = bounds.get(first, [0.0, 1.0])
    second_min, second_max = bounds.get(second, [0.0, 1.0])
    first_weight = max(float(first_min), min(float(first_max), float(raw_weights[first])))
    first_weight = max(1.0 - float(second_max), min(1.0 - float(second_min), first_weight))
    return {first: round(first_weight, 6), second: round(1.0 - first_weight, 6)}


def _blend_covariance(returns: pd.DataFrame, windows: dict[str, int]) -> np.ndarray:
    annualizer = 252.0
    short_cov = returns.tail(int(windows.get("short", 30))).cov().values * annualizer
    medium_cov = returns.tail(int(windows.get("medium", 60))).cov().values * annualizer
    long_cov = returns.tail(int(windows.get("long", 120))).cov().values * annualizer
    cov = (0.30 * short_cov) + (0.50 * medium_cov) + (0.20 * long_cov)
    return np.nan_to_num(cov, nan=0.0, posinf=0.0, neginf=0.0)


def _two_asset_risk_parity_weights(cov: np.ndarray, budgets: dict[str, float], symbols: list[str]) -> dict[str, float]:
    vol = np.sqrt(np.maximum(np.diag(cov), 1e-8))
    b0 = max(0.0, float(budgets.get(symbols[0], 0.5)))
    b1 = max(0.0, float(budgets.get(symbols[1], 0.5)))
    if b0 + b1 <= 0:
        b0 = b1 = 0.5
    b0, b1 = b0 / (b0 + b1), b1 / (b0 + b1)
    inv = np.array([b0 / vol[0], b1 / vol[1]], dtype=float)
    raw = inv / inv.sum() if inv.sum() > 0 else np.array([0.5, 0.5])
    return {symbols[0]: float(raw[0]), symbols[1]: float(raw[1])}


def _risk_contribution(cov: np.ndarray, weights: dict[str, float], symbols: list[str], budgets: dict[str, float]) -> dict:
    w = np.array([weights[sym] for sym in symbols], dtype=float)
    portfolio_vol = float(np.sqrt(np.dot(w.T, np.dot(cov, w))))
    mctr = np.dot(cov, w) / portfolio_vol if portfolio_vol > 0 else np.zeros(len(symbols))
    actr = w * mctr
    total_actr = float(actr.sum())
    actr_pct = actr / total_actr if total_actr > 0 else np.ones(len(symbols)) / len(symbols)
    budget_total = sum(max(0.0, float(budgets.get(sym, 0.0))) for sym in symbols) or 1.0
    details = {}
    for idx, sym in enumerate(symbols):
        details[sym] = {
            "risk_budget_pct": round(max(0.0, float(budgets.get(sym, 0.0))) / budget_total * 100.0, 2),
            "actual_risk_contribution_pct": round(float(actr_pct[idx]) * 100.0, 2),
            "mctr_pct": round(float(mctr[idx]) * 100.0, 4),
            "actr": round(float(actr[idx]), 6),
            "asset_volatility_pct": round(float(np.sqrt(max(cov[idx, idx], 0.0))) * 100.0, 2),
        }
    return {"portfolio_volatility_pct": round(portfolio_vol * 100.0, 4), "risk_contribution": details}


def _execution_plan(
    target_weights: dict[str, float],
    current_weights: dict[str, float],
    threshold: float,
    max_single_trade_weight: float,
    max_total_trade_weight: float | None = None,
) -> tuple[str, list[dict]]:
    plan = []
    has_rebalance = False
    for sym, target in target_weights.items():
        current = float(current_weights.get(sym, 0.0))
        drift = float(target) - current
        trade_weight = max(-max_single_trade_weight, min(max_single_trade_weight, drift))
        if abs(drift) >= threshold:
            action = "BUY" if drift > 0 else "REDUCE"
            has_rebalance = True
        else:
            action = "HOLD"
            trade_weight = 0.0
        plan.append({
            "symbol": sym,
            "current_weight": round(current, 6),
            "target_weight": round(float(target), 6),
            "drift_weight": round(drift, 6),
            "trade_weight": round(trade_weight, 6),
            "action": action,
        })
    if max_total_trade_weight is not None:
        max_total = max(0.0, float(max_total_trade_weight))
        total_trade = sum(abs(float(item["trade_weight"])) for item in plan)
        if max_total > 0 and total_trade > max_total:
            scale = max_total / total_trade
            for item in plan:
                item["trade_weight"] = round(float(item["trade_weight"]) * scale, 6)
    return ("rebalance_required" if has_rebalance else "no_action"), plan


def _symbol_key(symbol: str) -> str:
    return str(symbol or "").strip().upper()


def _resolve_current_strategy_weights(symbols: list[str], fallback_weights: dict[str, float]) -> tuple[dict[str, float], dict]:
    try:
        snapshot = build_portfolio_snapshot(load_portfolio_positions())
    except Exception as exc:
        return dict(fallback_weights), {
            "source": "policy_weights",
            "fallback_used": True,
            "reason": str(exc),
        }

    alias_to_target = {}
    for sym in symbols:
        alias_to_target[_symbol_key(sym)] = sym
        alias_to_target[_symbol_key(sym).split(".")[0]] = sym
        for alias in STRATEGY_SYMBOL_ALIASES.get(sym, []):
            alias_to_target[_symbol_key(alias)] = sym

    current_weights = {sym: 0.0 for sym in symbols}
    aliases_applied = False
    for position in snapshot.get("positions", []):
        raw_symbol = _symbol_key(position["symbol"])
        target_symbol = alias_to_target.get(raw_symbol)
        if not target_symbol:
            continue
        current_weights[target_symbol] += float(position["weight"])
        if raw_symbol != _symbol_key(target_symbol):
            aliases_applied = True

    current_weights = {sym: round(weight, 6) for sym, weight in current_weights.items()}
    return current_weights, {
        "source": "portfolio_book",
        "fallback_used": False,
        "total_market_value": snapshot.get("total_market_value"),
        "symbol_aliases_applied": aliases_applied,
    }


def compute_global_risk_parity():
    policy = STRATEGY_CONFIG["risk_parity"]
    symbols = list(policy["symbols"])
    current_weights, current_weight_meta = _resolve_current_strategy_weights(symbols, dict(policy["policy_weights"]))
    budgets = dict(policy["risk_budgets"])
    bounds = dict(policy["weight_bounds"])
    threshold = float(policy["rebalance_threshold"])
    max_trade = float(policy["max_single_trade_weight"])

    try:
        series = []
        for sym in symbols:
            frame = get_symbol_data(sym, years=1)
            if frame is None or "Close" not in frame or len(frame) < 40:
                raise ValueError(f"insufficient close series for {sym}")
            series.append(frame["Close"].astype(float).rename(sym))

        prices = pd.concat(series, axis=1).dropna()
        returns = prices.pct_change().dropna()
        if len(returns) < 30:
            raise ValueError("insufficient aligned return history")

        cov = _blend_covariance(returns, policy["vol_windows"])
        raw_weights = _two_asset_risk_parity_weights(cov, budgets, symbols)
        target_weights = _bounded_two_asset_weights(raw_weights, bounds)
        risk_metrics = _risk_contribution(cov, target_weights, symbols, budgets)
        decision_state, execution = _execution_plan(target_weights, current_weights, threshold, max_trade)

        w_csi = target_weights["510300.SH"]
        w_spy = target_weights["513500.SH"]
        csi_vol = risk_metrics["risk_contribution"]["510300.SH"]["asset_volatility_pct"] / 100.0
        spy_vol = risk_metrics["risk_contribution"]["513500.SH"]["asset_volatility_pct"] / 100.0
        signal = "OVERWEIGHT OVERSEAS" if w_spy > w_csi else "OVERWEIGHT A-SHARE"
        status = "active"
        quality = _data_quality(
            as_of=str(prices.index[-1]) if len(prices.index) else None,
            fallback_used=current_weight_meta["fallback_used"],
            current_weights_source=current_weight_meta["source"],
            current_weights_reason=current_weight_meta.get("reason"),
        )

    except Exception as e:
        print(f"Risk Parity error: {e}")
        target_weights = {sym: round(float(policy["policy_weights"].get(sym, 1.0 / len(symbols))), 6) for sym in symbols}
        w_csi = target_weights["510300.SH"]
        w_spy = target_weights["513500.SH"]
        csi_vol, spy_vol = 0.0, 0.0
        risk_metrics = {
            "portfolio_volatility_pct": 0.0,
            "risk_contribution": {
                sym: {
                    "risk_budget_pct": round(float(budgets.get(sym, 0.0)) * 100.0, 2),
                    "actual_risk_contribution_pct": 0.0,
                    "mctr_pct": 0.0,
                    "actr": 0.0,
                    "asset_volatility_pct": 0.0,
                }
                for sym in symbols
            },
        }
        decision_state = "blocked"
        execution = [
            {
                "symbol": sym,
                "current_weight": round(float(current_weights.get(sym, 0.0)), 6),
                "target_weight": target_weights[sym],
                "drift_weight": 0.0,
                "trade_weight": 0.0,
                "action": "HOLD",
            }
            for sym in symbols
        ]
        signal = "NO_SIGNAL"
        status = "degraded"
        quality = _data_quality(
            "degraded",
            str(e),
            fallback_used=True,
            current_weights_source=current_weight_meta["source"],
            current_weights_reason=current_weight_meta.get("reason"),
        )

    action_by_symbol = {item["symbol"]: item["action"] for item in execution}
    return {
        "id": "global_risk_parity",
        "name": "全球宏观风险平价",
        "name_en": "GLOBAL RISK PARITY",
        "status": status,
        "signal": signal,
        "color": "#3b82f6",
        "model_mode": "live" if status == "active" else "degraded",
        "tradeable": status == "active",
        "decision_state": decision_state,
        "target_weights": target_weights,
        "current_weights": current_weights,
        "risk_metrics": risk_metrics,
        "execution_plan": execution,
        "data_quality": quality,
        "description": "Volatility-inverse allocation across global broad indices.",
        "details": [
            {"label": "A-Share Vol (30d)", "value": f"{csi_vol*100:.1f}%", "color": "#ef4444" if csi_vol > 0.2 else "#22c55e"},
            {"label": "US-Share Vol (30d)", "value": f"{spy_vol*100:.1f}%", "color": "#ef4444" if spy_vol > 0.2 else "#22c55e"},
            {"label": "Portfolio Vol", "value": f"{risk_metrics['portfolio_volatility_pct']:.1f}%"},
            {"label": "A-Share Risk Contribution", "value": f"{risk_metrics['risk_contribution']['510300.SH']['actual_risk_contribution_pct']:.1f}%"},
            {"label": "Overseas Risk Contribution", "value": f"{risk_metrics['risk_contribution']['513500.SH']['actual_risk_contribution_pct']:.1f}%"},
            {"label": "Target Weight A-Share", "value": f"{w_csi*100:.1f}%"},
            {"label": "Target Weight US/JP", "value": f"{w_spy*100:.1f}%"}
        ],
        "holdings": [
            {"symbol": "513500.SH", "name": "标普500ETF", "action": action_by_symbol.get("513500.SH", "HOLD"), "weight": f"{int(round(w_spy*100))}%"},
            {"symbol": "510300.SH", "name": "沪深300ETF", "action": action_by_symbol.get("510300.SH", "HOLD"), "weight": f"{int(round(w_csi*100))}%"}
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
