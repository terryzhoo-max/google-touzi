import urllib.request
import json
from core.market_data import DATA_CACHE

from core.config import settings

def generate_llm_insight():
    def safe_get_last(cache_key):
        cache_data = DATA_CACHE.get(cache_key, {}).get("data")
        if cache_data is None: return 0.0
        vals = cache_data.get("data", cache_data) if isinstance(cache_data, dict) else cache_data
        
        if hasattr(vals, "iloc"):
            return float(vals.iloc[-1]) if len(vals) > 0 else 0.0
        elif isinstance(vals, (list, tuple, str)):
            return float(vals[-1]) if len(vals) > 0 else 0.0
        return 0.0

    try:
        vix = safe_get_last("vix")
        tnx = safe_get_last("tnx")
        dxy = safe_get_last("dxy")
        csi300 = safe_get_last("csi300")
        
        corr_data = DATA_CACHE.get("correlation", {}).get("data", {})
        spy_tlt_corr = 0.0
        if corr_data is not None and isinstance(corr_data, dict) and "matrix" in corr_data:
            for item in corr_data["matrix"]:
                if (item[0] == 0 and item[1] == 1) or (item[0] == 1 and item[1] == 0):
                    spy_tlt_corr = float(item[2])
                    break

        prompt = f"""你是一个顶级的华尔街宏观量化基金经理 (CIO)。请根据以下最新的实时宏观数据，生成一段 150 字左右的【每日机构决策大纲】。直接给出硬核的操作指令和市场定性，语气要极其专业、冰冷、果断。绝对不要有任何多余的问候语或解释。
        
实时数据锚点：
- VIX (恐慌指数): {vix:.2f}
- 10Y美债收益率: {tnx:.2f}%
- 美元指数 (DXY): {dxy:.2f}
- 沪深300 (A股): {csi300:.2f}
- 股债相关性 (SPY vs TLT): {spy_tlt_corr:.2f} (注：若大于0代表同跌双杀风险，小于0代表对冲健康)
"""
        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        models_to_try = [
            ("deepseek-chat", 8),
            ("deepseek-chat", 12)  # 备用节点：延长超时时间重试
        ]
        
        content = None
        for model_name, timeout_val in models_to_try:
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": "You are a quantitative hedge fund manager."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 300
            }
            try:
                req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=timeout_val) as response:
                    result = json.loads(response.read().decode("utf-8"))
                    content = result["choices"][0]["message"]["content"]
                    break
            except Exception as e:
                print(f"Model {model_name} failed: {e}")
                continue
                
        if content:
            return {"insight": content}
        else:
            raise Exception("All Gen-AI endpoints failed to respond.")
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        print(f"LLM API Error: {e}")
        
        # Phase 22: Local Healer (Fallback to deterministic rule-based insight)
        if vix > settings.VIX_PANIC_THRESH:
            local_insight = f"🔴 极寒预警：本地终端探针监测到 VIX 飙升至 {vix:.2f}。大模型集群已触发断网熔断机制，建议立即切入防御资产。"
        elif tnx > settings.TNX_TIGHT_THRESH and dxy > 105:
            local_insight = f"🟡 抽水预警：本地探针监测到 10Y={tnx:.2f}% 且 DXY={dxy:.2f}。大模型云端连接异常，全球流动性高度紧张，现金为王。"
        else:
            local_insight = f"🟢 状态平稳：本地探针监测到当前宏观环境平稳 (VIX={vix:.2f}, 10Y={tnx:.2f}%)。云端推演暂缓，请参考下方量化沙盘维持既定投资节奏。"
            
        return {"insight": local_insight}

