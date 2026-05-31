// custom_shock.js - AlphaCore frontend panel module.
window.runCustomShockSimulation = async function() {
    const sliderIds = {
        equity_shock: 'slider-shock-equity',
        rate_shock: 'slider-shock-rate',
        vol_shock: 'slider-shock-vol',
        commodity_shock: 'slider-shock-commodity',
    };
    const payload = {};
    for (const [key, id] of Object.entries(sliderIds)) {
        const el = document.getElementById(id);
        payload[key] = el ? Number(el.value || 0) : 0;
    }
    const lossEl = document.getElementById('custom-shock-loss-display');
    const statusEl = document.getElementById('custom-shock-status-badge');
    const actionEl = document.getElementById('custom-shock-action');
    const commitBtn = document.getElementById('btn-commit-shock');
    if (lossEl) {
        lossEl.textContent = '...';
        lossEl.style.color = '#facc15';
    }
    if (statusEl) {
        statusEl.textContent = '正在推演因子冲击';
        statusEl.style.background = 'rgba(250,204,21,0.12)';
        statusEl.style.color = '#facc15';
        statusEl.style.borderColor = 'rgba(250,204,21,0.3)';
    }
    try {
        const response = await fetch('/api/institutional/scenarios/custom', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const result = await response.json();
        const loss = Number(result.custom_loss_pct || 0);
        const status = String(result.status || 'green').toLowerCase();
        const color = status === 'red' ? '#ef4444' : status === 'yellow' ? '#facc15' : '#10b981';
        const label = status === 'red' ? '压力阈值突破' : status === 'yellow' ? '观察区间' : '组合安全';
        const action = status === 'red' ? '暂停再平衡，优先对冲或降仓' : status === 'yellow' ? '降低追涨仓位，保留对冲预算' : '观察，维持当前风险预算';
        if (lossEl) {
            lossEl.textContent = `${loss.toFixed(2)}%`;
            lossEl.style.color = color;
            lossEl.style.textShadow = `0 0 15px ${color}55`;
        }
        if (statusEl) {
            statusEl.textContent = label;
            statusEl.style.background = `${color}20`;
            statusEl.style.color = color;
            statusEl.style.borderColor = `${color}55`;
        }
        if (actionEl) {
            actionEl.textContent = action;
            actionEl.style.color = color;
            actionEl.style.borderColor = `${color}55`;
            actionEl.style.background = `${color}14`;
        }
        if (commitBtn) commitBtn.style.display = 'inline-block';
        const chartDom = document.getElementById('custom-shock-asset-chart');
        if (chartDom && window.echarts) {
            const rows = (result.asset_contributions || [])
                .slice()
                .sort((a, b) => Number(a.loss_contribution_pct || 0) - Number(b.loss_contribution_pct || 0))
                .slice(0, 8);
            if (window.customShockChart) window.customShockChart.dispose();
            window.customShockChart = echarts.init(chartDom, 'dark');
            window.customShockChart.setOption({
                backgroundColor: 'transparent',
                grid: { left: 70, right: 24, top: 10, bottom: 20 },
                xAxis: {
                    type: 'value',
                    axisLabel: { color: '#94a3b8', formatter: '{value}%' },
                    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
                },
                yAxis: {
                    type: 'category',
                    data: rows.map(row => row.symbol),
                    axisLabel: { color: '#cbd5e1' },
                },
                tooltip: {
                    trigger: 'axis',
                    formatter: params => {
                        const item = rows[params[0].dataIndex] || {};
                        return `${item.symbol || '--'}<br/>损益贡献: ${Number(item.loss_contribution_pct || 0).toFixed(2)}%<br/>资产冲击: ${Number(item.asset_loss_pct || 0).toFixed(2)}%`;
                    },
                },
                series: [{
                    type: 'bar',
                    data: rows.map(row => Number(row.loss_contribution_pct || 0)),
                    itemStyle: { color: value => Number(value.data || 0) < 0 ? '#ef4444' : '#10b981' },
                    barWidth: 12,
                }],
            });
        }
    } catch (error) {
        console.error('Custom shock simulation failed:', error);
        if (lossEl) {
            lossEl.textContent = 'ERR';
            lossEl.style.color = '#ef4444';
        }
        if (statusEl) {
            statusEl.textContent = '情景引擎异常';
            statusEl.style.background = 'rgba(239,68,68,0.12)';
            statusEl.style.color = '#ef4444';
            statusEl.style.borderColor = 'rgba(239,68,68,0.4)';
        }
    }
};
window.resetCustomShock = function() {
    const defaults = [
        ['slider-shock-equity', 'shock-val-equity', '0%'],
        ['slider-shock-rate', 'shock-val-rate', '0%'],
        ['slider-shock-vol', 'shock-val-vol', '0%'],
        ['slider-shock-commodity', 'shock-val-commodity', '0%'],
    ];
    defaults.forEach(([sliderId, labelId, text]) => {
        const slider = document.getElementById(sliderId);
        const label = document.getElementById(labelId);
        if (slider) slider.value = 0;
        if (label) label.textContent = text;
    });
    const lossEl = document.getElementById('custom-shock-loss-display');
    const statusEl = document.getElementById('custom-shock-status-badge');
    const actionEl = document.getElementById('custom-shock-action');
    const commitBtn = document.getElementById('btn-commit-shock');
    if (lossEl) {
        lossEl.textContent = '0.00%';
        lossEl.style.color = '#10b981';
        lossEl.style.textShadow = '0 0 15px rgba(16,185,129,0.3)';
    }
    if (statusEl) {
        statusEl.textContent = '组合安全';
        statusEl.style.background = 'rgba(16,185,129,0.15)';
        statusEl.style.color = '#10b981';
        statusEl.style.borderColor = 'rgba(16,185,129,0.3)';
    }
    if (actionEl) {
        actionEl.textContent = '观察';
        actionEl.style.color = '#10b981';
        actionEl.style.borderColor = 'rgba(16,185,129,0.3)';
        actionEl.style.background = 'rgba(16,185,129,0.08)';
    }
    if (commitBtn) commitBtn.style.display = 'none';
    if (window.customShockChart) {
        window.customShockChart.dispose();
        window.customShockChart = null;
    }
};
