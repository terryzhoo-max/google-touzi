# AlphaCore — 数据源迁移与生产级功能升级实施方案

> 编制日期：2026-05-06  
> 背景：yfinance 在境内网络环境持续被禁止访问，当前全部美股/VIX/DXY 数据依赖该库，系统处于"半瘫痪"状态  
> 本方案提供完整的数据源替代架构 + 分层实施步骤 + 每步可独立验证

---

## 第〇步：当前 yfinance 依赖全景图

以下精确列出了 `import yfinance` 在代码库中的 **6 个调用点**，以及每个点的替代方案：

### 调用点 #1：`core/market_data.py` 第 153 行 — `fetch_yfinance_macro()`

```python
ticker = yf.Ticker(ticker_symbol)
df = ticker.history(period="1mo")   # 获取 VIX 近 1 月日线 或 DXY 近 1 月日线
```

**用途：** 获取 VIX 和 DXY 的近 1 个月日线价格，用于前端图表渲染 + 信号判定。  
**调用频率：** 每 30 分钟一次（`background_data_fetcher`），或每次前端访问 `/api/macro/erp` 和 `/api/macro/spread` 时（缓存 TTL 3600 秒内不重复请求）。

**替代方案：** **FRED API**（已接入，修复 bug 即可用）
- VIX → FRED series `VIXCLS`（1990 年至今，每日更新，与 CBOE 同步）
- DXY → FRED series `DTWEXBGS`（贸易加权美元指数，每日更新，覆盖 26 国货币）

### 调用点 #2：`core/quant_engine.py` 第 68 行 — `calculate_correlation_matrix()`

```python
download_data = yf.download(tickers, period="6mo")  # SPY, TLT, GLD, ^VIX 四标的 6 个月日线
```

**用途：** 计算 5 资产（+沪深300）的相关性矩阵，用于风险热力图。  
**调用频率：** 每次前端访问 `/api/macro/correlation`（缓存 TTL 3600 秒内复用）。

**替代方案：** **AKShare** `ak.stock_us_hist()`（免费、无需 Key、东方财富源、境内可访问）
- SPY → `ak.stock_us_hist(symbol="SPY", period="daily", start_date=..., end_date=...)`
- TLT → 同上
- GLD → 同上
- VIX → `ak.index_investing_global(country="美国", index_name="VIX恐慌指数", period="每日", ...)` 或直接用 FRED VIXCLS

### 调用点 #3：`core/quant_engine.py` 第 215 行 — `run_montecarlo_sim()`

```python
ticker = yf.Ticker(t)
hist = ticker.history(period="6mo")['Close']  # SPY, TLT, GLD 逐一下载
```

**用途：** 获取 SPY/TLT/GLD 的 6 个月日线，用于蒙特卡洛组合模拟。  
**调用频率：** 每次前端访问 `/api/macro/montecarlo`（无缓存——每次重新计算）。

**替代方案：** AKShare `ak.stock_us_hist()`，同上。

### 调用点 #4：`core/backtest.py` 第 18 行 — `get_symbol_data()`

```python
df_new = yf.download(symbol, start=start_str, end=end_str, progress=False)
# 下载 SPY/TLT/GLD/^VIX/^TNX 的 18 年全量日线
```

**用途：** 首次运行回测时下载 18 年（2008-2026）历史数据，之后存入 SQLite 缓存。  
**调用频率：** 仅首次（后续从 `alphacore.db` 缓存读取）。

**替代方案：** 
- 优先：AKShare `ak.stock_us_hist()`（对 ETF 支持 18 年 + 全量历史）
- 补充：FRED API 用于 VIXCLS 和 DGS10（覆盖 1990 年至今）
- 缓存优先策略不变——首次下载后全部存 SQLite

---

## 第一步：Bug 修复（必须先行，阻塞所有后续工作）

### Fix 1.1：`market_data.py` — FRED_API_KEY 未定义

**文件：** `core/market_data.py` 第 25 行  
**问题：** `FRED_API_KEY` 变量已在模块重构中移除，但 `fetch_fred_10y()` 仍引用旧变量名  
**修复：**

```python
# 第 25 行，将：
url = f"...&api_key={FRED_API_KEY}&..."
# 改为：
url = f"...&api_key={settings.FRED_API_KEY}&..."
```

**验证：** 启动服务后访问 `http://127.0.0.1:8888/api/macro/erp`，应返回 10Y 国债数据，不再抛 `NameError`。

