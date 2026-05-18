"""
Unified data abstraction layer for AlphaCore.
Replaces yfinance with multi-provider architecture:
  VIX  → FRED VIXCLS (primary) / AKShare (fallback)
  DXY  → Tushare fx_daily USDOLLAR.FXCM (primary) / FRED DTWEXBGS (fallback)
  10Y  → FRED DGS10
  SPY/TLT/GLD → AKShare stock_us_hist (primary) / Tushare QDII ETF (fallback)

All functions return pd.Series with DatetimeIndex and float values.
"""

import urllib.request
import json
import time
import datetime
import pandas as pd

from core.config import settings

# ── internal constants ──────────────────────────────────────────
FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
TUSHARE_BASE = "https://api.tushare.pro"

_last_request_time: dict[str, float] = {}

# ── L2 provider cache + health stats ────────────────────────────
_provider_cache: dict[str, tuple[float, object]] = {}
_provider_stats: dict[str, dict] = {
    "fred":       {"calls": 0, "hits": 0, "errors": 0, "last_ok": 0, "last_err": "", "avg_ms": 0},
    "tushare_fund": {"calls": 0, "hits": 0, "errors": 0, "last_ok": 0, "last_err": "", "avg_ms": 0},
    "tushare_fx":   {"calls": 0, "hits": 0, "errors": 0, "last_ok": 0, "last_err": "", "avg_ms": 0},
    "tushare_index": {"calls": 0, "hits": 0, "errors": 0, "last_ok": 0, "last_err": "", "avg_ms": 0},
    "akshare":    {"calls": 0, "hits": 0, "errors": 0, "last_ok": 0, "last_err": "", "avg_ms": 0},
}
PROVIDER_CACHE_TTL = 3600
MACRO_CACHE_TTL     = 900
EQUITY_CACHE_TTL    = 3600

# ── Circuit breaker ────────────────────────────────────────────
CIRCUIT_FAIL_THRESH = 5    # consecutive failures before opening
CIRCUIT_COOLDOWN_S  = 300  # 5 minutes before half-open probe

_circuit: dict[str, dict] = {
    "fred":          {"state": "closed", "failures": 0, "opened_at": 0},
    "tushare_fund":  {"state": "closed", "failures": 0, "opened_at": 0},
    "tushare_fx":    {"state": "closed", "failures": 0, "opened_at": 0},
    "tushare_index": {"state": "closed", "failures": 0, "opened_at": 0},
}

def _circuit_allow(source: str) -> bool:
    """Return True if this source is allowed to make HTTP calls."""
    cb = _circuit.get(source)
    if not cb: return True
    now = time.time()
    if cb["state"] == "closed": return True
    if cb["state"] == "open":
        if now - cb["opened_at"] > CIRCUIT_COOLDOWN_S:
            cb["state"] = "half-open"
            print(f"[circuit] {source} → half-open, probing …")
            return True
        return False
    return True  # half-open: allow one probe

def _circuit_record(source: str, success: bool):
    cb = _circuit.get(source)
    if not cb: return
    if success:
        cb["failures"] = 0
        cb["state"] = "closed"
    else:
        cb["failures"] += 1
        if cb["failures"] >= CIRCUIT_FAIL_THRESH and cb["state"] != "open":
            cb["state"] = "open"
            cb["opened_at"] = time.time()
            print(f"[circuit] {source} OPEN — {CIRCUIT_FAIL_THRESH} consecutive failures")

def get_circuit_state() -> dict:
    return {k: dict(v) for k, v in _circuit.items()}

def get_provider_stats() -> dict:
    """Return provider health summary for the /api/health endpoint."""
    result = {}
    for name, s in _provider_stats.items():
        total = max(s["calls"], 1)
        result[name] = {
            "calls": s["calls"],
            "hit_ratio": round(s["hits"] / total, 2),
            "error_rate": round(s["errors"] / total, 2),
            "last_ok_secs_ago": round(time.time() - s["last_ok"], 0) if s["last_ok"] else None,
            "last_error": s["last_err"] or None,
            "avg_ms": round(s["avg_ms"], 1),
        }
    return result


import random

