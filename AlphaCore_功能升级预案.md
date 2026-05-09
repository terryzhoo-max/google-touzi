# AlphaCore 量化终端 — 功能升级与辅助决策增强预案

> 编制日期：2026-05-06  
> 编制方法：对比 Bloomberg Terminal / Koyfin / QuantConnect / Bridgewater 全天候 / TradingView 五类业界标杆系统的功能矩阵，结合 AlphaCore 当前架构能力，提出增、改、删三类建议

---

## 一、变动审查：上次审计后已修复项

更新至本次审查，以下上一次审计报告中 P0/P1 级别问题已经解决：

| 问题 | 修复状态 |
|:---|:---|
| API 密钥硬编码 | ✅ 迁移至 `.env` + `python-dotenv`（`market_data.py`、`db.py`、`llm_agent.py`） |
| `.env` 加入 `.gitignore` | ✅ 已配置 |
| Tushare HTTP → HTTPS | ✅ 两处调用均已改为 `https://api.tushare.pro` |
| 前端 StaticFiles 全目录暴露 | ✅ 改为 `directory="static"`，前端资源已移入 `static/` 子目录 |
| SQL 注入（`db_layer.py`） | ✅ 已改为参数化查询 `params=(symbol, start_date, end_date)` |
| 后台守护进程无优雅关闭 | ✅ 引入 `asyncio.Event` + `shutdown_event` + `asyncio.wait_for` |
| LLM Agent `KeyError: -1` Bug | ✅ 引入 `safe_get_last()` 健壮的缓存读取函数 |
| `test_system.py` 端点名不匹配 | ✅ `spreads→spread`、`ai_cio→ai_insight`、`cio_insight→insight` 均已修正 |
| 蒙特卡洛单资产 GBM 简化 | ✅ 已升级为多元正态分布 + 协方差矩阵 (`np.random.multivariate_normal`) |
| 蒙特卡洛无风险利率硬编码 | ✅ 改为动态读取 TNX 缓存 (`tnx_rate / 100 / 252`) |
| `optimize.py` 基线参数不一致 | ✅ 已对齐为回测默认参数 `(25, 200, [0.6,0.3,0.1,0], [0,0.8,0.2,0], [0,0,0.4,0.6])` |

**遗留待处理：**

| 问题 | 说明 |
|:---|:---|
| `python-dotenv` 未加入 `requirements.txt` | `.env` 加载依赖 `pip install python-dotenv`，但 `requirements.txt` 未列出 |
| `.gitignore` 文件编码异常 | 文件内容显示为 `��.env` 乱码，可能是编码问题 |
| `core/__init__.py` 仍为空 | 无模块公开 API 导出 |
| 缺少单元测试 | 核心计算逻辑无独立测试覆盖 |
| `requirements.txt` 无版本锁定 | 依赖可能漂移 |

---

## 二、对标分析：五大业界标杆系统的辅助决策功能矩阵

将 AlphaCore 当前能力与五类标杆系统逐项对标：

| 功能维度 | Bloomberg | Koyfin | TradingView | QuantConnect | Bridgewater | **AlphaCore 当前** |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| 宏观数据仪表盘 | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ TNX/VIX/DXY |
| 资产配置建议 | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ 四通道状态机 |
| 相关性风险矩阵 | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ 5资产热力图 |
| 蒙特卡洛 VaR | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ 多元GBM |
| 历史回测 | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ 18年回测 |
| AI 决策洞察 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ DeepSeek LLM |
| 告警推送 | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ SMTP + 微信 |
| **利率期限结构 (Yield Curve)** | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| **经济日历 / 事件风险** | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| **因子归因分析** | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ |
| **历史情景压力测试** | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ |
| **行业轮动热力图** | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| **Markowitz 有效前沿** | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ |
| **多时间周期信号** | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| **条件告警规则引擎** | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **持仓跟踪 (Portfolio Tracker)** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| **新闻情绪分析** | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| **波动率期限结构** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |

---

## 三、建议新增的辅助决策功能（按投资回报比排序）

### 第一梯队：高价值 / 低成本（建议本月实现）