def generate_portfolio_compliance_insight(compliance_status, tracking_error, var_95, top_factor, concentration):
    try:
        prompt = f"""你是一个极其严格的华尔街量化基金风控总监（Chief Risk Officer）。
请根据以下最新的实盘组合风控数据，生成一段 150 字以内的【高管风控批示】。
直接给出硬核的裁决指令（如熔断、放行、对冲、调仓等）。语气冰冷、极度专业、不留情面。绝对不要有任何多余的话。

当前组合审计快照：
- 综合合规状态: {compliance_status.upper()}
- 跟踪误差 (Tracking Error): {tracking_error}%
- 95% 在险价值 (VaR): {var_95}%
- 最大风险归因因子: {top_factor}
- 集中度水平: {concentration}
"""
        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are a ruthless Chief Risk Officer at a top quantitative hedge fund."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 300
        }
        
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            content = result["choices"][0]["message"]["content"]
            return {"insight": content}
    except Exception as e:
        import traceback
        print(f"LLM API Error in Compliance Insight: {e}")
        
        # Local Fallback
        try:
            te_val = float(str(tracking_error).replace('%', ''))
        except:
            te_val = 0.0
            
        if compliance_status.lower() in ['block', 'fail'] or te_val > 8.0:
            local = f"🔴 风控熔断：终端监控到跟踪误差达 {tracking_error}% 且合规状态 {compliance_status}。系统已强制阻断新增买入指令，建议立刻开启 {top_factor} 因子的反向对冲。"
        elif compliance_status.lower() == 'warn' or te_val > 4.0:
            local = f"🟡 风控警告：{top_factor} 因子暴露偏高 (TE: {tracking_error}%)，集中度 {concentration}。合规绿灯已降级，限制大规模调仓，建议以不超过 5% 的换手率进行微调。"
        else:
            local = f"🟢 合规放行：组合在险价值 (VaR: {var_95}%) 处于安全阈值内，未触发刚性风控红线。允许交易台按照既定模型执行目标权重。"
            
        return {"insight": local}


def generate_red_team_advisory(compliance_status, tracking_error, var_95, top_factor, concentration, worst_scenario_name="未知冲击", worst_loss=0.0):
    """Generates a critical, adversarial CRO response focusing on tail-risks and crowded factors."""
    try:
        prompt = f"""你是一个极其苛刻、挑剔、冰冷且完全理性的对冲基金独立红队风控官 (Red Team CRO)。
你的唯一职责是向投资委员会的偏见与乐观情绪“泼冷水”，一针见血指出当前资产配置的最致命死穴。
请基于以下数据，生成一段 150 字以内的【红队风控质询意见】。语气必须极其冷酷、一针见血，绝无任何废话。

当前组合风控及压测快照：
- 合规绿灯状态: {compliance_status.upper()}
- 跟踪误差 (Tracking Error): {tracking_error}%
- 95% 在险价值 (VaR): {var_95}%
- 最大风险溢价因子: {top_factor}
- 集中度水位: {concentration}
- 最恶劣情景压测 (Scenario Stress): 「{worst_scenario_name}」，预期最大回撤 {worst_loss}%
"""
        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are a highly skeptical and aggressive Red Team Risk Officer at a global macro hedge fund. Your goal is to highlight blind spots and challenge the portfolio managers."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.4,
            "max_tokens": 300
        }
        
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            content = result["choices"][0]["message"]["content"]
            return {"insight": content}
    except Exception as e:
        print(f"LLM API Error in Red Team Advisory: {e}")
        
        # Highly realistic deterministic local fallback based on factor exposures and worst loss
        if worst_loss < -8.0 or compliance_status.lower() in ['block', 'fail']:
            local = f"⚠️ 红队严厉质询：最坏场景「{worst_scenario_name}」预期损失达 {worst_loss}% 已击穿风险预算底线。强配 {top_factor} 因子属于严重的认知偏差，完全低估了流动性踩踏风险。建议立即否决本期投资建议，削减敞口。"
        else:
            local = f"⚠️ 红队风险警示：当前合规状态虽显示为 {compliance_status.upper()}，但组合在 {top_factor} 因子上的拥挤暴露是不容忽视的隐患。在极端流动性逆风下，其相关性通常会迅速飙升，导致 VaR 模型瞬间失效。建议维持高度警惕，增配现金。"
            
        return {"insight": local}