def _rate_limit(source: str, min_interval: float = 1.0) -> None:
    """Prevent triggering remote WAF by spacing requests, with Jitter."""
    now = time.time()
    prev = _last_request_time.get(source)
    # Add random jitter to prevent concurrent spike lockouts
    jitter = random.uniform(0.1, 0.5)
    actual_interval = min_interval + jitter
    if prev is not None and (elapsed := now - prev) < actual_interval:
        time.sleep(actual_interval - elapsed)
    _last_request_time[source] = time.time()


def _retry_akshare(func, *args, **kwargs):
    """Wrapper to retry AKShare functions with exponential backoff to handle RemoteDisconnected."""
    import requests
    import urllib3
    from urllib3.exceptions import ProtocolError
    from requests.exceptions import ConnectionError, ReadTimeout

    max_retries = 3
    base_wait = 1.5

    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            err_str = str(e)
            # Catch common network disconnect errors from AKShare
            if "Connection aborted" in err_str or "RemoteDisconnected" in err_str or "timeout" in err_str.lower() or "Connection reset" in err_str:
                if attempt < max_retries - 1:
                    wait_time = base_wait * (2 ** attempt) + random.uniform(0.1, 0.5)
                    time.sleep(wait_time)
                else:
                    print(f"[data_providers] AKShare failed completely after {max_retries} retries: {e}")
                    raise
            else:
                raise


# ── low-level fetchers ──────────────────────────────────────────

def _http_get(url: str, timeout: float = 10.0, retries: int = 3) -> bytes:
    """HTTP GET with exponential backoff retry."""
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                wait = 2 ** attempt
                print(f"[data_providers] HTTP retry {attempt+1}/{retries} in {wait}s …")
                time.sleep(wait)
    raise last_err


def _http_post(url: str, body: bytes, timeout: float = 10.0, retries: int = 2) -> bytes:
    """HTTP POST with retry."""
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=body,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise last_err


def _fred_series(series_id: str, limit: int = 60) -> pd.Series:
    """Fetch a FRED series.  L2-cached per (series_id, limit)."""
    cache_key = f"fred:{series_id}:{limit}"
    now = time.time()

    # L2 cache check — FRED macro data uses shorter TTL
    if cache_key in _provider_cache:
        ts, val = _provider_cache[cache_key]
        if now - ts < MACRO_CACHE_TTL:
            _provider_stats["fred"]["hits"] += 1
            return val

    if not _circuit_allow("fred"):
        if cache_key in _provider_cache:
            print(f"[circuit] FRED open — serving stale cache")
            return _provider_cache[cache_key][1]
        print(f"[circuit] FRED open — no cache available, returning empty series")
        return pd.Series(dtype=float, name=series_id)
    _rate_limit("fred", 1.0)
    _provider_stats["fred"]["calls"] += 1
    t0 = time.time()
    url = (
        f"{FRED_BASE}?series_id={series_id}"
        f"&api_key={settings.FRED_API_KEY}"
        f"&file_type=json&limit={limit}&sort_order=desc"
    )
    try:
        body = _http_get(url, timeout=15.0, retries=3)
        data = json.loads(body.decode("utf-8"))
        observations = data.get("observations", [])
        dates: list[str] = []
        values: list[float] = []
        for obs in reversed(observations):
            if obs["value"] != ".":
                try:
                    val = float(obs["value"])
                    if not pd.isna(val):
                        dates.append(obs["date"])
                        values.append(val)
                except (ValueError, TypeError):
                    continue
        result = pd.Series(values, index=pd.to_datetime(dates), name=series_id).dropna()
        _provider_stats["fred"]["last_ok"] = now
        _provider_stats["fred"]["avg_ms"] = round(
            (_provider_stats["fred"]["avg_ms"] * (_provider_stats["fred"]["calls"] - 1) + (time.time() - t0) * 1000)
            / _provider_stats["fred"]["calls"], 1)
        _provider_cache[cache_key] = (now, result)
        _circuit_record("fred", True)
        return result
    except Exception as e:
        _provider_stats["fred"]["errors"] += 1
        _provider_stats["fred"]["last_err"] = str(e)[:120]
        _circuit_record("fred", False)
        if cache_key in _provider_cache:
            print(f"[data_providers] FRED error — serving stale cache")
            return _provider_cache[cache_key][1]
        print(f"[data_providers] FRED error — no cache available, returning empty series")
        return pd.Series(dtype=float, name=series_id)


