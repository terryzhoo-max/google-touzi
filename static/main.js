// main.js - Logic and Chart Initialization

document.addEventListener("DOMContentLoaded", () => {
    initDashboard();
    initERPChart();
    initSpreadChart();
    setTimeout(() => {
        initYieldCurve();
        initAllocationChart();
        initCorrelationChart();
        initMonteCarloChart();
        initEfficientFrontier();
        initScenarioTest();
        initBacktest();
        initTreemapChart('sector-chart', '/api/macro/sector_rotation', 'sr-indicator', 'sr-insight', '31行业已加载', 'default');
        initTreemapChart('theme-chart', '/api/macro/theme_rotation', 'tr-indicator', 'tr-insight', '政策主线已加载', 'purple');
        initTreemapChart('domestic-etf-chart', '/api/macro/domestic_etf', 'de-indicator', 'de-insight', 'A股宽基已加载', 'etf');
        initTreemapChart('global-etf-chart', '/api/macro/global_etf', 'ge-indicator', 'ge-insight', '全球宽基已加载', 'blue');
        initChinaMacro();
        initMarketBreadth();
        initFedProb();
        initGlobalAssets();
        initValuation();
    }, 500);
    initGenAI();
    initSignals();

    // Simple smooth scroll for nav links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            document.querySelector(this.getAttribute('href')).scrollIntoView({
                behavior: 'smooth'
            });
        });
    });


});

async function initDashboard() {
    try {
        const resp = await fetch('/api/macro/decision');
        const d = await resp.json();

        // ── signal ring ──
        const perc = d.score / 100;
        const arc = document.getElementById('signal-arc');
        if (arc) {
            const len = 327 * perc;
            arc.setAttribute('stroke-dasharray', `${len} ${327 - len}`);
            arc.setAttribute('stroke', d.color);
        }
        const st = document.getElementById('signal-text');
        if (st) { st.textContent = d.score; st.style.color = d.color; }
        const sl = document.getElementById('signal-label');
        if (sl) { sl.textContent = d.signal; sl.style.color = d.color; }

        // ── regime badge ──
        const rb = document.getElementById('regime-badge');
        if (rb) {
            const fac = d.factors.find(f => f.name === '当前象限');
            rb.textContent = fac ? fac.detail : '--';
            rb.style.background = d.color + '20';
            rb.style.color = d.color;
            rb.style.border = `1px solid ${d.color}40`;
        }
        const rd = document.getElementById('regime-detail');
        if (rd) {
            rd.textContent = d.factors.map(f => `${f.name}: ${f.score}`).join(' ｜ ');
        }

        // ── allocation bars ──
        const ab = document.getElementById('alloc-bars');
        if (ab) {
            const w = d.regime_alloc || { spy: 60, tlt: 30, gld: 10, cash: 0 };
            ab.innerHTML = `
                <div class="bar bar-spy" style="width:${w.spy}%"></div>
                <div class="bar bar-tlt" style="width:${w.tlt}%"></div>
                <div class="bar bar-gld" style="width:${w.gld}%"></div>
                <div class="bar bar-cash" style="width:${w.cash}%"></div>
            `;
        }
        const ad = document.getElementById('alloc-detail');
        if (ad) {
            const w = d.regime_alloc || { spy: 60, tlt: 30, gld: 10, cash: 0 };
            ad.textContent = `股 ${w.spy}% ｜ 债 ${w.tlt}% ｜ 金 ${w.gld}% ｜ 现 ${w.cash}%`;
        }

        // ── alert banner ──
        const banner = document.getElementById('alert-banner');
        const count = document.getElementById('alert-count');
        const list = document.getElementById('alert-list');
        if (banner && d.active_warnings && d.active_warnings.length > 0) {
            banner.style.display = 'block';
            banner.classList.add('has-warnings');
            if (count) count.textContent = d.active_warnings.length;
            if (list) list.innerHTML = d.active_warnings.map(a =>
                `<div class="alert-${a.level}">▸ ${a.text}</div>`
            ).join('');
            // badge on relevant panel groups
            const hasMacro = d.active_warnings.some(a => a.source === 'yield_curve');
            const hasRisk = d.active_warnings.some(a => a.source === 'correlation');
            const mBadge = document.getElementById('macro-alert-badge');
            const rBadge = document.getElementById('risk-alert-badge');
            if (mBadge) mBadge.style.display = hasMacro ? 'inline' : 'none';
            if (rBadge) rBadge.style.display = hasRisk ? 'inline' : 'none';
            // auto-expand groups with alerts
            if (hasMacro) {
                const g = document.querySelector('.panel-group:nth-of-type(1)');
                if (g) g.open = true;
            }
            if (hasRisk) {
                const g = document.querySelector('.panel-group:nth-of-type(2)');
                if (g) g.open = true;
            }
        } else if (banner) {
            banner.style.display = 'none';
        }

    } catch (e) {
        console.error('Dashboard failed:', e);
    }

    // data freshness
    try {
        const h = await fetch('/api/health');
        const hd = await h.json();
        const fi = document.getElementById('freshness-indicator');
        if (fi) {
            const degraded = hd.degraded_sources || [];
            const hitPct = Math.round((hd.cache?.hit_ratio || 0) * 100);
            if (degraded.length > 0) {
                fi.innerHTML = `⚠️ 数据源降级: ${degraded.join(', ')} | 缓存命中 ${hitPct}%`;
                fi.style.color = '#fbbf24';
            } else {
                fi.innerHTML = `● 数据正常 | 缓存命中 ${hitPct}% | 活跃警示 ${hd.active_alerts}`;
                fi.style.color = '#4ade80';
            }
        }
    } catch (e) {
        console.error('Health check failed:', e);
    }
}