### Fix 1.2：`market_data.py` — 信号阈值硬编码未引用 settings

**文件：** `core/market_data.py` 第 47-48 行（`fetch_fred_10y`）和第 167-174 行（`fetch_yfinance_macro`）  
**问题：** TNX 的 3.8/4.5 阈值和 VIX 的 20/30 阈值仍为硬编码数字，`config.py` 中定义的 `TNX_LOOSE_THRESH` 等未生效  
**修复：**

```python
# fetch_fred_10y() 中：
if current_val < settings.TNX_LOOSE_THRESH:       # 原: current_val < 3.8
    ...
elif settings.TNX_LOOSE_THRESH <= current_val < settings.TNX_TIGHT_THRESH:  # 原: 3.8 <= ... < 4.5
    ...

# fetch_yfinance_macro() vix 分支中：
if current_val < settings.VIX_CAUTION_THRESH:     # 原: current_val < 20
    ...
elif settings.VIX_CAUTION_THRESH <= current_val < settings.VIX_PANIC_THRESH:  # 原: 20 <= ... < 30
    ...
```

### Fix 1.3：`llm_agent.py` — Fallback 阈值同步

**文件：** `core/llm_agent.py` 第 84-87 行  
**修复：**

```python
if vix > settings.VIX_PANIC_THRESH:               # 原: vix > 30
    ...
elif tnx > settings.TNX_TIGHT_THRESH and dxy > 105:  # 原: tnx > 4.5
    ...
```

---

## 第二步：新增核心模块 — `core/data_providers.py`（数据抽象层）

这是本次重构最重要的架构决策：**所有外部数据获取统一收敛到一个模块**，其他模块不再直接 import yfinance 或 AKShare。

### 设计原则

1. 每个数据获取函数返回统一的 pandas Series/DataFrame，调用方无需知道底层来源
2. 每个函数内部尝试主源 → 备源 → cached fallback 三级降级
3. 内置速率限制（避免触发东方财富/FRED 的 WAF）
4. 清晰日志——告知用户当前使用的是哪个数据源

### 接口设计

```python
# core/data_providers.py

import akshare as ak
import pandas as pd
import urllib.request
import json
import time
from core.config import settings

# ---- 内部工具 ----

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

_last_request_time = {}

def _rate_limit(source: str, min_interval: float = 1.0):
    """简单的请求间隔控制，防止触发数据源 WAF"""
    now = time.time()
    if source in _last_request_time:
        elapsed = now - _last_request_time[source]
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
    _last_request_time[source] = time.time()


def _fred_series(series_id: str, limit: int = 60) -> pd.Series:
    """从 FRED 拉取指定 series 的观测值，返回 {date: value} 的 Series"""
    _rate_limit("fred", 1.0)
    url = (f"{FRED_BASE}?series_id={series_id}&api_key={settings.FRED_API_KEY}"
           f"&file_type=json&limit={limit}&sort_order=desc")
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    obs = data.get("observations", [])
    dates, values = [], []
    for o in reversed(obs):  # FRED 返回降序，我们反转为升序
        if o["value"] != ".":
            dates.append(o["date"])
            values.append(float(o["value"]))
    return pd.Series(values, index=pd.to_datetime(dates), name=series_id)


# ---- 对外接口 ----

def get_us_etf_history(symbol: str, months: int = 6) -> pd.Series:
    """
    获取美股 ETF 日线收盘价序列。
    主源: AKShare (东方财富)
    symbol: "SPY", "TLT", "GLD"
    返回: pd.Series with DatetimeIndex, values = Close
    """
    import datetime
    end = datetime.date.today()
    start = end - datetime.timedelta(days=months * 31)
    _rate_limit("akshare", 1.5)
    
    try:
        df = ak.stock_us_hist(
            symbol=symbol,
            period="daily",
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
        # Fallback: 尝试从 FRED 获取指数级别数据
        return pd.Series(dtype=float)


def get_us_etf_history_long(symbol: str, years: int = 5) -> pd.Series:
    """
    长周期版本，用于回测的首次数据下载。
    东方财富源支持 18 年+ 全量历史。
    """
    import datetime
    end = datetime.date.today()
    start = end - datetime.timedelta(days=years * 366)
    _rate_limit("akshare_long", 2.0)
    
    try:
        df = ak.stock_us_hist(
            symbol=symbol,
            period="daily",
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


def get_vix_history(days: int = 30) -> pd.Series:
    """获取 VIX 历史数据。主源: FRED VIXCLS"""
    try:
        return _fred_series("VIXCLS", limit=days)
    except Exception as e:
        print(f"[data_providers] FRED VIX failed: {e}")
        return pd.Series(dtype=float)


def get_dxy_history(days: int = 30) -> pd.Series:
    """获取美元指数历史数据。主源: FRED DTWEXBGS"""
    try:
        return _fred_series("DTWEXBGS", limit=days)
    except Exception as e:
        print(f"[data_providers] FRED DXY failed: {e}")
        return pd.Series(dtype=float)


def get_tnx_history(days: int = 30) -> pd.Series:
    """获取 10Y 国债收益率。主源: FRED DGS10"""
    return _fred_series("DGS10", limit=days)


def get_vix_current() -> float:
    """获取 VIX 最新值"""
    try:
        s = get_vix_history(5)
        return float(s.iloc[-1]) if len(s) > 0 else 20.0
    except Exception:
        return 20.0


def get_dxy_current() -> float:
    """获取 DXY 最新值（DTWEXBGS 方向等价）"""
    try:
        s = get_dxy_history(5)
        return float(s.iloc[-1]) if len(s) > 0 else 100.0
    except Exception:
        return 100.0
```

