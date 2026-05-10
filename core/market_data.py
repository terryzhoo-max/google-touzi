import time
import asyncio
import urllib.request
import json

from core.config import settings
from core.data_providers import get_vix_history, get_dxy_history, get_tnx_history
from core.cache_store import invalidate

DATA_CACHE = {
    "tnx": {"timestamp": 0, "data": None},
    "vix": {"timestamp": 0, "data": None},
    "dxy": {"timestamp": 0, "data": None},
    "csi300": {"timestamp": 0, "data": None},
    "correlation": {"timestamp": 0, "data": None}
}


def fetch_fred_10y():
    """Fetch 10-Year Treasury Constant Maturity Rate from FRED"""
    now = time.time()
    if now - DATA_CACHE["tnx"]["timestamp"] < settings.CACHE_TTL and DATA_CACHE["tnx"]["data"] is not None:
        return DATA_CACHE["tnx"]["data"]
        
    try:
        url = f"https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&api_key={settings.FRED_API_KEY}&file_type=json&limit=30&sort_order=desc"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            
        observations = data.get("observations", [])
        # FRED sorts desc, we want asc for chart
        observations.reverse()
        
        dates = []
        values = []
        for obs in observations:
            if obs["value"] != ".": # FRED uses "." for missing data
                dates.append(obs["date"])
                values.append(float(obs["value"]))
                
        if not values:
            raise Exception("FRED API returned no valid float observations.")
            
        current_val = values[-1]
        
        # Signal Generation
        if current_val < settings.TNX_LOOSE_THRESH:
            signal_state = "宽松周期 (利好权益)"
            signal_color = "#4ade80" # Green
            action_insight = f"量化信号：美债基准利率为 {current_val}%，全球流动性宽裕，分子端盈利预期上修，利好成长股与新兴市场资产。"
        elif settings.TNX_LOOSE_THRESH <= current_val < settings.TNX_TIGHT_THRESH:
            signal_state = "中性震荡"
            signal_color = "#00F0FF" # Cyan
            action_insight = f"量化信号：美债收益率为 {current_val}%，处于中性均衡区间，长久期资产估值承压，重点关注高股息与红利低波策略。"
        else:
            signal_state = "紧缩高压 (杀估值警戒)"
            signal_color = "#ef4444" # Red
            action_insight = f"量化信号：美债飙升至 {current_val}% 警戒线以上！无风险利率对所有权益资产估值形成巨大压制，建议清仓劣质资产。"

        result = {
            "dates": dates,
            "data": values,
            "signal_state": signal_state,
            "signal_color": signal_color,
            "action_insight": action_insight
        }
        
        DATA_CACHE["tnx"]["data"] = result
        DATA_CACHE["tnx"]["timestamp"] = now
        return result
    except Exception as e:
        print(f"FRED API Error: {e}")
        return fetch_macro_indicator("^TNX", "tnx")

