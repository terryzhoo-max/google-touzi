# AlphaCore 项目机构视角完整报告

生成日期：2026-05-25  
项目路径：`D:\FIONA\google touzi`  
分析口径：基于当前工作区源码、配置、测试契约、持仓 JSON 与本地数据库结构静态审阅；未联网拉取行情，未改动业务代码。

## 1. 结论摘要

AlphaCore 当前已经不是单一投研看板，而是一个“宏观信号 - 组合风险 - 情景压力 - 配置建议 - 合规闸门 - 审计追踪 - QMT 执行网关”的机构化决策系统雏形。核心优势在于链路完整、接口契约较丰富、审计和复盘意识明确，并且开始引入 Black-Litterman、Risk Parity、因子风险、情景复现、跨组合风险网络、交易摩擦和执行滑点等机构框架。

当前主要短板集中在三类：

1. 数据与模型口径仍混杂。部分模块使用真实数据源，部分使用确定性 fallback、静态 ADV、手工参数或旧测试样本；因子注册表与当前真实持仓代码覆盖不完全。
2. 当前组合风险暴露偏集中。最新 `data/institutional_portfolio.json` 显示组合约 91.35% 权益、90.52% 中国地区、最大单票中芯国际约 33.78%，现金只有约 0.15%。这是高权益、高中国、高半导体/科技相关敞口组合，不是均衡机构组合。
3. 生产可用性还需要治理。存在中文编码显示异常、测试契约与当前持仓样本不完全同步、Python 运行依赖在当前环境不可直接导入、QMT 配置仍含占位账户与路径，说明“研究/演示系统”向“可控生产系统”仍有工程化距离。

机构视角判断：系统适合继续作为个人/小型团队的机构化投研与交易决策中台打磨；在真实资金规模化执行前，应优先完成数据口径校验、参数校准留痕、合规阈值冻结、执行网关隔离和端到端验收。

## 2. 系统定位

项目定位可以概括为：

- 宏观多资产投研终端：VIX、TNX、收益率曲线、中国宏观、估值、市场宽度、行业/主题轮动、全球资产等。
- 机构组合工作台：组合导入、风险分解、情景压力、因子暴露、基准/主动风险、归因、what-if 调仓。
- 决策与合规引擎：政策哈希、配置模型哈希、合规阈值、审计留痕、复盘排程。
- 交易执行桥：审批订单写入 SQLite，QMT 网关轮询并以 DIRECT/TWAP 方式执行或 dry-run。
- 前端仪表盘：`static/index.html` + `static/main.js` 展示宏观、机构、模拟、审计、执行状态等面板。

主要入口：

- 后端：`data_engine.py`，FastAPI 服务，默认 `127.0.0.1:8888`。
- 前端：`static/index.html`、`static/main.js`、`static/styles.css`。
- 决策中枢：`core/global_decision_hub.py`。
- 机构组合链路：`core/portfolio_book.py`、`core/risk_engine.py`、`core/scenario_engine.py`、`core/allocation_model.py`、`core/compliance_engine.py`。
- 执行网关：`qmt_gateway_daemon.py`。
- 持仓输入：`data/institutional_portfolio.json`、`data/tactical_hedged_portfolio.json`。
- 审计/交易数据库：`alphacore.db`、`alphacore_audit.db`。

## 3. 决策链路理解

系统存在两条相互关联的主链路。

### 3.1 机构决策包链路

`/api/institutional/decision` 通过 `_build_institutional_payload()` 聚合：

1. 组合快照：读取持仓 JSON，计算权重、资产类别、地区、策略、货币、集中度和 T+1 资金占用成本。
2. 数据质量：判断组合文件是否存在、是否 fallback、是否 stale、缺失率与异常数。
3. 风险：计算日波动率、VaR、CVaR、风险贡献、MCTR/ACTR、DTL 流动性。
4. 情景压力：套用预设宏观、主题、地区冲击，找出最差情景。
5. 因子风险：通过 `FACTOR_REGISTRY` 映射资产到宏观、主题、地区、策略、资产类别暴露。
6. 基准与主动风险：构建 policy benchmark，计算主动权重和 tracking error proxy。
7. 归因：基于 T-1/T+1/T+5 回报口径生成 allocation/selection/currency/decision attribution。
8. 决策票据：按政策阈值生成 status、score、primary driver 和 review schedule。
9. What-if 与配置模型：生成风险改善调仓、合规检查、配置建议。
10. 审计与复盘：提供记录端点，并生成 T+1、T+5、T+20 复盘窗口。

机构化要点：所有关键政策对象带 `policy_hash` 或 `model_hash`，这是比较正确的设计。它让历史决策可以追溯到当时的规则版本。

### 3.2 L1-L5 Global Decision Hub 链路