#### 3.1 利率期限结构面板 (Yield Curve Dashboard)

**行业对标：** 美联储官网 Yield Curve、Bloomberg GC function

**当前不足：** 仅监控单一 10Y 利率，无法判断期限结构的倒挂/陡峭化趋势。2s10s 利差是全世界最重要的衰退先行指标。

**实现方案：**
- 后端新增 `core/yield_curve.py`：通过 FRED API 拉取 DGS2、DGS5、DGS10、DGS30 四条关键期限利率
- 前端新增曲线卡片：ECharts 折线图，X 轴为期限 (2Y/5Y/10Y/30Y)，Y 轴为收益率，支持历史动画回放（点击可看到曲线从一年前到今天的形变动画）
- 关键信号输出：2s10s 利差当前值、历史分位数、倒挂持续天数
- 工作量：后端 2h + 前端 2h

#### 3.2 历史情景压力测试 (Scenario Engine)

**行业对标：** Bloomberg scenarios、QuantConnect 历史情景回放

**当前不足：** 蒙特卡洛模拟给出了统计意义上的 VaR，但用户更关心"如果再来一次 2008 年，我的组合亏多少？"

**实现方案：**
- 后端新增 `core/scenario.py`：内置三个历史极端情景的数据快照——
  - 2008 全球金融危机 (2008/09-2009/03)
  - 2020 新冠熔断 (2020/02-2020/03)
  - 2022 加息周期 (2022/01-2022/10)
- 应用当前回测给出的权重配置，计算在每个历史情景下的 P&L 和最大回撤
- 前端新增"压力测试"卡片：三列对比表，每列显示该情景下策略 vs 基准的收益和回撤
- 工作量：后端 3h + 前端 1.5h

#### 3.3 多时间周期信号面板 (Multi-Timeframe Signal)

**行业对标：** TradingView 多时间框架、Bloomberg trend analysis

**当前不足：** 系统只有一个时间维度的状态判定。短期交易者想看周度信号，长期配置者想看季度信号，目前无法满足差异化需求。

**实现方案：**
- 后端新增 `core/signals.py`：为 VIX 和 TNX 计算三个时间窗口的 Z-Score ——
  - 短期 (20 日)：捕捉动量突破
  - 中期 (60 日)：识别趋势方向
  - 长期 (252 日)：判断周期位势
- 前端新增小型三联信号灯面板：每个时间框架一个红/黄/绿指示灯 + 一句话操作建议
- 工作量：后端 1.5h + 前端 1h

---

### 第二梯队：中等价值 / 中等成本（建议下月实现）

#### 3.4 Markowitz 有效前沿与组合优化器 (Efficient Frontier)

**行业对标：** QuantConnect Optimization、Portfolio Visualizer

**当前不足：** `optimize.py` 仅对回测参数做网格搜索，不涉及真正的组合优化（最小方差、最大夏普、风险平价）。这是一款"量化"平台的标志性能力缺失。

**实现方案：**
- 后端新增 `core/portfolio_opt.py`：使用 `scipy.optimize.minimize` 实现——
  - 最小方差组合 (Global Minimum Variance)
  - 最大夏普比率组合 (Tangency Portfolio)
  - 风险平价组合 (Risk Parity, 各资产风险贡献相等)
- 前端新增 ECharts 散点图：X 轴为波动率，Y 轴为预期收益，散点为随机组合，标注最优组合点，连线为有效前沿
- 当前 AlphaCore 的四通道策略也标注在前沿图上，直观展示其效率
- 工作量：后端 4h + 前端 3h

#### 3.5 波动率期限结构与 VIX 期货面板 (Vol Term Structure)

**行业对标：** VIX Central、Bloomberg VIX term structure

**当前不足：** 三个深度研报中有一篇专门讲 VIX 对冲，但系统内没有展示 VIX 期货期限结构的可视化面板。用户在研报中读到"Contango 抽血"却无法在终端上看到实时的升贴水状态。