def fetch_tushare_csi300():
    """Fetch CSI 300 Index (沪深300) from Tushare"""
    now = time.time()
    if now - DATA_CACHE["csi300"]["timestamp"] < settings.CACHE_TTL and DATA_CACHE["csi300"]["data"] is not None:
        return DATA_CACHE["csi300"]["data"]
        
    try:
        url = "https://api.tushare.pro"
        payload = {
            "api_name": "index_daily",
            "token": settings.TUSHARE_TOKEN,
            "params": {"ts_code": "000300.SH"},
            "fields": "trade_date,close"
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as response:
            res = json.loads(response.read().decode("utf-8"))
            
        items = res.get("data", {}).get("items", [])
        if not items:
            return {"data": [0.0]}
            
        # Tushare returns desc order (latest first)
        items = items[:30]
        items.reverse()
        
        values = [float(item[1]) for item in items]
        
        result = {"data": values}
        DATA_CACHE["csi300"]["data"] = result
        DATA_CACHE["csi300"]["timestamp"] = now
        return result
    except Exception as e:
        print(f"Tushare API Error: {e}")
        return {"data": [0.0]}

def fetch_tushare_csi300_history(months=6):
    """Fetch CSI 300 Index (沪深300) historical data for correlation engine"""
    try:
        import pandas as pd
        from datetime import datetime, timedelta
        url = "https://api.tushare.pro"
        start_date = (datetime.now() - timedelta(days=months*30)).strftime("%Y%m%d")
        payload = {
            "api_name": "index_daily",
            "token": settings.TUSHARE_TOKEN,
            "params": {"ts_code": "000300.SH", "start_date": start_date},
            "fields": "trade_date,close"
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as response:
            res = json.loads(response.read().decode("utf-8"))
            
        items = res.get("data", {}).get("items", [])
        if not items:
            return pd.Series(dtype=float)
            
        df = pd.DataFrame(items, columns=["trade_date", "close"])
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df.set_index('trade_date', inplace=True)
        df.sort_index(inplace=True)
        hist = df['close']
        hist.name = "CSI300"
        return hist
    except Exception as e:
        import pandas as pd
        print(f"Tushare History Error: {e}")
        return pd.Series(dtype=float)

def fetch_macro_indicator(_ticker: str, cache_key: str):
    """Fetch VIX / DXY / TNX macro data from unified data providers.
    Keeps the same cache + signal-generation contract so front-end is unchanged."""
    now = time.time()
    cached = DATA_CACHE.get(cache_key, {})
    if (
        cached.get("data") is not None
        and (now - cached.get("timestamp", 0)) < settings.CACHE_TTL
    ):
        return cached["data"]

    try:
        # ── fetch raw series ──────────────────────────────────
        if cache_key == "vix":
            series = get_vix_history(30)
        elif cache_key == "dxy":
            series = get_dxy_history(30)
        elif cache_key == "tnx":
            series = get_tnx_history(30)
        else:
            return _empty_result("未知缓存键")

        if series.empty:
            # stale-cache fallback: return last known data when APIs are unreachable
            if cached.get("data") is not None:
                print(f"  ⚠ {cache_key} API unreachable — serving stale cache")
                return cached["data"]
            return _empty_result("无数据")

        dates = [d.strftime("%Y-%m-%d") for d in series.index]
        values = series.round(2).tolist()
        current_val = values[-1]

        # ── signal generation ──────────────────────────────────
        if cache_key == "vix":
            if current_val < settings.VIX_CAUTION_THRESH:
                signal_state = "Risk-On (低波动安全区)"
                signal_color = "#4ade80"
                action_insight = f"量化信号：当前恐慌指数低至 {current_val}，处于安全的流动性溢价区间，建议保持核心多头敞口以获取复利。"
            elif current_val < settings.VIX_PANIC_THRESH:
                signal_state = "Caution (波动率警告)"
                signal_color = "#fbbf24"
                action_insight = f"量化信号：当前恐慌指数升至 {current_val}，市场分歧显著加剧，建议利用期权构建保护性颈线 (Collar)。"
            else:
                signal_state = "Risk-Off (极度恐慌)"
                signal_color = "#ef4444"
                action_insight = f"量化信号：恐慌指数飙升至 {current_val}，系统性尾部风险已爆发！强制平仓高 Beta 资产，全面转向避险与波动率多头配置。"
        elif cache_key == "dxy":
            if current_val > 108:
                signal_state = "强美元抽水 (离岸承压)"
                signal_color = "#ef4444"
                action_insight = f"量化信号：美元指数强至 {current_val}，全球离岸流动性被大幅抽干，新兴市场与大宗商品全面承压。"
            elif current_val > 100:
                signal_state = "中性偏强 (观望)"
                signal_color = "#fbbf24"
                action_insight = f"量化信号：美元指数 {current_val}，方向性信号偏强但不极端，黄金与资源品谨慎持有。"
            else:
                signal_state = "弱美元宽松 (利好风险资产)"
                signal_color = "#4ade80"
                action_insight = f"量化信号：美元指数走弱至 {current_val}，全球流动性充裕，利好新兴市场与大宗商品。"
        elif cache_key == "tnx":
            if current_val < settings.TNX_LOOSE_THRESH:
                signal_state = "宽松周期"
                signal_color = "#4ade80"
                action_insight = f"美债收益率 {current_val}%，流动性宽裕。"
            elif current_val < settings.TNX_TIGHT_THRESH:
                signal_state = "中性震荡"
                signal_color = "#00F0FF"
                action_insight = f"美债收益率 {current_val}%，中性区间。"
            else:
                signal_state = "紧缩高压"
                signal_color = "#ef4444"
                action_insight = f"美债收益率 {current_val}%，承压！"
        else:
            signal_state = "Normal"
            signal_color = "#00F0FF"
            action_insight = ""

        result = {
            "dates": dates,
            "data": values,
            "signal_state": signal_state,
            "signal_color": signal_color,
            "action_insight": action_insight,
        }
        DATA_CACHE[cache_key]["data"] = result
        DATA_CACHE[cache_key]["timestamp"] = now
        return result

    except Exception as e:
        print(f"MacroIndicator({cache_key}) error: {e}")
        if cached.get("data") is not None:
            print(f"  ⚠ {cache_key} exception — serving stale cache")
            return cached["data"]
        return _empty_result("网络故障")


def _empty_result(reason: str) -> dict:
    return {
        "dates": ["Error"],
        "data": [0.0],
        "signal_state": reason,
        "signal_color": "#94a3b8",
        "action_insight": "无法连接至数据源。",
    }

shutdown_event = asyncio.Event()

async def background_data_fetcher():
    while not shutdown_event.is_set():
        try:
            print("[Background Daemon] Syncing multi-source institutional macro pipelines...")
            fetch_fred_10y()
            fetch_macro_indicator("^VIX", "vix")
            fetch_macro_indicator("DX-Y.NYB", "dxy")
            fetch_tushare_csi300()
            # selectively invalidate only routes whose source data was refreshed
            for rk in ("erp", "spread", "yield_curve", "decision", "signals", "allocation"):
                invalidate(rk)
            print("[Background Daemon] Sync complete. Macro caches refreshed.")
            
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=1800)
            except asyncio.TimeoutError:
                pass
        except Exception as e:
            if shutdown_event.is_set():
                break
            print(f"[Background Daemon] Sync failed: {e}")
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=60)
            except asyncio.TimeoutError:
                pass

# Wrapper to maintain compatibility with core.quant_engine expectations
def fetch_yfinance_data(ticker_symbol: str, cache_key: str):
    if cache_key == "tnx":
        return fetch_fred_10y()
    return fetch_macro_indicator(ticker_symbol, cache_key)