`/api/institutional/decision_hub` 由 `compute_decision_matrix()` 输出：

- L1 Macro Filter：读取 VIX、TNX、收益率曲线、中国宏观，调用 `compute_decision()` 生成宏观状态、分数和最大权益敞口。
- L2 Quant Signals：读取 Strategy Lab 各策略信号，转换为前端可消费的数值信号。
- L3 Allocator：调用 `build_allocation_recommendation()` 生成目标权重。
- L4 Compliance Gate：调用 `evaluate_pre_trade_compliance()`，输出 `PASSED`、`SOFT_WARNING` 或 `HARD_BLOCK`。
- L5 AI Memo：用确定性模板生成 CIO/CRO 风格解释。
- Execution Plan：计算当前权重与目标权重差，生成 proposed orders；若存在 hard block，则目标权重回滚为当前权重。
- Broker Orders：从 `trade_journal` 查询 `PENDING` 订单，供 QMT 网关轮询。

这条链路更接近“盘中审批与执行漏斗”，适合前端展示和网关对接。

## 4. 当前组合诊断

基于当前 `data/institutional_portfolio.json` 计算：

| 指标 | 当前值 |
|---|---:|
| 总市值 | 545,021.60 |
| 持仓数量 | 13 |
| 权益权重 | 91.35% |
| 黄金权重 | 8.50% |
| 现金权重 | 0.15% |
| 中国地区权重 | 90.52% |
| 香港地区权重 | 9.48% |
| 最大单票 | 688981 中芯国际，33.78% |
| 前三大权重 | 57.87% |
| 估算日波动率 | 1.48% |
| 估算 95% VaR | -2.43% |
| 估算 95% CVaR | -3.29% |

前五大持仓：

| 代码 | 名称 | 类别 | 地区 | 权重 |
|---|---|---|---|---:|
| 688981 | 中芯国际 | equity | China | 33.78% |
| 159218 | 卫星ETF招商 | equity | China | 14.50% |
| 588000 | 科创50ETF华夏 | equity | China | 9.59% |
| 518880 | 黄金ETF华安 | gold | China | 8.50% |
| 09988 | 阿里巴巴-W | equity | HongKong | 8.03% |

机构视角评价：

- 组合不是多资产平衡组合，而是高权益中国科技/成长组合，黄金只是轻度缓冲。
- 最大单票 33.78% 未触及默认合规硬限制 50%，但显著高于多数机构内部单一标的舒适区。
- 现金几乎为零，若系统要执行再平衡，实际交易约束需要考虑可用资金、T+1、卖出到账、交易单位和费用。
- 当前组合与部分测试中 900,000 市值、9 个等权 ETF 样本不一致，说明测试契约和真实输入样本已有漂移。

## 5. 核心参数与阈值

### 5.1 宏观与系统参数

来自 `core/config.py`：

| 参数 | 默认值 | 用途 |
|---|---:|---|
| `TNX_LOOSE_THRESH` | 3.8 | 利率宽松阈值 |
| `TNX_TIGHT_THRESH` | 4.5 | 利率收紧阈值 |
| `VIX_CAUTION_THRESH` | 20.0 | 波动警戒阈值 |
| `VIX_PANIC_THRESH` | 30.0 | 波动恐慌阈值 |
| `CORR_DUAL_KILL_THRESH` | 0.15 | 股债相关性异常阈值 |
| `MAX_REQUESTS_PER_MINUTE` | 240 | API 限流 |
| `CACHE_TTL` | 3600 | 默认缓存秒数 |
| `AIAE_VIX_THRESHOLD` | 25.0 | AIAE 波动触发阈值 |
| `AIAE_TURNOVER_THRESHOLD` | 0.05 | AIAE 换手阈值 |

### 5.2 风险参数

来自 `core/risk_engine.py` 与配置：

| 参数 | 默认值 | 含义 |
|---|---:|---|
| 权益日波动 | 1.6% | VaR/风险贡献基础波动 |
| 债券日波动 | 0.7% | VaR/风险贡献基础波动 |
| 黄金日波动 | 1.2% | VaR/风险贡献基础波动 |
| 现金日波动 | 0.01% | 近似无风险 |
| 权益-债券相关 | -0.2 | 组合协方差 |
| 权益-黄金相关 | 0.1 | 组合协方差 |
| 债券-黄金相关 | 0.2 | 组合协方差 |
| VaR high 阈值 | -6.0% | 高风险判断 |
| VaR medium 阈值 | -1.0% | 中风险判断 |
| DTL warning | >5 天 | 流动性警告 |
| DTL block | >10 天 | 流动性硬阻断 |

### 5.3 配置模型参数

来自 `core/allocation_policy.py`：

