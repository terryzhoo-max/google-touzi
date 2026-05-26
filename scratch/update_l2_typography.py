import os

def run():
    file_path = 'static/main.js'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target = """        if (l2) {
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
                                <span style="color:var(--text-secondary);">${s.top_holding ? (typeof s.top_holding === 'object' ? (s.top_holding.symbol || s.top_holding.name || JSON.stringify(s.top_holding)) : s.top_holding) : '--'}</span>
                            </div>
                            <div style="font-family:var(--font-mono); font-weight:900; font-size:0.9rem; color:${valColor}; text-shadow:0 0 10px ${valColor}40;">
                                ${valText}
                            </div>
                        </div>
                    </div>
                `;
            });
            l2.innerHTML = html;
        }"""

    replacement = """        if (l2) {
            const sigs = data.l2_signals || [];
            let html = '';
            
            const signalZHMap = {
                'BULLISH': '多头看涨',
                'BEARISH': '空头看跌',
                'DEFENSIVE TILT': '防御倾向',
                'A-SHARE CAUTION': 'A股谨慎对冲',
                'HEDGE ACTIVE': '对冲激活',
                'HEDGE INACTIVE': '未对冲',
                'OVERWEIGHT OVERSEAS': '超配海外宽基',
                'OVERWEIGHT A-SHARE': '超配A股资产',
                'PLACEHOLDER - NOT TRADEABLE': '等候接入 (不可交易)',
                'BULLISH ON GOLD': '看多黄金',
                'NEUTRAL ON GOLD': '常规避险 (中性持有)',
                'NO_SIGNAL': '暂无信号'
            };

            sigs.forEach(s => {
                const k = s.source || 'Unknown';
                const valColor = s.signal > 0.5 ? '#22c55e' : (s.signal < -0.5 ? '#ef4444' : '#94a3b8');
                const valText = s.signal > 0.5 ? (k.toLowerCase().includes('parity') ? 'OVERWEIGHT OVERSEAS' : 'BULLISH') : 
                               (s.signal < -0.5 ? (k.toLowerCase().includes('hedge') ? 'HEDGE ACTIVE' : 'BEARISH') : 
                               (k.toLowerCase().includes('hedge') ? 'HEDGE INACTIVE' : (k.toLowerCase().includes('barbell') ? 'DEFENSIVE TILT' : 'A-SHARE CAUTION')));
                
                const rawSig = s.raw_text || valText;
                const sigZH = signalZHMap[rawSig] || rawSig;
                const sigEN = rawSig;
                
                let targetName = '--';
                let targetSymbol = '';

                if (s.top_holding) {
                    if (typeof s.top_holding === 'object') {
                        targetName = s.top_holding.name || '--';
                        targetSymbol = s.top_holding.symbol || '';
                    } else {
                        targetSymbol = s.top_holding;
                        const cleanSymbol = targetSymbol.split('.')[0];
                        const symNames = (data.l3_routing && data.l3_routing.symbol_names) || window.symbolNamesCache || {};
                        targetName = symNames[targetSymbol] || symNames[cleanSymbol] || targetSymbol;
                    }
                }

                html += `
                    <div style="background:rgba(255,255,255,0.02); border:1px solid var(--row-border); border-radius:6px; padding:12px; display:flex; flex-direction:column; justify-content:space-between; min-height:120px;">
                        <div style="display:flex; flex-direction:column; margin-bottom:8px; gap:2px;">
                            <span style="font-size:0.95rem; font-weight:700; color:var(--text-primary);">${s.source_zh || s.source}</span>
                            ${s.source_zh ? `<span style="font-size:0.65rem; color:var(--text-tertiary); font-family:var(--font-mono); text-transform:uppercase; letter-spacing:0.5px; font-weight:400;">${s.source}</span>` : ''}
                        </div>
                        <div style="display:flex; justify-content:space-between; align-items:flex-end;">
                            <div style="font-size:0.75rem; color:var(--text-tertiary); line-height:1.3; display:flex; flex-direction:column; gap:2px;">
                                <span>顶配锚定 <small style="font-size:0.8em; color:var(--text-tertiary); font-family:var(--font-mono);">TOP HOLDING</small></span>
                                <span style="font-weight:700; color:var(--text-primary); font-size:0.85rem; margin-top:2px;">${targetName}</span>
                                <span style="color:var(--text-tertiary); font-family:var(--font-mono); font-size:0.65rem;">${targetSymbol}</span>
                            </div>
                            <div style="font-family:var(--font-sans); font-weight:900; font-size:1rem; color:${valColor}; text-shadow:0 0 10px ${valColor}40; text-align:right; line-height:1.2;">
                                ${sigZH}
                                <small style="display:block; font-size:0.65rem; font-family:var(--font-mono); color:var(--text-tertiary); font-weight:400; text-transform:uppercase; margin-top:2px;">${sigEN}</small>
                            </div>
                        </div>
                    </div>
                `;
            });
            l2.innerHTML = html;
        }"""

    normalized_content = content.replace('\r\n', '\n')
    normalized_target = target.replace('\r\n', '\n')
    normalized_replacement = replacement.replace('\r\n', '\n')

    if normalized_target in normalized_content:
        new_content = normalized_content.replace(normalized_target, normalized_replacement)
        # Restore CRLF
        new_content = new_content.replace('\n', '\r\n')
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("SUCCESS: L2 Quant Engines visual hierarchy optimized!")
    else:
        print("ERROR: Target not found in file!")

if __name__ == '__main__':
    run()
