(function (app) {
    const originalFetch = window.fetch.bind(window);
    let globalRiskNetCache = null;
    let auditTrailResponse = null;
    let auditTrailResponseAt = 0;
    let auditTrailResponseInflight = null;
    const AUDIT_TRAIL_RESPONSE_TTL_MS = 10000;

    function resetGlobalRiskNetCache() {
        globalRiskNetCache = null;
    }

    async function loadGlobalRiskNet(init) {
        if (!globalRiskNetCache) {
            const resp = await originalFetch('/api/institutional/global_risk_net', init);
            globalRiskNetCache = await resp.json();
        }
        return globalRiskNetCache;
    }

    function shouldAttachPortfolio(input) {
        const currentPortfolio = app.state ? app.state.getCurrentPortfolio() : window.currentPortfolio;
        if (!currentPortfolio || currentPortfolio === 'ALL') return false;
        if (typeof input === 'string') return input.startsWith('/api/institutional/');
        return input instanceof Request && input.url.includes('/api/institutional/');
    }

    function withPortfolioParam(input) {
        if (typeof input === 'string') {
            const urlObj = new URL(input, window.location.origin);
            if (!urlObj.searchParams.has('portfolio')) {
                urlObj.searchParams.set('portfolio', app.state ? app.state.getCurrentPortfolio() : window.currentPortfolio);
            }
            return urlObj.pathname + urlObj.search;
        }

        const urlObj = new URL(input.url);
        if (!urlObj.searchParams.has('portfolio')) {
            urlObj.searchParams.set('portfolio', app.state ? app.state.getCurrentPortfolio() : window.currentPortfolio);
        }
        return new Request(urlObj.toString(), input);
    }

    function isAuditTrailRequest(input, init) {
        const method = init && init.method ? String(init.method).toUpperCase() : "GET";
        if (method !== "GET") return false;
        const urlStr = typeof input === 'string' ? input : input.url;
        return new URL(urlStr, window.location.origin).pathname === '/api/audit_trail';
    }

    function auditLimitFromRequest(input) {
        const urlStr = typeof input === 'string' ? input : input.url;
        const urlObj = new URL(urlStr, window.location.origin);
        return Number(urlObj.searchParams.get('limit') || 50);
    }

    async function fetchAuditTrailResponse(input, init) {
        const now = Date.now();
        if (auditTrailResponse && now - auditTrailResponseAt < AUDIT_TRAIL_RESPONSE_TTL_MS) {
            return new Response(JSON.stringify(auditTrailResponse), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }
        if (!auditTrailResponseInflight) {
            if (window.fetchAuditTrail) {
                auditTrailResponseInflight = window.fetchAuditTrail(auditLimitFromRequest(input));
            } else {
                auditTrailResponseInflight = originalFetch(input, init).then(resp => resp.json());
            }
        }
        const data = await auditTrailResponseInflight.finally(() => {
            auditTrailResponseInflight = null;
        });
        auditTrailResponse = data;
        auditTrailResponseAt = Date.now();
        return new Response(JSON.stringify(data), { status: 200, headers: { 'Content-Type': 'application/json' } });
    }

    async function portfolioAwareFetch(input, init) {
        const urlStr = typeof input === 'string' ? input : input.url;
        const currentPortfolio = app.state ? app.state.getCurrentPortfolio() : window.currentPortfolio;

        if (isAuditTrailRequest(input, init)) {
            return fetchAuditTrailResponse(input, init);
        }

        if (currentPortfolio === 'ALL') {
            if (urlStr.includes('/api/institutional/portfolio') && !urlStr.includes('/portfolios') && !urlStr.includes('/portfolio_raw')) {
                const riskNet = await loadGlobalRiskNet(init);
                const fakePortfolio = {
                    total_market_value: riskNet.total_market_value,
                    positions: [],
                    concentration_level: "Global risk net",
                    position_count: 0
                };
                return new Response(JSON.stringify(fakePortfolio), { status: 200, headers: { 'Content-Type': 'application/json' } });
            }

            if (urlStr.includes('/api/institutional/scenarios') && !urlStr.includes('/historical')) {
                const riskNet = await loadGlobalRiskNet(init);
                const fakeScenarios = {
                    scenarios: riskNet.joint_scenarios,
                    worst_scenario: riskNet.worst_scenario
                };
                return new Response(JSON.stringify(fakeScenarios), { status: 200, headers: { 'Content-Type': 'application/json' } });
            }
        }

        if (shouldAttachPortfolio(input)) {
            input = withPortfolioParam(input);
        }
        return originalFetch(input, init);
    }

    async function fetchJsonWithRetry(url, attempts = 25, delayMs = 1500) {
        let lastError;
        for (let attempt = 1; attempt <= attempts; attempt++) {
            try {
                const response = await window.fetch(url, { cache: 'no-store' });
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                const data = await response.json();
                if (data && data.status === "syncing") {
                    console.log(`[Syncing] ${url} is building cache (attempt ${attempt}/${attempts})...`);
                    throw new Error("Data syncing");
                }
                return data;
            } catch (error) {
                lastError = error;
                if (attempt < attempts) {
                    await sleep(delayMs);
                }
            }
        }
        throw lastError;
    }

    function sleep(ms) {
        return new Promise(resolve => window.setTimeout(resolve, ms));
    }

    window.fetch = portfolioAwareFetch;
    window.fetchJsonWithRetry = fetchJsonWithRetry;
    window.sleep = sleep;

    app.api = {
        fetch: portfolioAwareFetch,
        fetchJsonWithRetry,
        originalFetch,
        resetGlobalRiskNetCache,
        sleep,
    };
})(window.AlphaCore);