| 参数 | 默认值 | 含义 |
|---|---:|---|
| `max_single_weight` | 22% | 配置模型目标单标的上限 |
| `max_region_weight` | 55% | 地区上限 |
| `max_theme_weight` | 45% | 主题上限 |
| `min_gold_weight` | 8% | 黄金最低配置 |
| `max_gold_weight` | 22% | 黄金最高配置 |
| `max_turnover` | 16% | 单次模型换手上限 |
| `max_single_trade` | 5% | 单笔建议交易上限 |
| `min_trade_size` | 1% | 最小交易权重 |
| `worst_scenario_limit_pct` | -12% | 压力损失上限 |
| `data_quality_min_score` | 80 | 配置模型数据信任门槛 |
| `max_step_weight` | 4% | 单信号最大调仓步长 |

配置模型逻辑：ETF 信号综合分高于 68 增加一档，58-68 增加半档，低于 32 降一档，32-42 降半档；资本调仓再按“权益波动 / 资产波动”做逆波动缩放，然后套用单标的、黄金、换手限制。

### 5.4 合规参数

来自 `core/compliance_engine.py`：

| 参数 | 默认值 | 含义 |
|---|---:|---|
| 单标的硬上限 | 50% | 超过即 violation |
| 地区硬上限 | 60% | 超过即 violation |
| 策略硬上限 | 45% | 超过即 violation |
| 换手硬上限 | 20% | 超过即 violation |
| 单标的交易上限 | 10% | 超过即 violation |
| DTL 上限 | 5 天 | 超过 warning，10 天 hard block |
| 弱数据分数 | 80 | 弱数据不得新增风险 |
| warning buffer | 3% | 接近限制时警告 |

注意：配置模型的 `max_single_weight=22%` 与合规硬上限 `max_position_weight=50%` 是不同层级。前者是目标构建约束，后者是交易审批红线。当前 688981 约 33.78%，不违反合规硬限制，但高于配置模型目标上限。

## 6. 数据、缓存与审计

数据源模块集中在 `core/data_providers.py`、`core/market_data.py` 和各宏观模块。系统使用多层 fallback/circuit/cache 思路：

- `api_cache` 表缓存 API payload。
- `time_series` 表缓存行情序列。
- `ROUTE_TTL` 控制不同接口缓存时长。
- `/api/health` 暴露 source status、circuit、cache、runtime diagnostics、rate limit 和 active alerts。

审计链路：

- `core/audit_log.py` 负责决策记录、payload hash、完整性验证和复盘分数。
- `alphacore_audit.db` 是审计库。
- `core/db_layer.py` 管理 `alphacore.db` 的时序缓存、API 缓存和 `trade_journal`。
- `trade_journal` 记录订单、状态、执行算法、基准价、成交量、均价、滑点 bps、组合 ID。

机构视角评价：审计结构方向正确，但数据库 schema 仍由运行时懒迁移完成，正式生产建议改成显式 migration，并把审计库、交易库、行情缓存库分权限隔离。

## 7. 执行与 QMT 网关

`qmt_gateway_daemon.py` 的流程：

1. 检测 `xtquant`，存在则 LIVE，否则 DRY_RUN。
2. 每 10 秒轮询 `http://127.0.0.1:8888/api/institutional/decision_hub`。
3. 若 `global_status=HARD_BLOCK`，真实模式跳过执行，dry-run 模式允许模拟。
4. 读取 `broker_orders` 中的订单。
5. DIRECT 订单直接发出并记录 FILLED。
6. TWAP 订单开线程切片，支持 100 股单位、tick 保护、滑点记录。
7. 写 `qmt_heartbeat.json`，后端接口用 heartbeat 判断在线状态。
8. API 断连时指数退避，状态从 HEALTHY 到 RECONNECTING/DEGRADED。

关键生产风险：

- `QMT_ACCOUNT_ID` 仍是 `YOUR_ACCOUNT_ID`。
- `QMT_DATA_DIR` 是本地路径且当前显示编码异常。
- dry-run 下 hard block 会被绕过用于本地模拟，真实生产需要明确环境变量开关，避免误配置。
- 订单唯一 ID 使用日期 + 短 ID，足够演示，但机构生产建议使用统一 OMS order id 和幂等键。

## 8. 测试与契约

测试覆盖面较宽，包括：

- 机构 API 契约。
- 配置模型、风险、情景、归因、合规。
- Black-Litterman、Risk Parity、交易摩擦、DTL、资金占用。
- QMT 网关退避、静态安全、前端契约。
- 审计提交、自定义决策、跨组合风险网络。

但当前存在一个明显治理信号：`tests/test_institutional_api_contract.py` 中仍断言默认组合为 900,000 市值、9 个标准 ETF、首仓 `CSI300_ETF`；当前 `data/institutional_portfolio.json` 已是 545,021.60 市值、13 个真实/半真实持仓、首仓 `CASH`。这意味着：

