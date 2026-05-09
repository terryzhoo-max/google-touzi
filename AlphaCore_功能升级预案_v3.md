# AlphaCore 量化终端 — 功能升级与辅助决策增强预案（第三轮更新）

> 审计日期：2026-05-06（第三轮）  
> 当前版本：v2.3（配置中心化 + 精简架构 + 研报预渲染）

---

## 一、本轮 (Round 3) 变更审查

### 1.1 已实现的上轮建议

| 上轮建议 | 实现状态 | 文件 |
|:---|:---:|:---|
| 统一配置中心 Settings 类 | ✅ | `core/config.py` (新建) |
| 删除邮件订阅系统 (subscribers.db + 路由) | ✅ | `data_engine.py` 移除 `/api/subscribe` 和 `init_db` 引用 |
| 删除冗余测试文件 | ✅ | `test_llm.py`、`test_prompt.py` 已删除 |
| 研报预渲染为静态 HTML | ✅ | `render_reports.py` + `static/reports/*.html` |
| YFinance 批量下载优化 | ✅ | `quant_engine.py` 相关性矩阵改用 `yf.download(tickers, ...)` |
| 依赖锁定版本 | ✅ | `requirements.txt` 所有包均带 `==` 版本号 |
| .gitignore 增强 | ✅ | 追加 `__pycache__/`、`*.pyc`、`alphacore.db` |
| 告警推送简化为单通道 | ✅ | `db.py` 移除订阅者群发，改为管理员自收 |
| 前端移除订阅 UI | ✅ | `index.html` 删除表单和按钮区块，`main.js` 删除表单监听 |

### 1.2 本轮新发现的 Bug

#### 🔴 致命：`market_data.py` 第 25 行 — 未定义变量 `FRED_API_KEY`

```python
# 文件顶部已移除 FRED_API_KEY 的 os.getenv 声明，改为从 settings 读取
# 但 fetch_fred_10y() 第 25 行仍使用旧变量名：
url = f"https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&api_key={FRED_API_KEY}&file_type=json&limit=30&sort_order=desc"
```

`FRED_API_KEY` 在该模块中已不存在（已迁移至 `settings.FRED_API_KEY`），此调用将抛出 `NameError`。**需要立即修复为 `settings.FRED_API_KEY`。**

#### 🟡 中危：`fetch_yfinance_macro` 中的硬编码阈值未同步

```python
# market_data.py 第 167 行 (vix 信号判定) 仍使用硬编码数值 20/30：
if current_val < 20:          # 应为 settings.VIX_CAUTION_THRESH
elif 20 <= current_val < 30:  # 应为 settings.VIX_PANIC_THRESH
```

`config.py` 已定义 `VIX_CAUTION_THRESH=20.0` 和 `VIX_PANIC_THRESH=30.0`，但 `fetch_yfinance_macro` 中 VIX 分支的信号判定未引用 settings。`fetch_fred_10y` 中同样存在此问题（第 47 行 TNX 阈值 3.8/4.5 仍为硬编码）。

#### 🟡 中危：`llm_agent.py` Fallback 逻辑中的硬编码阈值

```python
# llm_agent.py 第 84-87 行  
if vix > 30:                       # 应为 settings.VIX_PANIC_THRESH
elif tnx > 4.5 and dxy > 105:     # 应为 settings.TNX_TIGHT_THRESH
```

#### 🟢 低危：`.gitignore` 文件编码异常

文件内容显示为带 NUL 字节的乱码（如 `__pycache__/` 显示为 `__pycache__/`）。不影响 git 功能但暗示该文件可能被错误编码写入，建议用 UTF-8 without BOM 重建。

#### 🟢 低危：`data_engine.py` 移除了 `init_db` 调用

旧代码在 `startup_event()` 中调用 `init_db()` 初始化订阅者数据库。移除后无副作用（因为 `subscribers.db` 已废弃），但 `backtest.py` 和 `optimize.py` 中分别有各自的 `init_db()` 调用（来自 `db_layer` 模块），两套初始化逻辑互相独立且目前正常工作。

---

## 二、当前架构全景

