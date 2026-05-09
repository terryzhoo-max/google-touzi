# AlphaCore — 数据源迁移方案（v2：Tushare 5000 积分最优利用版）

> 编制日期：2026-05-06  
> 关键前提：用户持有 Tushare Pro 5000 积分 API Key  
> 核心结论：**Tushare 5000 积分可接管 DXY，但无法接管 SPY/TLT/GLD/VIX**。最优方案为 Tushare + FRED + AKShare 三源混合架构。

---

## 〇、Tushare 5000 积分能力边界（精确结论）

经过对 Tushare Pro 官方接口文档的逐项验证：

| 数据需求 | 最相关 Tushare 接口 | 积分门槛 | 5000积分可用？ | 结论 |
|:---|:---|:---:|:---:|:---|
| **DXY / 美元指数** | `fx_daily(ts_code='USDOLLAR.FXCM')` | 2000 | ✅ 可用 | ⭐ 直接替代 yfinance DXY |
| **SPY / 标普500** | `us_daily(ts_code='SPY')` | ¥2000/年现金 | ❌ 不走积分体系 | 积分无用，需单独付费 |
| **TLT / 长债** | `us_daily(ts_code='TLT')` | ¥2000/年现金 | ❌ 不走积分体系 | 同上 |
| **GLD / 黄金** | `us_daily(ts_code='GLD')` | ¥2000/年现金 | ❌ 不走积分体系 | 同上 |
| **VIX / 恐慌指数** | **无对应接口** | — | ❌ 不存在 | Tushare 无 VIX 数据 |
| **SPX / DJI / IXIC** | `index_global` | **6000** | ❌ 差1000分 | 不可用 |
| **沪深300** | `index_daily(ts_code='000300.SH')` | 120 | ✅ 已在使用 | 不变 |
| **中国 QDII ETF** (如513500标普ETF) | `fund_daily(ts_code='513500.SH')` | 2000 | ✅ 可用 | 可作为备源，但含汇率噪声 |
| **中国黄金ETF** (如518880) | `fund_daily(ts_code='518880.SH')` | 2000 | ✅ 可用 | 同上 |

**一句话结论：** 5000 积分的 Tushare 能精准替代 yfinance 的 DXY 调用，还能提供中国 QDII ETF 作为美股 ETF 的**备源**。但 SPY/TLT/GLD 的美元计价一级数据仍需 AKShare，VIX 仍需 FRED。

---

## 一、修正后的数据源架构

```
数据抽象层: core/data_providers.py
│
├── DXY / 美元指数
│   主源: Tushare fx_daily(USDOLLAR.FXCM)  ← 5000积分 ✅
│   备源: FRED DTWEXBGS
│
├── 10Y 美债收益率
│   主源: FRED DGS10
│   备源: (无 — FRED 是最权威的10Y数据源)
│
├── VIX 恐慌指数
│   主源: FRED VIXCLS  (1990年至今，每日更新)
│   备源: AKShare index_investing_global
│
├── SPY / TLT / GLD (美股 ETF 日线)
│   主源: AKShare stock_us_hist()  (东方财富源，免费，境内可用)
│   备源: Tushare fund_daily(中国QDII-ETF)  ← 5000积分 ✅，但有汇率噪声
│   缓存: SQLite alphacore.db (18年回测数据)
│
├── CSI 300 / A股
│   主源: Tushare index_daily(000300.SH)  ← 不变
│
└── AI 洞察 / 告警
    不变 (DeepSeek + Server酱)
```

**关键设计决策：** DXY 从 FRED DTWEXBGS 改回 Tushare `fx_daily(USDOLLAR.FXCM)`。原因：
- Tushare USDOLLAR.FXCM 与市场通用的 DXY 数值更接近（均基于 100 附近），而 FRED DTWEXBGS 的基准是 2006=100（当前值约 128），差异较大
- 避免前端 insight 文本中 DXY 数值突然跳变（从 ~104 → ~128），减少用户困惑
- Tushare 5000 积分已付费，充分利用

---

## 二、修正后的实施步骤

### 第〇步：Bug 修复（不变，5 分钟）

**Fix：** `market_data.py` 第 25 行 `FRED_API_KEY` → `settings.FRED_API_KEY`

