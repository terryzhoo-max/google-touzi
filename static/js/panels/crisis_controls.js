// crisis_controls.js - AlphaCore focused panel module.
window.triggerCrisisSimulation = async function() {
    const chartDom = document.getElementById('chart-historical-drawdown');
    if (!chartDom) return;

    let myChart = echarts.getInstanceByDom(chartDom);
    if (!myChart) myChart = echarts.init(chartDom, 'dark');

    myChart.showLoading({
        text: '重现历史危机时空序列...',
        color: '#38bdf8',
        textColor: '#fff',
        maskColor: 'rgba(20,20,25,0.8)'
    });

    try {
        const triggerVal = Number(document.getElementById('crisis-defense-trigger').value || 5) / 100.0;
        const cutVal = Number(document.getElementById('crisis-defense-cut').value || 50) / 100.0;
        const daysVal = Number(document.getElementById('crisis-defense-days').value || 10);

        let url = `/api/institutional/scenarios/historical?defense_trigger_drawdown=${triggerVal}&defense_risk_cut_ratio=${cutVal}&stabilization_days=${daysVal}`;
        if (window.currentPortfolio) {
            url += `&portfolio=${window.currentPortfolio}`;
        }

        const response = await fetch(url);
        const data = await response.json();
        window.historicalCrisisCache = data;

        myChart.hideLoading();

        const selector = document.getElementById('historical-crisis-selector');
        const val = selector ? selector.value : 'lehman_2008';
        switchHistoricalCrisisScenario(val);
    } catch (e) {
        console.error('Failed to run crisis simulation', e);
        myChart.hideLoading();
    }
};