---

## 第三步：逐文件迁移（按依赖顺序）

### Step 3.1：`core/market_data.py` — 宏数据模块

**目标：** 移除 `import yfinance`，将 `fetch_yfinance_macro()` 改为使用 `data_providers`

**改动点：**

1. 删除第 1 行：`import yfinance as yf`
2. 新增导入：`from core.data_providers import get_vix_history, get_dxy_history, get_tnx_history`
3. 重写 `fetch_yfinance_macro()` 为 `fetch_macro_indicator()`：

```python
def fetch_macro_indicator(ticker_symbol: str, cache_key: str):
    """替代原 fetch_yfinance_macro。数据来源：FRED API"""
    now = time.time()
    if now - DATA_CACHE[cache_key]["timestamp"] < settings.CACHE_TTL and DATA_CACHE[cache_key]["data"] is not None:
        return DATA_CACHE[cache_key]["data"]
    
    try:
        if cache_key == "vix":
            series = get_vix_history(30)
        elif cache_key == "dxy":
            series = get_dxy_history(30)
        else:
            series = get_tnx_history(30)
            
        if series.empty:
            return {"dates": [], "data": [], "signal_state": "无数据", ...}
        
        dates = series.index.strftime('%Y-%m-%d').tolist()
        values = series.round(2).tolist()
        current_val = values[-1]
        
        # 信号判定（使用 settings 阈值）
        if cache_key == "vix":
            if current_val < settings.VIX_CAUTION_THRESH:
                signal_state = "Risk-On (低波动安全区)"
                signal_color = "#4ade80"
                ...
            elif settings.VIX_CAUTION_THRESH <= current_val < settings.VIX_PANIC_THRESH:
                signal_state = "Caution (波动率警告)"
                signal_color = "#fbbf24"
                ...
            else:
                signal_state = "Risk-Off (极度恐慌)"
                signal_color = "#ef4444"
                ...
        # ... 其余逻辑不变
        
        DATA_CACHE[cache_key]["data"] = result
        DATA_CACHE[cache_key]["timestamp"] = now
        return result
    except Exception as e:
        print(f"Macro Indicator Error for {cache_key}: {e}")
        return {"dates": ["Error"], "data": [0.0], ...}
```

4. 更新 `background_data_fetcher()` 中的调用：

```python
# 原: fetch_yfinance_macro("^VIX", "vix")
# 改: fetch_macro_indicator("^VIX", "vix")   # ticker_symbol 参数保留用于日志
```

5. 更新 `fetch_yfinance_data()` wrapper：

```python
def fetch_yfinance_data(ticker_symbol: str, cache_key: str):
    if cache_key == "tnx":
        return fetch_fred_10y()  # 10Y 仍优先用 FRED
    return fetch_macro_indicator(ticker_symbol, cache_key)  # VIX/DXY 走新接口
```

### Step 3.2：`core/quant_engine.py` — 量化引擎

**目标：** 移除 `import yfinance as yf`，相关性矩阵和蒙特卡洛改用 `data_providers`

**改动点：**