// ── shared panel helper ──────────────────────────────────
function initPanel({url, indicatorId, insightId, onData, onError}) {
    fetch(url).then(r=>r.json()).then(d=>{
        if(d.error)throw new Error(d.error);
        onData(d);
    }).catch(e=>{
        console.error(url, e);
        if(onError)onError(e);
        const ind=document.getElementById(indicatorId);
        if(ind){ind.innerText='加载失败';ind.style.color='#ef4444';}
    });
}

// Common ECharts styling for dark theme
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

// Fetch real data from our FastAPI Quant Engine
async function fetchMacroData(endpoint) {
    try {
        // Now using relative path since backend and frontend are on the same server
        const response = await fetch(`/api/macro/${endpoint}`);
        if (!response.ok) throw new Error('Network response was not ok');
        return await response.json();
    } catch (error) {
        console.error('Failed to fetch data, falling back to cached view:', error);
        // Fallback robust data if backend is offline
        return {
            dates: ['01-01', '01-02', '01-03', '01-04', '01-05'],
            data: [5.1, 5.2, 5.0, 5.3, 5.4]
        };
    }
}

async function initERPChart() {
    const chartDom = document.getElementById('erp-chart');
    if (!chartDom) return;
    
    // Show a native loading spinner provided by ECharts
    const myChart = echarts.init(chartDom, 'dark');
    myChart.showLoading({ text: '加载核心模型数据...', color: '#00F0FF', textColor: '#fff', maskColor: 'rgba(20, 20, 25, 0.8)' });
    
    const macroData = await fetchMacroData('erp');
    myChart.hideLoading();

    // Dynamically update Quant Signals in DOM
    const ind = document.getElementById('tnx-indicator');
    const ins = document.getElementById('tnx-insight');
    if (ind && ins && macroData.signal_state) {
        ind.innerText = macroData.signal_state;
        ind.style.color = macroData.signal_color;
        ind.style.borderColor = macroData.signal_color;
        ind.style.boxShadow = `0 0 10px ${macroData.signal_color}40`;
        ins.innerText = macroData.action_insight;
    }
    
    const lineColor = macroData.signal_color || '#00F0FF';

    const option = {
        backgroundColor: 'transparent',
        color: [lineColor],
        tooltip: {
            trigger: 'axis',
            ...chartTheme.tooltip
        },
        grid: chartTheme.grid,
        xAxis: {
            type: 'category',
            boundaryGap: false,
            data: macroData.dates,
            axisLine: { lineStyle: { color: '#444' } },
            axisLabel: { color: '#9ca3af' }
        },
        yAxis: {
            type: 'value',
            min: 'dataMin',
            axisLine: { show: false },
            splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
            axisLabel: { color: '#9ca3af', formatter: '{value}%' }
        },
        series: [
            {
                name: '美国10Y国债',
                type: 'line',
                smooth: true,
                symbol: 'none',
                areaStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: lineColor + '80' },
                        { offset: 1, color: 'rgba(0, 0, 0, 0.0)' }
                    ])
                },
                lineStyle: { 
                    width: 3,
                    color: lineColor,
                    shadowColor: lineColor,
                    shadowBlur: 10
                },
                data: macroData.data,
                markLine: {
                    data: [{ type: 'average', name: '历史均值' }],
                    lineStyle: { color: '#fbbf24', type: 'dashed' },
                    label: { color: '#fbbf24', formatter: '均值' }
                }
            }
        ]
    };

    myChart.setOption(option);
    window.addEventListener('resize', () => myChart.resize());
}

function initSpreadChart() {
    const chartDom = document.getElementById('spread-chart');
    if (!chartDom) return;
    const myChart = echarts.init(chartDom, 'dark');
    myChart.showLoading({ text: '加载信用利差数据...', color: '#7000FF', textColor: '#fff', maskColor: 'rgba(20, 20, 25, 0.8)' });
    
    fetchMacroData('spread').then(macroData => {
        myChart.hideLoading();

        // Dynamically update Quant Signals in DOM
        const ind = document.getElementById('vix-indicator');
        const ins = document.getElementById('vix-insight');
        if (ind && ins && macroData.signal_state) {
            ind.innerText = macroData.signal_state;
            ind.style.color = macroData.signal_color;
            ind.style.borderColor = macroData.signal_color;
            ind.style.boxShadow = `0 0 10px ${macroData.signal_color}40`;
            ins.innerText = macroData.action_insight;
        }

        const lineColor = macroData.signal_color || '#7000FF';

        const option = {
            backgroundColor: 'transparent',
            color: [lineColor],
            tooltip: {
                trigger: 'axis',
                ...chartTheme.tooltip
            },
            grid: chartTheme.grid,
            xAxis: {
                type: 'category',
                boundaryGap: false,
                data: macroData.dates,
                axisLine: { lineStyle: { color: '#444' } },
                axisLabel: { color: '#9ca3af' }
            },
            yAxis: {
                type: 'value',
                min: 'dataMin',
                axisLine: { show: false },
                splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
                axisLabel: { color: '#9ca3af', formatter: '{value}' }
            },
            series: [
                {
                    name: 'VIX 波动率',
                    type: 'line',
                    smooth: true,
                    symbol: 'none',
                    areaStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: lineColor + '80' },
                            { offset: 1, color: 'rgba(0, 0, 0, 0.0)' }
                        ])
                    },
                    lineStyle: { 
                        width: 3,
                        color: lineColor,
                        shadowColor: lineColor,
                        shadowBlur: 10
                    },
                    data: macroData.data
                }
            ]
        };

        myChart.setOption(option);
    });
    
    window.addEventListener('resize', () => myChart.resize());
}

async function initSignals() {
    try {
        const resp = await fetch('/api/macro/signals');
        const data = await resp.json();
        if (data.error) return;

        const containers = { tnx: 'tnx-insight', vix: 'vix-insight' };
        for (const [key, elId] of Object.entries(containers)) {
            const el = document.getElementById(elId);
            if (!el || !data[key]) continue;
            const dots = data[key].map(s =>
                `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${s.color};margin:0 2px;" title="${s.label}: ${s.signal} (z=${s.zscore})"></span>`
            ).join('');
            el.innerHTML = el.innerHTML + '<br/><span style="font-size:0.75rem;color:#64748b;">' +
                data[key].map(s => `${s.label} ${s.signal}`).join(' | ') + '</span>';
        }
    } catch (e) {
        console.error("Signals failed:", e);
    }
}

