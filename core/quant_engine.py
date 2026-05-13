import pandas as pd
import numpy as np
import time
from core.db import trigger_emergency_alert
from core.market_data import DATA_CACHE, fetch_yfinance_data, fetch_tushare_csi300_history
from core.data_providers import get_us_etf_history, get_vix_history
from core.config import settings
from core.alert_state import set_alert, clear_alert

def calculate_asset_allocation():
    vix_data = fetch_yfinance_data("^VIX", "vix")
    tnx_data = fetch_yfinance_data("^TNX", "tnx")
    dxy_data = fetch_yfinance_data("DX-Y.NYB", "dxy")
    
    try:
        current_vix = vix_data["data"][-1]
        current_tnx = tnx_data["data"][-1]
        current_dxy = dxy_data["data"][-1]
    except Exception:
        current_vix = 20
        current_tnx = 4.0
        current_dxy = 100.0
        
    try:
        from core.backtest import run_backtest
        bt_results = run_backtest()
        state = bt_results.get("current_state", {})
        strategies = state.get("asset_strategies", [])
        
        alloc = []
        for s in strategies:
            if s["weight"] > 0:
                alloc.append({
                    "value": s["weight"],
                    "name": s["asset"],
                    "icon": s["icon"],
                    "strategy": s["strategy"]
                })
        
        regime = state.get("regime", "中性震荡 (全天候配资期)")
    except Exception as e:
        print(f"Error syncing allocation with backtest: {e}")
        alloc = [
            {"value": 40, "name": "均衡大盘权益"},
            {"value": 40, "name": "中期国债"},
            {"value": 10, "name": "黄金等另类资产"},
            {"value": 10, "name": "战略现金"}
        ]
        regime = "中性震荡 (全天候配资期)"
        
    return {
        "regime": regime,
        "vix_ref": round(current_vix, 2),
        "tnx_ref": round(current_tnx, 2),
        "dxy_ref": round(current_dxy, 2),
        "allocation": alloc
    }