**实现方案：**
- 后端新增 `core/vix_term.py`：通过 yfinance VIX 期货数据 (^VIX 即期 + /VX 期货连续合约链) 或 Finnhub API 获取近月/次月/远月合约价格
- 计算 Contango/Backwardation 程度
- 前端新增"VIX 期限结构"卡片：柱状图 + 升贴水判定标签 + 与研报中的三级纪律联动
- 工作量：后端 3h + 前端 2h

#### 3.6 行业/板块轮动热力图 (Sector Rotation Heatmap)

**行业对标：** Koyfin Relative Rotation Graph、Bloomberg RRG

**当前不足：** 系统仅涵盖 SPY/TLT/GLD 三大类资产，无法深入到行业层面。对于 A 股用户，申万行业轮动是核心决策维度。

**实现方案：**
- 后端新增 `core/sector_rotation.py`：通过 yfinance 拉取 SPDR 11 个行业 ETF (XLK, XLF, XLE, XLV, XLI, XLP, XLY, XLB, XLU, XLRE, XLC)
- 计算每个行业相对 SPY 的相对强弱 (RS) 和 RS 的动量 (Momentum Ratio)
- 前端新增 RRG 散点图：X 轴 RS-Ratio (相对强度)，Y 轴 RS-Momentum (动量)，四个象限（领先/走弱/落后/改善）以不同颜色区分
- 工作量：后端 3h + 前端 4h

---

### 第三梯队：高价值 / 高成本（远期规划）

#### 3.7 经济日历与 Fed 利率概率监控 (Econ Calendar)

- 通过 FRED 或 CME FedWatch 数据，在前端展示未来 30 天关键经济事件（CPI、NFP、FOMC 等）及其预期影响等级
- 与当前宏观状态机联动：在 FOMC 会议前自动提高告警敏感度
- 工作量：后端 5h + 前端 4h

#### 3.8 条件告警规则引擎 (Rule Builder)

- 当前告警为硬编码触发条件。应提供前端 UI 让用户自定义：例如"当 VIX > 30 AND SPY-TLT 相关性 > 0.3 时，推送到我的微信"
- 后端新增 `core/alert_rules.py`：持久化规则到 SQLite，后台定时评估
- 工作量：后端 6h + 前端 5h

#### 3.9 持仓跟踪器 (Portfolio Tracker)

- 用户在前端输入个人持仓（手动录入或 CSV 导入），系统自动计算——
  - 实时 P&L、币种敞口、行业集中度
  - 与 AlphaCore 建议权重的偏离度分析
  - 压力测试穿透结果
- 工作量：后端 8h + 前端 6h

#### 3.10 因子归因分析 (Factor Attribution)

- 用 Fama-French 三因子（或五因子）模型对策略收益做时序回归，分解 Alpha 来源
- 告诉用户"你的超额收益是多少来自市场 Beta、多少来自规模因子、多少来自动量因子、多少是真 Alpha"
- 工作量：后端 4h + 前端 3h

---

## 四、建议删除或精简的功能

### 4.1 邮件订阅系统 → 简化为单通道告警

**理由：** AlphaCore 定位为个人量化终端而非 SaaS 平台。维护订阅者数据库 (`subscribers.db`)、SMTP 配置、去重逻辑、退订机制——对于一个没有多用户增长预期的工具，这些代码属于"过度工程化"。

**建议：** 保留告警推送逻辑，但简化为单一推送通道（微信 Server酱已足够），移除 `subscribers.db` 和 `/api/subscribe` 路由。前端订阅表单改为"开通告警"按钮，单次绑定到后台配置。

**收益：** 减少约 80 行 Python 代码、1 个数据库文件、1 个 API 路由、2 个前端表单组件。

### 4.2 冗余测试文件 → 合并

**理由：** `test_llm.py` 和 `test_prompt.py` 功能高度重叠（都是测试 LLM 调用），且使用与生产环境不同的 API 端点 (SiliconFlow vs DeepSeek 官方)。这两个文件不能代表生产行为的正确性验证。

**建议：** 合并为单一 `test_llm.py`，统一切换到 DeepSeek 官方 API，从 `.env` 读取 key。或直接删除并依赖 `test_system.py` 的集成测试。

### 4.3 `FINNHUB_API_KEY` → 移除

