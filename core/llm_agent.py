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
