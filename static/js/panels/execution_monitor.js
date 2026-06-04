// execution_monitor.js - AlphaCore focused panel module.
window.renderL6Blotter = function(data) {
    const l6Card = document.getElementById('hub-l6-card');
    const l6Content = document.getElementById('hub-l6-content');
    if (!l6Card || !l6Content) return;

    l6Card.style.display = 'block';

    const proposed = data.proposed_orders || [];
    const symNames = data.l3_routing.symbol_names || {};

    let html = '';

    // 1. Proposed Orders section
    html += `
        <div style="background:rgba(0,0,0,0.25); border:1px solid rgba(255,255,255,0.05); border-radius:6px; padding:16px; margin-bottom:20px; box-shadow:inset 0 2px 10px rgba(0,0,0,0.5);">
            <div style="font-weight:700; color:var(--accent-primary); margin-bottom:12px; font-size:0.85rem; letter-spacing:1px; display:flex; justify-content:space-between; align-items:center;">
                <span>Proposed Orders Sign-Off Blotter</span>
                <span style="font-size:0.75rem; font-weight:400; color:var(--text-tertiary);">* Generated from Barra portfolio risk and turnover constraints</span>
            </div>
    `;

    if (proposed.length === 0) {
        html += `
            <div style="text-align:center; padding:30px; color:var(--text-tertiary); font-family:var(--font-mono); font-size:0.85rem; letter-spacing:1px;">
                Portfolio is balanced; no proposed rebalance orders.
            </div>
        `;
    } else {
        html += `
            <table class="institutional-table" style="width:100%; font-family:var(--font-sans); font-size:0.85rem; border-collapse:collapse; margin-bottom:16px;">
                <thead>
                    <tr style="border-bottom:1px solid rgba(255,255,255,0.1); color:var(--text-tertiary); font-family:var(--font-mono); font-size:0.75rem;">
                        <th style="padding:10px 8px; text-align:left;">资产标的</th>
                        <th style="padding:10px 8px; text-align:left;">方向</th>
                        <th style="padding:10px 8px; text-align:right;">拟调额度</th>
                        <th style="padding:10px 8px; text-align:right;">估算股数</th>
                        <th style="padding:10px 8px; text-align:right;">限价保护</th>
                        <th style="padding:10px 8px; text-align:center; width:160px;">执行算法 (ALGO)</th>
                        <th style="padding:10px 8px; text-align:center; width:100px;">签发</th>
                    </tr>
                </thead>
                <tbody>
        `;

        proposed.forEach((order, idx) => {
            const sName = symNames[order.symbol] || order.symbol;
            const actionColor = order.side === 'BUY' ? '#22c55e' : '#ef4444';
            const actionBg = order.side === 'BUY' ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)';
            const estVal = order.estimated_value || 0;

            html += `
                <tr class="proposed-order-row" data-symbol="${order.symbol}" data-side="${order.side}" data-qty="${order.quantity}" data-price="${order.limit_price}" style="border-bottom:1px solid rgba(255,255,255,0.03); transition:background 0.2s;">
                    <td style="padding:10px 8px;">
                        <strong style="color:#fff; font-size:0.95rem;">${sName}</strong>
                        <span style="display:block; font-family:var(--font-mono); font-size:0.7rem; color:var(--text-tertiary); margin-top:2px;">${order.symbol}</span>
                    </td>
                    <td style="padding:10px 8px;">
                        <span style="color:${actionColor}; background:${actionBg}; border:1px solid ${actionColor}30; padding:2px 6px; border-radius:3px; font-weight:700; font-family:var(--font-mono); font-size:0.75rem;">${order.side}</span>
                    </td>
                    <td style="padding:10px 8px; text-align:right; font-family:var(--font-mono); color:var(--text-secondary);">
                        $${estVal.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}
                    </td>
                    <td style="padding:10px 8px; text-align:right; font-family:var(--font-mono); font-weight:700; color:var(--text-primary);">
                        ${parseInt(order.quantity).toLocaleString()} shares
                    </td>
                    <td style="padding:10px 8px; text-align:right; font-family:var(--font-mono); color:var(--text-secondary);">
                        ${parseFloat(order.limit_price).toFixed(3)}
                    </td>
                    <td style="padding:10px 8px; text-align:center;">
                        <select class="proposed-algo-select" style="background:#090d16; color:var(--accent-primary); border:1px solid rgba(255,255,255,0.15); border-radius:4px; padding:4px 8px; font-family:var(--font-mono); font-size:0.8rem; cursor:pointer; width:100%; outline:none;">
                            <option value="TWAP">TWAP (time-weighted execution)</option>
                            <option value="DIRECT">DIRECT (single direct order)</option>
                        </select>
                    </td>
                    <td style="padding:10px 8px; text-align:center;">
                        <button data-action="sign-off-single-order" data-order-index="${idx}" class="btn-action-primary" style="padding:4px 10px; font-size:0.75rem; border-radius:4px; font-weight:bold; width:100%; letter-spacing:1px;">Sign off</button>
                    </td>
                </tr>
            `;
        });

        html += `
                </tbody>
            </table>
            <div style="display:flex; justify-content:flex-end;">
                <button data-action="sign-off-all-orders" class="btn-action-secondary" style="padding:8px 20px; font-size:0.85rem; font-weight:bold; letter-spacing:1px; border:1px solid var(--accent-primary); box-shadow:0 0 15px rgba(59,130,246,0.3);">
                    Authorize all orders to gateway
                </button>
            </div>
        `;
    }

    html += `</div>`;

    // 2. Real-time Algorithmic Execution Monitor
    html += `
        <div style="background:rgba(0,0,0,0.25); border:1px solid rgba(255,255,255,0.05); border-radius:6px; padding:16px; box-shadow:inset 0 2px 10px rgba(0,0,0,0.5);">
            <div style="font-weight:700; color:var(--accent-secondary); margin-bottom:12px; font-size:0.85rem; letter-spacing:1px; display:flex; justify-content:space-between; align-items:center;">
                <span>Algorithmic Execution & Slippage Audit</span>
                <span id="gateway-status-badge-monitor" style="font-family:var(--font-mono); font-size:0.7rem; color:var(--text-tertiary);">AUTO-POLLING SYNC</span>
            </div>
            <div id="algo-executions-container">
                <div class="loading-spinner" style="margin:20px auto;"></div>
            </div>
        </div>
    `;

    l6Content.innerHTML = html;

    // Save proposed orders mapping on window for action handlers
    window.proposedOrdersData = proposed;

    // Immediately pull the audit trail to populate the monitor
    window.syncExecutionMonitor();
};
window.syncExecutionMonitor = function() {
    const container = document.getElementById('algo-executions-container');
    if (!container) return;

    const auditTrailRequest = window.fetchAuditTrail
        ? window.fetchAuditTrail(15)
        : fetch('/api/audit_trail?limit=15').then(r => r.json());

    auditTrailRequest
    .then(data => {
        if (!data || !data.trades) {
            container.innerHTML = `<div style="text-align:center; padding:20px; color:var(--text-tertiary);">Failed to sync execution status.</div>`;
            return;
        }

        const trades = data.trades;

        // Filter and display trades
        let executionsHTML = '';

        const activeAlgos = trades.filter(t => t.execution_algo === 'TWAP' || t.status === 'PENDING' || t.status === 'EXECUTING');

        if (activeAlgos.length === 0) {
            executionsHTML = `
                <div style="text-align:center; padding:30px; color:var(--text-tertiary); font-family:var(--font-mono); font-size:0.85rem; letter-spacing:1px;">
                    No active algorithmic trades.
                </div>
            `;
        } else {
            activeAlgos.forEach(tx => {
                const qty = parseInt(tx.quantity);
                const executed = parseInt(tx.executed_qty || 0);
                const progress = qty > 0 ? (executed / qty) * 100 : 0;

                const sideColor = tx.side === 'BUY' ? '#22c55e' : '#ef4444';
                const sideBg = tx.side === 'BUY' ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)';

                // Slippage styling
                const slip = parseFloat(tx.slippage_bps || 0);
                let slipText = slip.toFixed(1) + ' Bps';
                let slipColor = '#94a3b8';

                if (slip < 0) {
                    slipText = `-${Math.abs(slip).toFixed(1)} Bps saved`;
                    slipColor = '#22c55e';
                } else if (slip > 0) {
                    slipText = `+${slip.toFixed(1)} Bps slippage`;
                    slipColor = '#f43f5e';
                }

                let statusBadge = '';
                let progressColor = 'linear-gradient(90deg, #3b82f6, #00ffcc)';
                let rowStyle = '';

                if (tx.status === 'PENDING') {
                    statusBadge = `<span style="background:rgba(245,158,11,0.15); color:#f59e0b; border:1px solid rgba(245,158,11,0.3); padding:2px 6px; border-radius:3px; font-size:0.7rem; font-weight:700;">WAITING GATEWAY</span>`;
                    progressColor = 'rgba(255,255,255,0.1)';
                } else if (tx.status === 'EXECUTING') {
                    statusBadge = `<span class="executing-pulsate" style="background:rgba(0,255,204,0.15); color:#00ffcc; border:1px solid rgba(0,255,204,0.3); padding:2px 6px; border-radius:3px; font-size:0.7rem; font-weight:700; box-shadow:0 0 10px rgba(0,255,204,0.2);">EXECUTING TWAP</span>`;
                    rowStyle = 'background:rgba(59,130,246,0.03); border-left:3px solid #00ffcc;';
                } else {
                    statusBadge = `<span style="background:rgba(34,197,94,0.15); color:#22c55e; border:1px solid rgba(34,197,94,0.3); padding:2px 6px; border-radius:3px; font-size:0.7rem; font-weight:700;">FILLED</span>`;
                    progressColor = '#22c55e';
                }

                executionsHTML += `
                    <div style="border-bottom:1px solid rgba(255,255,255,0.05); padding:14px 8px; display:flex; flex-direction:column; gap:8px; ${rowStyle} transition:background 0.2s;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div style="display:flex; align-items:center; gap:10px;">
                                <strong style="font-family:var(--font-mono); color:#fff; font-size:0.9rem;">${tx.symbol}</strong>
                                <span style="color:${sideColor}; background:${sideBg}; padding:2px 6px; border-radius:3px; font-weight:700; font-size:0.7rem;">${tx.side}</span>
                                <span style="font-family:var(--font-mono); font-size:0.75rem; color:var(--text-tertiary);">${tx.execution_algo}</span>
                            </div>
                            <div style="display:flex; align-items:center; gap:16px;">
                                <div style="text-align:right;">
                                    <span style="font-size:0.65rem; color:var(--text-tertiary); display:block;">当前滑点漂移</span>
                                    <strong style="font-family:var(--font-mono); font-size:0.85rem; color:${slipColor};">${slipText}</strong>
                                </div>
                                <div style="text-align:right;">
                                    <span style="font-size:0.65rem; color:var(--text-tertiary); display:block;">成交均价</span>
                                    <strong style="font-family:var(--font-mono); font-size:0.85rem; color:var(--text-primary);">${parseFloat(tx.avg_executed_price || tx.limit_price).toFixed(3)}</strong>
                                </div>
                                ${statusBadge}
                            </div>
                        </div>

                        <div style="display:flex; align-items:center; gap:12px;">
                            <div style="flex:1; height:6px; background:rgba(255,255,255,0.03); border-radius:3px; overflow:hidden;">
                                <div style="height:100%; width:${progress}%; background:${progressColor}; transition:width 0.4s ease-out; box-shadow:0 0 10px rgba(59,130,246,0.5);"></div>
                            </div>
                            <span style="font-family:var(--font-mono); font-size:0.75rem; color:var(--text-secondary); min-width:130px; text-align:right;">
                                ${progress.toFixed(0)}% (${executed.toLocaleString()} / ${qty.toLocaleString()} shares)
                            </span>
                        </div>
                    </div>
                `;
            });
        }

        container.innerHTML = executionsHTML;
    }).catch(e => {
        console.error("Execution monitor sync failed", e);
    });
};
window.renderExecutionMonitorFromAuditTrail = function(trades) {
    const container = document.getElementById('algo-executions-container');
    if (!container || !Array.isArray(trades)) return;

    const activeAlgos = trades.filter(t => t.execution_algo === 'TWAP' || t.status === 'PENDING' || t.status === 'EXECUTING');
    if (activeAlgos.length === 0) {
        container.innerHTML = `
            <div style="text-align:center; padding:30px; color:var(--text-tertiary); font-family:var(--font-mono); font-size:0.85rem; letter-spacing:1px;">
                No active algorithmic trades.
            </div>
        `;
        return;
    }

    container.innerHTML = activeAlgos.map(tx => `
        <div style="border-bottom:1px solid rgba(255,255,255,0.05); padding:14px 8px; display:flex; justify-content:space-between; align-items:center;">
            <div style="display:flex; align-items:center; gap:10px;">
                <strong style="font-family:var(--font-mono); color:#fff; font-size:0.9rem;">${tx.symbol}</strong>
                <span style="color:${tx.side === 'BUY' ? '#22c55e' : '#ef4444'}; font-weight:700; font-size:0.75rem;">${tx.side || tx.action || 'ORDER'}</span>
                <span style="font-family:var(--font-mono); font-size:0.75rem; color:var(--text-tertiary);">${tx.execution_algo || 'MANUAL'}</span>
            </div>
            <span style="font-family:var(--font-mono); font-size:0.75rem; color:var(--text-secondary);">${tx.status || 'UNKNOWN'}</span>
        </div>
    `).join('');
};
window.signOffSingleOrder = async function(idx) {
    if (!window.proposedOrdersData || !window.proposedOrdersData[idx]) return;

    const row = document.querySelectorAll('.proposed-order-row')[idx];
    const select = row.querySelector('.proposed-algo-select');
    const algo = select.value;

    const order = window.proposedOrdersData[idx];

    const btn = row.querySelector('button');
    btn.disabled = true;
    btn.innerText = 'Signing...';

    try {
        const response = await fetch('/api/institutional/sign_off_orders', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                orders: [{
                    symbol: order.symbol,
                    side: order.side,
                    quantity: parseInt(order.quantity),
                    price: parseFloat(order.limit_price),
                    execution_algo: algo
                }]
            })
        });

        const res = await response.json();
        if (res.status === 'success') {
            if (window.initInstitutionalDecision) window.initInstitutionalDecision();
            if (window.refreshAuditTrail) window.refreshAuditTrail();
        } else {
            alert('[SYS_ERROR] Order sign-off failed: ' + (res.error || 'Unknown error'));
            btn.disabled = false;
            btn.innerText = 'Sign off';
        }
    } catch(e) {
        alert('[SYS_ERROR] Backend network error; unable to sign order.');
        btn.disabled = false;
        btn.innerText = 'Sign off';
    }
};
window.signOffAllOrders = async function() {
    if (!window.proposedOrdersData || window.proposedOrdersData.length === 0) return;

    const btn = document.querySelector('button[data-action="sign-off-all-orders"]');
    btn.disabled = true;
    btn.innerText = 'Authorizing all orders...';

    const orders = [];
    const rows = document.querySelectorAll('.proposed-order-row');

    window.proposedOrdersData.forEach((order, idx) => {
        const select = rows[idx].querySelector('.proposed-algo-select');
        orders.push({
            symbol: order.symbol,
            side: order.side,
            quantity: parseInt(order.quantity),
            price: parseFloat(order.limit_price),
            execution_algo: select.value
        });
    });

    try {
        const response = await fetch('/api/institutional/sign_off_orders', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ orders })
        });

        const res = await response.json();
        if (res.status === 'success') {
            if (window.initInstitutionalDecision) window.initInstitutionalDecision();
            if (window.refreshAuditTrail) window.refreshAuditTrail();
        } else {
            alert('[SYS_ERROR] Bulk order authorization failed: ' + (res.error || 'Unknown error'));
            btn.disabled = false;
            btn.innerText = 'Authorize all orders to gateway';
        }
    } catch(e) {
        alert('[SYS_ERROR] Backend network error; unable to sign order.');
        btn.disabled = false;
        btn.innerText = 'Authorize all orders to gateway';
    }
};
window.pollGatewayHeartbeat = function() {
    const indicator = document.getElementById('gateway-heartbeat-indicator');
    const text = document.getElementById('gateway-status-text');
    if (!indicator || !text) return;

    const dot = indicator.querySelector('.heartbeat-dot');

    fetch('/api/institutional/execution/status')
    .then(r => r.json())
    .then(data => {
        if (data.status === 'ONLINE') {
            text.textContent = `ONLINE (${data.dry_run ? 'DRY-RUN' : 'LIVE'})`;
            dot.style.background = '#00ffcc';
            dot.style.boxShadow = '0 0 8px #00ffcc';
            indicator.style.border = '1px solid rgba(0, 255, 204, 0.2)';
            indicator.style.background = 'rgba(0, 255, 204, 0.03)';
        } else {
            text.textContent = 'OFFLINE';
            dot.style.background = '#94a3b8';
            dot.style.boxShadow = 'none';
            indicator.style.border = '1px solid rgba(255, 255, 255, 0.05)';
            indicator.style.background = 'rgba(0,0,0,0.3)';
        }
    })
    .catch(() => {
        text.textContent = 'OFFLINE';
        dot.style.background = '#94a3b8';
        dot.style.boxShadow = 'none';
    });
};
// Start custom heartbeat and monitor polling on startup
setInterval(window.pollGatewayHeartbeat, 3000);

// =========================================================================
// P1 & P2 & P3: New Institutional Extension Functions
// =========================================================================

