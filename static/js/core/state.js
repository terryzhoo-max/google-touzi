(function (app) {
    window.currentPortfolio = window.currentPortfolio || '';

    function getCurrentPortfolio() {
        return window.currentPortfolio || '';
    }

    function setCurrentPortfolio(portfolio) {
        window.currentPortfolio = portfolio || '';
        return window.currentPortfolio;
    }

    app.state = {
        getCurrentPortfolio,
        setCurrentPortfolio,
    };
})(window.AlphaCore);
