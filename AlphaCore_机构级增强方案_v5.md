# AlphaCore — 机构级辅助决策增强方案 v5

> 编制日期：2026-05-07  
> 对标平台：Bloomberg Terminal / Wind 万得 / Koyfin / TradingView / CME FedWatch / FRED  
> 当前版本：v5.0（19 路由 / 20 核心模块 / 中美双市场 / 行业+主题+ETF 三层轮动）

---

## 〇、当前能力矩阵 vs 顶级机构平台

| 功能域 | Bloomberg | Wind | Koyfin | TradingView | **AlphaCore** |
|:---|:---:|:---:|:---:|:---:|:---:|
| 美股宏观量化 | ✅ | ❌ | ✅ | ❌ | ✅ TNX/VIX/DXY/曲线 |
| A股宏观量化 | ❌ | ✅ | ❌ | ❌ | ✅ CPI/PMI/M2/GDP |
| 申万行业轮动 | ❌ | ✅ | ❌ | ❌ | ✅ 31行业 treemap |
| 主题+ETF轮动 | ❌ | ✅ | ❌ | ❌ | ✅ 8主题+6国内+6全球 |
| 风险矩阵+VaR | ✅ | ✅ | ❌ | ❌ | ✅ 相关性+蒙特卡洛+压力测试 |
| 组合优化 | ✅ | ✅ | ✅ | ❌ | ✅ GMV+切线+AlphaCore标注 |
| 决策信号引擎 | ❌ | ❌ | ❌ | ❌ | ✅ 5因子加权 0-100分 |
| 利率期限结构 | ✅ | ✅ | ✅ | ❌ | ✅ 2s10s+4期限 |
| **Fed 利率概率** | ✅ | ❌ | ✅ | ❌ | ❌ |
| **经济意外指数** | ✅ | ✅ | ✅ | ❌ | ❌ |
| **自定义告警规则** | ✅ | ✅ | ❌ | ✅ | ❌ 仅硬编码 |
| **全球跨资产仪表盘** | ✅ | ✅ | ✅ | ❌ | ❌ |
| **技术指标叠加** | ✅ | ✅ | ❌ | ✅ | ❌ |
| **相对强度矩阵** | ✅ | ✅ | ✅ | ❌ | ❌ |
| **资金流向纵深** | ✅ | ✅ | ✅ | ❌ | ⚠️ 仅北向汇总 |
| **估值温度计** | ✅ | ✅ | ✅ | ❌ | ❌ |

---

## 一、Top 5 建议新增（按机构决策价值排序）

### 1. Fed 利率概率监控 — CME FedWatch 风格

**对标：** Bloomberg WIRP、CME FedWatch Tool、Koyfin Rate Monitor  
**决策价值：★★★★★** — 全球所有利率敏感资产的定价锚  
**数据源：** CME FedWatch Tool 公开数据（无需 API Key），或 FRED 联邦基金期货

**实现：**
- 后端 `core/fed_prob.py`：爬取或通过 FRED 联邦基金期货合约推导未来 4 次 FOMC 会议的加息/降息概率
- 前端：横条图，X 轴为概率 0-100%，Y 轴为会议日期，每个会议两条色条（加息概率/降息概率）
- 新增路由：`GET /api/macro/fed_prob`

**工时：** 后端 2h + 前端 1.5h

### 2. 经济意外指数 (Economic Surprise Index)

**对标：** Bloomberg ECO Surprise、Citi Economic Surprise Index (CESI)  
**决策价值：★★★★★** — 告诉你宏观数据是在持续 beat 还是 miss 预期，领先于资产价格  
**数据源：** FRED 或公开经济数据 + 彭博/路透一致预期（可用历史均值模拟）

**实现：**
- 后端 `core/surprise_index.py`：计算过去 90 天中国+美国关键经济数据（CPI、PMI、GDP、NFP、零售）的实际值与预测值差异的标准化 Z-Score
- 前端：累计折线图，正数区域绿色（数据超预期），负数区域红色（数据不及预期），当前值 + 近期趋势箭头
- 新增路由：`GET /api/macro/surprise_index`

**工时：** 后端 2h + 前端 1.5h