async function initYieldCurve() {
    const chartDom = document.getElementById('yieldcurve-chart');
    if (!chartDom) return;
    const myChart = echarts.init(chartDom, 'dark');
    myChart.showLoading({ text: '拉取期限结构...', color: '#fbbf24', textColor: '#fff', maskColor: 'rgba(20, 20, 25, 0.8)' });

    try {
        const resp = await fetch('/api/macro/yield_curve');
        const data = await resp.json();
        myChart.hideLoading();

        const ind = document.getElementById('yc-indicator');
        const ins = document.getElementById('yc-insight');
        if (ind && ins) {
            ind.innerText = data.signal_state;
            ind.style.color = data.signal_color;
            ind.style.borderColor = data.signal_color;
            ind.style.boxShadow = `0 0 10px ${data.signal_color}40`;
            ins.innerText = data.insight;
        }

        const option = {
            backgroundColor: 'transparent',
            tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
            legend: { data: ['利差 (bp)', '零轴'], textStyle: { color: '#94a3b8' }, top: 0 },
            grid: { left: '3%', right: '4%', top: '18%', bottom: '3%', containLabel: true },
            xAxis: {
                type: 'category', boundaryGap: false,
                data: data.spread_dates,
                axisLabel: { color: '#94a3b8' },
            },
            yAxis: {
                type: 'value',
                name: 'bp',
                splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
                axisLabel: { color: '#94a3b8' },
            },
            series: [
                {
                    name: '利差 (bp)', type: 'line', smooth: true,
                    symbol: 'none', lineStyle: { width: 2, color: '#fbbf24' },
                    areaStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: 'rgba(251,191,36,0.3)' },
                            { offset: 1, color: 'rgba(0,0,0,0)' }
                        ])
                    },
                    data: data.spread_values,
                    markArea: {
                        silent: true,
                        data: [[{ yAxis: -200, itemStyle: { color: 'rgba(239,68,68,0.08)' } }, { yAxis: 0 }]]
                    }
                },
                {
                    name: '零轴', type: 'line',
                    symbol: 'none',
                    lineStyle: { width: 1, color: '#ef4444', type: 'dashed' },
                    data: data.spread_values.map(() => 0),
                }
            ]
        };
        myChart.setOption(option);
        window.addEventListener('resize', () => myChart.resize());
    } catch (e) {
        myChart.hideLoading();
        console.error("Yield curve failed:", e);
    }
}

async function initAllocationChart() {
    const chartDom = document.getElementById('allocation-chart');
    if (!chartDom) return;
    chartDom.innerHTML = '';
    const myChart = echarts.init(chartDom, 'dark');
    myChart.showLoading({ text: '量化沙盘推演中...', color: '#4ade80', textColor: '#fff', maskColor: 'rgba(20, 20, 25, 0.8)' });
    
    try {
        const response = await fetch('/api/macro/allocation');
        const allocData = await response.json();
        myChart.hideLoading();

        const ind = document.getElementById('alloc-indicator');
        const ins = document.getElementById('alloc-insight');
        if (ind && ins) {
            ind.innerText = allocData.regime;
            ind.style.color = '#4ade80';
            ind.style.borderColor = '#4ade80';
            ind.style.boxShadow = `0 0 10px rgba(74, 222, 128, 0.4)`;
            ins.innerText = `当前宏观锚点: VIX=${allocData.vix_ref} | 10Y=${allocData.tnx_ref}% | DXY=${allocData.dxy_ref}。引擎已自动输出当前宏观状态下的极简持仓比例。`;
        }

        const option = {
            backgroundColor: 'transparent',
            color: ['#00F0FF', '#7000FF', '#4ade80', '#fbbf24', '#ef4444'],
            tooltip: { 
                trigger: 'item',
                backgroundColor: 'rgba(20, 20, 25, 0.95)',
                borderColor: 'rgba(255,255,255,0.1)',
                textStyle: { color: '#f0f0f0' },
                formatter: function (params) {
                    const data = params.data;
                    return `
                        <div style="max-width: 300px; white-space: normal; padding: 5px;">
                            <div style="font-weight: bold; font-size: 1.1rem; color: ${params.color}; margin-bottom: 5px;">
                                ${data.icon} ${data.name} : ${data.value}%
                            </div>
                            <div style="font-size: 0.85rem; color: #94a3b8; line-height: 1.4;">
                                ${data.strategy}
                            </div>
                        </div>
                    `;
                }
            },
            legend: { 
                top: '5%', 
                left: 'center', 
                textStyle: { color: '#9ca3af' } 
            },
            series: [
                {
                    name: '资产配置建议',
                    type: 'pie',
                    radius: ['40%', '70%'],
                    avoidLabelOverlap: false,
                    itemStyle: {
                        borderRadius: 10,
                        borderColor: '#141419',
                        borderWidth: 2
                    },
                    label: { show: false, position: 'center' },
                    emphasis: {
                        label: { show: true, fontSize: 20, fontWeight: 'bold', color: '#fff', formatter: '{b}\n\n{c}%' }
                    },
                    labelLine: { show: false },
                    data: allocData.allocation
                }
            ]
        };
        myChart.setOption(option);
        window.addEventListener('resize', () => myChart.resize());
    } catch (e) {
        myChart.hideLoading();
        console.error("Allocation sandbox failed:", e);
    }
}