def generate_morning_brief(decision_matrix: dict, scenarios: dict, factor_risk: dict, macro_data: dict) -> dict:
    try:
        # Extract macro data
        vix = macro_data.get("vix", 20.0)
        tnx = macro_data.get("tnx", 4.0)
        
        # Extract risk and scenario data
        worst_scenario = scenarios.get("worst_scenario", {})
        worst_scenario_name = worst_scenario.get("name_zh", "未知冲击")
        worst_loss = worst_scenario.get("portfolio_loss_pct", 0.0)
        
        # Extract decision data
        compliance_status = decision_matrix.get("global_status", "UNKNOWN")
        drift = decision_matrix.get("drift_monitor", {}).get("total_gap_pct", 0.0)
        
        # Extract factor risk data
        top_factor = factor_risk.get("top_factor", {}).get("factor_name", "未知因子")
        top_factor_exposure = factor_risk.get("top_factor", {}).get("exposure", 0.0)
        
        # Extract top scoring assets from the decision hub recommendations (if available)
        # We assume decision_matrix has some actionable trades or signals
        exec_plan = decision_matrix.get("execution_plan", [])
        trades_summary = ", ".join([f"{t['action'].upper()} {t['symbol']} (Delta: {t['delta_weight']*100:.1f}%)" for t in exec_plan[:3]])
        if not trades_summary:
            trades_summary = "暂无调仓动作 (维持现有权重)"
        
        prompt = f"""你是一个顶尖对冲基金的联席投资总监 (Co-CIO)。现在是盘前晨会，请基于以下底层量化引擎刚刚跑出的 T-0 数据快照，撰写一份极度专业的【每日机构晨会简报 (Morning Brief)】。
请使用 Markdown 格式，严格按照以下四个模块输出。你的语气必须冰冷、克制、一针见血，绝不使用任何口语化或情感化的表达。如果合规状态为 HARD_BLOCK，你必须在第一段发出严厉的熔断警告。

系统数据快照：
1. 宏观水位: VIX={vix:.1f}, 10Y美债={tnx:.2f}%
2. 极端压测 (Beta协方差): 最恶劣情景为「{worst_scenario_name}」，预期最大回撤 {worst_loss}%
3. JCS 组合合规: 状态={compliance_status}, 仓位总漂移={drift}%
4. 因子暴露: 最大敞口为 {top_factor} (暴露度 {top_factor_exposure*100:.1f}%)
5. 核心交易指令: {trades_summary}

晨会简报结构要求：
### 一、 宏观与系统水位 (Macro & Liquidity)
(1-2句话定性今日宏观)
### 二、 风控与合规审查 (Risk & Compliance)
(点评合规状态与最大压测回撤，若有违规需直接点明阻断)
### 三、 因子敞口评估 (Factor Exposure)
(点评当前最大因子暴露的风险或机遇)
### 四、 日内交易指令 (Intraday Execution)
(直接下达交易台指令)
"""
        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are a ruthless and precise CIO at a top quantitative hedge fund. You speak only in concise, professional financial Mandarin."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 500
        }
        
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=12) as response:
            result = json.loads(response.read().decode("utf-8"))
            content = result["choices"][0]["message"]["content"]
            return {"brief": content}
            
    except Exception as e:
        import traceback
        print(f"LLM Morning Brief API Error: {e}")
        
        # Local Fallback
        fallback = f"""### 一、 宏观与系统水位 (Macro & Liquidity)
本地探针监测到 VIX={macro_data.get('vix', 20.0):.1f}，10Y={macro_data.get('tnx', 4.0):.2f}%。大模型云端连接超时，采用本地降级评估。

### 二、 风控与合规审查 (Risk & Compliance)
当前 JCS 合规状态: {decision_matrix.get('global_status', 'UNKNOWN')}。最恶劣压测情景为「{scenarios.get('worst_scenario', {}).get('name_zh', '未知')}」，预期最大回撤 {scenarios.get('worst_scenario', {}).get('portfolio_loss_pct', 0.0)}%。

### 三、 因子敞口评估 (Factor Exposure)
大模型暂不可用，请人工复核 {factor_risk.get('top_factor', {}).get('factor_name', '未知因子')} 的局部风险。

### 四、 日内交易指令 (Intraday Execution)
交易台遵循系统硬编码指令执行。若触发 HARD_BLOCK，立刻停止一切做多操作。
"""
        return {"brief": fallback}