def _tushare_items(api_name: str, params: dict, fields: str) -> list:
    """Generic Tushare API call. L2-cached per API, params, and fields."""
    ts_code = params.get("ts_code", "")
    start = params.get("start_date", "")
    end = params.get("end_date", "")
    trade_date = params.get("trade_date", "")
    cache_key = f"ts:{api_name}:{ts_code}:{start}:{end}:{trade_date}:{fields}"

    now = time.time()
    if cache_key in _provider_cache:
        ts, val = _provider_cache[cache_key]
        if now - ts < PROVIDER_CACHE_TTL:
            src = "tushare_fund" if "fund" in api_name else ("tushare_fx" if "fx" in api_name else "tushare_index")
            _provider_stats[src]["hits"] += 1
            return val

    src = "tushare_fund" if "fund" in api_name else ("tushare_fx" if "fx" in api_name else "tushare_index")
    if not _circuit_allow(src):
        if cache_key in _provider_cache:
            print(f"[circuit] Tushare {src} open — serving stale cache")
            return _provider_cache[cache_key][1]
        print(f"[circuit] Tushare {src} open — no cache available, returning empty list")
        return []
    _rate_limit("tushare", 1.0)
    _provider_stats[src]["calls"] += 1
    t0 = time.time()
    payload = {
        "api_name": api_name, "token": settings.TUSHARE_TOKEN,
        "params": params, "fields": fields,
    }
    try:
        raw = _http_post(TUSHARE_BASE, json.dumps(payload).encode("utf-8"),
                         timeout=15.0, retries=2)
        res = json.loads(raw.decode("utf-8"))
        items = res.get("data", {}).get("items", [])
        _provider_stats[src]["last_ok"] = now
        _provider_stats[src]["avg_ms"] = round(
            (_provider_stats[src]["avg_ms"] * (_provider_stats[src]["calls"] - 1) + (time.time() - t0) * 1000)
            / _provider_stats[src]["calls"], 1)
        _provider_cache[cache_key] = (now, items)
        _circuit_record(src, True)
        return items
    except Exception as e:
        _provider_stats[src]["errors"] += 1
        _provider_stats[src]["last_err"] = str(e)[:120]
        _circuit_record(src, False)
        if cache_key in _provider_cache:
            print(f"[data_providers] Tushare {src} error — serving stale cache")
            return _provider_cache[cache_key][1]
        print(f"[data_providers] Tushare {src} error — no cache available, returning empty list")
        return []


def _ts_items_to_series(
    items: list, date_col: int, val_col: int, name: str
) -> pd.Series:
    """Convert Tushare item rows into a sorted DatetimeIndex Series."""
    if not items:
        return pd.Series(dtype=float)
    rows = []
    for r in items:
        try:
            val = float(r[val_col])
            if not pd.isna(val):
                rows.append((pd.to_datetime(r[date_col]), val))
        except (ValueError, TypeError):
            continue
    df = pd.DataFrame(rows, columns=["dt", "val"]).sort_values("dt")
    return pd.Series(df["val"].values, index=df["dt"], name=name).dropna()


def _akshare_us_etf(symbol: str, days_back: int) -> pd.Series:
    """Fetch US ETF daily close via AKShare (East Money source)."""
    _rate_limit("akshare", 1.5)
    import akshare as ak
    end = datetime.date.today()
    start = end - datetime.timedelta(days=days_back + 5)
    df = _retry_akshare(ak.stock_us_hist,
        symbol=symbol, period="daily",
        start_date=start.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
        adjust="qfq",
    )
    if df is None or df.empty:
        return pd.Series(dtype=float)
    df["日期"] = pd.to_datetime(df["日期"])
    df = df.set_index("日期").sort_index()
    s = pd.to_numeric(df["收盘"], errors='coerce').dropna()
    s.name = symbol
    return s


