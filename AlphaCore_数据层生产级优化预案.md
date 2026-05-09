# AlphaCore — 数据接口与缓存层生产级优化预案（机构视角）

> 编制日期：2026-05-06  
> 审计范围：13 个 core/*.py 模块 + data_engine.py 的完整数据流追踪  
> 核心发现：**一次页面加载触发 25+ 次外部 API 调用 + 4 次重复回测**

---

## 〇、关键发现：当前数据流瓶颈测绘

启动 Trace 跟踪一次完整页面加载的 API 调用链：

```
┌─ /api/macro/decision ──────────────────────────────────┐
│  FRED: VIXCLS(30d) + DGS10(30d) + DTWEXBGS(30d)       │
│  FRED: DGS2(60d) + DGS10(60d)     ← yield_curve      │
│  Tushare: SPY(6m) + TLT(6m) + GLD(6m)  ← correlation │
│  Tushare: CSI300(6m)                                   │
│  RUN_BACKTEST() ×1            ← 18年全量计算 ❌ 重复1   │
├────────────────────────────────────────────────────────┤
│ /api/macro/erp   → TNX (cache hit)                     │
│ /api/macro/spread → VIX (cache hit)                    │
├─ /api/macro/yield_curve ──────────────────────────────┤
│  FRED: DGS2(60d) + DGS5(60d) + DGS10(60d) + DGS30(60d)│
│  ❌ DGS2/DGS10 已由 decision 获取过，重复调用            │
├─ /api/macro/allocation ────────────────────────────────┤
│  RUN_BACKTEST() ×1            ← 重复2                  │
├─ /api/macro/correlation ───────────────────────────────┤
│  Tushare: SPY+TLT+GLD(6m) + VIX(130d)                  │
│  ❌ 与 decision 中的 correlation 调用完全相同，重复       │
├─ /api/macro/montecarlo ────────────────────────────────┤
│  Tushare: SPY+TLT+GLD(6m)                              │
│  ❌ 与 correlation 获取的数据同源，重复                   │
├─ /api/macro/efficient_frontier ────────────────────────┤
│  Tushare: SPY+TLT+GLD(12m)                             │
├─ /api/macro/scenario ──────────────────────────────────┤
│  RUN_BACKTEST() ×1            ← 重复3                  │
├─ /api/macro/backtest ──────────────────────────────────┤
│  RUN_BACKTEST() ×1            ← 重复4                  │
├─ /api/macro/signals ──────────────────────────────────┤
│  FRED: VIXCLS(300d) + DGS10(300d)                      │
│  ❌ 与 erp/spread 的 30d 数据同源但粒度不同，仍可复用缓存 │
└────────────────────────────────────────────────────────┘
```

**关键数字：**
- `run_backtest()` 被调用 **4 次**，每次遍历 18 年 × 252 天 = 4536 行数据
- DGS10（10Y）被 FRED 调用 **5 次**（erp, decision, yield_curve, signals, backtest）
- SPY/TLT/GLD 被 Tushare 调用 **4 次**（correlation, montecarlo, efficient_frontier, backtest）
- **估算每次页面加载产生 25-30 次外部 HTTP 调用**

---

## 一、优化方案：三层缓存架构

```
┌──────────────────────────────────────────────────┐
│                  路由层 (data_engine.py)           │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐            │
│  │decision │ │correlat.│ │backtest │  ...       │
│  └────┬────┘ └────┬────┘ └────┬────┘            │
├───────┼──────────┼──────────┼───────────────────┤
│       ▼          ▼          ▼                    │
│  ╔══════════════════════════════════════╗        │
│  ║  L1: 结果缓存 (cache_store.py)      ║        │
│  ║  • per-route TTL                    ║        │
│  ║  • decision: 300s  correlation:3600s║        │
│  ║  • backtest: 86400s  signals:3600s  ║        │
│  ║  • 写入即返回，跳过下游所有 API 调用 ║        │
│  ╚═══════════╤══════════════════════════╝        │
│              │ miss                              │
│  ╔═══════════╧══════════════════════════╗        │
│  ║  L2: 数据缓存 (DATA_CACHE 现有)     ║        │
│  ║  • TNX/VIX/DXY/correlation: 3600s   ║        │
│  ║  • 按 source key 去重               ║        │
│  ╚═══════════╤══════════════════════════╝        │
│              │ miss                              │
│  ╔═══════════╧══════════════════════════╗        │
│  ║  L3: 请求合并 (request_coalescer)   ║        │
│  ║  • 同一 source+params 的并发请求    ║        │
│  ║  • 第一个请求执行，后续请求等待结果  ║        │
│  ╚═══════════╤══════════════════════════╝        │
│              │                                   │
│              ▼                                   │
│  ┌──────────────────────────────────────┐        │
│  │  Provider: FRED / Tushare / DeepSeek │        │
│  └──────────────────────────────────────┘        │
└──────────────────────────────────────────────────┘
```

### 1.1 L1：结果缓存 — 消除 4 次重复回测

**新建 `core/cache_store.py`：** 路由级别的结果缓存。当一个路由产生结果后，后续相同路由的直接返回缓存值。

```python
# 每条路由独立的 TTL
ROUTE_TTL = {
    "decision":      300,   # 5 min  — 综合信号变化慢
    "erp":           3600,  # 1 hour — TNX 每日更新
    "spread":        600,   # 10 min — VIX 日内变化
    "yield_curve":   3600,  # 1 hour
    "allocation":    600,   # 10 min — 依赖 backtest
    "correlation":   7200,  # 2 hours — 日收益率相关性变化慢
    "montecarlo":    1800,  # 30 min
    "efficient_frontier": 3600,  # 1 hour
    "scenario":      600,   # 10 min — 依赖 allocation
    "signals":       3600,  # 1 hour
    "backtest":      86400, # 24 hours — 18年回测只在盘后变化
    "ai_insight":    600,   # 10 min
}
```

**效果：** `run_backtest()` 从每页 4 次降至 1 次。同名路由并发调用从多次 API 调用降为 1 次。

### 1.2 L2：数据缓存增强 — 按 source 粒度去重

**改造 `data_providers.py`：** 当前 `_fred_series` / `_tushare_items` 每次都走 HTTP。增加模块级缓存：

```python
# 以 (source, series_id/ts_code, days) 为 key 的缓存
_PROVIDER_CACHE: dict = {}

def _fred_series_cached(series_id, limit):
    key = f"fred:{series_id}:{limit}"
    now = time.time()
    if key in _PROVIDER_CACHE:
        ts, val = _PROVIDER_CACHE[key]
        if now - ts < settings.CACHE_TTL:
            return val
    result = _fred_series(series_id, limit)  # actual HTTP
    _PROVIDER_CACHE[key] = (now, result)
    return result
```

**效果：** DGS10 从 5 次 FRED 调用降至 1 次。SPY/TLT/GLD 日线从 4 次 Tushare 调用降至 1 次。

### 1.3 L3：请求合并 — 防止并发重复

**在 `data_providers.py` 增加 inflight 请求追踪：** 当两个并发 goroutine 同时请求同一数据时，第二个等待第一个的结果而不是独立发送请求。

```python
import threading
_inflight: dict = {}
_inflight_lock = threading.Lock()

def _fred_series_cached(series_id, limit):
    key = f"fred:{series_id}:{limit}"
    with _inflight_lock:
        if key in _inflight:
            # another request is already fetching this exact data
            fut = _inflight[key]
        else:
            fut = _inflight[key] = threading.Event()
    # ... fetch and signal
```

**效果：** `decision` 路由内并行调用的 VIX/TNX 与外部 `erp`/`spread` 路由的相同调用合并为一次 HTTP。

### 1.4 增加数据新鲜度指标

**新增 `GET /api/health` — 系统健康检查端点：**

```json
{
  "status": "healthy",
  "sources": {
    "fred":       {"status": "ok", "last_success": "2026-05-06T14:30:00", "latency_ms": 234},
    "tushare_fund": {"status": "ok", "last_success": "2026-05-06T14:30:01", "latency_ms": 180},
    "tushare_fx":   {"status": "degraded", "last_error": "SSL timeout", "fallback": "fred_dtwexbgs"},
    "deepseek":   {"status": "ok", "last_success": "2026-05-06T14:30:02"}
  },
  "cache_stats": {
    "l1_hit_ratio": 0.73,
    "l2_hit_ratio": 0.91,
    "backtest_runs_today": 1
  }
}
```

**前端：** Dashboard 底部显示"数据刷新于 14:30"的小字，FRED 不可用时显示黄色"部分数据源降级"。

---

## 二、实施步骤

| 步骤 | 内容 | 工时 | 效果 |
|:---|:---|---:|:---|
| **1** | 新建 `core/cache_store.py` — L1 路由结果缓存装饰器 | 1h | 消除重复回测和重复路由调用 |
| **2** | 改造 `data_providers.py` — L2 提供者缓存 + L3 请求合并 | 1.5h | 外部 API 调用减少 60% |
| **3** | 新增 `GET /api/health` 端点 | 0.5h | 运维可见性 |
| **4** | 前端增加数据新鲜度指示器 | 0.5h | 用户知道数据时效 |
| **总计** | | **3.5h** | API 调用从 25-30 降至 8-10 |

---

## 三、预期效果对比

| 指标 | 当前 | 优化后 |
|:---|:---:|:---:|
| 每页加载外部 API 调用 | 25-30 次 | 8-10 次 |
| `run_backtest()` 调用 | 4 次 | 1 次（24h 缓存） |
| DGS10 FRED 调用 | 5 次 | 1 次 |
| SPY/TLT/GLD Tushare 调用 | 4 次 | 1 次 |
| 首屏渲染时间 (Dashboard) | ~3-5s | ~0.5-1s |
| 数据新鲜度可见 | 无 | 实时显示 |

## 四、不对现有功能产生任何破坏

所有改动为**增量叠加**：
- `cache_store.py` 是在路由函数外包装一层 `@cached(ttl=...)` 装饰器，不修改业务逻辑
- `data_providers.py` 的缓存是在 HTTP 调用前加一层内存查找，命中则跳过 HTTP
- `/api/health` 是纯新增端点，不影响现有路由

---

> 编制人：Claude（全量数据流 Trace 分析）
