# AlphaCore — 机构级打磨优化方案 v6

> 编制日期：2026-05-07  
> 审计方法：全量 22 路由 × 20 模块的逐行一致性检查  
> 核心发现：**功能广度已达 Bloomberg 60% 水平，但代码一致性和容错性需要机构级收紧**

---

## 一、逐模块问题清单

### 1.1 代码模式重复（架构债）

| 文件 | 重复内容 | 根因 |
|:---|:---|:---|
| `sector_rotation.py` L40-67 | 4-date 快照循环逻辑 | 与 `asset_rotation.py` `_compute_rotation()` 完全相同 |
| `global_assets.py` L33-80 | 逐资产独立 `_tushare_items` 调用 | 可用 `asset_rotation._compute_rotation` 模式批量获取 |
| `china_macro.py` L28-46, L51-69 | 列名自动检测（`date_col`/`val_col` 推断） | 应抽取为 `_safe_parse_ts_items()` 共享函数 |

**影响：** 任何 Tushare API 字段变更需要修改 3 个文件。`asset_rotation.py` 已有 `_compute_rotation()` 是正确模式，但 `sector_rotation.py` 和 `global_assets.py` 未复用。

**修复：** 将 `_compute_rotation()` 提升为 `data_providers.py` 的公共函数 `get_multi_asset_snapshot()`，三个模块共享。

---

### 1.2 决策信号维度缺失（能力债）

| 问题 | 现状 | 影响 |
|:---|:---|:---|
| 决策信号仅 5 个美国因子 | VIX/TNX/曲线/相关性/象限 | 中国 CPI/PMI/M2/GDP 数据已就绪但未参与决策 |
| 无"中国宏观方向"因子 | china_macro 面板独 | Dashboard 信号在 A 股极端行情时可能给出错误方向 |
| 无估值因子 | valuation 面板独 | PE 分位 90%+ 的泡沫区间，决策信号仍可能显示"买入" |

**修复：** `decision_signal.py` 增加第 6 因子"中国宏观方向"（权重 10%，从 china_macro 数据推导），调整现有 5 因子权重。增加第 7 因子"估值分位"（权重 5%，PE 分位>80% 扣分）。

---

### 1.3 前端 JS 模式不统一（一致性债）

| 模块 | 当前模式 | 问题 |
|:---|:---|:---|
| sector/theme/domestic/global ETF | `initTreemapChart(id, url, ...)` 共享函数 | ✅ 用户重构后的正确模式 |
| Fed prob / ChinaMacro / MarketBreadth / Valuation / GlobalAssets | 各自独立 `initXxx()` 函数 | ❌ 每函数 20-40 行，大量重复的 fetch/error/indicator 更新逻辑 |

**修复：** 抽取 `async function initPanel({chartId, url, indicatorId, insightId, render})` 共享包装器，减少 main.js 约 200 行重复代码。

---

### 1.4 容错性不均（可靠性债）

| 模块 | 容错等级 | 问题 |
|:---|:---:|:---|
| `data_providers.py` | ⭐⭐⭐⭐⭐ | HTTP 重试 + L2 缓存 + 统计 — 机构级 |
| `market_data.py` | ⭐⭐⭐⭐ | 过期缓存兜底 — 良好 |
| `china_macro.py` | ⭐⭐ | CPI/PMI 失败后静默 `continue`，前端显示"无数据" |
| `global_assets.py` | ⭐⭐ | 14 个资产逐个 try/except，一个失败不影响其他，但失败原因不可见 |
| `fed_prob.py` | ⭐⭐ | FRED 失败后硬编码 5.25%/5.00% 作为默认值，无日志 |
| `valuation.py` | ⭐⭐ | `index_dailybasic` 不可用时静默跳过，前端空白 |

**修复：** 
- 对关键模块（china_macro/fed_prob）增加过期缓存兜底（参考 market_data.py 的 stale cache 模式）
- global_assets 失败时在前端显示"▲ 数据暂不可用"而非静默缺行

---

### 1.5 Fed 利率概率名副其实（功能债）

**当前实现：** 利率历史折线图 + FOMC 虚线标记。  
**机构对标：** CME FedWatch 显示的是"概率分布"——下次会议加息 25bp 的概率 XX%，降息的概率 YY%。

**修复：** 从 2Y 国债收益率与当前联邦基金利率的利差，推导简单的市场隐含概率：
- 利差 < -50bp → 降息概率 70%+
- 利差 > 25bp → 加息概率 60%+
- 利差在中间 → 按兵不动概率高  
在图表右侧增加概率条形图子图。

---

## 二、优化优先级矩阵

| 优先级 | 条目 | 工时 | 影响类型 | 交付效果 |
|:---:|---|:---:|:---|:---|
| P0 | 决策信号增加中国因子 | 1.5h | 决策质量 | Dashboard 信号包含中国维度 |
| P1 | `_compute_rotation` 提升为公共函数 | 1h | 架构一致性 | sector/asset/global 三模块共享 |
| P1 | 前端 JS `initPanel` 共享包装器 | 1.5h | 代码质量 | main.js 减少 200 行 |
| P2 | china_macro + fed_prob 过期缓存兜底 | 1h | 可靠性 | CPI/PMI 不可用时显示"上次数据 (5分钟前)" |
| P2 | Fed 概率计算（利差→概率） | 1.5h | 功能完整 | 图表右侧增加概率条形图 |
| P3 | global_assets 容错展示 | 0.5h | 体验 | 失败行显示"▲"而非缺行 |

**合计：约 7h，可分两轮执行。**

---

## 三、本轮不做的优化（原因）

| 项目 | 暂缓原因 |
|:---|:---|
| main.js 拆分为多文件 | 需要引入模块打包器（webpack/vite），工作量 ×5 |
| 市场宽度改用真涨跌比 | Tushare `limit_list` API 权限需要 6000+ 积分，5000 积分可能不可用 |
| 数据库迁移机制 | 当前两个 SQLite 表结构稳定，无变更需求 |
| WebSocket 实时推送 | 当前 30min 轮询 + L1 缓存足够，实时性非个人终端刚需 |

---

> 编制人：Claude（全量架构一致性审计）
