import re

with open('d:\\FIONA\\google touzi\\static\\main.js', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update injectTradeFromModal
inject_replacement = '''async function injectTradeFromModal(action, qty) {
    if (!currentActionContext || qty <= 0) return;
    
    // UI state: disable buttons
    const btns = document.querySelectorAll('.modal-action-btn');
    btns.forEach(b => b.disabled = true);
    const originalText = btns[0].innerText;
    btns[0].innerText = 'EXECUTING...';

    try {
        const response = await fetch('/api/execute', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                ticker: currentActionContext.ticker,
                action: action,
                qty: parseFloat(qty)
            })
        });
        const result = await response.json();
        if(result.status === 'success') {
            // refresh execution history immediately
            if(window.refreshAuditTrail) window.refreshAuditTrail();
        } else {
            alert('[SYS_ERROR] Gateway Execution Failed: ' + (result.error || 'Unknown error'));
        }
    } catch(e) {
        alert('[SYS_ERROR] Gateway Offline or Unreachable.');
    } finally {
        btns.forEach(b => b.disabled = false);
        btns[0].innerText = originalText;
        closeActionModal();
        if (!document.getElementById('view-simu').classList.contains('active')) {
            switchView('simu');
        }
    }
}'''

text = re.sub(r'function injectTradeFromModal\(action, qty\)\s*\{.*?switchView\(\'simu\'\);\s*\}\s*\}', inject_replacement, text, flags=re.DOTALL)

# 2. Strip out the inline rendering in initDecisionHub BEFORE appending the new function
inline_render_pattern = r'const historyCard = document\.getElementById\(\'hub-execution-history-card\'\);.*?historyContent\.innerHTML = historyHTML;\s*\}'
text = re.sub(inline_render_pattern, 'renderExecutionHistory(data.recent_executions);', text, flags=re.DOTALL)

# 3. Add renderExecutionHistory and startAuditTrailSync at the end of the file
polling_code = '''

// ==========================================
// L6 EXECUTION GATEWAY & POLLING
// ==========================================

function renderExecutionHistory(recentExecutions) {
    const historyCard = document.getElementById('hub-execution-history-card');
    const historyContent = document.getElementById('hub-execution-history-content');
    if (!historyCard || !historyContent) return;
    
    historyCard.style.display = 'block';
    
    let historyHTML = `
        <table class="institutional-table" style="width:100%; font-family:var(--font-mono); font-size:0.8rem; margin:0; border-collapse:collapse;">
            <thead>
                <tr style="border-bottom:1px solid rgba(255,255,255,0.1); color:var(--text-tertiary);">
                    <th style="padding:8px; text-align:left;">时间 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">TIMESTAMP</span></th>
                    <th style="padding:8px; text-align:left;">单号 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">ORDER ID</span></th>
                    <th style="padding:8px; text-align:left;">方向 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">ACTION</span></th>
                    <th style="padding:8px; text-align:left;">标的 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">SYMBOL</span></th>
                    <th style="padding:8px; text-align:right;">数量 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">QTY</span></th>
                    <th style="padding:8px; text-align:right;">成交价 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">PRICE</span></th>
                    <th style="padding:8px; text-align:right;">状态 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">STATUS</span></th>
                </tr>
            </thead>
            <tbody>
    `;
    
    if (!recentExecutions || recentExecutions.length === 0) {
        historyHTML += `
            <tr style="background:rgba(0,0,0,0.2);">
                <td colspan="7" style="text-align:center; padding:30px; color:var(--text-tertiary); font-family:var(--font-mono); font-size:0.85rem; letter-spacing:2px; border-bottom:1px solid rgba(255,255,255,0.05);">
                    NO EXECUTED TRADES FOUND IN DATABASE
                </td>
            </tr>
        `;
    } else {
        recentExecutions.forEach(tx => {
            const dateObj = new Date(tx.timestamp * 1000);
            const timeStr = dateObj.toLocaleTimeString('zh-CN', {hour12:false});
            const actionColor = tx.action.includes('BUY') ? '#22c55e' : (tx.action.includes('SELL') ? '#ef4444' : '#f59e0b');
            const actionBg = tx.action.includes('BUY') ? 'rgba(34,197,94,0.1)' : (tx.action.includes('SELL') ? 'rgba(239,68,68,0.1)' : 'rgba(245,158,11,0.1)');
            
            historyHTML += `
                <tr style="border-bottom:1px solid rgba(255,255,255,0.05); transition:background 0.2s;">
                    <td style="padding:8px;">${timeStr}</td>
                    <td style="padding:8px; color:var(--accent-secondary);">${tx.order_id}</td>
                    <td style="padding:8px;">
                        <span style="color:${actionColor}; background:${actionBg}; padding:2px 6px; border-radius:3px; font-weight:700; font-size:0.7rem;">${tx.action}</span>
                    </td>
                    <td style="padding:8px; font-weight:700;">${tx.symbol}</td>
                    <td style="padding:8px; text-align:right; color:var(--text-primary);">${tx.quantity}</td>
                    <td style="padding:8px; text-align:right; color:var(--text-secondary);">${parseFloat(tx.limit_price || 0).toFixed(2)}</td>
                    <td style="padding:8px; text-align:right; color:#22c55e;">${tx.status}</td>
                </tr>
            `;
        });
    }
    historyHTML += `</tbody></table>`;
    historyContent.innerHTML = historyHTML;
}

window.refreshAuditTrail = function() {
    fetch('/api/audit_trail')
    .then(r => r.json())
    .then(data => {
        if(data && data.trades) {
            renderExecutionHistory(data.trades);
        }
    }).catch(e => console.error('Audit trail poll failed', e));
};

// Start polling every 3 seconds
setInterval(window.refreshAuditTrail, 3000);
'''

text += polling_code

with open('d:\\FIONA\\google touzi\\static\\main.js', 'w', encoding='utf-8') as f:
    f.write(text)

print('Updated main.js successfully.')