- 要么测试依赖 monkeypatch/fixture 未从静态阅读中体现；
- 要么当前真实持仓与测试基准已漂移；
- 要么部分测试在当前环境会失败。

正式投产前必须先跑通 `python -m pytest -q`、`node --check static\main.js`、`git diff --check`，并同步测试契约与实际默认组合。

## 9. 主要问题清单

### P0：真实执行前必须解决

1. 运行环境依赖不完整。当前 bundled Python 直接导入项目时报 `ModuleNotFoundError: dotenv`，说明缺少项目依赖安装或运行脚本未固化。
2. QMT 实盘配置未生产化。账户、路径、环境隔离、dry-run/live 开关、hard block 绕过逻辑都需要硬化。
3. 测试契约与当前组合样本疑似不一致。机构系统最忌“输入口径变了但测试没变”。
4. 因子注册覆盖不足。当前真实代码如 `688981`、`159218`、`588000` 等未必在 `FACTOR_REGISTRY` 中完整映射，压力测试会退回启发式。

### P1：提高机构可信度

1. 中文编码异常需要系统性修复。多个源码注释、UI 文案和 QMT 路径出现 mojibake，影响审计可读性与运维判断。
2. 静态 ADV proxy 需要替换为可审计数据源。当前 DTL 逻辑正确，但输入是静态表或 fallback。
3. 参数校准需要报告化。配置里写明“18-year backtest calibrated”，但建议把样本区间、目标函数、稳定性、walk-forward 结果纳入报告。
4. 风险模型仍是资产类别协方差 + 因子 beta 混合框架，适合轻量系统，但应明确模型边界。
5. 合规阈值应按组合类型区分。当前单一政策同时约束 ETF 样本、真实 A/H 持仓、跨组合网络，未来应按 portfolio mandate 分层。

### P2：体验与维护

1. `data_engine.py` 体量过大，机构接口、宏观接口、交易接口、审计接口都在同一文件，可拆分 router。
2. SQLite schema 懒迁移可以改为显式版本化 migration。
3. 前端契约覆盖不错，但建议补充 Playwright 级别页面 smoke。
4. 将 `scratch/`、一次性 patch 脚本、历史预案与正式模块区分，减少维护噪声。

## 10. 建议路线图

### 第一阶段：冻结可验证版本

- 建立干净 Python 环境，安装 `requirements.txt`，跑全量测试。
- 修复或更新默认组合测试契约。
- 生成当前组合的正式 baseline：组合快照、风险、情景、因子覆盖、配置建议、合规结果。
- 固定 policy hash、model hash、benchmark hash，并把结果写入审计样例。

### 第二阶段：机构数据治理

- 把持仓输入、行情、ADV、因子暴露、交易回报分离成可追踪数据集。
- 为每个数据源记录 source、timestamp、staleness、fallback reason。
- 对真实持仓代码补齐 `FACTOR_REGISTRY`，或改成代码映射表 + 行业/主题自动识别。
- 建立参数校准报告：训练区间、验证区间、稳健性、敏感性。

### 第三阶段：执行安全

- 明确 `DRY_RUN`、`LIVE`、`PAPER` 三种环境配置。
- 真实模式下禁止任何 hard block 绕过。
- QMT 账户、路径、交易权限用环境变量注入，禁止源码占位常量。
- 订单审批与执行分离：只有 `SIGNED_OFF` 状态可被网关执行。
- 增加盘中撤单、部分成交、异常重试和人工 kill switch。

### 第四阶段：投资能力升级

- 将当前组合按 mandate 拆成：核心权益、科技成长、黄金对冲、现金管理。
- 对高集中持仓设置单票和主题预算，例如单票 20%-25% 观察线、35% 强制复核线。
- 引入真实基准：中证偏股/科技/沪深港混合基准，而不是单一 policy benchmark。
- 对 Black-Litterman views 做审计：观点来源、置信度、有效期、复盘命中率。
- 对 Risk Parity 输出加入交易摩擦和税费后的净改善判断。

## 11. 机构视角最终评价

AlphaCore 的方向是正确的：它已经具备机构系统最重要的几块骨架，即可解释决策、约束优先、审计留痕、复盘机制和执行闭环。当前最大问题不是“功能不够”，而是“口径治理、参数可信度和生产边界还不够硬”。

如果用于个人资金辅助决策，当前系统已经有较高实用价值；如果用于机构级真实执行，应先把它定位为投研与审批辅助系统，等 P0/P1 问题解决、全量测试稳定、执行隔离完成后，再逐步开放到小规模 paper/live pilot。