# ── primary public API ──────────────────────────────────────────

def get_vix_history(days: int = 30) -> pd.Series:
    """VIX daily close.  Primary: FRED VIXCLS.  Fallback: AKShare."""
    try:
        s = _fred_series("VIXCLS", limit=days)
        if len(s) > 0:
            return s
    except Exception as e:
        print(f"[data_providers] FRED VIXCLS failed: {e}")

    # fallback: AKShare VIX (try both known function names)
    print("[data_providers] Falling back to AKShare for VIX …")
    try:
        import akshare as ak
        end = datetime.date.today()
        start = end - datetime.timedelta(days=days + 10)
        df = None
        # try newer function first, then legacy
        for fn_name in ("index_vix", "index_investing_global"):
            try:
                fn = getattr(ak, fn_name, None)
                if fn is None:
                    continue
                if fn_name == "index_vix":
                    df = _retry_akshare(fn, start_date=start.strftime("%Y-%m-%d"),
                            end_date=end.strftime("%Y-%m-%d"))
                else:
                    df = _retry_akshare(fn, country="美国", index_name="VIX恐慌指数",
                            period="每日",
                            start_date=start.strftime("%Y-%m-%d"),
                            end_date=end.strftime("%Y-%m-%d"))
                if df is not None and not df.empty:
                    break
            except Exception:
                continue

        if df is not None and not df.empty:
            # normalize column names
            date_col = next((c for c in df.columns if "日" in c or "date" in c.lower()), df.columns[0])
            close_col = next((c for c in df.columns if "收" in c or "close" in c.lower()), df.columns[-1])
            df[date_col] = pd.to_datetime(df[date_col])
            df = df.sort_values(date_col)
            return pd.Series(df[close_col].values, index=df[date_col], name="VIX")
    except Exception as e2:
        print(f"[data_providers] AKShare VIX also failed: {e2}")

    return pd.Series(dtype=float)


def get_dxy_history(days: int = 30) -> pd.Series:
    """USD index daily close.  Primary: Tushare fx_daily.  Fallback: FRED DTWEXBGS."""
    try:
        end = datetime.date.today()
        start = end - datetime.timedelta(days=days + 5)
        items = _tushare_items(
            "fx_daily",
            params={
                "ts_code": "USDOLLAR.FXCM",
                "start_date": start.strftime("%Y%m%d"),
                "end_date": end.strftime("%Y%m%d"),
            },
            fields="trade_date,bid_close",
        )
        s = _ts_items_to_series(items, date_col=0, val_col=1, name="DXY")
        if len(s) > 0:
            return s
    except Exception as e:
        print(f"[data_providers] Tushare DXY failed: {e}")

    print("[data_providers] Falling back to FRED DTWEXBGS for DXY …")
    return _fred_series("DTWEXBGS", limit=days)


def get_tnx_history(days: int = 30) -> pd.Series:
    """10Y US Treasury yield.  Primary: FRED DGS10."""
    return _fred_series("DGS10", limit=days)


def get_us_etf_history(symbol: str, months: int = 6) -> pd.Series:
    """US ETF daily close (SPY / TLT / GLD).
    Primary: Tushare QDII ETF (works in CN without VPN).
    Fallback: AKShare (East Money, may be blocked)."""
    days = months * 31 + 5

    # proxy map: US ETF → Tushare QDII / domestic ETF
    # All three are China-listed ETFs accessible via Tushare fund_daily (2000+ pts)
    proxy_map = {
        "SPY": "513500.SH",   # 标普500ETF
        "GLD": "518880.SH",   # 黄金ETF
        "TLT": "511260.SH",   # 10年国债ETF (directional proxy for US long bonds)
    }

    ts_code = proxy_map.get(symbol)
    if ts_code:
        try:
            end = datetime.date.today()
            start = end - datetime.timedelta(days=days)
            items = _tushare_items(
                "fund_daily",
                params={
                    "ts_code": ts_code,
                    "start_date": start.strftime("%Y%m%d"),
                    "end_date": end.strftime("%Y%m%d"),
                },
                fields="trade_date,close",
            )
            s = _ts_items_to_series(items, date_col=0, val_col=1,
                                    name=f"{symbol}_proxy({ts_code})")
            if len(s) > 0:
                print(f"[data_providers] {symbol} → Tushare QDII {ts_code} ({len(s)} rows)")
                return s
        except Exception as e:
            print(f"[data_providers] Tushare QDII {ts_code} failed for {symbol}: {e}")
    else:
        print(f"[data_providers] No proxy mapping for {symbol}")

    # fallback: AKShare (may work on some networks)
    try:
        s = _akshare_us_etf(symbol, days_back=days)
        if len(s) > 0:
            print(f"[data_providers] {symbol} → AKShare ({len(s)} rows)")
            return s
    except Exception as e:
        print(f"[data_providers] AKShare failed for {symbol}: {e}")

    print(f"[data_providers] ⚠ all sources exhausted for {symbol}")
    return pd.Series(dtype=float)


