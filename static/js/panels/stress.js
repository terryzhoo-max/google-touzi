// stress.js - AlphaCore focused panel module.
async function initStressTesting() {
    try {
        const statusEl = document.getElementById('stress-engine-status');
        if(statusEl) {
            statusEl.innerText = '正在计算压力情景';
            statusEl.style.background = 'rgba(245,158,11,0.12)';
        }
        const res = await fetchJsonWithRetry('/api/institutional/scenarios');

        if(statusEl) {
            statusEl.innerText = '压力治理引擎在线';
            statusEl.style.background = 'rgba(15,118,110,0.18)';
        }
        renderStressTesting(res);
    } catch (e) {
        console.error('Failed to init stress testing:', e);
        const statusEl = document.getElementById('stress-engine-status');
        if(statusEl) {
            statusEl.innerText = '压力治理引擎异常';
            statusEl.style.color = '#fff';
            statusEl.style.background = '#ef4444';
        }
    }
}
function renderStressTesting(data) {
    if (!data || !data.scenarios) return;
    const worst = data.worst_scenario || {};
    const lossPct = worst.portfolio_loss_pct || 0;
    // --- L1 KPIs ---
    const worstNameEl = document.getElementById('stress-worst-name');
    const drawdownEl = document.getElementById('stress-max-drawdown');
    const resiliencyEl = document.getElementById('stress-resiliency-grade');
    if (worstNameEl) {
        const primary = worst.name_zh || (worst.name ? worst.name.toUpperCase() : '--');
        const secondary = worst.name_zh && worst.name
            ? `<span class="stress-kpi-subtext">${worst.name.toUpperCase()}</span>`
            : '';
        worstNameEl.innerHTML = `<span class="stress-kpi-maintext">${primary}</span>${secondary}`;
    }
    if (drawdownEl) drawdownEl.innerText = lossPct.toFixed(2) + '%';
    if (resiliencyEl) {
        let grade = 'D';
        let color = '#ef4444';
        let note = '需立即降风险';
        if (lossPct >= -5.0) { grade = 'A'; color = '#10b981'; note = '压力下韧性充足'; }
        else if (lossPct >= -10.0) { grade = 'B'; color = '#f59e0b'; note = '可承受但需跟踪'; }
        else if (lossPct >= -15.0) { grade = 'C'; color = '#f97316'; note = '建议降低尾部风险'; }

        resiliencyEl.innerHTML = `<span class="stress-grade-main">${grade}级</span><span class="stress-grade-note">${note}</span>`;
        resiliencyEl.style.color = color;
        resiliencyEl.style.textShadow = `0 0 15px ${color}`;
    }
    // --- L2 ECharts Impact Distribution ---
    const impactChartDom = document.getElementById('stress-impact-chart');
    if (impactChartDom && window.echarts) {
        let impactChart = echarts.getInstanceByDom(impactChartDom);
        if (!impactChart) impactChart = echarts.init(impactChartDom);
        // Sort ascending (worst drop at the bottom, so it shows up at the top in Echarts horizontal bar)
        const sortedScenarios = [...data.scenarios].sort((a,b) => a.portfolio_loss_pct - b.portfolio_loss_pct);
        impactChart.setOption({
            tooltip: {
                className: 'terminal-hud-tooltip',
                trigger: 'axis',
                axisPointer: {type:'shadow'},
                formatter: function(params) {
                    const p = params[0];
                    // Find the original scenario to get name_zh
                    const scenario = sortedScenarios.find(s => (s.name + ' | ' + s.name_zh) === p.name || s.name === p.name);
                    const title = scenario ? (scenario.name_zh || scenario.name) : p.name;
                    const riskLevel = p.value <= -15 ? '红色预警' : p.value <= -8 ? '橙色关注' : '常规跟踪';
                    return `<div class="hud-title">情景名称：${title}</div><div class="hud-value">组合损益：${p.value > 0 ? '+' : ''}${p.value}%</div><div class="hud-note">风险等级：${riskLevel}</div>`;
                }
            },
            grid: { left: '15%', right: '10%', bottom: '10%', top: '5%', containLabel: true },
            xAxis: {
                type: 'value',
                splitLine: { show: true, lineStyle: { color: 'rgba(255,255,255,0.05)', type: 'dashed' } },
                axisLabel: { color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', fontSize: 10, formatter: '{value}%' },
                axisLine: { show: true, lineStyle: { color: 'rgba(255,255,255,0.3)', width: 2 } }
            },
            yAxis: {
                type: 'category',
                data: sortedScenarios.map(s => s.name_zh || s.name),
                axisLabel: { color: '#e2e8f0', fontFamily: 'var(--font-sans)', fontSize: 11, fontWeight: 'bold' },
                axisLine: { show: false },
                axisTick: { show: false },
                splitArea: { show: true, areaStyle: { color: ['rgba(255,255,255,0.02)', 'transparent'] } }
            },
            series: [{
                name: '组合损益',
                type: 'bar',
                barWidth: '50%',
                label: {
                    show: true,
                    position: 'right',
                    formatter: '{c}%',
                    fontFamily: 'var(--font-mono)',
                    color: '#fff'
                },
                data: sortedScenarios.map(s => {
                    const val = s.portfolio_loss_pct;
                    const isWorst = (s.id === worst.id);
                    return {
                        value: val,
                        itemStyle: {
                            borderRadius: 3,
                            color: new echarts.graphic.LinearGradient(1, 0, 0, 0, [
                                { offset: 0, color: val >= 0 ? 'rgba(16,185,129,0.9)' : (isWorst ? 'rgba(220,38,38,1)' : 'rgba(244,63,94,0.7)') },
                                { offset: 1, color: val >= 0 ? 'rgba(16,185,129,0.3)' : 'rgba(244,63,94,0.2)' }
                            ]),
                            shadowBlur: isWorst ? 15 : 5,
                            shadowColor: isWorst ? 'rgba(220,38,38,0.6)' : 'rgba(244,63,94,0.2)',
                            borderColor: isWorst ? '#ef4444' : 'transparent',
                            borderWidth: isWorst ? 1 : 0
                        }
                    };
                })
            }]
        });
    }
    // --- L3 Shock Propagation Ledger ---
    const tbody = document.getElementById('stress-ledger-body');
    if (!tbody) return;
    const fmtShockBadge = (val, maxShock = 20) => {
        if (val === 0 || !val) return `<span style="color:var(--text-tertiary);">-</span>`;
        // Convert to percentage display
        const valPct = val * 100;
        const color = val > 0 ? '#10b981' : '#f43f5e';
        const sign = val > 0 ? '+' : '';
        const intensity = Math.min(Math.abs(valPct) / maxShock, 1.0);
        const bgRgb = val > 0 ? `16,185,129` : `244,63,94`;
        const bgStr = `rgba(${bgRgb}, ${Math.max(intensity * 0.35, 0.1)})`;
        const borderStr = `1px solid rgba(${bgRgb}, ${Math.max(intensity, 0.2)})`;

        return `<span style="display:inline-block; background:${bgStr}; color:${color}; font-family:var(--font-mono); font-weight:800; text-align:right; padding:4px 8px; border-radius:4px; border-right:${borderStr}; box-sizing:border-box; text-shadow:0 0 8px rgba(${bgRgb},0.4);">${sign}${valPct.toFixed(1)}%</span>`;
    };
    let html = '';
    const displayScenarios = [...data.scenarios].sort((a,b) => a.portfolio_loss_pct - b.portfolio_loss_pct);
    displayScenarios.forEach(s => {
        const eqShock = s.shocks?.equity || 0;
        const bdShock = s.shocks?.bond || 0;
        const gldShock = s.shocks?.gold || 0;

        // aggregate region and strategy shocks into a string
        let extraStr = [];
        if (s.region_shocks) {
            Object.keys(s.region_shocks).forEach(k => {
                if (s.region_shocks[k] !== 0) extraStr.push(`${k}: ${(s.region_shocks[k]*100).toFixed(0)}%`);
            });
        }
        if (s.strategy_shocks) {
            Object.keys(s.strategy_shocks).forEach(k => {
                if (s.strategy_shocks[k] !== 0) extraStr.push(`${k}: ${(s.strategy_shocks[k]*100).toFixed(0)}%`);
            });
        }
        let extraBadge = extraStr.length > 0
            ? `<span style="font-size:0.7rem; color:var(--text-secondary); background:rgba(255,255,255,0.05); padding:2px 6px; border-radius:4px;">${extraStr.join(' | ')}</span>`
            : `<span style="color:var(--text-tertiary);">-</span>`;
        const pnlPct = s.portfolio_loss_pct;
        const pColor = pnlPct > 0 ? '#10b981' : '#f43f5e';
        const pSign = pnlPct > 0 ? '+' : '';
        const isWorst = (s.id === worst.id);
        const rowClass = isWorst ? 'clickable-row stress-priority-row' : 'clickable-row';

        html += `
            <tr class="${rowClass}" style="transition: background-color 0.2s ease;">
                <td style="padding-left:16px;">
                    <div style="display:flex; flex-direction:column; gap:2px;">
                        <span style="font-weight:700; color:var(--text-primary); font-size:0.95rem;">${s.name_zh || s.name}</span>
                        <span style="font-size:0.7rem; color:var(--text-tertiary); letter-spacing:0;">${isWorst ? '风险重点行' : '压力情景'}</span>
                    </div>
                </td>
                <td style="text-align:right; font-family:var(--font-mono); font-weight:800; color:${pColor}; font-size:1.1rem; text-shadow:0 0 10px ${pColor}55;">
                    ${pSign}${pnlPct.toFixed(2)}%
                </td>
                <td style="padding:4px; text-align:right;">${fmtShockBadge(eqShock)}</td>
                <td style="padding:4px; text-align:right;">${fmtShockBadge(bdShock)}</td>
                <td style="padding:4px; text-align:right;">${fmtShockBadge(gldShock)}</td>
                <td style="padding:4px; text-align:right; padding-right:16px;">${extraBadge}</td>
            </tr>
        `;
    });

    tbody.innerHTML = html;
}
// --- [STRA] Strategy Lab ---
