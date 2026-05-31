// brinson_attribution.js - AlphaCore focused panel module.
async function initBrinsonAttribution() {
    const chartDom = document.getElementById('chart-brinson-attribution');
    if (!chartDom) return;

    let myChart = echarts.getInstanceByDom(chartDom);
    if (!myChart) myChart = echarts.init(chartDom, 'dark');

    try {
        let url = '/api/institutional/attribution?period=T-1';
        if (window.currentPortfolio) {
            url += `&portfolio=${window.currentPortfolio}`;
        }
        const resp = await fetch(url);
        const data = await resp.json();

        // Populate table
        const tbody = document.getElementById('brinson-table-body');
        if (tbody) {
            if (!data.by_class || data.by_class.length === 0) {
                tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:20px; color:var(--text-tertiary);">No attribution data available</td></tr>`;
            } else {
                tbody.innerHTML = data.by_class.map(c => {
                    const formatPct = (val) => `${(val * 100).toFixed(2)}%`;
                    const formatBps = (val) => {
                        const bps = val * 10000;
                        const sign = bps >= 0 ? '+' : '';
                        const color = bps >= 0 ? '#10b981' : '#f43f5e';
                        return `<span style="color:${color}; font-family:var(--font-mono); font-weight:700;">${sign}${bps.toFixed(1)} Bps</span>`;
                    };

                    const acZh = {
                        equity: '权益资产 (Equity)',
                        bond: '固收债券 (Bond)',
                        gold: '商品避险 (Gold)',
                        cash: '货币现金 (Cash)'
                    }[c.asset_class] || c.asset_class;

                    return `<tr>
                        <td style="font-weight:700;">${acZh}</td>
                        <td style="text-align:right; font-family:var(--font-mono);">${formatPct(c.portfolio_weight)}</td>
                        <td style="text-align:right; font-family:var(--font-mono);">${formatPct(c.benchmark_weight)}</td>
                        <td style="text-align:right;">${formatBps(c.allocation_effect)}</td>
                        <td style="text-align:right;">${formatBps(c.selection_effect)}</td>
                        <td style="text-align:right;">${formatBps(c.interaction_effect)}</td>
                    </tr>`;
                }).join('') + `
                <tr style="border-top:2px solid rgba(255,255,255,0.1); font-weight:700; background:rgba(255,255,255,0.02);">
                    <td>合计 (Total)</td>
                    <td style="text-align:right; font-family:var(--font-mono);">100.00%</td>
                    <td style="text-align:right; font-family:var(--font-mono);">100.00%</td>
                    <td style="text-align:right;">${((data.allocation_effect*10000) >= 0 ? '+' : '')}${(data.allocation_effect*10000).toFixed(1)} Bps</td>
                    <td style="text-align:right;">${((data.selection_effect*10000) >= 0 ? '+' : '')}${(data.selection_effect*10000).toFixed(1)} Bps</td>
                    <td style="text-align:right;">${((data.interaction_effect*10000) >= 0 ? '+' : '')}${(data.interaction_effect*10000).toFixed(1)} Bps</td>
                </tr>`;
            }
        }

        // Render Chart
        const categories = (data.by_class || []).map(c => {
            return {
                equity: 'Equity',
                bond: 'Bond',
                gold: 'Gold',
                cash: 'Cash'
            }[c.asset_class] || c.asset_class;
        });
        const allocEffects = (data.by_class || []).map(c => (c.allocation_effect * 10000).toFixed(1));
        const selectEffects = (data.by_class || []).map(c => (c.selection_effect * 10000).toFixed(1));
        const interEffects = (data.by_class || []).map(c => (c.interaction_effect * 10000).toFixed(1));

        myChart.setOption({
            backgroundColor: 'transparent',
            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
            legend: { data: ['配置效应', '选择效应', '交互效应'], textStyle: { color: 'var(--text-secondary)' } },
            grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
            xAxis: { type: 'value', axisLabel: { color: 'var(--text-tertiary)', formatter: '{value} Bps' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
            yAxis: { type: 'category', data: categories, axisLabel: { color: 'var(--text-primary)' } },
            series: [
                { name: '配置效应', type: 'bar', stack: 'total', data: allocEffects, itemStyle: { color: '#00f0ff' } },
                { name: '选择效应', type: 'bar', stack: 'total', data: selectEffects, itemStyle: { color: '#10b981' } },
                { name: '交互效应', type: 'bar', stack: 'total', data: interEffects, itemStyle: { color: '#a855f7' } }
            ]
        });
        window.addEventListener('resize', () => myChart.resize());
    } catch (e) {
        console.error('Failed to load Brinson attribution:', e);
    }
}