def get_us_etf_history_long(symbol: str, years: int = 5) -> pd.Series:
    """Long-history variant for back-test initial download.
    Tushare QDII primary, AKShare fallback."""
    days = years * 366 + 10

    proxy_map = {
        "SPY": "513500.SH",
        "GLD": "518880.SH",
        "TLT": "511260.SH",
    }
    ts_code = proxy_map.get(symbol)
    if ts_code:
        try:
            end = datetime.date.today()
            start = end - datetime.timedelta(days=days)
            items = _tushare_items(
                "fund_daily",
                params={
                    "ts_code": ts_code,
                    "start_date": start.strftime("%Y%m%d"),
                    "end_date": end.strftime("%Y%m%d"),
                },
                fields="trade_date,close",
            )
            s = _ts_items_to_series(items, date_col=0, val_col=1,
                                    name=f"{symbol}_proxy({ts_code})")
            if len(s) > 0:
                print(f"[data_providers] {symbol} long → Tushare QDII {ts_code} ({len(s)} rows)")
                return s
        except Exception as e:
            print(f"[data_providers] Tushare QDII long failed for {symbol}: {e}")

    try:
        s = _akshare_us_etf(symbol, days_back=days)
        if len(s) > 0:
            print(f"[data_providers] {symbol} long → AKShare ({len(s)} rows)")
            return s
    except Exception as e:
        print(f"[data_providers] AKShare long failed for {symbol}: {e}")

    return pd.Series(dtype=float)


# ── convenience helpers ─────────────────────────────────────────

def get_global_index_history_long(symbol: str, years: int = 10) -> pd.Series:
    """Fetch native global indices to avoid exchange rate noise in scientific backtest.
    Supported: SPX (S&P 500), IXIC (Nasdaq), N225 (Nikkei), 
               000300.SH (CSI 300), 000905.SH (CSI 500).
    """
    days = years * 366 + 10
    end = datetime.date.today()
    start = end - datetime.timedelta(days=days)
    
    if symbol.endswith(".SH") or symbol.endswith(".SZ"):
        api_name = "index_daily"
    else:
        api_name = "index_global"
        
    try:
        items = _tushare_items(
            api_name,
            params={
                "ts_code": symbol,
                "start_date": start.strftime("%Y%m%d"),
                "end_date": end.strftime("%Y%m%d"),
            },
            fields="trade_date,close",
        )
        s = _ts_items_to_series(items, date_col=0, val_col=1, name=symbol)
        if len(s) > 0:
            print(f"[data_providers] {symbol} long native → Tushare {api_name} ({len(s)} rows)")
            return s
    except Exception as e:
        print(f"[data_providers] Tushare {api_name} failed for {symbol}: {e}")

    # Fallback to AKShare
    if api_name == "index_global":
        try:
            import akshare as ak
            df = _retry_akshare(ak.index_investing_global, country="美国" if symbol in ["SPX", "IXIC"] else "日本", 
                                           index_name="标普500" if symbol == "SPX" else ("纳斯达克综合指数" if symbol == "IXIC" else "日经225"), 
                                           period="每日", 
                                           start_date=start.strftime("%Y-%m-%d"), 
                                           end_date=end.strftime("%Y-%m-%d"))
            if df is not None and not df.empty:
                date_col = next((c for c in df.columns if "日" in c or "date" in c.lower()), df.columns[0])
                close_col = next((c for c in df.columns if "收" in c or "close" in c.lower()), df.columns[-1])
                df[date_col] = pd.to_datetime(df[date_col])
                df = df.sort_values(date_col)
                s = pd.Series(df[close_col].values, index=df[date_col], name=symbol)
                print(f"[data_providers] {symbol} long native → AKShare ({len(s)} rows)")
                return s
        except Exception as e:
            print(f"[data_providers] AKShare native failed for {symbol}: {e}")

    return pd.Series(dtype=float)