def calculate_correlation_matrix():
    now = time.time()
    if DATA_CACHE.get("correlation", {}).get("data") is not None and (now - DATA_CACHE["correlation"]["timestamp"] < settings.CACHE_TTL):
        return DATA_CACHE["correlation"]["data"]

    try:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        # Parallelize data fetching
        fetch_tasks = {
            "SP500": lambda: get_us_etf_history("SPY", months=6),
            "TLT":   lambda: get_us_etf_history("TLT", months=6),
            "GLD":   lambda: get_us_etf_history("GLD", months=6),
            "VIX":   lambda: get_vix_history(130),
            "CSI300": lambda: fetch_tushare_csi300_history(months=6)
        }
        
        results = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_label = {executor.submit(func): label for label, func in fetch_tasks.items()}
            for future in as_completed(future_to_label):
                label = future_to_label[future]
                try:
                    results[label] = future.result()
                except Exception as e:
                    print(f"  ⚠ fetching {label} failed: {e}")
                    results[label] = pd.Series()
                    
        df_list = []
        active_labels = []
        
        # Ensure specific order and handle naming
        ticker_names = {"SP500": "SPY", "TLT": "TLT", "GLD": "GLD", "VIX": "^VIX", "CSI300": "CSI300"}
        for label in ["SP500", "TLT", "GLD", "VIX", "CSI300"]:
            hist = results.get(label, pd.Series())
            if hist.empty:
                print(f"  ⚠ skipping {label} — no data")
                continue
            hist.name = ticker_names[label]
            if hasattr(hist.index, 'tz') and hist.index.tz is not None:
                hist.index = hist.index.tz_localize(None)
            df_list.append(hist)
            active_labels.append(label)

        has_csi = "CSI300" in active_labels

        if len(df_list) < 2:
            raise ValueError(f"Only {len(df_list)} assets available; need ≥2 for correlation")

        df = pd.concat(df_list, axis=1).ffill().dropna()
        returns = df.pct_change().dropna()
        corr = returns.corr().round(2)

        # use the ACTUAL columns from the DataFrame (stays in sync)
        actual_cols = list(corr.columns)
        n = len(actual_cols)
        data_list = []
        for i in range(n):
            for j in range(n):
                val = float(corr.iloc[i, j])
                if pd.isna(val):
                    val = 0.0
                data_list.append([j, i, val])

        # build user-friendly labels from actual column names
        label_pretty = []
        for c in actual_cols:
            if c == "SPY":      label_pretty.append("SP500 (美股)")
            elif c == "TLT":    label_pretty.append("TLT (长债)")
            elif c == "GLD":    label_pretty.append("GLD (黄金)")
            elif c == "^VIX":   label_pretty.append("VIX (恐慌)")
            elif c == "CSI300": label_pretty.append("沪深300 (A股)")
            else:               label_pretty.append(c)

        # Safely extract correlation pairs
        def get_corr(a, b):
            try:
                val = float(corr.loc[a, b])
                return 0.0 if pd.isna(val) else val
            except Exception:
                return 0.0

        spy_ticker = "SPY"
        tlt_ticker = "TLT"
        gld_ticker = "GLD"
        vix_ticker = "^VIX"
        csi_ticker = "CSI300"

        spy_tlt = get_corr(spy_ticker, tlt_ticker) if spy_ticker in corr.index and tlt_ticker in corr.index else 0.0
        spy_csi = get_corr(spy_ticker, csi_ticker) if has_csi else 0.0
        gld_vix = get_corr(gld_ticker, vix_ticker) if gld_ticker in corr.index and vix_ticker in corr.index else 0.0
        
        insight_lines = []
        state = "中性震荡"
        color = "#fbbf24"
        
        # 因子 A: 股债对冲
        if spy_tlt > settings.CORR_DUAL_KILL_THRESH:
            insight_lines.append(f"🔴 <b>股债双杀</b>：SPY与TLT正相关({spy_tlt:.2f})，传统60/40对冲失效。")
            state = "尾部重仓预警"
            color = "#ef4444"
        elif spy_tlt < -0.2:
            insight_lines.append(f"🟢 <b>对冲健康</b>：股债呈现负相关({spy_tlt:.2f})，投资组合具备极强韧性。")
            state = "对冲健康"
            color = "#4ade80"
        else:
            insight_lines.append(f"🟡 <b>震荡监测</b>：股债相关性中性({spy_tlt:.2f})，资产独立性尚可。")
            
        # 因子 B: 中美资产脱钩
        if has_csi:
            if spy_csi < 0.2:
                insight_lines.append(f"🇨🇳 <b>中美脱钩</b>：SPY与A股相关性极低({spy_csi:.2f})，建议超配A股作为风险隔离垫。")
            elif spy_csi > 0.6:
                insight_lines.append(f"⚠️ <b>系统共振</b>：SPY与A股高度联动({spy_csi:.2f})，跨国分散化投资失效。")
                
        # 因子 C: 黄金避险与熔断器
        if gld_vix < 0:
            insight_lines.append(f"⚠️ <b>流动性危机</b>：恐慌爆发但黄金遭抛售({gld_vix:.2f})，极致避险失效。")
            if spy_tlt > settings.CORR_DUAL_KILL_THRESH:
                # Smart Trigger: 只有股债双杀且黄金避险失效，才触发最高级别警报
                state = "全球流动性枯竭"
                color = "#ef4444"
                alert_text = " | ".join([line.replace('<b>', '').replace('</b>', '') for line in insight_lines])
                trigger_emergency_alert("【全球流动性枯竭】最高级别风控警报", alert_text)
        else:
            insight_lines.append(f"🛡️ <b>黄金防御</b>：GLD与VIX正相关({gld_vix:.2f})，贵金属抗风险属性完好。")

        insight = "<br/>".join(insight_lines)

        extreme_action = None
        if state == "全球流动性枯竭" or state == "尾部重仓预警":
            extreme_action = "放弃所有风险敞口与传统避险资产，即刻将 80% 以上仓位转为无风险现金（如 1-3 个月期美国国债 SHV）等待流动性恢复。"

        # ── alert state ──────────────────────────────────────
        if state == "全球流动性枯竭":
            set_alert("correlation", "danger", f"全球流动性枯竭 — 股债双杀 + 黄金避险失效")
        elif state == "尾部重仓预警":
            set_alert("correlation", "warning", f"尾部重仓预警 — SPY-TLT 相关性 {spy_tlt:.2f}")
        else:
            clear_alert("correlation")

        result = {
            "assets": label_pretty,
            "matrix": data_list,
            "insight": insight,
            "color": color,
            "state": state,
            "extreme_action": extreme_action
        }
        
        DATA_CACHE["correlation"]["data"] = result
        DATA_CACHE["correlation"]["timestamp"] = now
        return result
        
    except Exception as e:
        print(f"Error calculating correlation: {e}")
        return {"error": str(e), "matrix": []}

