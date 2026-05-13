# AlphaCore — 收尾优化预案 v8（机构优先级排序）

> 编制日期：2026-05-13  
> 背景：7 份预案 90% 已实施，剩余 4 项收尾

---

## 优先级排序

| 优先级 | 项目 | 工时 | 理由 |
|:---:|---|:---:|:---|
| **P0** | 熔断器 (Circuit Breaker) | 1h | 当前 FRED/Tushare 间歇故障时会持续重试直到超时。生产系统须有自保能力。 |
| **P1** | 自定义告警规则引擎 | 4h | 从"被动看面板"到"主动推警示"的质变。机构终端的核心差异化能力。 |
| **P2** | 降级模式指示器 | 0.5h | 数据源降级时 Dashboard 透明告知用户，建立信任。 |
| **P3** | 经济意外指数 | 3.5h | 宏观数据 beat/miss 追踪。需额外调研数据源。 |

---

## P0：熔断器（1h）

### 规则

FRED / Tushare 每个 provider 独立熔断：

```
连续失败 5 次 → 熔断打开 (open) → 跳过 HTTP，直接返回 stale cache → 持续 5 分钟
5 分钟后 → 半开 (half-open) → 允许 1 次试探请求
试探成功 → 关闭 (closed) → 恢复正常
试探失败 → 回到 open → 再等 5 分钟
```

### 实现

`data_providers.py` 增加模块级状态字典：

```python
_CIRCUIT = {
    "fred": {"state": "closed", "failures": 0, "opened_at": 0},
    "tushare_fund": {"state": "closed", "failures": 0, "opened_at": 0},
    ...
}
```

`_fred_series()` 和 `_tushare_items()` 在 HTTP 调用前检查熔断状态，失败后记录。

### 前端联动

`/api/health` 返回 `circuit_state`，Dashboard 新鲜度指示器在熔断时显示 `⚠ 数据源熔断中`。

---

## P1：自定义告警规则引擎（4h）

### 规则

6 条预定义条件规则，用户可通过 UI 开关 + 调阈值：

| 规则 ID | 条件 | 默认阈值 | 推送方式 |
|:---|:---|:---|:---|
| `vix_spike` | VIX > X | 30 | 前端横幅 + Server酱 |
| `tnx_tight` | TNX > X | 4.5% | 同上 |
| `curve_invert` | 2s10s < X bp | -50bp | 同上 |
| `dual_kill` | SPY-TLT corr > X | 0.3 | 同上 |
| `valuation_extreme` | PE分位 > X% | 90% | 同上 |
| `flow_outflow` | 北向5日 < X 亿 | -100 | 同上 |

### 实现

**后端：** `core/alert_rules.py`
- 规则定义存入 `alert_rules.json`（可读写）
- 后台守护进程每 5 分钟评估一次
- 触发时调用 `core/db.py` 的 `trigger_emergency_alert()` 推送

**前端：** 告警中心面板新增"规则配置"区
- 每条规则一行：开关 + 阈值滑块 + 当前值 + 推送方式选择
- 新增路由：`GET /api/alerts/rules` + `PUT /api/alerts/rules`

### 预期效果

用户设定 `VIX > 28` 时推送微信。某天 VIX 飙到 32 → 手机收到 `🔴 VIX 飙升至 32.5，超过阈值 28`。

---

## P2：降级模式指示器（0.5h）

### 规则

Dashboard 新鲜度指示器根据 `/api/health` 返回的状态切换：

- `● 数据正常` — 所有 provider error_rate < 30%
- `⚠ 部分降级` — 1+ provider error_rate > 30%
- `🔴 严重降级` — 2+ provider error_rate > 50% 或熔断打开

### 实现

`initDashboard()` 中已有的 `freshnessCheck` 逻辑增强为三态。同时在 Dashboard 首屏增加一条降级横幅（与警示横幅同风格，但黄色背景）。

---

## P3：经济意外指数（3.5h）

### 规则

Bloomberg/Citi CESI 风格：计算过去 90 天关键经济数据的实际值 vs 预期值的标准化 Z-Score 累计和。

### 数据源

需调研 FRED 中是否有预期值字段。若无，可用以下替代方案：
- 使用历史均值作为"预期"代理
- 或接入外部 API（如 Nasdaq Data Link 的 CESI 数据）

### 实现

`core/surprise_index.py` → `GET /api/macro/surprise_index`  
前端新增 ECharts 累计折线图卡片。

**因数据源未确定，本期仅列为远期规划。**

---

## 实施建议

**本轮（约 5.5h）：P0 + P1 + P2**  
完成后 AlphaCore 具备：生产级自保（熔断）+ 主动推送（告警规则）+ 透明状态（降级指示）

**远期（待数据源）：P3**  

---

> 编制人：Claude