def get_china_etf_history_long(symbol: str, years: int = 5) -> pd.Series:
    """Fetch history for A-Share ETFs. Primary: Tushare, Fallback: AKShare (qfq)."""
    start_date = (datetime.datetime.now() - datetime.timedelta(days=365 * years)).strftime("%Y%m%d")
    end_date = datetime.datetime.now().strftime("%Y%m%d")
    
    # Format symbol for Tushare
    ts_code = symbol
    if not ts_code.endswith(".SH") and not ts_code.endswith(".SZ"):
        if ts_code.startswith("6") or ts_code.startswith("5"):
            ts_code += ".SH"
        else:
            ts_code += ".SZ"
            
    is_fund = ts_code.startswith("5") or ts_code.startswith("15")
    ts_api = "fund_daily" if is_fund else "daily"
    
    # Primary: Tushare (Stable, Institutional grade)
    try:
        items = _tushare_items(
            ts_api,
            {"ts_code": ts_code, "start_date": start_date, "end_date": end_date},
            "trade_date,close"
        )
        if items:
            s = _ts_items_to_series(items, 0, 1, symbol)
            print(f"[data_providers] {symbol} (China) → Tushare {ts_api} ({len(s)} rows)")
            return s
    except Exception as e:
        print(f"[data_providers] Tushare {ts_api} failed for {symbol}: {e}")

    # Fallback: AKShare with qfq (Forward-Adjusted)
    try:
        import akshare as ak
        ak_sym = symbol.split(".")[0]
        if ak_sym.startswith("5") or ak_sym.startswith("15"):
            df = _retry_akshare(ak.fund_etf_hist_em,
                symbol=ak_sym, period="daily",
                start_date=start_date, end_date=end_date,
                adjust="qfq"
            )
        else:
            df = _retry_akshare(ak.stock_zh_a_hist,
                symbol=ak_sym, period="daily",
                start_date=start_date, end_date=end_date,
                adjust="qfq"
            )
        if df is not None and not df.empty:
            df["日期"] = pd.to_datetime(df["日期"])
            df = df.set_index("日期").sort_index()
            s = pd.to_numeric(df["收盘"], errors='coerce').dropna()
            s.name = symbol
            print(f"[data_providers] {symbol} (China) → AKShare qfq ({len(s)} rows)")
            return s
    except Exception as e:
        print(f"[data_providers] AKShare failed for {symbol}: {e}")
        
    return pd.Series(dtype=float)


def get_vix_current() -> float:
    try:
        s = get_vix_history(5)
        return float(s.iloc[-1]) if len(s) > 0 else 20.0
    except Exception:
        return 20.0


def get_dxy_current() -> float:
    try:
        s = get_dxy_history(5)
        return float(s.iloc[-1]) if len(s) > 0 else 100.0
    except Exception:
        return 100.0

# ═══════════════════════════════════════════════════════════════
# Shared multi-asset snapshot — used by sector_rotation and
# asset_rotation to fetch 4 key dates and compute 5D/20D/60D returns.
# ═══════════════════════════════════════════════════════════════

