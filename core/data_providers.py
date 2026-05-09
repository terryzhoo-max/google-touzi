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
# L3: inflight tracker to deduplicate concurrent same-param requests
import threading as _threading
_inflight: dict[str, _threading.Event] = {}
_inflight_lock = _threading.Lock()

PROVIDER_CACHE_TTL = 3600  # 1-hour default for raw provider data

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


def _rate_limit(source: str, min_interval: float = 1.0) -> None:
    """Prevent triggering remote WAF by spacing requests."""
    now = time.time()
    prev = _last_request_time.get(source)
    if prev is not None and (elapsed := now - prev) < min_interval:
        time.sleep(min_interval - elapsed)
    _last_request_time[source] = time.time()


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

    # L2 cache check
    if cache_key in _provider_cache:
        ts, val = _provider_cache[cache_key]
        if now - ts < PROVIDER_CACHE_TTL:
            _provider_stats["fred"]["hits"] += 1
            return val

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
        return result
    except Exception as e:
        _provider_stats["fred"]["errors"] += 1
        _provider_stats["fred"]["last_err"] = str(e)[:120]
        raise


def _tushare_items(api_name: str, params: dict, fields: str) -> list:
    """Generic Tushare API call.  L2-cached per (api, ts_code, start, end)."""
    ts_code = params.get("ts_code", "")
    start = params.get("start_date", "")
    end = params.get("end_date", "")
    trade_date = params.get("trade_date", "")
    cache_key = f"ts:{api_name}:{ts_code}:{start}:{end}:{trade_date}"

    now = time.time()
    if cache_key in _provider_cache:
        ts, val = _provider_cache[cache_key]
        if now - ts < PROVIDER_CACHE_TTL:
            # classify source
            src = "tushare_fund" if "fund" in api_name else "tushare_index"
            _provider_stats[src]["hits"] += 1
            return val

    _rate_limit("tushare", 1.0)
    src = "tushare_fund" if "fund" in api_name else ("tushare_fx" if "fx" in api_name else "tushare_index")
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
        return items
    except Exception as e:
        _provider_stats[src]["errors"] += 1
        _provider_stats[src]["last_err"] = str(e)[:120]
        raise


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
    df = ak.stock_us_hist(
        symbol=symbol, period="daily",
        start_date=start.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
        adjust="",
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
                    df = fn(start_date=start.strftime("%Y-%m-%d"),
                            end_date=end.strftime("%Y-%m-%d"))
                else:
                    df = fn(country="美国", index_name="VIX恐慌指数",
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