async function initCorrelationChart() {
    const chartDom = document.getElementById('correlation-chart');
    if (!chartDom) return;
    const myChart = echarts.init(chartDom, 'dark');
    myChart.showLoading({ text: '风险矩阵演算中...', color: '#ef4444', textColor: '#fff', maskColor: 'rgba(20, 20, 25, 0.8)' });
    
    try {
        const response = await fetch('/api/macro/correlation');
        const corrData = await response.json();
        myChart.hideLoading();

        if (corrData.error) throw new Error(corrData.error);

        const ind = document.getElementById('corr-indicator');
        const ins = document.getElementById('corr-insight');
        const banner = document.getElementById('corr-action-banner');
        const actionText = document.getElementById('corr-extreme-action');
        
        if (ind && ins) {
            ind.innerText = corrData.state;
            ind.style.color = corrData.color;
            ind.style.borderColor = corrData.color;
            ind.style.boxShadow = `0 0 10px ${corrData.color}40`;
            ins.innerHTML = corrData.insight;
        }

        if (corrData.extreme_action && banner && actionText) {
            banner.style.display = 'block';
            actionText.innerText = corrData.extreme_action;
        } else if (banner) {
            banner.style.display = 'none';
        }

        const option = {
            backgroundColor: 'transparent',
            tooltip: {
                position: 'top',
                formatter: function (params) {
                    return `${corrData.assets[params.value[1]]} vs ${corrData.assets[params.value[0]]}: <br/><b>${params.value[2]}</b>`;
                }
            },
            grid: {
                height: '70%',
                top: '10%'
            },
            xAxis: {
                type: 'category',
                data: corrData.assets,
                splitArea: { show: true, areaStyle: { color: ['rgba(255,255,255,0.02)', 'rgba(255,255,255,0.05)'] } },
                axisLabel: { color: '#9ca3af' },
                axisLine: { lineStyle: { color: '#444' } }
            },
            yAxis: {
                type: 'category',
                data: corrData.assets,
                splitArea: { show: true, areaStyle: { color: ['rgba(255,255,255,0.02)', 'rgba(255,255,255,0.05)'] } },
                axisLabel: { color: '#9ca3af' },
                axisLine: { lineStyle: { color: '#444' } }
            },
            visualMap: {
                min: -1,
                max: 1,
                calculable: true,
                orient: 'horizontal',
                left: 'center',
                bottom: '0%',
                inRange: {
                    color: ['#00F0FF', '#141419', '#ef4444'] // Cyan to Dark to Red
                },
                textStyle: { color: '#9ca3af' }
            },
            series: [{
                name: 'Pearson Correlation',
                type: 'heatmap',
                data: corrData.matrix,
                label: {
                    show: true,
                    color: '#fff',
                    formatter: function(p){ return p.value[2].toFixed(2); }
                },
                itemStyle: {
                    borderColor: '#141419',
                    borderWidth: 2
                }
            }]
        };
        myChart.setOption(option);
        window.addEventListener('resize', () => myChart.resize());
    } catch (e) {
        myChart.hideLoading();
        console.error("Correlation matrix failed:", e);
    }
}

