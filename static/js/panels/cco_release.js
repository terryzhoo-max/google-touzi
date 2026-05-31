// cco_release.js - AlphaCore focused panel module.
window.showCcoReleaseModal = function() {
    // Read parameters of the first proposed order if any, or default to sample
    const modal = document.getElementById('cco-release-modal');
    if (!modal) return;

    // We try to find blocked order info from proposedOrdersData
    let symbol = '510300';
    let side = 'BUY';
    let qty = 1000;
    let price = 3.200;

    if (window.proposedOrdersData && window.proposedOrdersData.length > 0) {
        // Find blocked orders
        const blocked = window.proposedOrdersData.find(o => o.status === 'BLOCKED_BY_COMPLIANCE' || o.action === 'BUY' || o.action === 'SELL');
        if (blocked) {
            symbol = blocked.symbol;
            side = blocked.action || 'BUY';
            qty = blocked.quantity || 1000;
            price = blocked.limit_price || 1.0;
        }
    }

    document.getElementById('cco-order-symbol').value = symbol;
    document.getElementById('cco-order-side').value = side.toUpperCase();
    document.getElementById('cco-order-qty').value = qty;
    document.getElementById('cco-order-price').value = price;
    document.getElementById('cco-auth-key').value = '';

    modal.style.display = 'flex';
};

window.closeCcoReleaseModal = function() {
    const modal = document.getElementById('cco-release-modal');
    if (modal) modal.style.display = 'none';
};

window.submitCcoForceRelease = async function() {
    const symbol = document.getElementById('cco-order-symbol').value;
    const side = document.getElementById('cco-order-side').value;
    const qty = parseInt(document.getElementById('cco-order-qty').value || 1000);
    const price = parseFloat(document.getElementById('cco-order-price').value || 1.0);
    const algo = document.getElementById('cco-order-algo').value;
    const authKey = document.getElementById('cco-auth-key').value;

    if (!authKey) {
        alert('Enter the compliance officer secondary authorization key.');
        return;
    }

    try {
        const response = await fetch('/api/institutional/execution/force_release', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                auth_key: authKey,
                symbol: symbol,
                side: side,
                quantity: qty,
                limit_price: price,
                execution_algo: algo,
                portfolio_id: window.currentPortfolio || 'institutional_portfolio'
            })
        });

        const res = await response.json();
        if (response.ok && res.status === 'success') {
            alert('Force release authorized. Order has been queued to the QMT gateway.');
            closeCcoReleaseModal();
            // Refresh
            if (window.initInstitutionalDecision) window.initInstitutionalDecision();
            if (window.syncExecutionMonitor) window.syncExecutionMonitor();
        } else {
            alert('Force release blocked by compliance validation: ' + (res.detail || res.error || 'Validation failed'));
        }
    } catch (e) {
        alert('Network error. Compliance officer force release validation failed.');
        console.error(e);
    }
};

// Also display CCO Force Release button if the portfolio has HARD_BLOCK compliance
const originalInitInstitutionalDecision = window.initInstitutionalDecision;
window.initInstitutionalDecision = async function() {
    if (originalInitInstitutionalDecision) {
        await originalInitInstitutionalDecision();
    }
    // Check global status to toggle CCO Force Release Button
    try {
        let url = '/api/institutional/decision';
        if (window.currentPortfolio) {
            url += `?portfolio=${window.currentPortfolio}`;
        }
        const response = await fetch(url);
        const data = await response.json();
        const btn = document.getElementById('cco-manual-release-btn');
        if (btn) {
            if (data.global_status === 'HARD_BLOCK') {
                btn.style.display = 'inline-block';
            } else {
                btn.style.display = 'none';
            }
        }
    } catch(e) {
        console.error(e);
    }
};