**Fix：** `market_data.py` 中两处硬编码阈值改为引用 `settings.TNX_LOOSE_THRESH` 等

**验证：** `curl http://127.0.0.1:8888/api/macro/erp` 正常返回 JSON

---

### 第一步：新建 `core/data_providers.py`（约 2.5h）

与 v1 方案的核心差异：DXY 走 Tushare 而非 FRED；新增 Tushare 中国 QDII ETF 作为备源。

```python
# core/data_providers.py

import akshare as ak
import pandas as pd
import urllib.request
import json
import time
from core.config import settings

# ============================================================
# 内部工具
# ============================================================

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
TUSHARE_BASE = "https://api.tushare.pro"

_last_request_time = {}

def _rate_limit(source: str, min_interval: float = 1.0):
    now = time.time()
    if source in _last_request_time:
        elapsed = now - _last_request_time[source]
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
    _last_request_time[source] = time.time()


def _fred_series(series_id: str, limit: int = 60) -> pd.Series:
    """FRED series → pd.Series with DatetimeIndex"""
    _rate_limit("fred", 1.0)
    url = (f"{FRED_BASE}?series_id={series_id}&api_key={settings.FRED_API_KEY}"
           f"&file_type=json&limit={limit}&sort_order=desc")
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    obs = data.get("observations", [])
    dates, values = [], []
    for o in reversed(obs):
        if o["value"] != ".":
            dates.append(o["date"])
            values.append(float(o["value"]))
    return pd.Series(values, index=pd.to_datetime(dates), name=series_id)


def _tushare_api(api_name: str, params: dict, fields: str) -> list:
    """通用 Tushare API 调用 → 返回 items 列表"""
    _rate_limit("tushare", 1.0)
    payload = {
        "api_name": api_name,
        "token": settings.TUSHARE_TOKEN,
        "params": params,
        "fields": fields
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        TUSHARE_BASE, data=data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    return res.get("data", {}).get("items", [])


# ============================================================
# 一级接口：每个数据需求一个函数
# ============================================================

def get_dxy_history(days: int = 30) -> pd.Series:
    """
    美元指数历史数据。
    主源: Tushare fx_daily(USDOLLAR.FXCM) ← 5000 积分
    返回: pd.Series with DatetimeIndex, values = bid_close
    """
    import datetime
    end = datetime.date.today()
    start = end - datetime.timedelta(days=days + 5)
    try:
        items = _tushare_api(
            "fx_daily",
            params={
                "ts_code": "USDOLLAR.FXCM",
                "start_date": start.strftime("%Y%m%d"),
                "end_date": end.strftime("%Y%m%d")
            },
            fields="trade_date,bid_close"
        )
        if items:
            df = pd.DataFrame(items, columns=["trade_date", "bid_close"])
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            df = df.sort_values("trade_date")
            s = pd.Series(df["bid_close"].values, index=df["trade_date"], name="DXY")
            return s
    except Exception as e:
        print(f"[data_providers] Tushare DXY failed: {e}")

    # 备源: FRED DTWEXBGS
    print("[data_providers] Falling back to FRED DTWEXBGS for DXY...")
    return _fred_series("DTWEXBGS", limit=days)


def get_vix_history(days: int = 30) -> pd.Series:
    """
    VIX 恐慌指数历史数据。
    主源: FRED VIXCLS (1990年至今，Tushare 无此数据)
    """
    try:
        return _fred_series("VIXCLS", limit=days)
    except Exception as e:
        print(f"[data_providers] FRED VIX failed: {e}")
        # 备源: AKShare
        try:
            _rate_limit("akshare", 1.5)
            df = ak.index_investing_global(
                country="美国", index_name="VIX恐慌指数",
                period="每日",
                start_date=(pd.Timestamp.now() - pd.Timedelta(days=days+5)).strftime("%Y-%m-%d"),
                end_date=pd.Timestamp.now().strftime("%Y-%m-%d")
            )
            if df is not None and not df.empty:
                df["日期"] = pd.to_datetime(df["日期"])
                df = df.sort_values("日期")
                return pd.Series(df["收盘"].values, index=df["日期"], name="VIX")
        except Exception as e2:
            print(f"[data_providers] AKShare VIX also failed: {e2}")
    return pd.Series(dtype=float)


def get_tnx_history(days: int = 30) -> pd.Series:
    """10Y 美债收益率。主源: FRED DGS10"""
    return _fred_series("DGS10", limit=days)


def get_us_etf_history(symbol: str, months: int = 6) -> pd.Series:
    """
    美股 ETF 日线收盘价。
    主源: AKShare stock_us_hist (东方财富源，免费)
    symbol: "SPY", "TLT", "GLD"
    """
    import datetime
    end = datetime.date.today()
    start = end - datetime.timedelta(days=months * 31)
    _rate_limit("akshare", 1.5)

    try:
        df = ak.stock_us_hist(
            symbol=symbol, period="daily",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            adjust=""
        )
        if df is None or df.empty:
            raise ValueError(f"AKShare returned empty for {symbol}")
        df["日期"] = pd.to_datetime(df["日期"])
        df.set_index("日期", inplace=True)
        df.sort_index(inplace=True)
        s = df["收盘"]
        s.name = symbol
        return s
    except Exception as e:
        print(f"[data_providers] AKShare failed for {symbol}: {e}")
        # 备源: Tushare 中国 QDII ETF (5000积分，有汇率噪声)
        return _get_qdii_etf_proxy(symbol, months)


def _get_qdii_etf_proxy(symbol: str, months: int) -> pd.Series:
    """
    备源：用 Tushare fund_daily 获取中国 QDII ETF 作为美股 ETF 的代理。
    映射关系:
      SPY → 513500.SH (标普500ETF)
      GLD → 518880.SH (黄金ETF)
      TLT → 无直接A股对标，返回空
    """
    proxy_map = {
        "SPY": "513500.SH",   # 标普500ETF
        "GLD": "518880.SH",   # 黄金ETF
    }
    ts_code = proxy_map.get(symbol)
    if not ts_code:
        print(f"[data_providers] No QDII proxy for {symbol}")
        return pd.Series(dtype=float)

    import datetime
    end = datetime.date.today()
    start = end - datetime.timedelta(days=months * 31)
    try:
        items = _tushare_api(
            "fund_daily",
            params={
                "ts_code": ts_code,
                "start_date": start.strftime("%Y%m%d"),
                "end_date": end.strftime("%Y%m%d")
            },
            fields="trade_date,close"
        )
        if items:
            df = pd.DataFrame(items, columns=["trade_date", "close"])
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            df = df.sort_values("trade_date")
            s = pd.Series(df["close"].values, index=df["trade_date"],
                          name=f"{symbol}_proxy_{ts_code}")
            print(f"[data_providers] Using Tushare QDII proxy {ts_code} for {symbol}")
            return s
    except Exception as e:
        print(f"[data_providers] Tushare QDII proxy also failed for {symbol}: {e}")
    return pd.Series(dtype=float)


def get_us_etf_history_long(symbol: str, years: int = 5) -> pd.Series:
    """长周期版本（18 年回测首次下载），与 get_us_etf_history 逻辑相同"""
    import datetime
    end = datetime.date.today()
    start = end - datetime.timedelta(days=years * 366)
    _rate_limit("akshare_long", 2.0)
    try:
        df = ak.stock_us_hist(
            symbol=symbol, period="daily",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            adjust=""
        )
        if df is None or df.empty:
            return pd.Series(dtype=float)
        df["日期"] = pd.to_datetime(df["日期"])
        df.set_index("日期", inplace=True)
        df.sort_index(inplace=True)
        s = df["收盘"]
        s.name = symbol
        return s
    except Exception as e:
        print(f"[data_providers] AKShare long history failed for {symbol}: {e}")
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
```

