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
var AUDIT_TRAIL_REFRESH_MS = 10000;
var AUDIT_TRAIL_ERROR_BACKOFF_MS = 30000;
window.auditTrailState = window.auditTrailState || {
    inFlight: null,
    lastFetchAt: 0,
    nextAllowedAt: 0,
    lastPayload: null,
};
var AUDIT_TRAIL_LEADER_KEY = 'alphacore.auditTrail.leader.v2';
var AUDIT_TRAIL_LEADER_TTL_MS = 25000;
var AUDIT_TRAIL_CHANNEL_NAME = 'alphacore.auditTrail.v2';
window.auditTrailTabId = window.auditTrailTabId || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
window.auditTrailChannel = window.auditTrailChannel || (
    'BroadcastChannel' in window ? new BroadcastChannel(AUDIT_TRAIL_CHANNEL_NAME) : null
);
if (window.auditTrailChannel && !window.auditTrailChannelHandlerInstalled) {
    window.auditTrailChannelHandlerInstalled = true;
    window.auditTrailChannel.onmessage = event => {
        if (!event.data || event.data.type !== 'audit-trail-payload') return;
        window.auditTrailState.lastPayload = event.data.payload;
        window.auditTrailState.lastFetchAt = event.data.fetchedAt || Date.now();
        window.auditTrailState.nextAllowedAt = window.auditTrailState.lastFetchAt + AUDIT_TRAIL_REFRESH_MS;
        window.renderAuditTrailConsumers(window.auditTrailState.lastPayload);
    };
}

window.auditTrailTryBecomeLeader = function(now = Date.now()) {
    try {
        const raw = localStorage.getItem(AUDIT_TRAIL_LEADER_KEY);
        const current = raw ? JSON.parse(raw) : null;
        if (current && current.owner !== window.auditTrailTabId && now - Number(current.ts || 0) < AUDIT_TRAIL_LEADER_TTL_MS) {
            return false;
        }
        localStorage.setItem(AUDIT_TRAIL_LEADER_KEY, JSON.stringify({owner: window.auditTrailTabId, ts: now}));
        const confirmed = JSON.parse(localStorage.getItem(AUDIT_TRAIL_LEADER_KEY) || '{}');
        return confirmed.owner === window.auditTrailTabId;
    } catch (e) {
        return true;
    }
};

window.fetchAuditTrail = async function(limit = 50, options = {}) {
    const force = Boolean(options.force);
    const now = Date.now();
    const auditTrailState = window.auditTrailState;

    if (!force && document.hidden && auditTrailState.lastPayload) {
        return auditTrailState.lastPayload;
    }
    if (!force && auditTrailState.lastPayload && now - auditTrailState.lastFetchAt < AUDIT_TRAIL_REFRESH_MS) {
        return auditTrailState.lastPayload;
    }
    if (!force && now < auditTrailState.nextAllowedAt) {
        return auditTrailState.lastPayload || {trades: []};
    }
    if (auditTrailState.inFlight) {
        return auditTrailState.inFlight;
    }
    if (!window.auditTrailTryBecomeLeader(now)) {
        return auditTrailState.lastPayload || {trades: []};
    }

    const auditFetch = window.AlphaCore && window.AlphaCore.api
        ? window.AlphaCore.api.originalFetch
        : window.fetch.bind(window);

    auditTrailState.inFlight = auditFetch(`/api/audit_trail?limit=${encodeURIComponent(limit)}`)
        .then(response => {
            if (response.status === 429) {
                const retryAfter = Number(response.headers.get('Retry-After') || 30);
                auditTrailState.nextAllowedAt = Date.now() + Math.max(retryAfter * 1000, AUDIT_TRAIL_ERROR_BACKOFF_MS);
                throw new Error('Audit trail rate limited');
            }
            if (!response.ok) {
                throw new Error(`Audit trail request failed: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            auditTrailState.lastPayload = data;
            auditTrailState.lastFetchAt = Date.now();
            auditTrailState.nextAllowedAt = auditTrailState.lastFetchAt + AUDIT_TRAIL_REFRESH_MS;
            if (window.auditTrailChannel) {
                window.auditTrailChannel.postMessage({
                    type: 'audit-trail-payload',
                    payload: data,
                    fetchedAt: auditTrailState.lastFetchAt,
                });
            }
            return data;
        })
        .finally(() => {
            auditTrailState.inFlight = null;
        });

    return auditTrailState.inFlight;
};

window.renderAuditTrailConsumers = function(data) {
    if (data && data.trades) {
        renderExecutionHistory(data.trades);
        if (window.renderExecutionMonitorFromAuditTrail) {
            window.renderExecutionMonitorFromAuditTrail(data.trades);
        }
    }
};

window.refreshAuditTrail = function(options = {}) {
    return window.fetchAuditTrail(50, options)
        .then(data => {
            window.renderAuditTrailConsumers(data);
            return data;
        })
        .catch(e => console.error('Audit trail poll failed', e));
};
if (window.auditTrailPollerId) {
    clearInterval(window.auditTrailPollerId);
}
if (window.auditTrailVisibilityHandler) {
    window.removeEventListener('visibilitychange', window.auditTrailVisibilityHandler);
}
window.auditTrailVisibilityHandler = () => {
    if (!document.hidden) window.refreshAuditTrail({force: true});
};
window.addEventListener('visibilitychange', window.auditTrailVisibilityHandler);
window.auditTrailPollerId = setInterval(() => window.refreshAuditTrail(), AUDIT_TRAIL_REFRESH_MS);
// ============================================================================
// L3.5 INSTITUTIONAL QUANT WORKSPACES (Black-Litterman / Risk Parity / Crisis)
// ============================================================================
// --- 1. Black-Litterman Bayesian Optimizer ---
