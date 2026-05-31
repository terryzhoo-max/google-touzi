(function (app) {
    function refreshInstitutionalPanels() {
        console.log("[PORTFOLIO SWITCH] Active portfolio changed to:", window.currentPortfolio);

        if (typeof initPortfolio === 'function') initPortfolio();
        if (typeof initPortfolioLedger === 'function') initPortfolioLedger();
        if (typeof initInstitutionalDecision === 'function') initInstitutionalDecision();
        if (typeof initBrinsonAttribution === 'function') initBrinsonAttribution();
        if (typeof initHistoricalScenarios === 'function') initHistoricalScenarios();
        if (typeof loadBlackLittermanAssets === 'function') loadBlackLittermanAssets();
        if (typeof loadRiskParityAssets === 'function') loadRiskParityAssets();
        if (typeof initGenAI === 'function') initGenAI();
    }

    async function initPortfolioSelector() {
        const selector = document.getElementById('global-portfolio-selector');
        if (!selector) return;

        try {
            const resp = await fetch('/api/institutional/portfolios');
            const data = await resp.json();

            let html = '';
            data.portfolios.forEach(p => {
                html += `<option value="${p.name}">${p.display_name}</option>`;
            });
            html += `<option value="ALL">ALL (Global Risk Net)</option>`;
            selector.innerHTML = html;

            selector.addEventListener('change', function() {
                if (app.api) app.api.resetGlobalRiskNetCache();
                if (app.state) app.state.setCurrentPortfolio(this.value);
                else window.currentPortfolio = this.value;
                refreshInstitutionalPanels();
            });

            if (data.portfolios.length > 0) {
                const initialPortfolio = app.state ? app.state.setCurrentPortfolio(data.portfolios[0].name) : data.portfolios[0].name;
                if (!app.state) window.currentPortfolio = initialPortfolio;
                selector.value = initialPortfolio;
            }
        } catch (e) {
            console.error('Failed to initialize portfolio selector:', e);
        }
    }

    window.refreshInstitutionalPanels = refreshInstitutionalPanels;
    window.initPortfolioSelector = initPortfolioSelector;

    app.portfolio = {
        initPortfolioSelector,
        refreshInstitutionalPanels,
    };
})(window.AlphaCore);