---

### 第二步：迁移 `core/market_data.py`（约 1.5h，与 v1 相同）

核心改动：`fetch_yfinance_macro()` 中 DXY 分支改用 `get_dxy_history()`（内部主源 Tushare）。

其余逻辑（VIX → FRED、TNX → FRED fallback、信号判定、缓存）不变。

### 第三步：迁移 `core/quant_engine.py`（约 2h，与 v1 相同）

相关性矩阵和蒙特卡洛改用 `get_us_etf_history()` + `get_vix_history()`。

### 第四步：迁移 `core/backtest.py`（约 1h，与 v1 相同）

用 `get_us_etf_history_long()` 替代 `yf.download()`。

### 第五步：清理 + 集成测试（约 1h）

---

## 三、修正后的数据流全景

```
前端请求 /api/macro/spread (VIX)
  → data_engine.get_spread_data()
    → fetch_yfinance_data("^VIX", "vix")
      → (cache hit → 直接返回)
      → (cache miss → fetch_macro_indicator)
        → get_vix_history(days=30)           ← FRED VIXCLS (主源)
        → [fallback] AKShare index_investing_global

前端请求 /api/macro/allocation (需要VIX+TNX+DXY)
  → quant_engine.calculate_asset_allocation()
    → fetch_yfinance_data("^VIX", "vix")     ← 同上，VIX via FRED
    → fetch_yfinance_data("^TNX", "tnx")     ← FRED DGS10
    → fetch_yfinance_data("DX-Y.NYB", "dxy") ← 触发 macro indicator
        → get_dxy_history(days=30)           ← Tushare USDOLLAR.FXCM ⭐ (5000分)
        → [fallback] FRED DTWEXBGS

前端请求 /api/macro/correlation (需要SPY/TLT/GLD/VIX 6个月日线)
  → quant_engine.calculate_correlation_matrix()
    → for SPY: get_us_etf_history("SPY", 6)  ← AKShare (主源)
    → for TLT: get_us_etf_history("TLT", 6)  ← AKShare (主源)
    → for GLD: get_us_etf_history("GLD", 6)  ← AKShare (主源)
    → for VIX: get_vix_history(130)          ← FRED VIXCLS
    → [AKShare 失败时]
        → SPY → Tushare fund_daily(513500.SH) ← 标普500ETF ⭐ (2000分备源)
        → GLD → Tushare fund_daily(518880.SH) ← 黄金ETF ⭐ (2000分备源)
        → TLT → 无可用的中国代理 → 返回空

前端请求 /api/macro/backtest (需要18年数据)
  → backtest.run_backtest()
    → get_symbol_data("SPY", years=18)
      → (SQLite 缓存命中 → 直接返回)
      → (首次 → get_us_etf_history_long("SPY", 18) → AKShare → 存入 SQLite)
```

