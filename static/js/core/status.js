(function (app) {
    const COLORS = {
        loading: '#fbbf24',
        loaded: '#94a3b8',
        healthy: '#4ade80',
        degraded: '#fbbf24',
        error: '#ef4444',
    };

    function setFreshnessStatus({ state = 'loaded', text = '' } = {}) {
        const el = document.getElementById('freshness-indicator');
        if (!el) return;

        el.textContent = text || state;
        el.style.color = COLORS[state] || COLORS.loaded;
    }

    window.setFreshnessStatus = setFreshnessStatus;
    app.status = {
        setFreshnessStatus,
    };
})(window.AlphaCore);