```
alphacore/
├── .env                          # 密钥（.gitignore 保护）
├── .gitignore                    # git 忽略规则
├── requirements.txt              # 锁定版本的依赖（140行）
├── start_alphacore.bat           # Windows 一键启动脚本
├── render_reports.py             # 研报构建脚本
├── report_template.html          # 研报 HTML 模板
│
├── data_engine.py                # FastAPI 主入口（9条路由）
│
├── core/
│   ├── config.py                 # 🆕 统一配置中心
│   ├── __init__.py               # 空模块（待充实）
│   ├── market_data.py            # 多源数据获取 (FRED/Tushare/YFinance)
│   ├── quant_engine.py           # 量化计算引擎 (配置/相关性/蒙特卡洛)
│   ├── backtest.py               # 18年历史回测引擎
│   ├── llm_agent.py              # DeepSeek AI 决策生成
│   ├── db.py                     # 告警推送 (Server酱 + SMTP)
│   └── db_layer.py               # 时序数据 SQLite 持久层
│
├── static/
│   ├── index.html                # 主面板 (已精简订阅UI)
│   ├── main.js                   # 前端图表逻辑 (已精简表单代码)
│   ├── styles.css                # 暗色 Bloomberg 风格
│   └── reports/                  # 🆕 预渲染研报 HTML
│       ├── liquidity_trap.html
│       ├── ah_premium.html
│       └── vix_hedging.html
│
├── reports/                      # 研报 Markdown 源文件
├── optimize.py                   # 网格搜索参数优化
├── test_system.py                # 集成测试 (6 端点)
├── test.py                       # 单端点快速测试
└── opt_result.txt                # 上次优化结果
```

**路由表：**

| 路由 | 函数 | 来源模块 |
|:---|:---|:---|
| `GET /api/macro/erp` | 10Y 国债数据 + 信号 | `market_data.fetch_yfinance_data` |
| `GET /api/macro/spread` | VIX 数据 + 信号 | `market_data.fetch_yfinance_data` |
| `GET /api/macro/allocation` | 资产配置建议 | `quant_engine.calculate_asset_allocation` |
| `GET /api/macro/correlation` | 相关性风险矩阵 | `quant_engine.calculate_correlation_matrix` |
| `GET /api/macro/montecarlo` | 蒙特卡洛 VaR | `quant_engine.run_montecarlo_sim` |
| `GET /api/macro/ai_insight` | AI 决策洞察 | `llm_agent.generate_llm_insight` |
| `GET /api/macro/backtest` | 18年策略回测 | `backtest.run_backtest` |

---

## 三、行业对标：第三轮聚焦分析

在对标 Bloomberg、Koyfin、TradingView、QuantConnect、Bridgewater 的基础上，结合该项目的**个人量化终端**定位和用户的快速迭代节奏，本轮筛选标准收紧为三条：

1. **单功能闭环** — 不依赖外部账号体系、不引入新的持久层、不需要多用户协作
2. **投资回报比极高** — 核心前提是"200 行后端 + 200 行前端"以内能出效果
3. **填补当前最大的决策盲区** — 选择那些"有了它，用户做决策时信息不对称程度大幅降低"的功能

以这三条标准重新筛过后，以下四个功能胜出：

---

## 四、建议新增：决策增强功能（精选四件套）

### 4.1 利率期限结构面板 — 拆解最重要的衰退时钟

**为什么这是 No.1 优先级：** 2s10s 利差（2年期与10年期美债利差）是全球金融市场上预测衰退准确率最高的单一指标。自 1970 年代以来，每次倒挂后 6-24 个月内均出现衰退。当前系统只监控 10Y 单点值，完全看不到期限结构的倒挂/陡峭化趋势。

**实现：**

后端新增 `core/yield_curve.py`：
```python
# 通过 FRED API 拉取 DGS2, DGS5, DGS10, DGS30 四条期限
# 返回: dates[], curves[{2Y,5Y,10Y,30Y}], spread_2s10s, inversion_days
# 30行核心逻辑 + 缓存
```

前端新增一个 glass-card：
- ECharts 两条折线图：2s10s 利差历史走势 + 红/绿背景色带标识倒挂区间
- 关键信号输出：当前利差(bp)、距零轴距离、连续倒挂天数、历史分位数
- 一句话操作建议联动状态机

**工时：** 后端 2h + 前端 2h  
**新增路由：** `GET /api/macro/yield_curve`

### 4.2 历史情景压力测试 — 回答"再来一次怎么办"

**为什么是 No.2：** 蒙特卡洛模拟给出的是统计分布的 VaR，但用户真正想听到的答案是："2008 年那种情况再来一次，按现在的仓位我亏多少？"历史情景比随机模拟更具叙事力和说服力。

**实现：**

后端新增 `core/scenario.py`：
```python
# 内置三个极端情景的日收益率快照（硬编码为数据字典，不依赖网络）：
# - 2008 全球金融危机 (2008-09-15 至 2009-03-09)
# - 2020 新冠熔断 (2020-02-19 至 2020-03-23)
# - 2022 加息双杀 (2022-01-03 至 2022-10-12)
# 应用当前回测给出的四通道权重，输出每个情景的 P&L/MDD
```

前端新增"压力测试"卡片：
- 三列对比卡片，每列显示情景名称、时长、策略 P&L、基准 P&L、策略/基准 MDD
- 颜色编码（绿色=相对抗跌、红色=策略在此情景下失效）