async function initEfficientFrontier() {
    const chartDom = document.getElementById('frontier-chart');
    if (!chartDom) return;
    const myChart = echarts.init(chartDom, 'dark');
    myChart.showLoading({ text: '优化计算中...', color: '#7000FF', textColor: '#fff', maskColor: 'rgba(20, 20, 25, 0.8)' });

    try {
        const resp = await fetch('/api/macro/efficient_frontier');
        const data = await resp.json();
        myChart.hideLoading();
        if (data.error) throw new Error(data.error);

        const ind = document.getElementById('ef-indicator');
        const ins = document.getElementById('ef-insight');
        if (ind) { ind.innerText = '前沿计算完成'; ind.style.color = '#a78bfa'; ind.style.borderColor = '#a78bfa'; }
        if (ins) ins.innerText = data.insight;

        const option = {
            backgroundColor: 'transparent',
            tooltip: { trigger: 'item', formatter: p => `${p.seriesName}<br/>收益: ${p.value[0]}%  |  波动: ${p.value[1]}%` },
            grid: { left: '8%', right: '5%', top: '5%', bottom: '8%' },
            xAxis: { name: '年化波动率 (%)', nameTextStyle: { color: '#94a3b8' }, axisLabel: { color: '#94a3b8', formatter: '{value}%' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
            yAxis: { name: '年化收益率 (%)', nameTextStyle: { color: '#94a3b8' }, axisLabel: { color: '#94a3b8', formatter: '{value}%' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
            series: [
                {
                    name: '随机组合', type: 'scatter',
                    symbolSize: 4,
                    itemStyle: { color: 'rgba(148,163,184,0.3)' },
                    data: data.random_portfolios.map(p => [p.ret, p.vol]),
                },
                {
                    name: 'GMV', type: 'scatter',
                    symbolSize: 16, symbol: 'diamond',
                    itemStyle: { color: '#fbbf24' },
                    data: [[data.gmv.ret, data.gmv.vol]],
                    label: { show: true, formatter: 'GMV', position: 'top', color: '#fbbf24', fontSize: 12 },
                },
                {
                    name: '切线组合', type: 'scatter',
                    symbolSize: 16, symbol: 'triangle',
                    itemStyle: { color: '#4ade80' },
                    data: [[data.tangency.ret, data.tangency.vol]],
                    label: { show: true, formatter: '最优夏普', position: 'top', color: '#4ade80', fontSize: 12 },
                },
                {
                    name: 'AlphaCore', type: 'scatter',
                    symbolSize: 20, symbol: 'pin',
                    itemStyle: { color: '#00F0FF' },
                    data: [[data.alphacore.ret, data.alphacore.vol]],
                    label: { show: true, formatter: 'AlphaCore', position: 'right', color: '#00F0FF', fontSize: 13, fontWeight: 'bold' },
                }
            ]
        };
        myChart.setOption(option);
        window.addEventListener('resize', () => myChart.resize());
    } catch (e) {
        myChart.hideLoading();
        console.error("Efficient frontier failed:", e);
    }
}

async function initScenarioTest() {
    const grid = document.getElementById('scenario-grid');
    const ind = document.getElementById('sc-indicator');
    const ins = document.getElementById('sc-insight');
    if (!grid || !ind) return;

    try {
        const resp = await fetch('/api/macro/scenario');
        const data = await resp.json();

        ind.innerText = '三情景穿透完成';
        ind.style.color = '#fbbf24';
        ind.style.borderColor = '#fbbf24';
        if (ins) ins.innerText = data.insight;

        grid.innerHTML = data.scenarios.map(s => {
            const isWin = s.port_ret > s.bench_ret;
            const beat = (s.port_ret - s.bench_ret).toFixed(1);
            return `
                <div style="background: rgba(255,255,255,0.02); border: 1px solid ${s.color}40; border-radius: 8px; padding: 16px; display: flex; flex-direction: column; gap: 10px;">
                    <div style="font-size: 0.95rem; font-weight: bold; color: #e2e8f0;">${s.name}</div>
                    <div style="font-size: 0.7rem; color: #94a3b8;">${s.period}</div>
                    <div style="font-size: 0.75rem; color: #64748b; line-height: 1.5;">${s.desc}</div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 5px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.05);">
                        <div>
                            <div style="font-size: 0.65rem; color: #94a3b8;">策略收益</div>
                            <div style="font-family: var(--font-mono); font-size: 1.2rem; font-weight: bold; color: ${s.color};">${s.port_ret}%</div>
                        </div>
                        <div>
                            <div style="font-size: 0.65rem; color: #94a3b8;">基准收益</div>
                            <div style="font-family: var(--font-mono); font-size: 1.2rem; font-weight: bold; color: #ef4444;">${s.bench_ret}%</div>
                        </div>
                    </div>
                    <div style="font-size: 0.7rem; color: ${isWin ? '#4ade80' : '#ef4444'}; font-weight: 600;">
                        策略${isWin ? '领先' : '落后'}基准 ${isWin ? '+' : ''}${beat}%
                    </div>
                    <div style="font-size: 0.7rem; padding: 3px 8px; background: ${s.color}20; border-radius: 4px; color: ${s.color}; align-self: flex-start;">
                        ${s.verdict}
                    </div>
                </div>
            `;
        }).join('');

    } catch (e) {
        console.error("Scenario test failed:", e);
        ind.innerText = '推演失败';
        ind.style.color = '#ef4444';
    }
}

async function initMonteCarloChart() {
    const chartDom = document.getElementById('mc-chart');
    if (!chartDom) return;
    const myChart = echarts.init(chartDom, 'dark');
    myChart.showLoading({ text: '千次平行宇宙演算中...', color: '#00F0FF', textColor: '#fff', maskColor: 'rgba(20, 20, 25, 0.8)' });
    
    try {
        const response = await fetch('/api/macro/montecarlo');
        const mcData = await response.json();
        myChart.hideLoading();

        if (mcData.error) throw new Error(mcData.error);

        const ind = document.getElementById('mc-indicator');
        const ins = document.getElementById('mc-insight');
        if (ind && ins) {
            ind.innerText = "推演完成 (1000 Paths)";
            ind.style.color = mcData.color;
            ind.style.borderColor = mcData.color;
            ind.style.boxShadow = `0 0 10px ${mcData.color}40`;
            ins.innerText = mcData.insight;
        }

        const option = {
            backgroundColor: 'transparent',
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'cross', lineStyle: { color: '#444' } },
                backgroundColor: 'rgba(20, 20, 25, 0.9)',
                borderColor: 'rgba(255,255,255,0.1)',
                textStyle: { color: '#f0f0f0' }
            },
            legend: { top: '0%', textStyle: { color: '#9ca3af' } },
            grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
            xAxis: {
                type: 'category',
                boundaryGap: false,
                data: mcData.dates,
                axisLabel: { color: '#9ca3af' }
            },
            yAxis: {
                type: 'value',
                min: 'dataMin',
                splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
                axisLabel: { color: '#9ca3af', formatter: '{value}' }
            },
            series: [
                {
                    name: '极寒底线 (VaR P5)',
                    type: 'line',
                    smooth: true,
                    symbol: 'none',
                    lineStyle: { width: 1, color: '#ef4444' },
                    areaStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: 'rgba(239, 68, 68, 0.3)' },
                            { offset: 1, color: 'rgba(239, 68, 68, 0.0)' }
                        ])
                    },
                    data: mcData.p5
                },
                {
                    name: '乐观极限 (P95)',
                    type: 'line',
                    smooth: true,
                    symbol: 'none',
                    lineStyle: { width: 1, color: '#4ade80' },
                    data: mcData.p95
                },
                {
                    name: '中位数预期 (P50)',
                    type: 'line',
                    smooth: true,
                    symbol: 'none',
                    lineStyle: { width: 3, color: '#00F0FF', shadowColor: '#00F0FF', shadowBlur: 10 },
                    data: mcData.p50
                }
            ]
        };
        myChart.setOption(option);
        window.addEventListener('resize', () => myChart.resize());
    } catch (e) {
        myChart.hideLoading();
        console.error("Monte Carlo simulation failed:", e);
    }
}

