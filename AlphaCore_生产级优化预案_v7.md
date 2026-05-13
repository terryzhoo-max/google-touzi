# AlphaCore — 数据接口与缓存生产级优化预案 v7

> 编制日期：2026-05-13  
> 当前架构：L1 路由缓存 + L2 提供者缓存 + 6 模块 stale cache + SQLite 持久层

---

## 〇、已完成项（确认清单）

| 层级 | 实现 | 状态 |
|:---|:---|:---:|
| L1 路由缓存 | `cache_store.py` — per-key 锁 + 双重检查 + 过期兜底 + 统计埋点 | ✅ |
| L2 提供者缓存 | `data_providers.py` — MACRO 15min / EQUITY 1h 分层 TTL | ✅ |
| HTTP 重试 | `_http_get/_http_post` — 指数退避 3 次 | ✅ |
| Stale Cache | `market_data` / `fed_prob` / `china_macro` / `global_assets` / `valuation` | ✅ |
| 参数校准 | `decision_policy` / `risk_engine` / `allocation_policy` / `factor_risk` | ✅ |
| SQLite 持久层 | `backtest` 18 年数据缓存 | ✅ |
| Provider 统计 | `_provider_stats` → `/api/health` | ✅ |

---

## 一、未完成的高价值生产优化（Top 5）

### 1. 熔断器 (Circuit Breaker)

**问题：** FRED/Tushare 间歇故障时，每次请求仍然尝试 HTTP 调用。连续失败 10 次也不停止。

**方案：** `data_providers.py` 增加模块级熔断状态：
```python
_CIRCUIT_STATE = {"fred": "closed", "tushare_fund": "closed", ...}  # closed/open/half-open
_CIRCUIT_FAILURES = {"fred": 0, ...}
```
- 连续失败 5 次 → `open`（停止 HTTP 5 分钟，直接返回缓存/stale）
- 5 分钟后 → `half-open`（允许 1 次试探请求）
- 试探成功 → `closed`（恢复正常）

**工时：** 1h | **影响：** 防止 API 雪崩

### 2. 启动预热 (Cache Warming)

**问题：** 32 条路由中，后台守护进程只预热 4 条（TNX/VIX/DXY/CSI300）。首次访问 yield_curve/correlation/valuation 等路由时用户等待 2-5 秒。

**方案：** `market_data.py` 的 `on_startup` 增加预热列表：
```python
WARM_UP_ROUTES = ["yield_curve", "correlation", "china_macro", "valuation", "global_assets"]
```
启动后按梯度延迟（间隔 5 秒）依次调用，填充 L1 缓存。

**工时：** 0.5h | **影响：** 首次访问零等待

### 3. 路由超时中间件 (Request Deadline)

**问题：** 无全局超时保护。backtest 在数据缺失时可能无限等待 SQLite 查询。

**方案：** `data_engine.py` 增加 `TimeoutMiddleware`：
```python
ALLOWED_TIMEOUTS = {"backtest": 30, "correlation": 15, "default": 10}
```
超时返回 504 + 提示"请稍后重试或查看 /api/health 状态"。

**工时：** 0.5h | **影响：** 防止单条慢路由阻塞整个 Uvicorn worker

### 4. Provider 降级模式 (Graceful Degradation)

**问题：** 当 FRED 不可用时，依赖 FRED 的 8 条路由全部降级。前端无统一提示。

**方案：** `/api/health` 增加 `degraded_routes` 字段，前端 `freshness-indicator` 在数据源降级时从黄色变为红色。Dashboard 的 zone 信号在数据降级时加 `[降级模式]` 后缀。

**工时：** 0.5h | **影响：** 用户知道自己看到的可能不是最新数据

### 5. 响应压缩 (GZip Middleware)

**问题：** backtest 路由返回 4500 天 × 5 列 JSON，未压缩时约 200KB。

**方案：** FastAPI 内置 `GZipMiddleware`，一行代码：
```python
from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
```

**工时：** 5 分钟 | **影响：** 200KB → ~30KB

---

## 二、优化矩阵

| 优先级 | 功能 | 工时 | 风险 | 影响面 |
|:---:|---|:---:|:---:|:---|
| P0 | GZip 压缩 | 5min | 零 | 所有大响应 |
| P0 | 请求超时中间件 | 0.5h | 低 | 全局保护 |
| P1 | 启动预热 | 0.5h | 低 | 首次访问体验 |
| P1 | 降级模式 | 0.5h | 低 | 用户感知 |
| P2 | 熔断器 | 1h | 中（需测试） | API 保护 |

**总计：约 3h**

---

> 编制人：Claude（全量 37 路由 + 44 模块追踪）