def get_multi_asset_snapshot(api_name: str, codes_dict: dict,
                             benchmark_code: str,
                             days_back: int = 60) -> list[dict]:
    """Fetch 4 key dates and compute 5D/20D/60D returns for many codes.

    Returns list of {code, name, ret_5d, ret_20d, ret_60d, last_close}.
    """
    import datetime as _dt
    end = _dt.date.today()
    start = end - _dt.timedelta(days=days_back * 2)

    try:
        items = _tushare_items(api_name, {
            'ts_code': benchmark_code,
            'start_date': start.strftime("%Y%m%d"),
            'end_date': end.strftime("%Y%m%d"),
        }, 'trade_date')
    except Exception as e:
        return []  # caller handles empty

    dates = sorted([row[0] for row in items])
    if len(dates) < 61:
        return []

    t0, t5, t20, t60 = dates[-1], dates[-6], dates[-21], dates[-61]
    snapshots = {}
    for d in (t0, t5, t20, t60):
        try:
            its = _tushare_items(api_name, {'trade_date': d}, 'ts_code,close')
            snapshots[d] = {row[0]: float(row[1]) for row in its}
        except Exception:
            snapshots[d] = {}

    rows = []
    for code, name in codes_dict.items():
        if code not in snapshots.get(t0, {}) or code not in snapshots.get(t20, {}):
            continue
        last = snapshots[t0][code]
        try:
            r5  = round((last / snapshots[t5][code] - 1) * 100, 2) if code in snapshots.get(t5, {}) else 0
            r20 = round((last / snapshots[t20][code] - 1) * 100, 2)
            r60 = round((last / snapshots[t60][code] - 1) * 100, 2) if code in snapshots.get(t60, {}) else 0
        except (ZeroDivisionError, KeyError):
            r5 = r20 = r60 = 0
        rows.append({"code": code, "name": name, "ret_5d": r5, "ret_20d": r20,
                      "ret_60d": r60, "last_close": round(last, 2)})
    return rows


_attr_cache = {}

def get_attribution_returns(symbols: list[str], period: str = "T-1") -> dict[str, float]:
    """
    Fetch absolute returns for attribution concurrently.
    Uses forward-adjusted data where possible to match production logic.
    period mapping: 'T-1' -> 1 day, 'T-5' -> 5 days, etc.
    """
    import concurrent.futures
    import pandas as pd
    import time
    
    days_back = 5 if period == "T-5" else (30 if period == "T-30" else 1)
    now = time.time()
    
    def _fetch_single_return(symbol: str) -> tuple[str, float]:
        try:
            # Check cache first
            cache_key = f"{symbol}:{period}"
            if cache_key in _attr_cache:
                ts, val = _attr_cache[cache_key]
                if now - ts < 3600 * 4:  # 4 hour cache
                    return symbol, val
                    
            # We fetch a bit more history to ensure we get N trading days
            fetch_days = days_back + 10
            
            # Skip dummy text symbols
            if symbol.endswith("_ETF") or symbol in ["CASH"]:
                return symbol, 0.0
                
            # If purely numeric or explicitly A-share, use China ETF logic
            is_china = symbol.endswith(".SH") or symbol.endswith(".SZ") or symbol.split(".")[0].isdigit()
            if is_china:
                s = get_china_etf_history_long(symbol, years=1)
            else:
                s = get_us_etf_history(symbol.replace(".US", ""), months=max(1, fetch_days // 20 + 1))
                
            if s.empty or len(s) < days_back + 1:
                return symbol, 0.0
                
            latest = s.iloc[-1]
            past = s.iloc[-(days_back + 1)]
            
            if past == 0:
                return symbol, 0.0
                
            ret = round(float((latest / past) - 1.0), 6)
            _attr_cache[cache_key] = (now, ret)
            return symbol, ret
        except Exception as e:
            print(f"[data_providers] Attribution fetch failed for {symbol}: {e}")
            return symbol, 0.0

    results = {}
    uncached_symbols = [s for s in symbols if f"{s}:{period}" not in _attr_cache or now - _attr_cache[f"{s}:{period}"][0] >= 3600 * 4]
    
    # Fill cached ones immediately
    for s in symbols:
        if s not in uncached_symbols:
            results[s] = _attr_cache[f"{s}:{period}"][1]
            
    if uncached_symbols:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor: # Set to 1 to serialize requests and avoid WAF ban
            future_to_sym = {executor.submit(_fetch_single_return, sym): sym for sym in uncached_symbols}
            for future in concurrent.futures.as_completed(future_to_sym):
                sym, ret = future.result()
                results[sym] = ret
            
    return results