async function initTreemapChart(domId, apiUrl, indId, insId, successText, colorTheme) {
    const cd = document.getElementById(domId);
    if (!cd) return;
    const mc = echarts.init(cd, 'dark');
    mc.showLoading({text:'引擎演算中...',color:'#fbbf24',textColor:'#fff',maskColor:'rgba(20,20,25,0.8)'});
    try {
        const r = await fetch(apiUrl);
        const d = await r.json();
        mc.hideLoading();
        if (d.error) throw new Error(d.error);
        const si = document.getElementById(indId);
        const sn = document.getElementById(insId);
        if(si){si.innerText = successText; si.style.color='#fbbf24'; si.style.borderColor='#fbbf24';}
        if(sn)sn.innerText=d.insight;
        
        // Define color gradient base based on theme
        let posColorBase = [0, 80, 80]; // default green
        let negColorBase = [80, 30, 30]; // default red
        
        if (colorTheme === 'blue') {
            posColorBase = [0, 80, 160]; // tech blue
            negColorBase = [120, 60, 0]; // orange/brown
        } else if (colorTheme === 'purple') {
            posColorBase = [80, 0, 160]; // purple
            negColorBase = [120, 120, 0]; // yellow/olive
        }

        mc.setOption({
            backgroundColor:'transparent',
            tooltip:{formatter:p=>`${p.name}<br/>5日 ${p.data.ret_5d}% | 20日 ${p.data.ret_20d}% | 60日 ${p.data.ret_60d}%`},
            series:[{type:'treemap',roam:false,width:'96%',height:'85%',breadcrumb:{show:false},
                label:{show:true,formatter:p=>`${p.name}\n${p.data.ret_20d>0?'+':''}${p.data.ret_20d}%`,fontSize:10,color:'#e2e8f0'},
                data:d.sectors.map(s=> {
                    let intensity = Math.min(175, Math.abs(s.ret_20d)*30);
                    let colorStr = s.ret_20d >= 0 
                        ? `rgb(${posColorBase[0]},${posColorBase[1]+intensity},${posColorBase[2]})`
                        : `rgb(${negColorBase[0]+intensity},${negColorBase[1]},${negColorBase[2]})`;
                    
                    // Specific override for domestic/global ETF to keep classic red/green mapping
                    if (colorTheme === 'etf') {
                        colorStr = s.ret_20d >= 0 
                            ? `rgb(30,${80+intensity},30)` // Green up
                            : `rgb(${80+intensity},30,30)`; // Red down
                    }

                    return {
                        name:s.name, value:s.value, ret_5d:s.ret_5d, ret_20d:s.ret_20d, ret_60d:s.ret_60d,
                        itemStyle:{color: colorStr}
                    };
                })
            }]
        });
        window.addEventListener('resize',()=>mc.resize());
    }catch(e){mc.hideLoading();console.error(domId + ' failed:',e);}
}

async function initChinaMacro() {
    const gd = document.getElementById('china-macro-grid');
    if (!gd) return;
    try {
        const r = await fetch('/api/macro/china_macro');
        const d = await r.json();
        const labels={cpi:'CPI 同比(%)',pmi:'PMI 制造业',m2:'M2 同比(%)',gdp:'GDP 增速(%)'};
        gd.innerHTML = Object.entries(labels).map(([k,lb]) => {
            const v = d[k];
            if (!v) return '<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:6px;padding:14px;text-align:center;"><div style="color:#64748b;font-size:0.7rem;">'+lb+'</div><div style="color:#94a3b8;">无数据</div></div>';
            let chartId = 'cm-chart-'+k;
            setTimeout(()=>{
                const el=document.getElementById(chartId);if(!el)return;
                const mc=echarts.init(el,'dark');
                mc.setOption({backgroundColor:'transparent',grid:{left:0,right:0,top:5,bottom:0},xAxis:{show:false,data:v.dates},yAxis:{show:false,min:'dataMin',max:'dataMax'},
                    series:[{type:'line',data:v.values,smooth:true,symbol:'none',lineStyle:{width:2,color:v.color},
                        areaStyle:{color:new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:v.color+'60'},{offset:1,color:'rgba(0,0,0,0)'}])}}]});
            },100);
            return `<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:6px;padding:14px;text-align:center;">
                <div style="color:#64748b;font-size:0.7rem;margin-bottom:4px;">${lb}</div>
                <div style="font-size:1.4rem;font-weight:700;color:${v.color};font-family:var(--font-mono);">${v.current}%</div>
                <div style="font-size:0.7rem;color:${v.color};margin-top:2px;">${v.signal}</div>
                <div id="${chartId}" style="height:80px;margin-top:6px;"></div>
            </div>`;
        }).join('');
        document.getElementById('cm-indicator').innerText='已更新 '+d.updated;
        document.getElementById('cm-insight').innerText=`CPI ${d.cpi?.current}% (${d.cpi?.signal}) | PMI ${d.pmi?.current} (${d.pmi?.signal}) | M2 ${d.m2?.current}% (${d.m2?.signal}) | GDP ${d.gdp?.current}% (${d.gdp?.signal})`;
    }catch(e){console.error('China macro:',e);}
}

async function initMarketBreadth() {
    const cd = document.getElementById('breadth-chart');
    if (!cd) return;
    const mc = echarts.init(cd, 'dark');
    try {
        const r = await fetch('/api/macro/market_breadth');
        const d = await r.json();
        document.getElementById('mb-indicator').innerText=`涨停${d.today.up}/跌停${d.today.down}`;
        document.getElementById('mb-insight').innerText=d.insight;
        mc.setOption({
            backgroundColor:'transparent',
            tooltip:{trigger:'axis'},
            legend:{data:['AD Line','涨跌比(%)'],textStyle:{color:'#94a3b8'},top:0},
            grid:{left:'3%',right:'4%',top:'15%',bottom:'3%',containLabel:true},
            xAxis:{type:'category',data:d.ad_line.map(v=>v.date),axisLabel:{color:'#94a3b8'}},
            yAxis:[{type:'value',name:'AD Line',splitLine:{lineStyle:{color:'rgba(255,255,255,0.05)'}},axisLabel:{color:'#94a3b8'}},
                   {type:'value',name:'%',axisLabel:{color:'#94a3b8'}}],
            series:[
                {name:'AD Line',type:'line',data:d.ad_line.map(v=>v.value),smooth:true,symbol:'none',lineStyle:{width:2,color:'#00F0FF'}},
                {name:'涨跌比(%)',type:'bar',yAxisIndex:1,data:d.ad_ratio.map(v=>({value:v.value,itemStyle:{color:v.value>=0?'#4ade80':'#ef4444'}}))},
            ]
        });
        window.addEventListener('resize',()=>mc.resize());
    }catch(e){console.error('Market breadth:',e);}
}