def run_montecarlo_sim():
    try:
        days = 252
        simulations = 1000
        start_price = 100.0
        
        # Phase 18: Portfolio-Level Monte Carlo
        alloc_data = calculate_asset_allocation()["allocation"]
        w_spy, w_tlt, w_gld, w_cash = 0.0, 0.0, 0.0, 0.0
        for item in alloc_data:
            val = item["value"] / 100.0
            name = item["name"]
            if "权益" in name or "成长" in name or "股" in name:
                w_spy += val
            elif "债" in name or "票据" in name:
                w_tlt += val
            elif "黄金" in name or "商品" in name or "另类" in name:
                w_gld += val
            elif "现金" in name or "等价物" in name:
                w_cash += val
                
        # Normalize weights
        total_w = w_spy + w_tlt + w_gld + w_cash
        if total_w > 0:
            w_spy /= total_w; w_tlt /= total_w; w_gld /= total_w; w_cash /= total_w
        else:
            w_spy = 1.0 # fallback
            
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        tickers = ["SPY", "TLT", "GLD"]
        fetch_tasks = {t: lambda t=t: get_us_etf_history(t, months=6) for t in tickers}
        fetch_tasks["CSI300"] = lambda: fetch_tushare_csi300_history(months=6)
        
        results = {}
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_label = {executor.submit(func): label for label, func in fetch_tasks.items()}
            for future in as_completed(future_to_label):
                label = future_to_label[future]
                try:
                    results[label] = future.result()
                except Exception:
                    results[label] = pd.Series()
                    
        df_list = []
        for t in tickers:
            hist = results.get(t, pd.Series())
            if not hist.empty:
                hist.name = t
                df_list.append(hist)
                
        if not df_list:
            # Fallback
            hist = results.get("CSI300", pd.Series())
            if hist.empty:
                raise ValueError("No historical data available for Monte Carlo")
            daily_returns_hist = hist.pct_change().dropna()
        else:
            df = pd.concat(df_list, axis=1).ffill().dropna()
            returns = df.pct_change().dropna()
            
            # Ensure columns exist, fill missing with 0 returns
            for col in tickers:
                if col not in returns.columns:
                    returns[col] = 0.0
                    
            # Calculate multivariate mean and covariance matrix
            mu_vec = returns[tickers].mean().values
            cov_mat = returns[tickers].cov().values
            
            # Risk-free rate from TNX cache
            tnx_cache = DATA_CACHE.get("tnx", {}).get("data")
            tnx_vals = tnx_cache.get("data", tnx_cache) if isinstance(tnx_cache, dict) else tnx_cache
            if hasattr(tnx_vals, "iloc"):
                tnx_rate = float(tnx_vals.iloc[-1]) if len(tnx_vals) > 0 else 4.0
            elif isinstance(tnx_vals, (list, tuple, str)):
                tnx_rate = float(tnx_vals[-1]) if len(tnx_vals) > 0 else 4.0
            else:
                tnx_rate = 4.0
            R_cash = (tnx_rate / 100.0) / 252.0
            
            if np.any(np.isnan(mu_vec)) or np.any(np.isnan(cov_mat)) or np.all(cov_mat == 0):
                mu_vec = np.array([0.085/days]*len(tickers))
                cov_mat = np.eye(len(tickers)) * (0.125/np.sqrt(days))**2
                
            asset_returns = np.random.multivariate_normal(mu_vec, cov_mat, (days, simulations))
            w_vec = np.array([w_spy, w_tlt, w_gld])
            port_returns = np.dot(asset_returns, w_vec) + (R_cash * w_cash)
            
            ann_mu = port_returns.mean() * days * 100
            ann_vol = port_returns.std() * np.sqrt(days) * 100
            
            price_paths = start_price * np.exp(np.cumsum(port_returns, axis=0))
        
        p50 = np.percentile(price_paths, 50, axis=1).round(2).tolist()
        p5 = np.percentile(price_paths, 5, axis=1).round(2).tolist()
        p95 = np.percentile(price_paths, 95, axis=1).round(2).tolist()
        
        p50.insert(0, start_price)
        p5.insert(0, start_price)
        p95.insert(0, start_price)
        
        dates = [f"T+{i}" for i in range(days + 1)]
        
        final_p5 = p5[-1]
        var_95 = round(((start_price - final_p5) / start_price) * 100, 2)
        
        # Formatted string for current weights
        weight_str = f"{int(w_spy*100)}%股/{int(w_tlt*100)}%债/{int(w_gld*100)}%金/{int(w_cash*100)}%现"

        if var_95 <= 0:
            insight = f"多资产对冲推演 ({weight_str})：在 95% 置信度下，得益于资产弱相关性，未来一年保本无虞，组合极其强壮 (Mu: {ann_mu:.1f}%, Vol: {ann_vol:.1f}%)。"
            color = "#4ade80"
        elif var_95 <= 15.0:
            insight = f"多资产对冲推演 ({weight_str})：在 95% 置信度下，得益于底层风险平价对冲，组合回撤底线被硬核压制在 -{var_95}% (VaR)，绝对收益护城河有效。"
            color = "#4ade80"
        else:
            insight = f"组合高危预警 ({weight_str})：在 95% 置信度下，当前配资方案依然存在超过 -{var_95}% 的系统性回撤 (VaR 越界)，尾部风险爆发！"
            color = "#ef4444"
            trigger_emergency_alert(f"动态组合 VaR 回撤突破警戒线 (-{var_95}%)", insight)
            
        return {
            "dates": dates,
            "p50": p50,
            "p5": p5,
            "p95": p95,
            "insight": insight,
            "color": color
        }
    except Exception as e:
        return {"error": str(e)}
