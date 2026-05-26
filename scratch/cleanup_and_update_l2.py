import os

def run():
    file_path = 'static/main.js'
    with open(file_path, 'rb') as f:
        raw_bytes = f.read()

    # Decode as UTF-8
    content = raw_bytes.decode('utf-8', errors='replace')
    
    # Check if there are double newlines in the content
    print("Original file length in chars:", len(content))
    
    # Normalize all line endings to LF first for reliable search & replace
    # This also helps clean up any \r\r\n or double \n\n issues
    content = content.replace('\r\n', '\n')
    content = content.replace('\r', '\n')
    
    # If the file had double-newlines everywhere (i.e. \n\n instead of \n), let's normalize it
    # We detect if \n\n occurs more than 2000 times in the file
    double_nl_count = content.count('\n\n')
    print("Double newlines count:", double_nl_count)
    
    if double_nl_count > 1000:
        print("Normalizing double newlines in file...")
        while '\n\n' in content:
            content = content.replace('\n\n', '\n')
        print("Normalized file length in chars:", len(content))

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
                    <div style="background:rgba(255,255,255,0.02); border:1px solid var(--row-border); border-radius:6px; padding:12px; display:flex; flex-direction:column; justify-content:space-between; min-height:125px;">
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

    # Normalize newlines for target and replacement
    normalized_target = target.replace('\r\n', '\n').replace('\r', '\n')
    normalized_replacement = replacement.replace('\r\n', '\n').replace('\r', '\n')

    if normalized_target in content:
        new_content = content.replace(normalized_target, normalized_replacement)
        # Convert all LFs back to CRLF for Windows environment
        new_content = new_content.replace('\n', '\r\n')
        with open(file_path, 'wb') as f:
            f.write(new_content.encode('utf-8'))
        print("SUCCESS: Normalized file and updated L2 Quant Engines visual hierarchy successfully!")
    else:
        print("ERROR: Target block not found in content!")
        # Let's inspect content around a smaller target if it failed
        # Just in case there was a minor space or character mismatch
        l2_sig_idx = content.find('l2_signals')
        if l2_sig_idx != -1:
            print("Found l2_signals at char index:", l2_sig_idx)
            print("Snippet around l2_signals:")
            print(content[l2_sig_idx-200:l2_sig_idx+500])

if __name__ == '__main__':
    run()