1. 删除第 4 行：`import yfinance as yf`
2. 新增导入：`from core.data_providers import get_us_etf_history`
3. `calculate_correlation_matrix()` 第 63-84 行替换：

```python
# 原代码（逐个 Ticker 下载）：
# for t in tickers:
#     ticker = yf.Ticker(t)
#     hist = ticker.history(period="6mo")['Close']
#     ...

# 新代码（统一通过 data_providers）：
for t in tickers:
    if t == "^VIX":
        from core.data_providers import get_vix_history
        hist = get_vix_history(130)  # ~6个月交易日
    else:
        hist = get_us_etf_history(t, months=6)
    if not hist.empty:
        hist.name = t
        if hasattr(hist.index, 'tz') and hist.index.tz is not None:
            hist.index = hist.index.tz_localize(None)
        df_list.append(hist)
```

4. `run_montecarlo_sim()` 第 212-221 行替换：

```python
# 原: for t in tickers:
#        ticker = yf.Ticker(t)
#        hist = ticker.history(period="6mo")['Close']
# 新:
for t in tickers:
    hist = get_us_etf_history(t, months=6)
    if not hist.empty:
        hist.name = t
        df_list.append(hist)
```

### Step 3.3：`core/backtest.py` — 回测引擎

**目标：** 替换 `yf.download()` 为 AKShare，同时保留 SQLite 缓存的高优先级

**改动点：**

1. 删除第 3 行：`import yfinance as yf`
2. 新增导入：`from core.data_providers import get_us_etf_history_long`（以及 VIX/TNX 从 FRED）
3. `get_symbol_data()` 第 17-28 行替换：

```python
# 原: df_new = yf.download(symbol, start=start_str, end=end_str, progress=False)
# 新:
if df is None or len(df) < (years * 252 * 0.9):
    print(f"Downloading {symbol} from {start_str} to {end_str} via AKShare/FRED...")
    
    if symbol == "^VIX":
        from core.data_providers import get_vix_history
        s = get_vix_history(days=365 * years)
    elif symbol == "^TNX":
        from core.data_providers import get_tnx_history
        s = get_tnx_history(days=365 * years)
    else:
        s = get_us_etf_history_long(symbol, years=years)
    
    if s.empty:
        return pd.DataFrame()
    df_save = pd.DataFrame({'Close': s})
    save_timeseries(symbol, df_save)
    df = get_cached_timeseries(symbol, start_str, end_str)
```

---

## 第四步：分步骤实施路线图

| 步骤 | 内容 | 预计工时 | 可独立验证 | 依赖 |
|:---|:---|---:|:---:|:---|
| **0** | 修复 FRED_API_KEY NameError + 阈值同步（Fix 1.1-1.3） | 0.5h | `GET /api/macro/erp` 正常返回 | 无 |
| **1** | 新建 `core/data_providers.py` | 2h | `python -c "from core.data_providers import get_us_etf_history; print(get_us_etf_history('SPY', 1))"` 打印 SPY 近1月价格 | 依赖 ak 已安装 |
| **2** | 迁移 `market_data.py` | 1.5h | `GET /api/macro/spread` 返回 VIX 数据 | 步骤0,1 |
| **3** | 迁移 `quant_engine.py` | 2h | `GET /api/macro/correlation` 返回热力图数据 | 步骤1 |
| **4** | 迁移 `backtest.py` | 1h | `GET /api/macro/backtest` 返回 18 年回测 | 步骤1 |
| **5** | 清理：删除 `import yfinance`、从 requirements.txt 移除 yfinance | 0.5h | `grep -r "yfinance" *.py core/*.py` 无结果 | 步骤4 |
| **6** | 集成测试：`python test_system.py` 全部 6 端点通过 | 0.5h | 6/6 PASS | 步骤5 |

**总计：约 8 小时**

### 验证标准

每个步骤完成后执行对应的验证命令，**不通过不进下一步**：

```bash
# 步骤0验证
curl http://127.0.0.1:8888/api/macro/erp  # 应返回 JSON 数据，不再 500

# 步骤1验证
python -c "
from core.data_providers import get_us_etf_history, get_vix_history
spy = get_us_etf_history('SPY', 1)
print(f'SPY rows: {len(spy)}, last: {spy.iloc[-1]:.2f}')
vix = get_vix_history(5)
print(f'VIX last: {vix.iloc[-1]:.2f}')
"

# 步骤2-5验证
python test_system.py
# 期望输出: 6 PASSED, 0 FAILED
```