### 3. 全球跨资产一览表 (Global Cross-Asset Dashboard)

**对标：** Bloomberg MOST function、Koyfin Dashboard、TradingView Heatmap  
**决策价值：★★★★☆** — 一屏看完全球所有重要资产，立即识别资金流向  
**数据源：** Tushare（QDII ETF 代理，已有数据）

**实现：**
- 后端 `core/global_assets.py`：拉取 12-15 个全球核心资产（SPY/TLT/GLD/沪深300/恒生/日经/黄金/原油/比特币/美元指数/美债/中债）的日/周/月/季涨跌幅
- 前端：一张大号热力表格，行=资产，列=日涨跌/周涨跌/月涨跌/季涨跌/YTD，单元格颜色红绿渐变
- 新增路由：`GET /api/macro/global_assets`

**工时：** 后端 1.5h + 前端 2h

### 4. 估值温度计 (Valuation Thermometer)

**对标：** Bloomberg FA、Wind 估值分析、Koyfin Valuation  
**决策价值：★★★★☆** — 告诉你当前 PE/PB 在历史上处于什么分位，是贵还是便宜  
**数据源：** Tushare `daily_basic`（PE/PB 历史，5000 积分可用）

**实现：**
- 后端 `core/valuation.py`：拉取沪深300、中证500、创业板指的 PE/PB 近 10 年历史，计算当前分位数
- 前端：温度计样式（0-100% 的竖向进度条），颜色渐变（蓝=低估 绿=合理 黄=偏高 红=泡沫），标注均值±1σ±2σ 位置
- 三列对照：沪深300 / 中证500 / 创业板
- 新增路由：`GET /api/macro/valuation`

**工时：** 后端 1.5h + 前端 2h

### 5. 自定义告警规则引擎

**对标：** Bloomberg ALRT、TradingView Alerts、Wind 预警  
**决策价值：★★★★☆** — 从"被动查看"升级为"主动推送"，量化终端的关键一步  
**数据源：** 已有（所有宏数据在缓存中）

**实现：**
- 后端 `core/alert_rules.py`：支持 6 条预定义条件规则（如"VIX>30 AND 2s10s<-50bp → 推送微信"），存储于 JSON 配置文件
- 前端：告警中心面板中增加"规则配置"区，每条规则带开关 + 阈值滑块 + 推送方式选择（微信/邮件/前端横幅）
- 后台守护进程每 5 分钟评估一次规则
- 新增路由：`GET /api/alerts/rules` + `POST /api/alerts/rules`

**工时：** 后端 2.5h + 前端 2h

---

## 二、精简建议

| 项目 | 理由 | 操作 |
|:---|:---|:---|
| `optimize.py` | 网格搜索已被 `portfolio_opt.py` 有效前沿功能取代 | 移入 `tools/` 或标注 deprecated |
| 前端 `subscribe-form` 残留 | 订阅功能已在 v2 移除，但 CSS 中仍保留 `.subscribe-*` 样式类 | 清理 CSS |
| 研报 `render_reports.py` | 三篇研报已预渲染为 `static/reports/*.html`，脚本仅需在内容更新时执行 | 保留但标注为构建工具 |

---

## 三、实施路线（按决策价值排序）

| 优先级 | 功能 | 工时 | 数据就绪？ | 分组 |
|:---:|---|:---:|:---:|:---|
| P0 | Fed 利率概率 | 3.5h | FRED ✅ | 📡 宏观雷达 |
| P1 | 经济意外指数 | 3.5h | FRED+本地计算 ✅ | 📡 宏观雷达 |
| P2 | 全球跨资产一览 | 3.5h | Tushare ✅ | 首屏 Dashboard |
| P3 | 估值温度计 | 3.5h | Tushare ✅ | 📡 宏观雷达 |
| P4 | 自定义告警规则 | 4.5h | 已有 | ⚠️ 风险分析 |

**合计：18.5h。P0+P1+P2 三件套（10.5h）完成后，AlphaCore 将具备 Bloomberg 级别的宏观决策辅助能力。**

---

> 编制人：Claude  
> 对标数据：Bloomberg Terminal / Wind 万得 / Koyfin / TradingView / CME FedWatch 公开功能矩阵
