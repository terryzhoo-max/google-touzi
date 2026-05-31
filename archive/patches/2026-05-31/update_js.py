with open(r'd:\FIONA\google touzi\static\main.js', 'r', encoding='utf-8') as f:
    js = f.read()

# Hook into switchView
old_switch = '''    } else if (viewId === 'view-stress') {
        if (typeof initStressTesting === 'function') {
            initStressTesting();
        }
    }'''

new_switch = '''    } else if (viewId === 'view-stress') {
        if (typeof initStressTesting === 'function') {
            initStressTesting();
        }
    } else if (viewId === 'view-strategy') {
        if (typeof initStrategyLab === 'function') {
            initStrategyLab();
        }
    }'''

js = js.replace(old_switch, new_switch)

# Add initStrategyLab function
init_func = '''
// --- [STRA] Strategy Lab ---
async function initStrategyLab() {
    const view = document.getElementById('view-strategy');
    if (!view || !view.classList.contains('active')) return;

    // Time
    const timeEl = document.getElementById('strategy-time');
    if(timeEl) {
        timeEl.innerText = new Date().toLocaleTimeString('en-US', {hour12:false}) + '.' + new Date().getMilliseconds().toString().padStart(3,'0');
    }

    try {
        const res = await fetch('/api/institutional/strategies');
        const data = await res.json();
        
        // 1. Render Engines
        const engContainer = document.getElementById('strategy-engines-container');
        if (engContainer && data.engines) {
            engContainer.innerHTML = data.engines.map(eng => {
                const badgeColor = eng.status === 'active' ? '#10b981' : (eng.status === 'standby' ? '#f59e0b' : '#ef4444');
                const signalColor = eng.color || '#38bdf8';
                
                const detailsHtml = eng.details.map(d => 
                    `<div style="display:flex; justify-content:space-between; font-size:0.75rem; border-bottom:1px solid rgba(255,255,255,0.05); padding-bottom:4px;">
                        <span style="color:var(--text-tertiary);">${d.label}</span>
                        <span style="font-family:var(--font-mono); color:${d.color || '#e2e8f0'}">${d.value}</span>
                    </div>`
                ).join('');
                
                const holdingsHtml = eng.holdings.map(h => {
                    const actColor = h.action === 'BUY' ? '#10b981' : (h.action === 'LIQUIDATE' ? '#ef4444' : '#64748b');
                    return `<div style="display:flex; justify-content:space-between; font-size:0.7rem; font-family:var(--font-mono);">
                        <span><span style="color:var(--text-tertiary);">${h.symbol}</span> ${h.name}</span>
                        <span><span style="color:${actColor}; margin-right:8px;">[${h.action}]</span> <span style="color:var(--text-secondary);">${h.weight}</span></span>
                    </div>`;
                }).join('');

                return `
                <div class="glass-card" style="position:relative; overflow:hidden; display:flex; flex-direction:column; gap:12px;">
                    <!-- Accent Line -->
                    <div style="position:absolute; left:0; top:0; bottom:0; width:4px; background:${signalColor};"></div>
                    
                    <div style="padding-left:8px; display:flex; justify-content:space-between; align-items:flex-start;">
                        <div>
                            <div style="font-size:1.1rem; font-weight:700; color:var(--text-primary); margin-bottom:2px;">${eng.name_en}</div>
                            <div style="font-size:0.7rem; color:var(--text-tertiary); letter-spacing:1px;">${eng.name}</div>
                        </div>
                        <div style="display:flex; flex-direction:column; align-items:flex-end; gap:4px;">
                            <span style="font-size:0.6rem; font-family:var(--font-mono); padding:2px 6px; border-radius:4px; border:1px solid ${badgeColor}; color:${badgeColor}; background:${badgeColor}22;">STATUS: ${eng.status.toUpperCase()}</span>
                            <span style="font-size:0.8rem; font-family:var(--font-mono); color:${signalColor}; font-weight:bold;">> ${eng.signal}</span>
                        </div>
                    </div>
                    
                    <div style="padding-left:8px; font-size:0.8rem; color:var(--text-secondary); line-height:1.4;">
                        ${eng.description}
                    </div>
                    
                    <div style="padding-left:8px; display:flex; flex-direction:column; gap:8px; margin-top:8px;">
                        ${detailsHtml}
                    </div>
                    
                    <div style="padding-left:8px; margin-top:8px; background:rgba(0,0,0,0.2); padding:8px; border-radius:4px;">
                        <div style="font-size:0.65rem; color:var(--text-tertiary); margin-bottom:6px;">TARGET ALLOCATION:</div>
                        ${holdingsHtml}
                    </div>
                </div>`;
            }).join('');
        }

        // 2. Render Metrics Container
        const metricsContainer = document.getElementById('strategy-metrics-container');
        if (metricsContainer && data.backtest) {
            const m = data.backtest.metrics;
            metricsContainer.innerHTML = `
                <div class="metric-cell"><span style="display:flex; flex-direction:column; line-height:1.3;">Strategy YTD <small style="font-size:0.85em; color:var(--text-tertiary);">策略本年收益</small></span><strong style="color:#10b981;">${m.strategy_ytd}</strong></div>
                <div class="metric-cell"><span style="display:flex; flex-direction:column; line-height:1.3;">Benchmark YTD <small style="font-size:0.85em; color:var(--text-tertiary);">基准本年收益</small></span><strong style="color:var(--text-primary);">${m.benchmark_ytd}</strong></div>
                <div class="metric-cell"><span style="display:flex; flex-direction:column; line-height:1.3;">Max Drawdown <small style="font-size:0.85em; color:var(--text-tertiary);">最大回撤</small></span><strong style="color:#ef4444;">${m.max_drawdown}</strong></div>
                <div class="metric-cell"><span style="display:flex; flex-direction:column; line-height:1.3;">Sharpe Ratio <small style="font-size:0.85em; color:var(--text-tertiary);">夏普比率</small></span><strong style="color:#38bdf8;">${m.sharpe_ratio}</strong></div>
            `;
        }

        // 3. Render Equity Curve
        const eqChartDom = document.getElementById('chart-strategy-equity');
        if (eqChartDom && window.echarts && data.backtest) {
            let eqChart = echarts.getInstanceByDom(eqChartDom);
            if (!eqChart) eqChart = echarts.init(eqChartDom);
            
            eqChart.setOption({
                tooltip: { 
                    trigger: 'axis',
                    className: 'terminal-hud-tooltip',
                    formatter: function(params) {
                        let html = `<div class="hud-title" style="border-bottom-color:var(--text-tertiary);">${params[0].axisValue}</div>`;
                        params.forEach(p => {
                            html += `<div class="hud-value" style="color:${p.color}; font-size:1rem;">${p.seriesName}: ${p.value > 0 ? '+' : ''}${p.value.toFixed(2)}%</div>`;
                        });
                        return html;
                    }
                },
                legend: { data: ['STRATEGY (策略)', 'BENCHMARK (基准)'], textStyle: { color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }, top: 0, right: 0 },
                grid: { left: '3%', right: '4%', bottom: '5%', top: '15%', containLabel: true },
                xAxis: { 
                    type: 'category', 
                    boundaryGap: false, 
                    data: data.backtest.dates,
                    axisLine: { lineStyle: { color: 'rgba(255,255,255,0.2)' } },
                    axisLabel: { color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', fontSize: 10 }
                },
                yAxis: { 
                    type: 'value',
                    axisLabel: { color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', formatter: '{value}%' },
                    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }
                },
                series: [
                    {
                        name: 'STRATEGY (策略)',
                        type: 'line',
                        data: data.backtest.strategy_returns,
                        itemStyle: { color: '#38bdf8' },
                        lineStyle: { width: 3, shadowColor: 'rgba(56,189,248,0.5)', shadowBlur: 10 },
                        showSymbol: false,
                        areaStyle: {
                            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                                { offset: 0, color: 'rgba(56,189,248,0.3)' },
                                { offset: 1, color: 'rgba(56,189,248,0.0)' }
                            ])
                        }
                    },
                    {
                        name: 'BENCHMARK (基准)',
                        type: 'line',
                        data: data.backtest.benchmark_returns,
                        itemStyle: { color: '#64748b' },
                        lineStyle: { width: 2, type: 'dashed' },
                        showSymbol: false
                    }
                ]
            });
        }

        // 4. Render Universe
        const univContainer = document.getElementById('strategy-universe-container');
        if (univContainer && data.universe) {
            let uHtml = '';
            for (const [category, assets] of Object.entries(data.universe)) {
                let catColor = '#38bdf8';
                if(category.includes('A_SHARE')) catColor = '#ef4444';
                if(category.includes('OVERSEAS')) catColor = '#10b981';
                if(category.includes('THEME')) catColor = '#a855f7';
                
                uHtml += `<div style="flex: 1 1 200px; background:rgba(0,0,0,0.2); padding:12px; border-radius:4px; border-top:2px solid ${catColor};">
                    <div style="font-size:0.7rem; color:var(--text-tertiary); margin-bottom:8px; font-weight:bold;">${category.replace('_',' ')}</div>
                    <div style="display:flex; flex-direction:column; gap:6px;">`;
                
                assets.forEach(a => {
                    uHtml += `<div style="display:flex; justify-content:space-between; font-size:0.75rem; font-family:var(--font-mono);">
                        <span style="color:var(--text-secondary);">${a.name}</span>
                        <span style="color:var(--text-tertiary);">${a.symbol}</span>
                    </div>`;
                });
                
                uHtml += `</div></div>`;
            }
            univContainer.innerHTML = uHtml;
        }

    } catch (e) {
        console.error('Failed to init Strategy Lab:', e);
    }
}
'''

js += init_func

with open(r'd:\FIONA\google touzi\static\main.js', 'w', encoding='utf-8') as f:
    f.write(js)