async function initFedProb() {
    const cd=document.getElementById('fed-chart'); if(!cd)return;
    const mc=echarts.init(cd,'dark');
    try{
        const r=await fetch('/api/macro/fed_prob'); const d=await r.json();
        document.getElementById('fed-indicator').innerText=d.signal;
        document.getElementById('fed-insight').innerText=d.insight;
        mc.setOption({
            backgroundColor:'transparent',
            tooltip:{trigger:'axis'},grid:{left:'3%',right:'4%',top:'5%',bottom:'3%',containLabel:true},
            xAxis:{type:'category',data:d.rate_path.map(v=>v.date),axisLabel:{color:'#94a3b8',formatter:v=>v.slice(0,7)}},
            yAxis:{type:'value',name:'%',axisLabel:{color:'#94a3b8'}},
            series:[{name:'联邦基金利率',type:'line',data:d.rate_path.map(v=>v.rate),smooth:true,symbol:'none',
                lineStyle:{width:2,color:'#fbbf24'},
                areaStyle:{color:new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:'rgba(251,191,36,0.3)'},{offset:1,color:'rgba(0,0,0,0)'}])},
                markLine:{silent:true,lineStyle:{color:'#ef4444',type:'dashed'},label:{formatter:'FOMC'},data:d.fomc_upcoming.map(v=>({xAxis:v}))}
            }]
        });
        window.addEventListener('resize',()=>mc.resize());
    }catch(e){console.error('Fed prob:',e);}
}

async function initGlobalAssets() {
    const el=document.getElementById('global-assets-table'); if(!el)return;
    try{
        const r=await fetch('/api/macro/global_assets'); const d=await r.json();
        document.getElementById('ga-indicator').innerText='已更新 '+d.updated;
        const cats=[...new Set(d.assets.map(a=>a.cat))];
        const cols=['daily','weekly','monthly','quarterly','ytd'];
        const headers=['资产','类别','日涨跌','周涨跌','月涨跌','季涨跌','YTD'];
        el.innerHTML=`<table style="width:100%;border-collapse:collapse;"><thead><tr style="border-bottom:1px solid rgba(255,255,255,0.08);color:#64748b;font-size:0.7rem;">${headers.map(h=>`<th style="padding:6px 10px;text-align:right;">${h}</th>`).join('')}</tr></thead><tbody>`+
            d.assets.map(a=>`<tr style="border-bottom:1px solid rgba(255,255,255,0.03);">
                <td style="padding:6px 10px;text-align:left;color:#e2e8f0;font-weight:500;">${a.name}</td>
                <td style="padding:6px 10px;text-align:right;color:#64748b;font-size:0.7rem;">${a.cat}</td>
                ${cols.map(k=>`<td style="padding:6px 10px;text-align:right;font-family:var(--font-mono);font-weight:600;color:${a[k]>=0?'#4ade80':'#ef4444'};">${a[k]>0?'+':''}${a[k]}%</td>`).join('')}
            </tr>`).join('')+'</tbody></table>';
    }catch(e){console.error('Global assets:',e);}
}

async function initValuation() {
    const gd=document.getElementById('valuation-grid'); if(!gd)return;
    try{
        const r=await fetch('/api/macro/valuation'); const d=await r.json();
        document.getElementById('val-indicator').innerText='已更新 '+d.updated;
        document.getElementById('val-insight').innerText=d.insight;
        gd.innerHTML=d.indices.map(i=>{
            const pct=i.pe_pct; const barW=Math.max(2,pct);
            return `<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:8px;padding:16px;">
                <div style="font-weight:bold;color:#e2e8f0;font-size:0.95rem;margin-bottom:12px;">${i.name}</div>
                <div style="display:flex;justify-content:space-between;font-size:0.75rem;color:#94a3b8;margin-bottom:4px;"><span>PE ${i.pe_current}</span><span>分位 ${pct}% ${i.pe_signal}</span></div>
                <div style="height:10px;background:rgba(255,255,255,0.05);border-radius:5px;overflow:hidden;margin-bottom:12px;">
                    <div style="width:${barW}%;height:100%;background:${i.color};border-radius:5px;transition:width 0.6s;"></div>
                </div>
                <div style="display:flex;justify-content:space-between;font-size:0.75rem;color:#94a3b8;margin-bottom:4px;"><span>PB ${i.pb_current}</span><span>分位 ${i.pb_pct}% ${i.pb_signal}</span></div>
                <div style="height:6px;background:rgba(255,255,255,0.05);border-radius:3px;overflow:hidden;">
                    <div style="width:${Math.max(2,i.pb_pct)}%;height:100%;background:${i.color};border-radius:3px;transition:width 0.6s;"></div>
                </div>
            </div>`;
        }).join('');
    }catch(e){console.error('Valuation:',e);}
}

async function initGenAI() {
    const tw = document.getElementById('ai-text');
    const ind = document.getElementById('ai-indicator');
    if (!tw || !ind) return;

    try {
        const response = await fetch('/api/macro/ai_insight');
        const data = await response.json();
        
        ind.innerText = "DeepSeek 官方智算中心推演完成";
        ind.style.color = "#7000FF";
        ind.style.borderColor = "#7000FF";
        ind.style.boxShadow = `0 0 10px rgba(112, 0, 255, 0.4)`;
        
        // Phase 23: Markdown Parsing & HTML Injection
        let parsedHTML = window.marked ? marked.parse(data.insight) : data.insight;
        
        // Highlight critical keywords dynamically
        parsedHTML = parsedHTML
            .replace(/(清仓|风险|平仓|双杀|警告)/g, '<span style="color: #ef4444; font-weight: bold;">$1</span>')
            .replace(/(做多|看涨|买入|正收益)/g, '<span style="color: #4ade80; font-weight: bold;">$1</span>')
            .replace(/(VIX|10Y|DXY|SPY|TLT)/g, '<span style="color: #00F0FF; font-family: var(--font-mono);">$1</span>');
        
        tw.innerHTML = parsedHTML;
        tw.style.opacity = 0;
        tw.style.animation = "fadeIn 1s forwards";
        
    } catch (e) {
        console.error("Gen-AI failed:", e);
        tw.innerText = "大模型连接超时，请检查网络或 API Key。";
        ind.innerText = "推演失败";
        ind.style.color = "#ef4444";
    }
}

