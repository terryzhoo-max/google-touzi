import re
import codecs

with codecs.open('static/main.js', 'r', 'utf-8') as f:
    content = f.read()

# Define the start and end markers
start_marker = "// Render L4 Compliance Gate"
end_marker = "// Render L5 AI-CIO Synthesis"

if start_marker not in content or end_marker not in content:
    print("Markers not found!")
    exit(1)

# Extract everything before and after L4
before_l4 = content.split(start_marker)[0]
after_l4 = content.split(end_marker)[1]

new_l4_logic = """// Render L4 Compliance Gate
        // ----------------------------------------------------------------
        const l4 = document.getElementById('hub-l4-content');
        const l4Card = document.getElementById('hub-l4-card');
        if (l4) {
            const comp = data.l4_compliance;
            const isBlock = comp.gate_status === 'HARD_BLOCK';
            const isWarn = comp.gate_status === 'SOFT_WARNING';
            const statusColor = isBlock ? '#ef4444' : (isWarn ? '#f59e0b' : '#22c55e');
            
            // Institutional Translation Engine
            const translateRisk = (rawStr) => {
                if (rawStr.startsWith('region_limit_exceeded:')) return '🚨 单一区域暴露超限: ' + rawStr.split(':')[1];
                if (rawStr.startsWith('strategy_limit_exceeded:')) return '🚨 单一策略敞口超限: ' + rawStr.split(':')[1];
                if (rawStr.startsWith('position_limit_exceeded:')) return '🚨 单一标的权重超限: ' + rawStr.split(':')[1];
                if (rawStr.startsWith('trade_size_exceeded:')) return '⚠️ 单次调仓流动性规模超限: ' + rawStr.split(':')[1];
                if (rawStr === 'turnover_exceeded') return '⚠️ 组合预估换手率超额限制';
                if (rawStr === 'no_new_risk_when_risk_high') return '🔒 高波警戒期禁止风险敞口扩张';
                if (rawStr === 'fallback_data_non_defensive_action') return '🔒 数据降级期间禁止非防御性建仓';
                return rawStr;
            };
            
            // Apply warning tape styling if blocked
            if (isBlock) {
                l4Card.style.background = 'repeating-linear-gradient(45deg, rgba(239, 68, 68, 0.05), rgba(239, 68, 68, 0.05) 10px, rgba(0, 0, 0, 0) 10px, rgba(0, 0, 0, 0) 20px)';
                l4Card.style.border = '1px solid rgba(239,68,68,0.3)';
                l4Card.style.boxShadow = '0 0 30px rgba(239,68,68,0.1) inset';
            } else if (isWarn) {
                l4Card.style.background = 'repeating-linear-gradient(45deg, rgba(245, 158, 11, 0.03), rgba(245, 158, 11, 0.03) 10px, rgba(0, 0, 0, 0) 10px, rgba(0, 0, 0, 0) 20px)';
                l4Card.style.border = '1px solid rgba(245,158,11,0.3)';
                l4Card.style.boxShadow = '0 0 20px rgba(245,158,11,0.05) inset';
            } else {
                l4Card.style.background = '';
                l4Card.style.border = '1px solid rgba(34,197,94,0.3)';
                l4Card.style.boxShadow = '';
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
                            <i class="fas fa-ban"></i> 触发硬性风控拦截
                        </div>
                        <ul style="margin:0; padding-left:20px; color:#fca5a5; line-height:1.6;">
                            ${comp.violations.map(v => `<li>${translateRisk(v)}</li>`).join('')}
                        </ul>
                    </div>
                `;
            } else if (comp.warnings && comp.warnings.length > 0) {
                html += `
                    <div style="margin-top:auto; background:rgba(0,0,0,0.4); border:1px solid rgba(245,158,11,0.2); border-radius:4px; padding:12px; font-family:var(--font-mono); font-size:0.8rem;">
                        <div style="color:#f59e0b; margin-bottom:8px; font-weight:bold; letter-spacing:1px; display:flex; align-items:center; gap:6px;">
                            <i class="fas fa-exclamation-triangle"></i> 触发软性风控预警
                        </div>
                        <ul style="margin:0; padding-left:20px; color:#fcd34d; line-height:1.6;">
                            ${comp.warnings.map(v => `<li>${translateRisk(v)}</li>`).join('')}
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
                    <span>预估调仓换手率</span>
                    <strong style="color:var(--text-secondary);">${(comp.turnover * 100).toFixed(1)}%</strong>
                </div>
            `;
            
            l4.innerHTML = html;
        }
        
        // ----------------------------------------------------------------
        // Render L5 AI-CIO Synthesis"""

final_content = before_l4 + start_marker + new_l4_logic[len(start_marker):] + after_l4

with codecs.open('static/main.js', 'w', 'utf-8') as f:
    f.write(final_content)

print("L4 Compliance successfully rewritten to production grade with strict UTF-8!")
