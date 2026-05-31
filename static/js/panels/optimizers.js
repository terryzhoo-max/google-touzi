// optimizers.js - AlphaCore frontend panel module.
async function loadBlackLittermanAssets() {
    const container = document.getElementById('bl-views-container');
    if (!container) return;

    try {
        const res = await fetch('/api/institutional/portfolio_raw');
        const data = await res.json();

        if (!data.positions || data.positions.length === 0) {
            container.innerHTML = `<div style="text-align:center; padding:20px; color:var(--text-tertiary);">Portfolio is empty. Sync the holdings ledger first.</div>`;
            return;
        }

        const nonCash = data.positions.filter(p => p.symbol !== 'CASH');
        if (nonCash.length === 0) {
            container.innerHTML = `<div style="text-align:center; padding:20px; color:var(--text-tertiary);">Portfolio only contains cash. No views are required.</div>`;
            return;
        }

        let html = '';
        nonCash.forEach(p => {
            html += `
                <div style="display:grid; grid-template-columns: 80px 1fr 100px 150px; gap:16px; align-items:center; background:rgba(255,255,255,0.02); padding:8px 12px; border-radius:4px; border:1px solid rgba(255,255,255,0.05);">
                    <div style="font-family:var(--font-mono); font-weight:700; color:#fff;">${p.symbol}</div>
                    <div style="font-size:0.75rem; color:var(--text-secondary); text-overflow:ellipsis; overflow:hidden; white-space:nowrap;">${p.name || ''}</div>
                    <div style="display:flex; align-items:center; gap:4px;">
                        <input type="number" class="bl-view-input" data-symbol="${p.symbol}" step="0.1" value="0.0" style="width:70px; background:#000; color:var(--accent-primary); border:1px solid rgba(255,255,255,0.15); border-radius:4px; padding:4px; font-family:var(--font-mono); text-align:right;">
                        <span style="font-size:0.75rem; color:var(--text-tertiary);">%</span>
                    </div>
                    <div style="display:flex; align-items:center; gap:8px;">
                        <input type="range" class="bl-confidence-slider" data-symbol="${p.symbol}" min="0" max="100" value="50" style="flex:1; accent-color:var(--accent-primary);" oninput="this.nextElementSibling.innerText = this.value + '%'">
                        <span style="font-family:var(--font-mono); font-size:0.75rem; color:var(--accent-primary); min-width:35px;">50%</span>
                    </div>
                </div>
            `;
        });
        container.innerHTML = html;
    } catch (e) {
        console.error('Failed to load Black-Litterman assets', e);
        container.innerHTML = `<div style="text-align:center; padding:20px; color:var(--danger);">加载持仓清单失败</div>`;
    }
}
async function runBlackLittermanOptimization() {
    const inputs = document.querySelectorAll('.bl-view-input');
    const views = {};
    const confidences = {};

    let hasViews = false;
    inputs.forEach(input => {
        const val = parseFloat(input.value);
        const sym = input.getAttribute('data-symbol');
        if (!isNaN(val) && val !== 0) {
            views[sym] = val / 100.0;
            hasViews = true;
        }
    });

    if (!hasViews) {
        alert('Enter at least one non-zero Black-Litterman shock view, for example +2.5% or -1.0%.');
        return;
    }

    const sliders = document.querySelectorAll('.bl-confidence-slider');
    sliders.forEach(slider => {
        const sym = slider.getAttribute('data-symbol');
        if (views[sym] !== undefined) {
            confidences[sym] = parseFloat(slider.value) / 100.0;
        }
    });

    const chartDom = document.getElementById('chart-bl-comparison');
    if (!chartDom) return;
    let myChart = echarts.getInstanceByDom(chartDom);
    if (!myChart) myChart = echarts.init(chartDom, 'dark');

    myChart.showLoading({
        text: 'Solving Black-Litterman equilibrium weights...',
        color: '#38bdf8',
        textColor: '#fff',
        maskColor: 'rgba(20,20,25,0.8)'
    });

    try {
        const response = await fetch('/api/institutional/portfolio_opt/black_litterman', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ views, confidences })
        });
        const data = await response.json();
        myChart.hideLoading();

        if (data && !data.error) {
            const symbols = data.symbols;
            const originalWeights = symbols.map(s => (data.original_weights[s] * 100).toFixed(2));
            const benchmarkWeights = symbols.map(s => (data.benchmark_weights[s] * 100).toFixed(2));
            const posteriorWeights = symbols.map(s => (data.optimized_weights[s] * 100).toFixed(2));

            const option = {
                backgroundColor: 'transparent',
                tooltip: {
                    trigger: 'axis',
                    axisPointer: { type: 'shadow' },
                    backgroundColor: 'rgba(0,0,0,0.85)',
                    borderColor: 'rgba(255,255,255,0.1)',
                    textStyle: { color: '#fff' }
                },
                legend: {
                    data: ['Benchmark prior', 'Original allocation', 'Bayesian posterior'],
                    textStyle: { color: 'var(--text-secondary)' },
                    bottom: 0
                },
                grid: {
                    left: '3%',
                    right: '4%',
                    top: '10%',
                    bottom: '15%',
                    containLabel: true
                },
                xAxis: {
                    type: 'value',
                    axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
                    axisLabel: { color: 'var(--text-tertiary)', formatter: '{value}%' },
                    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.03)' } }
                },
                yAxis: {
                    type: 'category',
                    data: symbols,
                    axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
                    axisLabel: { color: '#fff', fontWeight: 'bold' }
                },
                series: [
                    {
                        name: '业绩基准先验 (Benchmark)',
                        type: 'bar',
                        data: benchmarkWeights,
                        itemStyle: { color: '#9ca3af' }
                    },
                    {
                        name: '原仓实际比例 (Original)',
                        type: 'bar',
                        data: originalWeights,
                        itemStyle: { color: '#f59e0b' }
                    },
                    {
                        name: 'Bayesian posterior',
                        type: 'bar',
                        data: posteriorWeights,
                        itemStyle: { color: '#38bdf8' }
                    }
                ]
            };

            myChart.setOption(option);

            const metricsEl = document.getElementById('bl-active-risk-metrics');
            if (metricsEl) {
                metricsEl.textContent = `主动跟踪误差(TE): ${(data.active_risk * 100).toFixed(2)}% | 主动份额(Active Share): ${(data.active_share * 100).toFixed(1)}%`;
            }

            const btnCommit = document.getElementById('btn-commit-bl');
            if (btnCommit) btnCommit.style.display = 'block';

            const responseFric = await fetch('/api/institutional/sandbox/friction', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ target_weights: data.optimized_weights })
            });
            const dataFric = await responseFric.json();
            if (dataFric && !dataFric.error) {
                const commEl = document.getElementById('simu-audit-commission');
                const impEl = document.getElementById('simu-audit-impact');
                const totEl = document.getElementById('simu-audit-total-cost');
                const netAumEl = document.getElementById('simu-audit-net-aum');

                if (commEl) commEl.textContent = '¥' + dataFric.commission_cost.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
                if (impEl) impEl.textContent = '¥' + dataFric.market_impact_cost.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
                if (totEl) totEl.textContent = `¥${dataFric.total_friction_cost.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})} (${dataFric.total_cost_bps.toFixed(2)} bps)`;
                if (netAumEl) netAumEl.textContent = '¥' + dataFric.net_projected_aum.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});

                const radar = document.getElementById('simu-liquidity-radar');
                const radarContent = document.getElementById('simu-radar-content');
                if (radar && radarContent) {
                    const warnings = dataFric.details.filter(d => d.warning_level === 'RED' || d.warning_level === 'YELLOW');
                    if (warnings.length > 0) {
                        radar.style.display = 'block';
                        radarContent.innerHTML = warnings.map(w => `<div>[WARN] <strong>${w.symbol}</strong>: ADV participation ${(w.participation_rate * 100).toFixed(2)}% - ${w.warning_msg}</div>`).join('');
                    } else {
                        radar.style.display = 'none';
                    }
                }
            }
        } else {
            alert('Black-Litterman optimization failed: ' + (data.error || 'Unknown error'));
        }
    } catch (e) {
        console.error('Failed to run Black-Litterman optimization', e);
        myChart.hideLoading();
        alert('System error: optimizer failed.');
    }
}
function resetBlackLittermanViews() {
    const inputs = document.querySelectorAll('.bl-view-input');
    inputs.forEach(input => input.value = "0.0");
    const sliders = document.querySelectorAll('.bl-confidence-slider');
    sliders.forEach(slider => {
        slider.value = "50";
        slider.nextElementSibling.innerText = "50%";
    });
    const btnCommit = document.getElementById('btn-commit-bl');
    if (btnCommit) btnCommit.style.display = 'none';
}
// --- 2. Risk Parity All-Weather Allocator ---
async function loadRiskParityAssets() {
    const container = document.getElementById('rp-budgets-container');
    if (!container) return;

    try {
        const res = await fetch('/api/institutional/portfolio_raw');
        const data = await res.json();

        if (!data.positions || data.positions.length === 0) {
            container.innerHTML = `<div style="text-align:center; padding:20px; color:var(--text-tertiary);">Portfolio is empty. Sync the holdings ledger first.</div>`;
            return;
        }

        const nonCash = data.positions.filter(p => p.symbol !== 'CASH');
        if (nonCash.length === 0) {
            container.innerHTML = `<div style="text-align:center; padding:20px; color:var(--text-tertiary);">Portfolio only contains cash. Risk-parity allocation is not required.</div>`;
            return;
        }

        const N = nonCash.length;
        const equalBudget = (100 / N).toFixed(1);

        let html = '';
        nonCash.forEach(p => {
            html += `
                <div style="display:grid; grid-template-columns: 80px 1fr 180px; gap:16px; align-items:center; background:rgba(255,255,255,0.02); padding:8px 12px; border-radius:4px; border:1px solid rgba(255,255,255,0.05);">
                    <div style="font-family:var(--font-mono); font-weight:700; color:#fff;">${p.symbol}</div>
                    <div style="font-size:0.75rem; color:var(--text-secondary); text-overflow:ellipsis; overflow:hidden; white-space:nowrap;">${p.name || ''}</div>
                    <div style="display:flex; align-items:center; gap:8px;">
                        <input type="range" class="rp-budget-slider" data-symbol="${p.symbol}" min="0" max="100" value="${equalBudget}" step="0.1" style="flex:1; accent-color:var(--accent-primary);" oninput="scaleRiskParitySliders('${p.symbol}')">
                        <span style="font-family:var(--font-mono); font-size:0.75rem; color:var(--accent-primary); min-width:45px; text-align:right;">${equalBudget}%</span>
                    </div>
                </div>
            `;
        });
        container.innerHTML = html;
    } catch (e) {
        console.error('Failed to load Risk Parity assets', e);
        container.innerHTML = `<div style="text-align:center; padding:20px; color:var(--danger);">加载持仓清单失败</div>`;
    }
}
function scaleRiskParitySliders(changedSym) {
    const sliders = document.querySelectorAll('.rp-budget-slider');
    if (sliders.length <= 1) return;

    const changedSlider = Array.from(sliders).find(s => s.getAttribute('data-symbol') === changedSym);
    if (!changedSlider) return;

    const newVal = parseFloat(changedSlider.value);
    changedSlider.nextElementSibling.innerText = newVal + '%';

    let otherSum = 0;
    const others = [];
    sliders.forEach(s => {
        const sym = s.getAttribute('data-symbol');
        if (sym !== changedSym) {
            others.push(s);
            otherSum += parseFloat(s.value);
        }
    });

    const remaining = 100.0 - newVal;
    if (otherSum > 0) {
        others.forEach(s => {
            const prevVal = parseFloat(s.value);
            const scaled = (prevVal / otherSum) * remaining;
            s.value = scaled.toFixed(1);
            s.nextElementSibling.innerText = s.value + '%';
        });
    } else {
        others.forEach(s => {
            s.value = (remaining / others.length).toFixed(1);
            s.nextElementSibling.innerText = s.value + '%';
        });
    }
}
async function runRiskParityOptimization() {
    const sliders = document.querySelectorAll('.rp-budget-slider');
    const budgets = {};

    sliders.forEach(slider => {
        const sym = slider.getAttribute('data-symbol');
        budgets[sym] = parseFloat(slider.value) / 100.0;
    });

    const chartDom = document.getElementById('chart-rp-comparison');
    if (!chartDom) return;
    let myChart = echarts.getInstanceByDom(chartDom);
    if (!myChart) myChart = echarts.init(chartDom, 'dark');

    myChart.showLoading({
        text: '求解对数障碍凹凸风险平价优化权重...',
        color: '#10b981',
        textColor: '#fff',
        maskColor: 'rgba(20,20,25,0.8)'
    });

    try {
        const response = await fetch('/api/institutional/portfolio_opt/risk_parity', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ budgets })
        });
        const data = await response.json();
        myChart.hideLoading();

        if (data && !data.error) {
            const symbols = data.symbols;
            const originalWeights = symbols.map(s => (data.original_weights[s] * 100).toFixed(2));
            const optimizedWeights = symbols.map(s => (data.optimized_weights[s] * 100).toFixed(2));
            const actualRiskContributions = symbols.map(s => (data.actr_after[s] * 100).toFixed(2));

            const option = {
                backgroundColor: 'transparent',
                tooltip: {
                    trigger: 'axis',
                    axisPointer: { type: 'shadow' },
                    backgroundColor: 'rgba(0,0,0,0.85)',
                    borderColor: 'rgba(255,255,255,0.1)',
                    textStyle: { color: '#fff' }
                },
                legend: {
                    data: ['Original allocation', 'Risk-parity optimized', 'Optimized risk contribution (ACTR)'],
                    textStyle: { color: 'var(--text-secondary)' },
                    bottom: 0
                },
                grid: {
                    left: '3%',
                    right: '4%',
                    top: '10%',
                    bottom: '15%',
                    containLabel: true
                },
                xAxis: {
                    type: 'value',
                    axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
                    axisLabel: { color: 'var(--text-tertiary)', formatter: '{value}%' },
                    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.03)' } }
                },
                yAxis: {
                    type: 'category',
                    data: symbols,
                    axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
                    axisLabel: { color: '#fff', fontWeight: 'bold' }
                },
                series: [
                    {
                        name: 'Original allocation',
                        type: 'bar',
                        data: originalWeights,
                        itemStyle: { color: '#f59e0b' }
                    },
                    {
                        name: 'Risk-parity optimized',
                        type: 'bar',
                        data: optimizedWeights,
                        itemStyle: { color: '#10b981' }
                    },
                    {
                        name: 'Optimized risk contribution (ACTR)',
                        type: 'bar',
                        data: actualRiskContributions,
                        itemStyle: { color: '#a78bfa' }
                    }
                ]
            };

            myChart.setOption(option);

            const metricsEl = document.getElementById('rp-volatility-metrics');
            if (metricsEl) {
                metricsEl.textContent = `Original portfolio volatility: ${(data.volatility_before * 100).toFixed(2)}% | Optimized portfolio volatility: ${(data.volatility_after * 100).toFixed(2)}%`;
            }

            const btnCommit = document.getElementById('btn-commit-rp');
            if (btnCommit) btnCommit.style.display = 'block';

            const responseFric = await fetch('/api/institutional/sandbox/friction', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ target_weights: data.optimized_weights })
            });
            const dataFric = await responseFric.json();
            if (dataFric && !dataFric.error) {
                const commEl = document.getElementById('simu-audit-commission');
                const impEl = document.getElementById('simu-audit-impact');
                const totEl = document.getElementById('simu-audit-total-cost');
                const netAumEl = document.getElementById('simu-audit-net-aum');

                if (commEl) commEl.textContent = '¥' + dataFric.commission_cost.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
                if (impEl) impEl.textContent = '¥' + dataFric.market_impact_cost.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
                if (totEl) totEl.textContent = `¥${dataFric.total_friction_cost.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})} (${dataFric.total_cost_bps.toFixed(2)} bps)`;
                if (netAumEl) netAumEl.textContent = '¥' + dataFric.net_projected_aum.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});

                const radar = document.getElementById('simu-liquidity-radar');
                const radarContent = document.getElementById('simu-radar-content');
                if (radar && radarContent) {
                    const warnings = dataFric.details.filter(d => d.warning_level === 'RED' || d.warning_level === 'YELLOW');
                    if (warnings.length > 0) {
                        radar.style.display = 'block';
                        radarContent.innerHTML = warnings.map(w => `<div>[WARN] <strong>${w.symbol}</strong>: ADV participation ${(w.participation_rate * 100).toFixed(2)}% - ${w.warning_msg}</div>`).join('');
                    } else {
                        radar.style.display = 'none';
                    }
                }
            }
        } else {
            alert('风险平价优化失败: ' + (data.error || '未知错误'));
        }
    } catch (e) {
        console.error('Failed to run Risk Parity optimization', e);
        myChart.hideLoading();
        alert('System error: risk parity optimizer failed.');
    }
}
function resetRiskParityBudgets() {
    const sliders = document.querySelectorAll('.rp-budget-slider');
    const N = sliders.length;
    if (N === 0) return;
    const equalVal = (100 / N).toFixed(1);
    sliders.forEach(s => {
        s.value = equalVal;
        s.nextElementSibling.innerText = equalVal + '%';
    });
    const btnCommit = document.getElementById('btn-commit-rp');
    if (btnCommit) btnCommit.style.display = 'none';
}
// --- 3. Historical Black Swan Stress Replicator ---
