// audit_trail.js - AlphaCore focused panel module.
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
                    <th style="padding:8px; text-align:right;">Price<span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">PRICE</span></th>
                    <th style="padding:8px; text-align:right;">Status<span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">STATUS</span></th>
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
// ============================================================================
// L3.5 INSTITUTIONAL QUANT WORKSPACES (Black-Litterman / Risk Parity / Crisis)
// ============================================================================
// --- 1. Black-Litterman Bayesian Optimizer ---
