// historical_scenarios.js - AlphaCore focused panel module.
window.historicalCrisisCache = null;
async function initHistoricalScenarios() {
    triggerCrisisSimulation();
}
function switchHistoricalCrisisScenario(scenarioId) {
    if (!window.historicalCrisisCache || !window.historicalCrisisCache[scenarioId]) return;
    const data = window.historicalCrisisCache[scenarioId];

    const narrativeEl = document.getElementById('historical-crisis-narrative');
    if (narrativeEl) {
        narrativeEl.innerHTML = `
            <div style="font-weight: 700; color:#fff; font-size:0.95rem; border-bottom:1px solid rgba(255,255,255,0.05); padding-bottom:6px; margin-bottom:6px;">
                历史危机复盘：${data.name_zh}
            </div>
            <div style="color:var(--text-secondary);">${data.narrative_zh}</div>
        `;
    }

    const mddPort = document.getElementById('rp-maxdd-portfolio');
    const mddBench = document.getElementById('rp-maxdd-benchmark');
    const mddRP = document.getElementById('rp-maxdd-riskparity');
    const reduction = document.getElementById('rp-maxdd-reduction');

    if (mddPort) mddPort.textContent = `${data.max_drawdowns.portfolio_pct.toFixed(2)}%`;
    if (mddBench) mddBench.textContent = `${data.max_drawdowns.benchmark_pct.toFixed(2)}%`;
    if (mddRP) mddRP.textContent = `${data.max_drawdowns.risk_parity_pct.toFixed(2)}%`;
    if (reduction) {
        const val = data.max_drawdowns.drawdown_reduction_alpha_pct;
        reduction.textContent = `${val >= 0 ? '+' : ''}${val.toFixed(2)}%`;
        reduction.style.color = val >= 0 ? '#10b981' : '#ef4444';
    }

    const mddAIShield = document.getElementById('rp-maxdd-aishield');
    const survivalAlpha = document.getElementById('rp-maxdd-survival-alpha');
    if (mddAIShield) mddAIShield.textContent = `${data.max_drawdowns.blue_team_defense_pct.toFixed(2)}%`;
    if (survivalAlpha) {
        const val = data.max_drawdowns.survival_alpha_pct;
        survivalAlpha.textContent = `${val >= 0 ? '+' : ''}${val.toFixed(2)}%`;
        survivalAlpha.style.color = val >= 0 ? '#10b981' : '#ef4444';
    }

    const chartDom = document.getElementById('chart-historical-drawdown');
    if (!chartDom) return;
    let myChart = echarts.getInstanceByDom(chartDom);
    if (!myChart) myChart = echarts.init(chartDom, 'dark');

    const option = {
        backgroundColor: 'transparent',
        tooltip: {
            trigger: 'axis',
            backgroundColor: 'rgba(0,0,0,0.85)',
            borderColor: 'rgba(255,255,255,0.1)',
            textStyle: { color: '#fff' }
        },
                legend: {
            data: ['当前组合原仓', '基准组合', '风险平价', '蓝军防御'],
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
            type: 'category',
            data: data.dates,
            axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
            axisLabel: { color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }
        },
        yAxis: {
            type: 'value',
            min: function (value) { return (value.min - 0.02).toFixed(2); },
            max: 1.05,
            axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
            axisLabel: { color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' },
            splitLine: { lineStyle: { color: 'rgba(255,255,255,0.03)' } }
        },
        series: [
            {
                name: '当前组合原仓',
                type: 'line',
                data: data.portfolio_nav,
                lineStyle: { color: '#f59e0b', width: 2 },
                itemStyle: { color: '#f59e0b' },
                showSymbol: false
            },
            {
                name: '基准组合',
                type: 'line',
                data: data.benchmark_nav,
                lineStyle: { color: '#9ca3af', width: 1.5, type: 'dashed' },
                itemStyle: { color: '#9ca3af' },
                showSymbol: false
            },
            {
                name: '风险平价',
                type: 'line',
                data: data.risk_parity_nav,
                lineStyle: { color: '#10b981', width: 3 },
                itemStyle: { color: '#10b981' },
                showSymbol: false
            },
            {
                name: '蓝军防御',
                type: 'line',
                data: data.blue_team_defense_nav,
                lineStyle: { color: '#a78bfa', width: 3 },
                itemStyle: { color: '#a78bfa' },
                showSymbol: false
            }
        ]
    };

    myChart.setOption(option);
}
// --- 4. Custom Decision Archival / Committer ---
async function commitCustomDecision(source) {
    const payload = {
        source: source,
        portfolio: null
    };

    if (source === 'bayesian_rebalance') {
        const views = {};
        const confidences = {};

        const inputs = document.querySelectorAll('.bl-view-input');
        inputs.forEach(input => {
            const val = parseFloat(input.value);
            const sym = input.getAttribute('data-symbol');
            if (!isNaN(val) && val !== 0) {
                views[sym] = val / 100.0;
            }
        });

        const sliders = document.querySelectorAll('.bl-confidence-slider');
        sliders.forEach(slider => {
            const sym = slider.getAttribute('data-symbol');
            if (views[sym] !== undefined) {
                confidences[sym] = parseFloat(slider.value) / 100.0;
            }
        });

        payload.views = views;
        payload.confidences = confidences;
    } else if (source === 'risk_parity_rebalance') {
        const budgets = {};
        const sliders = document.querySelectorAll('.rp-budget-slider');
        sliders.forEach(slider => {
            const sym = slider.getAttribute('data-symbol');
            budgets[sym] = parseFloat(slider.value) / 100.0;
        });
        payload.budgets = budgets;
    } else if (source === 'macro_shock_sandbox') {
        const shocks = {
            equity_shock: parseFloat(document.getElementById('slider-shock-equity').value) / 100.0,
            rate_shock: parseFloat(document.getElementById('slider-shock-rate').value) / 100.0,
            vol_shock: parseFloat(document.getElementById('slider-shock-vol').value) / 100.0,
            commodity_shock: parseFloat(document.getElementById('slider-shock-commodity').value) / 100.0
        };
        payload.shocks = shocks;
    }

    try {
        const response = await fetch('/api/institutional/audit/commit_custom', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const result = await response.json();

        if (result && result.ticket_id) {
        alert(`Decision signed and evidence retained.\nAudit Ticket ID: ${result.ticket_id}\nCompliance: ${result.compliance_status.toUpperCase()}\nDecision score: ${result.score}`);
            if (window.initInstitutionalDecision) window.initInstitutionalDecision();
        } else {
            alert('签署决策存证失败: ' + (result.error || '未知内部错误'));
        }
    } catch(e) {
        console.error('Commit custom decision failed', e);
        alert('Unable to connect to the audit network.');
    }
}
// ============================================================================
// L6 INSTITUTIONAL ALGORITHMIC COUNTER (TWAP / DIRECT SIGN-OFF & SLIPPAGE AUDIT)
// ============================================================================