// ==========================================
// Phase 25: Backtest Engine Integration
// ==========================================
async function initBacktest() {
    const chartDom = document.getElementById('backtest-chart');
    const ind = document.getElementById('bt-indicator');
    if (!chartDom || !ind) return;
    
    let myChart = echarts.init(chartDom);
    
    try {
        const response = await fetch('/api/macro/backtest');
        const data = await response.json();
        
        if (data.error) throw new Error(data.error);
        
        // Render Live Signal Banner
        if (data.current_state) {
            const state = data.current_state;
            const banner = document.getElementById('live-signal-banner');
            const dateSpan = document.getElementById('signal-date');
            const regimeSpan = document.getElementById('signal-regime');
            const weightsSpan = document.getElementById('signal-weights');
            
            if (banner && dateSpan && regimeSpan && weightsSpan) {
                banner.style.display = 'flex';
                dateSpan.innerText = state.date;
                regimeSpan.innerText = state.regime;
                regimeSpan.style.color = state.regime_color;
                weightsSpan.innerText = `股 ${state.w_spy}% | 债 ${state.w_tlt}% | 金 ${state.w_gld}% | 现金 ${state.w_cash}%`;
                
                banner.style.borderColor = state.regime_color + '40';
                banner.style.backgroundColor = state.regime_color + '05';
            }
            
            // Render detailed asset strategies
            if (state.asset_strategies && state.asset_strategies.length > 0) {
                const grid = document.getElementById('asset-strategies-grid');
                if (grid) {
                    grid.style.display = 'grid';
                    grid.innerHTML = state.asset_strategies.map(s => `
                        <div style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); border-radius: 6px; padding: 12px; display: flex; flex-direction: column; gap: 8px;">
                            <div style="display: flex; justify-content: space-between; align-items: center; font-family: var(--font-mono);">
                                <span style="font-size: 0.95rem; color: #e2e8f0; font-weight: bold;">${s.icon} ${s.asset}</span>
                                <span style="font-size: 1.1rem; color: ${s.weight > 0 ? '#4ade80' : '#ef4444'}; font-weight: bold;">${s.weight}%</span>
                            </div>
                            <div style="font-size: 0.8rem; color: #94a3b8; line-height: 1.4;">${s.strategy}</div>
                        </div>
                    `).join('');
                }
            }
        }
        
        // Update Metrics
        document.getElementById('bt-cagr').innerText = data.metrics.strat_cagr + "%";
        document.getElementById('bt-mdd').innerText = data.metrics.strat_mdd + "%";
        document.getElementById('bt-sharpe').innerText = data.metrics.strat_sharpe;
        
        ind.innerText = "18 年全量回测已完成";
        ind.className = "status-indicator live";
        
        const option = {
            backgroundColor: 'transparent',
            tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
            legend: { 
                data: ['AlphaCore 对冲策略', 'Benchmark (SPY)'], 
                textStyle: { color: '#94a3b8' },
                top: 0
            },
            grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
            xAxis: {
                type: 'category',
                boundaryGap: false,
                data: data.dates,
                axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
                axisLabel: { color: '#94a3b8' }
            },
            yAxis: {
                type: 'value',
                scale: true,
                axisLine: { show: false },
                splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
                axisLabel: { color: '#94a3b8', formatter: '{value}' }
            },
            series: [
                {
                    name: 'AlphaCore 对冲策略',
                    type: 'line',
                    data: data.strat_eq,
                    itemStyle: { color: '#00F0FF' },
                    lineStyle: { width: 2 },
                    showSymbol: false
                },
                {
                    name: 'Benchmark (SPY)',
                    type: 'line',
                    data: data.bench_eq,
                    itemStyle: { color: '#ef4444' },
                    lineStyle: { width: 2, type: 'dashed' },
                    showSymbol: false
                }
            ]
        };
        myChart.setOption(option);
        
        // Render TradingView Signal Chart
        const signalDom = document.getElementById('signal-chart');
        if (signalDom) {
            signalDom.innerHTML = ""; // Clear skeleton
            const chart = LightweightCharts.createChart(signalDom, {
                layout: {
                    background: { type: 'solid', color: 'transparent' },
                    textColor: '#94a3b8',
                },
                grid: {
                    vertLines: { color: 'rgba(255, 255, 255, 0.05)' },
                    horzLines: { color: 'rgba(255, 255, 255, 0.05)' },
                },
                crosshair: {
                    mode: LightweightCharts.CrosshairMode.Normal,
                },
                rightPriceScale: {
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                },
                timeScale: {
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    timeVisible: true,
                },
            });

            const lineSeries = chart.addLineSeries({
                color: '#3b82f6',
                lineWidth: 2,
                crosshairMarkerVisible: true,
                crosshairMarkerRadius: 4,
            });

            const tvData = data.dates.map((d, i) => ({
                time: d,
                value: data.spy_close[i]
            }));
            
            lineSeries.setData(tvData);
            
            // Set Markers
            if (data.signals && data.signals.length > 0) {
                lineSeries.setMarkers(data.signals);
            }
            
            chart.timeScale().fitContent();
        }
        
    } catch (e) {
        console.error("Backtest failed:", e);
        ind.innerText = "时序数据拉取失败";
        ind.style.color = "#ef4444";
        chartDom.innerHTML = "<div style='color:#ef4444; padding:20px;'>本地时序数据库连接失败。</div>";
    }
}
