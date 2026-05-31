// risk.js - AlphaCore focused panel module.
window.factorRiskData = null;
let factorRadarChart = null;
let factorStyleChart = null;
window.initFactorRisk = async function() {
    document.getElementById('factor-ledger-body').innerHTML = `<tr><td colspan="6" style="text-align:center; padding:20px; color:var(--text-tertiary);">正在计算多因子风险矩阵...</td></tr>`;

    try {
        const response = await fetch('/api/institutional/factors');
        if (!response.ok) throw new Error('API Error');
        const data = await response.json();
        window.factorRiskData = data;
        renderFactorRisk(data);
    } catch (e) {
        console.error(e);
        document.getElementById('factor-ledger-body').innerHTML = `<tr><td colspan="6" style="text-align:center; padding:20px; color:var(--danger);">因子引擎加载失败</td></tr>`;
        document.getElementById('factor-engine-status').textContent = '因子引擎异常';
        document.getElementById('factor-engine-status').style.color = 'var(--danger)';
    }
};
function renderFactorRisk(data) {
    if (!data || !data.factor_groups) return;

    // --- L1: KPIs ---
    // 1. Coverage
    const coverage = data.coverage.coverage_ratio * 100;
    const covEl = document.getElementById('factor-coverage');
    covEl.textContent = coverage.toFixed(1) + '%';
    covEl.style.color = coverage < 80 ? 'var(--warning)' : 'var(--text-primary)';

    // 2. Dominant Risk
    const domEl = document.getElementById('factor-dominant');
    if (data.top_factor && data.top_factor.factor_name) {
        domEl.textContent = `${formatFactorGroup(data.top_factor.factor_group)} : ${formatFactorName(data.top_factor.factor_name)}`;
    } else {
        domEl.textContent = "暂无";
    }

    // 3. Factor Concentration (HHI)
    // Flatten all exposures
    let allExposures = [];
    Object.values(data.factor_groups).forEach(grp => {
        Object.values(grp).forEach(val => allExposures.push(Math.abs(val)));
    });

    let hhi = 0;
    if (allExposures.length > 0) {
        const totalExp = allExposures.reduce((a, b) => a + b, 0);
        if (totalExp > 0) {
            hhi = allExposures.reduce((sum, val) => sum + Math.pow((val / totalExp) * 100, 2), 0);
        }
    }
    const hhiEl = document.getElementById('factor-hhi');
    hhiEl.textContent = hhi.toFixed(0);
    const hhiCard = document.getElementById('factor-hhi-card');
    if (hhi > 2500) {
        hhiEl.style.color = 'var(--danger)';
        hhiCard.classList.add('glow-fail');
    } else if (hhi > 1500) {
        hhiEl.style.color = 'var(--warning)';
    } else {
        hhiEl.style.color = 'var(--success)';
        hhiCard.classList.add('glow-pass');
    }
    // --- L2: ECharts ---
    renderFactorRadar(data.factor_groups.macro || {});
    renderFactorStyleBar(data.factor_groups.strategy || {}, data.factor_groups.theme || {});

    // --- L3: Asset Ledger ---
    renderFactorLedger(data.positions);
}
function renderFactorRadar(macro) {
    if (!factorRadarChart) {
        factorRadarChart = echarts.init(document.getElementById('factor-radar-chart'));
    }

    const indicators = [
        { name: '权益贝塔', max: 1.5, min: -1.5 },
        { name: '流动性', max: 0.5, min: -0.5 },
        { name: '美元', max: 0.5, min: -0.5 },
        { name: '利率', max: 0.5, min: -0.5 },
        { name: '通胀', max: 1.0, min: -1.0 }
    ];

    const values = [
        macro['equity_beta'] || 0,
        macro['liquidity_sensitivity'] || 0,
        macro['dollar_sensitivity'] || 0,
        macro['rate_sensitivity'] || 0,
        macro['inflation_sensitivity'] || 0
    ];
    const option = {
        tooltip: {
            confine: true,
            backgroundColor: 'rgba(0,0,0,0.8)',
            borderColor: 'rgba(56,189,248,0.5)',
            textStyle: { color: '#fff', fontFamily: 'var(--font-mono)', fontSize: 12 },
            formatter: function(params) {
                let s = `<div style="font-weight:bold; margin-bottom:5px; color:var(--accent-primary);">宏观情景敏感度</div>`;
                s += `<div>权益贝塔: ${values[0].toFixed(2)} <span style="color:#aaa;font-size:0.8em;">(市场 +10% -> 组合 +${(values[0]*10).toFixed(1)}%)</span></div>`;
                s += `<div>美元敏感度: ${values[2].toFixed(2)} <span style="color:#aaa;font-size:0.8em;">(DXY +5% -> 组合 ${(values[2]*5 > 0 ? '+' : '')}${(values[2]*5).toFixed(1)}%)</span></div>`;
                s += `<div>通胀敏感度: ${values[4].toFixed(2)}</div>`;
                return s;
            }
        },
        radar: {
            indicator: indicators,
            shape: 'polygon',
            splitNumber: 4,
            axisName: { color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', fontSize: 10 },
            splitLine: { lineStyle: { color: ['rgba(255,255,255,0.02)', 'rgba(255,255,255,0.05)', 'rgba(255,255,255,0.08)', 'rgba(255,255,255,0.1)'].reverse() } },
            splitArea: { show: false },
            axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } }
        },
        series: [{
            type: 'radar',
            data: [{
                value: values,
                name: '组合暴露',
                symbol: 'circle',
                symbolSize: 8,
                itemStyle: { color: '#00f0ff', borderColor: '#fff', borderWidth: 1 },
                areaStyle: {
                    color: new echarts.graphic.RadialGradient(0.5, 0.5, 1, [
                        { offset: 0, color: 'rgba(0, 240, 255, 0.1)' },
                        { offset: 1, color: 'rgba(0, 240, 255, 0.4)' }
                    ])
                },
                lineStyle: { color: '#00f0ff', width: 2, shadowBlur: 15, shadowColor: '#00f0ff' }
            }]
        }]
    };
    factorRadarChart.setOption(option);
}
function renderFactorStyleBar(strategy, theme) {
    if (!factorStyleChart) {
        factorStyleChart = echarts.init(document.getElementById('factor-style-chart'));
    }

    // Combine and sort
    let items = [];
    Object.entries(strategy).forEach(([k, v]) => items.push({name: k, val: v}));
    Object.entries(theme).forEach(([k, v]) => items.push({name: k, val: v}));
    items.sort((a, b) => Math.abs(a.val) - Math.abs(b.val)); // Ascending by absolute value for bar chart

    const names = items.map(i => formatFactorName(i.name));
    const values = items.map(i => i.val);
    const option = {
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'shadow' },
            backgroundColor: 'rgba(0,0,0,0.8)',
            textStyle: { color: '#fff', fontFamily: 'var(--font-mono)' },
            formatter: params => `${params[0].name}: ${params[0].value.toFixed(3)}`
        },
        grid: { top: 20, bottom: 20, left: 140, right: 30 },
        xAxis: {
            type: 'value',
            splitLine: { show: true, lineStyle: { color: 'rgba(255,255,255,0.05)', type: 'dashed' } },
            axisLabel: { color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', fontSize: 10 },
            axisLine: { show: true, lineStyle: { color: 'rgba(255,255,255,0.3)', width: 2 } } // Emphasize zero line
        },
        yAxis: {
            type: 'category',
            data: names,
            axisLabel: { color: '#e2e8f0', fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 'bold' },
            axisLine: { show: false },
            axisTick: { show: false }
        },
        series: [{
            type: 'bar',
            data: values.map(v => ({
                value: v,
                itemStyle: {
                    color: new echarts.graphic.LinearGradient(1, 0, 0, 0, [
                        { offset: 0, color: v >= 0 ? 'rgba(16,185,129,0.9)' : 'rgba(244,63,94,0.3)' },
                        { offset: 1, color: v >= 0 ? 'rgba(16,185,129,0.3)' : 'rgba(244,63,94,0.9)' }
                    ]),
                    shadowBlur: 10,
                    shadowColor: v >= 0 ? 'rgba(16,185,129,0.4)' : 'rgba(244,63,94,0.4)'
                }
            })),
            barWidth: '45%',
            itemStyle: { borderRadius: 3 }
        }]
    };
    factorStyleChart.setOption(option);
}
function renderFactorLedger(positions) {
    const tbody = document.getElementById('factor-ledger-body');
    if (!positions || positions.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:20px; color:var(--text-tertiary);">暂无可映射持仓</td></tr>`;
        return;
    }

    // Sort positions by weight descending
    positions.sort((a, b) => b.weight - a.weight);

    let html = '';

    const fmtExposure = (val) => {
        if (val === 0) return `<span style="color:var(--text-tertiary);">-</span>`;
        const color = val > 0 ? '#10b981' : '#f43f5e';
        const sign = val > 0 ? '+' : '';
        // Calculate heat intensity 0-1
        const intensity = Math.min(Math.abs(val) * 2.5, 1);
        const bgRgb = val > 0 ? `16,185,129` : `244,63,94`;
        const bgStr = `rgba(${bgRgb}, ${intensity * 0.35})`;
        const borderStr = `1px solid rgba(${bgRgb}, ${Math.max(intensity, 0.2)})`;

        return `<span style="display:inline-block; width:100%; height:100%; background:${bgStr}; color:${color}; font-family:var(--font-mono); font-weight:800; text-align:right; padding:6px 10px; border-radius:4px; border-right:${borderStr}; box-sizing:border-box; text-shadow:0 0 8px rgba(${bgRgb},0.4);">${sign}${val.toFixed(3)}</span>`;
    };
    positions.forEach(pos => {
        if (!pos.mapped) return; // Skip unmapped for now to keep matrix clean

        // Extract macro exposures
        let expMap = {};
        pos.exposures.forEach(e => {
            if (e.factor_group === 'macro') {
                expMap[e.factor_name] = e.exposure * pos.weight; // Contribution = Exposure * Weight
            }
        });

        // Find quantity and price from actual portfolio
        // Since factor API doesn't return qty/price, we lookup from window.portfolioData
        let qty = 0;
        let price = 0;
        let name = pos.symbol;
        if (window.portfolioData && window.portfolioData.positions) {
            const actualPos = window.portfolioData.positions.find(p => p.symbol === pos.symbol);
            if (actualPos) {
                qty = actualPos.quantity || 0;
                price = actualPos.current_price || 0;
                name = actualPos.name || pos.symbol;
            }
        }

        html += `
            <tr class="clickable-row" style="transition: background-color 0.2s ease;" data-action="open-action-modal" data-symbol="${escapeHTML(pos.symbol)}" data-name="${escapeHTML(name)}" data-qty="${qty}" data-price="${price}">
                <td style="padding-left:16px;">
                    <div style="display:flex; flex-direction:column; gap:2px;">
                        <span style="font-weight:700; color:var(--text-primary); font-size:0.95rem;">${name || pos.symbol}</span>
                        <span style="font-family:var(--font-mono); font-size:0.7rem; color:var(--text-tertiary);">${pos.symbol}</span>
                    </div>
                </td>
                <td style="padding:4px;">${fmtExposure(expMap['equity_beta'] || 0)}</td>
                <td style="padding:4px;">${fmtExposure(expMap['liquidity_sensitivity'] || 0)}</td>
                <td style="padding:4px;">${fmtExposure(expMap['dollar_sensitivity'] || 0)}</td>
                <td style="padding:4px;">${fmtExposure(expMap['rate_sensitivity'] || 0)}</td>
                <td style="padding:4px; padding-right:16px;">${fmtExposure(expMap['inflation_sensitivity'] || 0)}</td>
            </tr>
        `;
    });

    tbody.innerHTML = html;
}
function formatFactorGroup(value) {
    const map = {
        macro: '宏观',
        strategy: '策略',
        theme: '主题',
        style: '风格',
    };
    return map[String(value || '').toLowerCase()] || String(value || '--').toUpperCase();
}
function formatFactorName(value) {
    const map = {
        equity_beta: '权益贝塔',
        liquidity_sensitivity: '流动性敏感度',
        dollar_sensitivity: '美元汇率暴露',
        rate_sensitivity: '利率敏感度',
        inflation_sensitivity: '通胀敏感度',
        momentum: '动量',
        value: '价值',
        growth: '成长',
        quality: '质量',
        defensive: '防御',
        cyclical: '周期',
    };
    const key = String(value || '').toLowerCase();
    return map[key] || String(value || '--').replace(/_/g, ' ').toUpperCase();
}
// --- [STRE] Historical Scenario Stress Testing ---