**理由：** 该 Key 在 `.env` 中声明，但在全部源文件中无任何引用。属于死凭证，增加维护负担和安全暴露面。

### 4.4 研报系统 → 迁至静态文件

**理由：** 当前 `/report/{doc_id}` 路由在每次请求时执行 `markdown.markdown()` 渲染。三篇研报的内容是静态的，可以预渲染为 HTML 后作为静态文件提供，减少 FastAPI 路由数量和 Python markdown 依赖。

**建议：** 预渲染研报为 `static/reports/*.html`，前端直接链接到静态文件。仅在研报内容更新时才需要重新渲染。

---

## 五、架构层面的前瞻性优化

### 5.1 引入配置中心模式

当前配置散落在 `.env`、各模块顶部变量（如 `CACHE_TTL`、`MAX_REQUESTS_PER_MINUTE`）、硬编码阈值（如 `current_val < 3.8` 的 TNX 分界线）。建议统一到 `core/config.py`：

```python
class Settings:
    # 从 .env 加载
    TUSHARE_TOKEN: str
    FRED_API_KEY: str
    # 量化参数（可从文件热加载）
    TNX_LOOSE_THRESH: float = 3.8
    TNX_TIGHT_THRESH: float = 4.5
    VIX_CAUTION_THRESH: float = 20.0
    VIX_PANIC_THRESH: float = 30.0
    CORR_DUAL_KILL_THRESH: float = 0.15
```

**收益：** 所有阈值集中管理，便于未来通过前端页面动态调整策略参数。

### 5.2 缓存层抽象

当前 `DATA_CACHE` 是模块级字典 + 手动 timestamp 管理。建议包装为统一的 `CacheStore` 类，提供 TTL 自动过期、线程安全读写、缓存命中率统计。

### 5.3 异步化 YFinance 调用

`quant_engine.py` 中的 `calculate_correlation_matrix()` 串联调用 4 个 `yf.Ticker(t).history()`，这些调用是同步阻塞的。可以改为 `asyncio.to_thread()` 或使用 `yfinance` 的多线程下载 API (`yf.download(tickers, ...)`) 一次请求获取全部数据。

---

## 六、新增文件结构预览

```
alphacore/
├── core/
│   ├── config.py              # 统一配置中心 (新增)
│   ├── cache_store.py          # 缓存抽象层 (新增)
│   ├── yield_curve.py          # 利率期限结构 (新增)
│   ├── scenario.py             # 历史情景压力测试 (新增)
│   ├── signals.py              # 多时间周期信号 (新增)
│   ├── portfolio_opt.py        # 有效前沿与组合优化 (新增)
│   ├── vix_term.py             # VIX期限结构 (新增)
│   └── sector_rotation.py      # 行业轮动 (新增)
├── static/
│   ├── index.html              # 主面板（扩展新卡片）
│   ├── main.js                 # 前端逻辑（扩展新图表）
│   └── reports/                # 预渲染研报 (从 /report 迁移)
├── .env                        # 密钥（已存在）
├── requirements.txt            # 添加 scipy, python-dotenv
└── optimize.py                 # （移除或将网格搜索功能并入 portfolio_opt）
```

---

## 七、实施路线图

| 阶段 | 内容 | 预计工时 | 交付物 |
|:---|:---|---:|:---|
| **Phase A** | 利率期限结构 + 历史情景压力测试 + 多时间周期信号 | 10h | 3 个新面板 |
| **Phase B** | 清理冗余（移除订阅DB、合并测试、精简配置）+ 配置中心引入 | 5h | 更干净的代码库 |
| **Phase C** | 有效前沿 + VIX期限结构 + 行业轮动 | 16h | 3 个新面板 |
| **Phase D** | 经济日历 + 告警规则引擎 + 持仓跟踪 + 因子归因 | 25h | 4 个重量级功能 |

**建议优先执行 Phase A + Phase B（共约 15h），即可使 AlphaCore 达到同类个人量化工具的顶尖水平。**

---

> 编制人：Claude (量化系统架构分析)  
> 对标数据来源：Bloomberg Terminal / Koyfin / TradingView / QuantConnect / Bridgewater Associates 公开产品文档
