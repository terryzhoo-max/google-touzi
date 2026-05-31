(function (app) {
    function scheduleInitializers(jobs) {
        jobs.forEach(([job, delay]) => {
            window.setTimeout(() => {
                try {
                    job();
                } catch (error) {
                    console.error('Initializer failed:', error);
                }
            }, delay);
        });
    }

    function bindSmoothAnchors() {
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function (e) {
                if (this.closest('.terminal-nav')) return;
                const target = document.querySelector(this.getAttribute('href'));
                if (!target) return;
                e.preventDefault();
                target.scrollIntoView({ behavior: 'smooth' });
            });
        });
    }

    function boot() {
        if (app.portfolio) app.portfolio.initPortfolioSelector();
        activateInitialView();
        window.addEventListener('hashchange', activateViewFromHash);

        const totalPanels = 21;
        let loadedCount = 0;
        const updateProgress = () => {
            loadedCount++;
            if (loadedCount <= totalPanels && app.status) {
                const isComplete = loadedCount >= totalPanels;
                app.status.setFreshnessStatus({
                    state: isComplete ? 'loaded' : 'loading',
                    text: isComplete ? 'Panels loaded' : `Loading panels... ${loadedCount}/${totalPanels}`,
                });
            }
        };
        const track = (fn) => async () => { try { await fn(); } catch(e) {} finally { updateProgress(); } };

        scheduleInitializers([
            [track(initDashboard), 0],
            [track(initERPChart), 80],
            [track(initSpreadChart), 160],
            [track(initSignals), 240],
            [track(initYieldCurve), 500],
            [track(initAllocationChart), 650],
            [track(initCorrelationChart), 800],
            [track(initPortfolio), 300],
            [track(initChinaMacro), 1000],
            [track(initSurpriseIndex), 1050],
            [track(initMarginMonitor), 1100],
            [track(initDividendLeaders), 1150],
            [track(initAlertCenter), 1000],
            [track(initMarketBreadth), 1100],
            [track(initFedProb), 1200],
            [track(initMonteCarloChart), 1500],
            [track(initGlobalAssets), 1700],
            [track(initValuation), 1900],
            [track(initScenarioTest), 2100],
            [track(initEfficientFrontier), 2500],
            [track(initRotationPanels), 2800],
            [track(initBacktest), 3200],
            [track(initInstitutionalDecision), 4000],
            [track(initPortfolioLedger), 4500],
            [track(initGenAI), 5000],
            [track(loadBlackLittermanAssets), 5100],
            [track(loadRiskParityAssets), 5200],
            [track(initHistoricalScenarios), 5300],
        ]);
        bindSmoothAnchors();
    }

    document.addEventListener("DOMContentLoaded", boot);

    window.scheduleInitializers = scheduleInitializers;
    app.bootstrap = { boot, scheduleInitializers };
})(window.AlphaCore);
