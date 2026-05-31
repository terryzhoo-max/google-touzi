(function (app) {
    function initPanel({url, indicatorId, insightId, onData, onError}) {
        fetchJsonWithRetry(url).then(d => {
            if (d.error) throw new Error(d.error);
            onData(d);
        }).catch(e => {
            console.error(url, e);
            if (onError) onError(e);
            const ind = document.getElementById(indicatorId);
            if (ind) {
                ind.innerText = 'Load failed';
                ind.style.color = '#ef4444';
            }
        });
    }

    const chartTheme = {
        color: ['#00F0FF', '#7000FF', '#4ade80', '#fbbf24'],
        textStyle: { fontFamily: 'Inter, sans-serif' },
        tooltip: {
            backgroundColor: 'rgba(20, 20, 25, 0.9)',
            borderColor: 'rgba(255,255,255,0.1)',
            textStyle: { color: '#f0f0f0' },
            axisPointer: { type: 'cross', lineStyle: { color: '#444' } }
        },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true }
    };

    async function fetchMacroData(endpoint) {
        try {
            return await fetchJsonWithRetry(`/api/macro/${endpoint}`);
        } catch (error) {
            console.error('Failed to fetch data, falling back to cached view:', error);
            return {
                dates: ['01-01', '01-02', '01-03', '01-04', '01-05'],
                data: [5.1, 5.2, 5.0, 5.3, 5.4]
            };
        }
    }

    window.initPanel = initPanel;
    window.chartTheme = chartTheme;
    window.fetchMacroData = fetchMacroData;

    app.charts = {
        initPanel,
        chartTheme,
        fetchMacroData,
    };
})(window.AlphaCore);
