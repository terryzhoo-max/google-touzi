(function (app) {
    const ACTIONS = {
        'switch-view': (target, event) => {
            event.preventDefault();
            if (typeof switchView === 'function') switchView(target.dataset.view);
        },
        'set-rotation-period': (target, event) => window.setRotationPeriod?.(target.dataset.period, event),
        'run-custom-shock': () => window.runCustomShockSimulation?.(),
        'commit-custom-decision': target => window.commitCustomDecision?.(target.dataset.source),
        'reset-custom-shock': () => window.resetCustomShock?.(),
        'import-tdx': () => window.importTDX?.(),
        'switch-sandbox-tab': target => window.switchSandboxTab?.(target.dataset.tab),
        'inject-simu-cash': () => window.injectSimuCashPrompt?.(),
        'set-simu-friction': () => window.setSimuFrictionPrompt?.(),
        'execute-simu-cli': () => window.executeSimuCLI?.(),
        'export-simu-csv': () => window.exportSimuCSV?.(),
        'reset-simu-sandbox': () => window.resetSimuSandbox?.(),
        'trigger-crisis-simulation': () => window.triggerCrisisSimulation?.(),
        'show-cco-release-modal': () => window.showCcoReleaseModal?.(),
        'close-action-modal': () => window.closeActionModal?.(),
        'execute-action-buy': () => window.executeActionModalBuy?.(),
        'execute-action-sell': () => window.executeActionModalSell?.(),
        'execute-action-tp': () => window.executeActionModalTP?.(),
        'execute-action-sl': () => window.executeActionModalSL?.(),
        'close-cco-release-modal': () => window.closeCcoReleaseModal?.(),
        'submit-cco-force-release': () => window.submitCcoForceRelease?.(),
        'open-action-modal': target => window.openActionModal?.(
            target.dataset.symbol,
            target.dataset.name || '',
            Number(target.dataset.qty || 0),
            Number(target.dataset.price || 0),
        ),
        'remove-simu-trade': target => window.removeSimuTrade?.(Number(target.dataset.tradeId)),
        'sign-off-single-order': target => window.signOffSingleOrder?.(Number(target.dataset.orderIndex)),
        'sign-off-all-orders': () => window.signOffAllOrders?.(),
    };

    const CHANGE_ACTIONS = {
        'switch-historical-crisis': target => window.switchHistoricalCrisisScenario?.(target.value),
        'handle-tdx-upload': (target, event) => window.handleTDXUpload?.(event),
    };

    function bindClickActions(root = document) {
        root.addEventListener('click', event => {
            const target = event.target.closest('[data-action]');
            if (!target) return;
            const handler = ACTIONS[target.dataset.action];
            if (!handler) return;
            handler(target, event);
        });
    }

    function bindChangeActions(root = document) {
        root.addEventListener('change', event => {
            const target = event.target.closest('[data-action]');
            if (!target) return;
            const handler = CHANGE_ACTIONS[target.dataset.action];
            if (!handler) return;
            handler(target, event);
        });
    }

    function bindDeclarativeActions(root = document) {
        bindClickActions(root);
        bindChangeActions(root);
    }

    document.addEventListener('DOMContentLoaded', () => bindDeclarativeActions(document));

    app.events = {
        bindDeclarativeActions,
        actions: ACTIONS,
        changeActions: CHANGE_ACTIONS,
    };
})(window.AlphaCore);
