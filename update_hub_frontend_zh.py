import re

def main():
    path = "static/main.js"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    start_idx = content.find("async function initDecisionHub() {")
    if start_idx == -1:
        print("Could not find initDecisionHub")
        return
        
    end_str = "Failed to load Decision Hub data. Check connection to core.</div>`;\n    }\n}"
    end_idx = content.find(end_str, start_idx)
    if end_idx == -1:
        print("Could not find end of initDecisionHub")
        return
    
    end_idx += len(end_str)
    
    new_func = """async function initDecisionHub() {
    const hubTime = document.getElementById('hub-time');
    if (hubTime) hubTime.textContent = new Date().toLocaleTimeString('en-US', {hour12: false});
    
    try {
        const response = await fetch('/api/institutional/decision_hub');
        const data = await response.json();
        
        // ----------------------------------------------------------------
        // Render L1 Macro (High-density 2x2 Grid with Glows)
        // ----------------------------------------------------------------
        const l1 = document.getElementById('hub-l1-content');
        if (l1) {
            const macro = data.l1_macro;
            const isStress = macro.vix_level > 25;
            const isCalm = macro.vix_level < 20;
            const scoreColor = macro.score > 70 ? '#22c55e' : (macro.score > 40 ? '#f59e0b' : '#ef4444');
            const regimeGlow = isStress ? 'rgba(239, 68, 68, 0.15)' : (isCalm ? 'rgba(34, 197, 94, 0.15)' : 'rgba(100, 116, 139, 0.1)');
            const regimeBorder = isStress ? '#ef4444' : (isCalm ? '#22c55e' : '#64748b');
            
            l1.style.display = 'grid';
            l1.style.gridTemplateColumns = '1fr 1fr';
            l1.style.gap = '12px';
            l1.innerHTML = `
                <div style="background:${regimeGlow}; border:1px solid ${regimeBorder}50; border-radius:6px; padding:12px; display:flex; flex-direction:column; justify-content:center; align-items:center; box-shadow:inset 0 0 20px ${regimeGlow};">
                    <span style="font-size:0.75rem; color:var(--text-tertiary); margin-bottom:4px; letter-spacing:1px;">宏观周期</span>
                    <strong style="color:${regimeBorder}; font-size:1.2rem; text-shadow:0 0 10px ${regimeBorder}80;">${macro.regime}</strong>
                </div>
                <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.05); border-radius:6px; padding:12px; display:flex; flex-direction:column; justify-content:center; align-items:center;">
                    <span style="font-size:0.75rem; color:var(--text-tertiary); margin-bottom:4px; letter-spacing:1px;">恐慌指数</span>
                    <strong style="font-family:var(--font-mono); font-size:1.2rem; color:var(--text-primary);">${macro.vix_level.toFixed(2)}</strong>
                </div>
                <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.05); border-radius:6px; padding:12px; display:flex; flex-direction:column; justify-content:center; align-items:center;">
                    <span style="font-size:0.75rem; color:var(--text-tertiary); margin-bottom:4px; letter-spacing:1px;">宏观得分</span>
                    <strong style="font-family:var(--font-mono); font-size:1.2rem; color:${scoreColor};">${macro.score}</strong>
                </div>
                <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.05); border-radius:6px; padding:12px; display:flex; flex-direction:column; justify-content:center; align-items:center;">
                    <span style="font-size:0.75rem; color:var(--text-tertiary); margin-bottom:4px; letter-spacing:1px;">权益上限</span>
                    <strong style="font-family:var(--font-mono); font-size:1.2rem; color:var(--text-primary);">${(macro.max_equity_exposure * 100).toFixed(0)}%</strong>
                </div>
                <div style="grid-column: span 2; margin-top:4px; padding:12px; background:rgba(0,0,0,0.3); border-radius:6px; border-left:4px solid ${isStress?'#ef4444':'#3b82f6'}; display:flex; justify-content:space-between; align-items:center;">
                    <span style="color:var(--text-secondary); font-size:0.85rem; letter-spacing:1px;">宏观指引:</span>
                    <strong style="font-family:var(--font-mono); font-size:1rem; color:${isStress?'#ef4444':'#60a5fa'}; text-shadow:0 0 10px ${isStress?'#ef4444':'#60a5fa'}40;">${macro.recommended_action}</strong>
                </div>
            `;
        }
        
        // ----------------------------------------------------------------
        // Render L2 Quant Signals
        // ----------------------------------------------------------------
        const l2 = document.getElementById('hub-l2-content');
        if (l2) {
            let html = '<div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; height:100%;">';
            data.l2_signals.forEach(sig => {
                const isBull = sig.signal > 0;
                const isBear = sig.signal < 0;
                const sColor = isBull ? '#22c55e' : (isBear ? '#ef4444' : '#64748b');
                const gradStart = isBull ? 'rgba(34,197,94,0.15)' : (isBear ? 'rgba(239,68,68,0.15)' : 'rgba(100,116,139,0.15)');
                const gradEnd = isBull ? 'rgba(34,197,94,0.02)' : (isBear ? 'rgba(239,68,68,0.02)' : 'rgba(100,116,139,0.02)');
                const th = sig.top_holding || {};
                const topStr = th.name ? `${th.name}` : '--';
                
                html += `
                    <div style="background:linear-gradient(135deg, ${gradStart} 0%, ${gradEnd} 100%); border:1px solid ${sColor}40; padding:16px 12px; border-radius:8px; display:flex; flex-direction:column; justify-content:space-between; position:relative; overflow:hidden;">
                        <!-- Glowing accent line at top -->
                        <div style="position:absolute; top:0; left:0; width:100%; height:2px; background:linear-gradient(90deg, transparent, ${sColor}, transparent);"></div>
                        
                        <span style="font-weight:bold; color:var(--text-primary); font-size:0.85rem; margin-bottom:12px; letter-spacing:0.5px; z-index:1;">${sig.source}</span>
                        
                        <div style="display:flex; justify-content:space-between; align-items:flex-end; z-index:1;">
                            <div style="display:flex; flex-direction:column;">
                                <span style="font-size:0.65rem; color:var(--text-tertiary); letter-spacing:1px; margin-bottom:2px;">核心持仓</span>
                                <span style="font-size:0.85rem; color:var(--text-secondary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:120px;">${topStr}</span>
                            </div>
                            <span style="color:${sColor}; font-family:var(--font-mono); font-weight:900; font-size:1.3rem; text-shadow:0 0 15px ${sColor}A0;">${sig.signal > 0 ? '+' : ''}${sig.signal}</span>
                        </div>
                    </div>
                `;
            });
            html += '</div>';
            l2.innerHTML = html;
        }
        
        // ----------------------------------------------------------------
        // Render L3 Routing & Allocation Chart
        // ----------------------------------------------------------------
        const rationaleEl = document.getElementById('hub-l3-rationale');
        if (rationaleEl) {
            rationaleEl.innerHTML = `<div style="display:inline-flex; align-items:center; background:rgba(56,189,248,0.1); padding:6px 12px; border-radius:4px; border:1px solid rgba(56,189,248,0.2);"><span style="color:#38bdf8; margin-right:8px; font-size:1.2em;">⬢</span> <span style="color:var(--text-secondary);">${data.l3_routing.rationale}</span></div>`;
        }
        
        const chartDom = document.getElementById('chart-hub-l3-alloc');
        if (chartDom && window.echarts) {
            let allocChart = echarts.getInstanceByDom(chartDom);
            if (!allocChart) allocChart = echarts.init(chartDom);
            
            const tgt = data.l3_routing.target_weights || {};
            const cur = data.l3_routing.before_weights || {};
            
            const symbols = Array.from(new Set([...Object.keys(tgt), ...Object.keys(cur)]));
            const curData = symbols.map(s => (cur[s] || 0) * 100);
            const tgtData = symbols.map(s => (tgt[s] || 0) * 100);
            
            allocChart.setOption({
                tooltip: {
                    trigger: 'axis',
                    backgroundColor: 'rgba(11, 13, 19, 0.9)',
                    borderColor: 'rgba(255,255,255,0.1)',
                    textStyle: { color: '#fff' },
                    axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(255,255,255,0.02)' } },
                    formatter: function(params) {
                        let res = `<div style="font-weight:bold; margin-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:6px; font-family:var(--font-mono);">${params[0].axisValue}</div>`;
                        params.forEach(p => {
                            res += `<div style="display:flex; justify-content:space-between; gap:16px; margin-bottom:4px;">
                                <span style="display:flex; align-items:center;"><span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${p.color.colorStops ? p.color.colorStops[0].color : p.color}; margin-right:8px;"></span><span style="color:var(--text-secondary);">${p.seriesName}</span></span>
                                <strong style="font-family:var(--font-mono);">${p.value.toFixed(1)}%</strong>
                            </div>`;
                        });
                        return res;
                    }
                },
                legend: {
                    data: ['当前仓位', '目标仓位'],
                    textStyle: { color: 'var(--text-secondary)', fontSize: 11 },
                    top: 0,
                    right: 0,
                    icon: 'roundRect'
                },
                grid: { left: '2%', right: '2%', bottom: '2%', top: '35px', containLabel: true },
                xAxis: {
                    type: 'category',
                    data: symbols,
                    axisLabel: { color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', fontSize: 10, interval: 0, rotate: 30 },
                    axisTick: { show: false },
                    axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } }
                },
                yAxis: {
                    type: 'value',
                    axisLabel: { color: 'var(--text-tertiary)', formatter: '{value}%', fontFamily: 'var(--font-mono)', fontSize: 10 },
                    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.03)', type: 'dashed' } }
                },
                series: [
                    {
                        name: '当前仓位',
                        type: 'bar',
                        data: curData,
                        itemStyle: { color: 'rgba(100, 116, 139, 0.3)', borderRadius: [2, 2, 0, 0], borderColor: 'rgba(100, 116, 139, 0.8)', borderWidth: 1 },
                        barWidth: '30%',
                        barGap: '15%'
                    },
                    {
                        name: '目标仓位',
                        type: 'bar',
                        data: tgtData,
                        itemStyle: { 
                            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                                { offset: 0, color: '#a855f7' },
                                { offset: 1, color: '#3b82f6' }
                            ]),
                            borderRadius: [3, 3, 0, 0],
                            shadowBlur: 10,
                            shadowColor: 'rgba(168, 85, 247, 0.4)'
                        },
                        barWidth: '30%'
                    }
                ]
            });
            window.addEventListener('resize', () => allocChart.resize());
        }
        
        // ----------------------------------------------------------------
        // Render L4 Compliance Gate
        // ----------------------------------------------------------------
        const l4 = document.getElementById('hub-l4-content');
        const l4Card = document.getElementById('hub-l4-card');
        if (l4) {
            const comp = data.l4_compliance;
            const isBlock = comp.gate_status === 'HARD_BLOCK';
            const isWarn = comp.gate_status === 'SOFT_WARNING';
            const statusColor = isBlock ? '#ef4444' : (isWarn ? '#f59e0b' : '#22c55e');
            
            // Apply warning tape styling if blocked
            if (isBlock) {
                l4Card.style.background = 'repeating-linear-gradient(45deg, rgba(239, 68, 68, 0.05), rgba(239, 68, 68, 0.05) 10px, rgba(0, 0, 0, 0) 10px, rgba(0, 0, 0, 0) 20px)';
                l4Card.style.border = '1px solid rgba(239,68,68,0.3)';
                l4Card.style.boxShadow = '0 0 30px rgba(239,68,68,0.1) inset';
            } else if (isWarn) {
                l4Card.style.border = '1px solid rgba(245,158,11,0.3)';
            } else {
                l4Card.style.border = '1px solid rgba(34,197,94,0.3)';
            }
            
            l4Card.style.borderLeft = `4px solid ${statusColor}`;
            
            let html = `
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div style="display:flex; align-items:center; gap:12px;">
                        <div style="width:12px; height:12px; border-radius:50%; background:${statusColor}; box-shadow:0 0 10px ${statusColor}; animation: modalFadeIn 1s infinite alternate;"></div>
                        <div style="font-size:1.3rem; font-weight:900; color:${statusColor}; font-family:var(--font-mono); letter-spacing:2px; text-shadow:0 0 15px ${statusColor}80;">
                            [ ${comp.gate_status} ]
                        </div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:0.65rem; color:var(--text-tertiary); letter-spacing:1px;">风控合规评分</div>
                        <div style="font-size:1.8rem; font-weight:900; color:var(--text-primary); font-family:var(--font-mono); line-height:1;">${comp.score}</div>
                    </div>
                </div>
                <div style="width:100%; height:4px; background:rgba(255,255,255,0.05); margin-top:16px; margin-bottom:16px; border-radius:2px; overflow:hidden;">
                    <div style="height:100%; width:${comp.score}%; background:${statusColor}; transition:width 1.5s cubic-bezier(0.4, 0, 0.2, 1); box-shadow:0 0 10px ${statusColor};"></div>
                </div>
            `;
            
            if (comp.violations && comp.violations.length > 0) {
                html += `
                    <div style="margin-top:auto; background:rgba(0,0,0,0.4); border:1px solid rgba(239,68,68,0.2); border-radius:4px; padding:12px; font-family:var(--font-mono); font-size:0.8rem;">
                        <div style="color:#ef4444; margin-bottom:8px; font-weight:bold; letter-spacing:1px; display:flex; align-items:center; gap:6px;">
                            <i class="fas fa-exclamation-triangle"></i> 触发硬性风控拦截:
                        </div>
                        <ul style="margin:0; padding-left:20px; color:#fca5a5; line-height:1.6;">
                            ${comp.violations.map(v => `<li>> ${v}</li>`).join('')}
                        </ul>
                    </div>
                `;
            } else if (comp.warnings && comp.warnings.length > 0) {
                html += `
                    <div style="margin-top:auto; background:rgba(0,0,0,0.4); border:1px solid rgba(245,158,11,0.2); border-radius:4px; padding:12px; font-family:var(--font-mono); font-size:0.8rem;">
                        <div style="color:#f59e0b; margin-bottom:8px; font-weight:bold; letter-spacing:1px;">! 触发软性风控预警:</div>
                        <ul style="margin:0; padding-left:20px; color:#fcd34d; line-height:1.6;">
                            ${comp.warnings.map(v => `<li>> ${v}</li>`).join('')}
                        </ul>
                    </div>
                `;
            } else {
                html += `
                    <div style="margin-top:auto; background:rgba(0,0,0,0.4); border:1px solid rgba(34,197,94,0.2); border-radius:4px; padding:12px; font-family:var(--font-mono); font-size:0.8rem; color:#86efac; display:flex; align-items:center; gap:8px;">
                        <i class="fas fa-check-circle" style="color:#22c55e;"></i> 全量风控规则检验通过
                    </div>
                `;
            }
            
            html += `
                <div style="display:flex; justify-content:space-between; color:var(--text-tertiary); font-family:var(--font-mono); font-size:0.75rem; margin-top:8px;">
                    <span>预估换仓换手率:</span>
                    <strong style="color:var(--text-secondary);">${(comp.turnover * 100).toFixed(1)}%</strong>
                </div>
            `;
            
            l4.innerHTML = html;
        }
        
        // ----------------------------------------------------------------
        // Render L5 AI-CIO Synthesis
        // ----------------------------------------------------------------
        const l5 = document.getElementById('hub-l5-content');
        const l5Card = document.getElementById('hub-l5-card');
        if (l5) {
            const memo = data.l5_ai_memo;
            const isBlocked = memo.headline.includes('BLOCKED');
            const isWarned = memo.headline.includes('WARN');
            const memoColor = isBlocked ? '#ef4444' : (isWarned ? '#f59e0b' : '#a855f7'); // Use purple for AI insight
            
            // Frosted glass effect for AI memo
            l5Card.style.borderTop = `1px solid ${memoColor}80`;
            l5Card.style.boxShadow = `0 -10px 30px ${memoColor}15`;
            
            l5.style.border = `1px solid ${memoColor}30`;
            l5.style.background = `linear-gradient(180deg, ${memoColor}10 0%, rgba(0,0,0,0.5) 100%)`;
            l5.style.backdropFilter = 'blur(16px)';
            
            l5.innerHTML = `
                <div style="display:flex; align-items:center; gap:16px; margin-bottom:16px; border-bottom:1px solid rgba(255,255,255,0.05); padding-bottom:16px;">
                    <div style="width:48px; height:48px; border-radius:12px; background:${memoColor}20; border:1px solid ${memoColor}40; display:flex; justify-content:center; align-items:center; color:${memoColor}; font-size:1.5rem; box-shadow:0 0 15px ${memoColor}40;">
                        <i class="fas fa-robot"></i>
                    </div>
                    <div>
                        <div style="font-size:0.7rem; color:var(--text-tertiary); letter-spacing:2px; font-family:var(--font-mono); margin-bottom:4px;">AI-CIO 决策归因协议</div>
                        <h2 style="color:${memoColor}; margin:0; font-size:1.3rem; letter-spacing:1px; text-shadow:0 0 15px ${memoColor}80;">${memo.headline}</h2>
                    </div>
                </div>
                <div style="padding:0 8px;">
                    <p style="margin-bottom:0; font-size:1.05rem; line-height:1.8; color:var(--text-primary); text-align:justify; position:relative;">
                        <span style="color:${memoColor}; font-family:var(--font-mono); margin-right:8px;">></span>${memo.memo}
                        <span style="display:inline-block; width:8px; height:18px; background:${memoColor}; margin-left:8px; vertical-align:middle; animation: modalFadeIn 0.8s infinite alternate;"></span>
                    </p>
                </div>
            `;
        }
        
    } catch (e) {
        console.error("Decision Hub Error", e);
        const l1 = document.getElementById('hub-l1-content');
        if (l1) l1.innerHTML = `<div style="color:#ef4444;">Failed to load Decision Hub data. Check connection to core.</div>`;
    }
}
"""

    new_content = content[:start_idx] + new_func + content[end_idx:]
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Successfully replaced initDecisionHub in main.js with Chinese translations.")

if __name__ == "__main__":
    main()
