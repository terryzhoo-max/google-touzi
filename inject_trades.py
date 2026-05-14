import os

with open("update_hub_frontend_zh_new.py", "r", encoding="utf-8") as f:
    content = f.read()

trade_logic = """
            });
            window.addEventListener('resize', () => allocChart.resize());
            
            // --- INJECT TRADE DIRECTIVES ---
            let tradesContainer = document.getElementById('hub-l3-trades');
            if (!tradesContainer) {
                tradesContainer = document.createElement('div');
                tradesContainer.id = 'hub-l3-trades';
                tradesContainer.style.marginTop = '12px';
                tradesContainer.style.padding = '12px';
                tradesContainer.style.background = 'rgba(0,0,0,0.2)';
                tradesContainer.style.borderRadius = '6px';
                tradesContainer.style.border = '1px solid rgba(255,255,255,0.05)';
                chartDom.parentNode.appendChild(tradesContainer);
            }
            
            let tradesHtml = `<div style="font-size:0.75rem; color:var(--text-tertiary); margin-bottom:8px; letter-spacing:1px; display:flex; justify-content:space-between; align-items:center;">
                <span>执行建议 (TRADE DIRECTIVES)</span>`;
            
            if (data.l3_routing.backtest_metrics && data.l3_routing.backtest_metrics.strat_sharpe !== undefined) {
                const sharpe = data.l3_routing.backtest_metrics.strat_sharpe;
                if (sharpe > 1.0) {
                    tradesHtml += `<span style="color:#22c55e; border:1px solid #22c55e50; padding:2px 6px; border-radius:4px; font-weight:bold;">高确信度 | 夏普: ${sharpe}</span>`;
                } else {
                    tradesHtml += `<span style="color:#f59e0b; border:1px solid #f59e0b50; padding:2px 6px; border-radius:4px;">中等确信度 | 夏普: ${sharpe}</span>`;
                }
            }
            tradesHtml += `</div><div style="display:flex; flex-wrap:wrap; gap:8px;">`;
            
            let hasTrades = false;
            const symNames = data.l3_routing.symbol_names || {};
            symbols.forEach(s => {
                const diff = (tgt[s] || 0) - (cur[s] || 0);
                const diffPct = diff * 100;
                const sName = symNames[s] || s;
                if (Math.abs(diffPct) > 0.5) {
                    hasTrades = true;
                    if (diffPct > 0) {
                        tradesHtml += `<span style="color:#22c55e; border:1px solid #22c55e; background:rgba(34,197,94,0.1); padding:4px 8px; border-radius:4px; font-family:var(--font-mono); font-size:0.9rem; box-shadow:0 0 8px rgba(34,197,94,0.2);">买入 ${sName} +${diffPct.toFixed(1)}%</span>`;
                    } else {
                        tradesHtml += `<span style="color:#ef4444; border:1px solid #ef4444; background:rgba(239,68,68,0.1); padding:4px 8px; border-radius:4px; font-family:var(--font-mono); font-size:0.9rem; box-shadow:0 0 8px rgba(239,68,68,0.2);">卖出 ${sName} ${diffPct.toFixed(1)}%</span>`;
                    }
                }
            });
            
            if (!hasTrades) {
                tradesHtml += `<span style="color:var(--text-tertiary); font-style:italic; font-size:0.9rem;">无需调仓 (HOLD) - 仓位偏离极小</span>`;
            }
            tradesHtml += `</div>`;
            tradesContainer.innerHTML = tradesHtml;
        }
"""

new_content = content.replace("            });\n            window.addEventListener('resize', () => allocChart.resize());\n        }", trade_logic)

with open("update_hub_frontend_zh_new.py", "w", encoding="utf-8") as f:
    f.write(new_content)

print("Injected trade logic into update_hub_frontend_zh_new.py")
