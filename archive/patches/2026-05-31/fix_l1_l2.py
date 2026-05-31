import re
import codecs

with codecs.open('static/main.js', 'r', 'utf-8') as f:
    full_content = f.read()

# Fix L1
l1_fix = """
        const l1 = document.getElementById('hub-l1-content');
        if (l1) {
            const macro = data.l1_macro;
            const regimeColor = macro.regime === 'NEUTRAL' ? '#22c55e' : (macro.regime === 'DEFENSIVE' ? '#ef4444' : '#3b82f6');
            const regimeBg = macro.regime === 'NEUTRAL' ? 'rgba(34,197,94,0.1)' : (macro.regime === 'DEFENSIVE' ? 'rgba(239,68,68,0.1)' : 'rgba(59,130,246,0.1)');
            const regimeBorder = macro.regime === 'NEUTRAL' ? '#22c55e' : (macro.regime === 'DEFENSIVE' ? '#ef4444' : '#3b82f6');
            
            // Map the regime to Chinese
            const regimeCnMap = {
                'NEUTRAL': '中性震荡',
                'BULLISH': '常态扩张',
                'DEFENSIVE': '防御收缩'
            };
            const regimeCn = regimeCnMap[macro.regime] || macro.regime;
            
            l1.innerHTML = `
                <div style="flex:1; min-width:140px; background:${regimeBg}; border:1px solid ${regimeBorder}40; border-radius:6px; padding:16px; text-align:center; box-shadow:0 0 20px ${regimeBg} inset;">
                    <div style="font-size:0.75rem; color:var(--text-tertiary); margin-bottom:4px; letter-spacing:1px;">宏观周期</div>
                    <strong style="color:${regimeBorder}; font-size:1.2rem; text-shadow:0 0 10px ${regimeBorder}80;">${regimeCn}</strong>
                </div>
                <div style="flex:1; min-width:140px; background:rgba(255,255,255,0.02); border:1px solid var(--row-border); border-radius:6px; padding:16px; text-align:center;">
                    <div style="font-size:0.75rem; color:var(--text-tertiary); margin-bottom:4px; letter-spacing:1px;">恐慌指数(VIX)</div>
                    <strong style="color:var(--text-primary); font-size:1.2rem; font-family:var(--font-mono);">${macro.vix_level !== undefined ? macro.vix_level.toFixed(2) : '--'}</strong>
                </div>
                <div style="flex:1; min-width:140px; background:rgba(255,255,255,0.02); border:1px solid var(--row-border); border-radius:6px; padding:16px; text-align:center;">
                    <div style="font-size:0.75rem; color:var(--text-tertiary); margin-bottom:4px; letter-spacing:1px;">核心动能</div>
                    <strong style="color:var(--accent-secondary); font-size:1.2rem; font-family:var(--font-mono);">${macro.score !== undefined ? macro.score : '--'}</strong>
                </div>
                <div style="flex:1; min-width:140px; background:rgba(255,255,255,0.02); border:1px solid var(--row-border); border-radius:6px; padding:16px; text-align:center;">
                    <div style="font-size:0.75rem; color:var(--text-tertiary); margin-bottom:4px; letter-spacing:1px;">股债偏好水位</div>
                    <strong style="color:var(--text-primary); font-size:1.2rem; font-family:var(--font-mono);">${macro.max_equity_exposure !== undefined ? (macro.max_equity_exposure * 100).toFixed(0) + '%' : '--'}</strong>
                </div>
                <div style="width:100%; margin-top:8px; padding:12px; border-left:3px solid var(--accent-primary); background:rgba(59,130,246,0.05); font-family:var(--font-mono); font-size:0.85rem; color:var(--text-secondary); display:flex; justify-content:space-between;">
                    <span>执行动作建议:</span>
                    <strong style="color:var(--accent-primary);">${macro.recommended_action || 'MAINTAIN'}</strong>
                </div>
            `;
        }
"""

l2_fix = """
        const l2 = document.getElementById('hub-l2-content');
        if (l2) {
            const sigs = data.l2_signals || [];
            let html = '';
            sigs.forEach(s => {
                const k = s.source || 'Unknown';
                const valColor = s.signal > 0.5 ? '#22c55e' : (s.signal < -0.5 ? '#ef4444' : '#94a3b8');
                const valText = s.signal > 0.5 ? (k.toLowerCase().includes('parity') ? 'OVERWEIGHT OVERSEAS' : 'BULLISH') : 
                               (s.signal < -0.5 ? (k.toLowerCase().includes('hedge') ? 'HEDGE ACTIVE' : 'BEARISH') : 
                               (k.toLowerCase().includes('hedge') ? 'HEDGE INACTIVE' : (k.toLowerCase().includes('barbell') ? 'DEFENSIVE TILT' : 'A-SHARE CAUTION')));
                html += `
                    <div style="background:rgba(255,255,255,0.02); border:1px solid var(--row-border); border-radius:6px; padding:12px; display:flex; flex-direction:column; justify-content:space-between;">
                        <div style="font-size:0.8rem; font-weight:bold; color:var(--text-primary); margin-bottom:8px; letter-spacing:1px;">${k.replace(/_/g, ' ').toUpperCase()}</div>
                        <div style="display:flex; justify-content:space-between; align-items:flex-end;">
                            <div style="font-size:0.7rem; color:var(--text-tertiary); font-family:var(--font-mono);">
                                顶配锚定<br>
                                <span style="color:var(--text-secondary);">${s.top_holding || '--'}</span>
                            </div>
                            <div style="font-family:var(--font-mono); font-weight:900; font-size:0.9rem; color:${valColor}; text-shadow:0 0 10px ${valColor}40;">
                                ${valText}
                            </div>
                        </div>
                    </div>
                `;
            });
            l2.innerHTML = html;
        }
"""

# Use regex to replace the sections in static/main.js
import re

new_content = re.sub(r"const l1 = document\.getElementById\('hub-l1-content'\);.*?// Render L2 Quant Signals", l1_fix.strip() + "\n        \n        // ----------------------------------------------------------------\n        // Render L2 Quant Signals", full_content, flags=re.DOTALL)
new_content = re.sub(r"const l2 = document\.getElementById\('hub-l2-content'\);.*?// Render L3 Allocator", l2_fix.strip() + "\n        \n        // ----------------------------------------------------------------\n        // Render L3 Allocator", new_content, flags=re.DOTALL)

with codecs.open('static/main.js', 'w', 'utf-8') as f:
    f.write(new_content)

print("L1 and L2 successfully patched for data schema.")