---

## 四、与 v1 方案的关键差异对照

| 决策点 | v1 方案 | v2 方案 (Tushare 5000分) | 变更理由 |
|:---|:---|:---|:---|
| DXY 主源 | FRED DTWEXBGS | **Tushare fx_daily(USDOLLAR.FXCM)** | USDOLLAR 与 DXY 数值一致（~104），DTWEXBGS 基准不同（~128），避免前端数值跳变 |
| DXY 备源 | 无 | FRED DTWEXBGS | 双重保障 |
| VIX 备源 | 无 | **AKShare index_investing_global** | FRED 不可用时多一层降级 |
| SPY 备源 | 无 | **Tushare fund_daily(513500.SH)** | 当 AKShare 失效时，用标普500ETF代理（含汇率噪声但方向一致） |
| GLD 备源 | 无 | **Tushare fund_daily(518880.SH)** | 黄金ETF备源 |
| TLT 备源 | 无 | 无（不存在中国 QDII 长债 ETF） | TLT 无备源，AKShare 单点依赖 |

---

## 五、实施优先级

| 顺序 | 任务 | 工时 | 依赖 |
|:---|:---|---:|:---|
| 0 | 修复 FRED_API_KEY NameError + 阈值同步 | 0.5h | — |
| 1 | 新建 `core/data_providers.py`（含 Tushare DXY + QDII 备源） | 2.5h | ak + tushare 已安装 |
| 2 | 迁移 `market_data.py` | 1.5h | 步骤0,1 |
| 3 | 迁移 `quant_engine.py` | 2h | 步骤1 |
| 4 | 迁移 `backtest.py` | 1h | 步骤1 |
| 5 | 清理 yfinance + 集成测试 | 1h | 步骤4 |
| **总计** | | **8.5h** | |

---

> 编制人：Claude（Tushare 接口矩阵精确验证 + 数据架构设计）  
> 验证数据：Tushare Pro 官方接口文档（`fx_daily`、`us_daily`、`fund_daily`、`index_global` 权限矩阵）