**工时：** 后端 2h + 前端 1.5h  
**新增路由：** `GET /api/macro/scenario`

### 4.3 多时间框架信号矩阵 — 一屏看清短中长期

**为什么是 No.3：** 当前系统的状态判定是单一时点的二进制输出（"宽松周期"、"紧缩高压"），相当于只给了用户一张照片。实际决策需要看到电影的走向——动量在加速还是减速。

**实现：**

后端新增 `core/signals.py`：
```python
# 为 VIX 和 TNX 计算三个时间窗口的 Z-Score：
# - 短期 (20D)：捕捉动量突破
# - 中期 (60D)：识别趋势方向
# - 长期 (252D)：判断周期位势
# 返回 2x3 信号矩阵
```

前端新增 3x2 小型信号灯卡片（可嵌入现有的 TNX 和 VIX 卡片下方）：
- 三列：短期 / 中期 / 长期
- 两行：利率方向 / 波动方向
- 每个单元格 = 一个红/黄/绿灯 + 一行简短文本

**工时：** 后端 1.5h + 前端 1.5h  
**新增路由：** `GET /api/macro/signals`

### 4.4 Markowitz 有效前沿 — 给用户一张地图

**为什么是 No.4：** AlphaCore 当前给用户一个点（"你应该配 60/30/10"），但没给用户一张地图（"在这个风险水平上，有没有更好的组合？"）。有效前沿就是这张地图。它也是所有机构量化平台的标配功能。

**实现：**

后端新增 `core/portfolio_opt.py`：
```python
# 基于近 5 年 SPY/TLT/GLD 的均值-协方差矩阵
# 使用 scipy.optimize.minimize 求解：
# - 全局最小方差组合 (GMV)
# - 最大夏普比率组合 (Tangency)
# - 随机生成 1000 个组合绘制前沿散点
# 将当前 AlphaCore 策略标注在前沿图上
```

前端新增 ECharts 散点图卡片：
- X 轴：年化波动率
- Y 轴：年化收益率
- 灰色散点：随机组合
- 金色曲线：有效前沿
- 红色星标：GMV
- 绿色星标：AlphaCore 当前策略
- 蓝色星标：最大夏普组合

**工时：** 后端 3h + 前端 2.5h  
**新增路由：** `GET /api/macro/efficient_frontier`

---

## 五、还存在一票否决级的问题 — 优先级高于所有新功能

本轮 Bug 发现中有两件事必须在新功能开发前修复：

1. `market_data.py` 第 25 行 `FRED_API_KEY` → `settings.FRED_API_KEY`（否则 FRED 数据获取全部崩溃）
2. `market_data.py` 中 `fetch_fred_10y()` 和 `fetch_yfinance_macro()` 的信号阈值统一改为引用 `settings`（否则配置中心形同虚设）

---

## 六、实施路线图

| 顺序 | 任务 | 工时 | 类型 |
|:---|:---|---:|:---|
| 0 | 修复 `FRED_API_KEY` NameError + 阈值同步 | 0.5h | 🐛 紧急修复 |
| 1 | 利率期限结构面板 | 4h | ⭐ 新功能 |
| 2 | 历史情景压力测试 | 3.5h | ⭐ 新功能 |
| 3 | 多时间框架信号矩阵 | 3h | ⭐ 新功能 |
| 4 | Markowitz 有效前沿 | 5.5h | ⭐ 新功能 |

完成 0-4 后，AlphaCore 将从一个优秀的**被动监测终端**升级为一个真正的**主动辅助决策系统**。用户可以在一个页面上一屏看完：宏观信号 + 仓位建议 + 风险矩阵 + 极端情景测试 + 组合优化地图。

---

## 七、不建议在当前阶段增加的功能

以下功能虽然在上轮预案中列出，但基于本轮的架构精简思路和投资回报比分析，建议**暂缓**：

| 功能 | 暂缓理由 |
|:---|:---|
| 经济日历 | 需要持续维护事件数据源，个人项目维护成本过高 |
| 条件告警规则引擎 | 需求尚未明确；当前告警已满足核心场景 |
| 持仓跟踪器 | 涉及用户数据输入界面和持久层设计，属于另一个量级的工程 |
| 行业轮动 RRG | 依赖 11 个行业 ETF 的批量数据，单次加载延迟太高 |
| VIX 期限结构 | 当前 yfinance 对 VIX 期货数据支持不稳定，可靠性存疑 |

---

> 编制人：Claude（第三轮全量审查 + 行业对标分析）  
> 审查文件数：22 个源文件 + 3 个预渲染 HTML（100% 覆盖）