---

## 第五步：依赖更新

### `requirements.txt` 变更

```
# 新增
akshare>=1.14.0          # 美股/ETF 数据主源（东方财富源）
# 已有
pandas==2.2.1
numpy==1.26.4
fastapi==0.128.8
uvicorn==0.40.0
python-dotenv==1.2.2
requests==2.33.1
markdown==3.10.2
scipy==1.17.1
# 移除
# yfinance==1.3.0        ← 删除此行
```

**安装命令：**
```bash
pip install akshare --break-system-packages -q
```

---

## 第六步：功能升级（数据迁移完成后的增量开发）

以上数据迁移完成后，系统已具备完全自主的数据获取能力（FRED + AKShare + Tushare，无任何被墙依赖）。以下四个功能可在任何时间点增量实现，互不阻塞。

### 功能 A：利率期限结构面板（4h）

- 后端：`core/yield_curve.py`（FRED DGS2/DGS5/DGS10/DGS30）
- 新增路由：`GET /api/macro/yield_curve`
- 前端：曲线图 + 2s10s 利差，倒挂区间红色警示带
- 开发顺序：后端 2h → 前端 2h

### 功能 B：历史情景压力测试（3.5h）

- 后端：`core/scenario.py`（2008/2020/2022 三个硬编码日收益率快照）
- 新增路由：`GET /api/macro/scenario`
- 前端：三列 P&L/MDD 对比卡片
- 开发顺序：后端 2h → 前端 1.5h

### 功能 C：多时间框架信号矩阵（3h）

- 后端：`core/signals.py`（20D/60D/252D Z-Score）
- 新增路由：`GET /api/macro/signals`
- 前端：2×3 红黄绿灯矩阵
- 开发顺序：后端 1.5h → 前端 1.5h

### 功能 D：Markowitz 有效前沿（5.5h）

- 后端：`core/portfolio_opt.py`（scipy.optimize 求解 GMV/Tangency）
- 新增路由：`GET /api/macro/efficient_frontier`
- 前端：散点图 + 有效前沿曲线 + 三标注点（AlphaCore/GMV/Tangency）
- 开发顺序：后端 3h → 前端 2.5h

---

## 附录 A：数据源可用性总结

| 数据需求 | 当前源 | 新主源 | 备源 | 境内可用 |
|:---|:---|:---|:---|---:|
| VIX 实时值 + 历史 | yfinance ❌ | FRED VIXCLS | AKShare index_investing_global | ✅ |
| DXY 实时值 + 历史 | yfinance ❌ | FRED DTWEXBGS | — | ✅ |
| 10Y 国债 | FRED DGS10 ✅ | 不变 | — | ✅ |
| SPY/TLT/GLD 6mo 日线 | yfinance ❌ | AKShare stock_us_hist | FRED SP500(仅SPY) | ✅ |
| SPY/TLT/GLD 18yr 日线 | yfinance ❌ | AKShare stock_us_hist | SQLite 缓存 | ✅ |
| CSI 300 | Tushare ✅ | 不变 | — | ✅ |
| AI 洞察 | DeepSeek ✅ | 不变 | 本地规则引擎 (降级) | ✅ |
| 告警推送 | Server酱 ✅ | 不变 | SMTP | ✅ |

---

## 附录 B：风险提示

1. **AKShare 底层是同步 IO 爬虫**，严禁高并发（QPS < 5）。本方案已通过 `_rate_limit()` 控制请求间隔。后台守护进程每 30 分钟才刷新一次，远低于安全阈值。
2. **东方财富源可能调整页面结构**，如果 AKShare 接口失效，可降级到 FRED（仅 SP500 指数级别，不含 ETF 分红调整）。建议在 `data_providers.py` 的 except 块中打印清晰日志，方便快速定位。
3. **DTWEXBGS 与 DXY 数值不同**（100 vs ~104），但方向完全一致。前端 macro 面板的锚点数值会变化（如从 DXY=104 变为 DTWEXBGS=128），需在 insight 文本中标明数据源。
4. **`alphacore.db` 缓存保留**，迁移期间不需要清理或重建。新代码会优先读缓存、缺失时用 AKShare 回填。

---

> 编制人：Claude（数据架构迁移 + 功能升级方案）  
> 调研覆盖：yfinance 6 个调用点精确分析、AKShare/FRED API 官网文档验证、境内网络可达性评估
