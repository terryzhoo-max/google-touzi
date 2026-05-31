// strategy.js - AlphaCore focused panel module.
const STRATEGY_ENGINE_NAME_MAP = {
    global_risk_parity: '全球宏观风险平价',
    barbell_allocation: '核心-卫星哑铃配置',
    absolute_momentum: '跨市场绝对动量防线',
    beta_hedging: '动态贝塔中性化对冲',
    gold_hedging: '黄金避险择时引擎'
};

const STRATEGY_SYMBOL_NAME_MAP = {
    '510300.SH': '沪深300ETF',
    '159601.SZ': 'A50ETF',
    '510880.SH': '红利ETF',
    '513500.SH': '标普500ETF',
    '513100.SH': '纳指100ETF',
    '513520.SH': '日经225ETF',
    '512760.SH': '芯片ETF',
    '159819.SZ': '人工智能ETF',
    '159825.SZ': '农业机械ETF',
    '512660.SH': '军工ETF',
    '518880.SH': '黄金ETF'
};

const STRATEGY_CATEGORY_MAP = {
    A_SHARE_BROAD: 'A股宽基底仓',
    OVERSEAS_BROAD: '海外宽基配置',
    '15TH_FYP_THEME': '十五五政策主题',
    ALTERNATIVE_HEDGE: '另类避险资产'
};

function hasStrategyBacktestSeries(backtest) {
    return Boolean(
        backtest &&
        !backtest.error &&
        backtest.metrics &&
        Array.isArray(backtest.dates) &&
        Array.isArray(backtest.strategy_returns) &&
        Array.isArray(backtest.benchmark_returns) &&
        backtest.dates.length > 0
    );
}

function safeStrategyColor(value, fallback) {
    const color = String(value || '');
    return /^#[0-9a-fA-F]{3,8}$/.test(color) ? color : fallback;
}

function strategyEscape(value, fallback) {
    return escapeHTML(value || fallback || '');
}

function normalizeStrategyValue(value) {
    return String(value || '')
        .replace('BULLISH', '多头')
        .replace('BEARISH', '空头')
        .replace('SAFE', '安全')
        .replace('TRIGGERED', '已触发')
        .replace('PLACEHOLDER (model inactive)', '模型待接入')
        .replace('PLACEHOLDER', '待接入')
        .replace('NOT LIVE', '未实盘')
        .replace('UNKNOWN', '未知')
        .replace('ERROR', '异常')
        .replace('HIGH', '高')
        .replace('LOW', '低')
        .replace('vs 200MA', '相对200日均线');
}

function renderStrategyBacktestUnavailable(metricsContainer, chartDom, message) {
    const safeMessage = strategyEscape(message, '回测数据暂不可用');
    if (metricsContainer) {
        metricsContainer.innerHTML = `
            <div class="metric-cell" style="grid-column:1/-1; align-items:flex-start; gap:4px;">
                <span style="font-family:var(--font-mono); color:#f59e0b;">回测暂不可用</span>
                <strong style="font-size:0.85rem; color:var(--text-secondary);">${safeMessage}</strong>
            </div>
        `;
    }
    if (chartDom && window.echarts) {
        let eqChart = echarts.getInstanceByDom(chartDom);
        if (!eqChart) eqChart = echarts.init(chartDom);
        eqChart.clear();
        eqChart.setOption({
            title: {
                text: '回测暂不可用',
                subtext: safeMessage,
                left: 'center',
                top: 'middle',
                textStyle: { color: '#f59e0b', fontFamily: 'var(--font-mono)', fontSize: 14 },
                subtextStyle: { color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }
            },
            xAxis: { show: false },
            yAxis: { show: false },
            series: []
        });
    } else if (chartDom) {
        chartDom.innerHTML = `<div class="strategy-chart-empty">${safeMessage}</div>`;
    }
}

function renderStrategyEngines(container, engines) {
    if (!container) return;
    if (!engines.length) {
        container.innerHTML = `<div class="glass-card strategy-empty-card">暂无可用策略引擎</div>`;
        return;
    }

    const statusMap = { active: '运行中', standby: '观察中', inactive: '停用', degraded: '降级运行', unknown: '未知' };
    const modeMap = { live: '实时测算', policy_static: '策略参数', placeholder: '模型待接入', live_with_placeholder_theme: '混合测算' };
    const signalMap = {
        'OVERWEIGHT A-SHARE': '超配A股宽基',
        'OVERWEIGHT OVERSEAS': '超配海外宽基',
        'DEFENSIVE TILT': '防御倾斜',
        'A-SHARE CAUTION': 'A股谨慎',
        'A-SHARE BULLISH': 'A股偏多',
        'PLACEHOLDER - NOT TRADEABLE': '模型待接入，不可交易',
        'BULLISH ON GOLD': '黄金偏多',
        'NEUTRAL ON GOLD': '黄金中性',
        NO_SIGNAL: '暂无信号'
    };
    const descMap = {
        'Volatility-inverse allocation across global broad indices.': '按波动率反向分配A股与海外宽基权重，降低单一市场风险暴露。',
        'Policy barbell allocation using configured broad, dividend, and 15th FYP theme weights.': '用核心宽基/红利底仓承载稳定收益，以政策主题作为卫星弹性。',
        '200-day SMA trend filter. Liquidates assets in structural bear markets.': '以200日均线识别结构性熊市，触发底仓降风险动作。',
        'Shorts Broad A-share ETF to isolate pure policy alpha of 15th FYP.': '通过宽基贝塔对冲隔离政策主题 alpha，当前作为待接入模块展示。',
        'Monitors systemic panic (VIX) and monetary cycles to dynamically allocate to Gold.': '监测VIX与黄金趋势，在系统性压力升高时提高避险资产权重。'
    };
    const labelMap = {
        'A-Share Vol (30d)': 'A股30日波动率',
        'US-Share Vol (30d)': '美股30日波动率',
        'Target Weight A-Share': 'A股目标权重',
        'Target Weight US/JP': '海外目标权重',
        'Core Allocation': '核心底仓比例',
        'Satellite Allocation': '卫星主题比例',
        'Dividend Yield (Core)': '核心红利收益率',
        'Theme Beta (Satellite)': '卫星主题Beta',
        'CSI 300 Trend': '沪深300趋势',
        'SP500 Trend': '标普500趋势',
        'AI Theme Trend': 'AI主题趋势',
        'Circuit Breaker': '风控熔断',
        'Systemic Risk Level': '系统风险等级',
        'Thematic Beta': '主题Beta',
        'Hedge Ratio': '对冲比例',
        'Alpha Capture': 'Alpha捕获',
        'VIX Panic Index': 'VIX恐慌指数',
        'Gold Trend (60MA)': '黄金60日趋势',
        'Systemic Hedge Need': '系统性对冲需求',
        'Allocation Target': '配置目标'
    };
    const actionMap = { BUY: '买入/增配', HOLD: '持有', LIQUIDATE: '清仓/降配', NEUTRAL: '中性' };

    container.innerHTML = engines.map(eng => {
        const status = String(eng.status || 'unknown');
        const badgeColor = status === 'active' ? '#10b981' : (status === 'standby' ? '#f59e0b' : '#ef4444');
        const signalColor = safeStrategyColor(eng.color, '#38bdf8');
        const details = Array.isArray(eng.details) ? eng.details : [];
        const holdings = Array.isArray(eng.holdings) ? eng.holdings : [];
        const dataQuality = eng.data_quality || {};
        const isDegraded = dataQuality.status && dataQuality.status !== 'ok';
        const isTradeable = eng.tradeable !== false;
        const translatedMode = modeMap[eng.model_mode] || eng.model_mode || '实时测算';
        const translatedStatus = statusMap[status] || status;
        const translatedSignal = signalMap[eng.signal] || eng.signal || '暂无信号';
        const translatedDesc = descMap[eng.description] || eng.description || '';
        const engineName = STRATEGY_ENGINE_NAME_MAP[eng.id] || eng.name;
        const qualityHtml = (isDegraded || !isTradeable) ? `
            <div class="strategy-quality-row">
                <span>${isTradeable ? '降级运行' : '禁止交易'}</span>
                <span>模式: ${strategyEscape(translatedMode)}</span>
                ${dataQuality.degraded_reason ? `<span>原因: ${strategyEscape(dataQuality.degraded_reason)}</span>` : ''}
            </div>
        ` : '';
        const detailsHtml = details.map(d => `
            <div class="strategy-detail-row">
                <span>${strategyEscape(labelMap[d.label] || d.label)}</span>
                <strong style="color:${safeStrategyColor(d.color, '#e2e8f0')}">${strategyEscape(normalizeStrategyValue(d.value))}</strong>
            </div>
        `).join('');
        const holdingsHtml = holdings.map(h => {
            const actColor = h.action === 'BUY' ? '#10b981' : (h.action === 'LIQUIDATE' ? '#ef4444' : '#64748b');
            const actZH = actionMap[h.action] || h.action;
            const holdingName = STRATEGY_SYMBOL_NAME_MAP[h.symbol] || h.name;
            return `
                <div class="strategy-holding-row">
                    <div>
                        <span>${strategyEscape(holdingName)}</span>
                        <small>${strategyEscape(h.symbol)}</small>
                    </div>
                    <strong><span style="color:${actColor};">[${strategyEscape(actZH)}]</span> ${strategyEscape(h.weight)}</strong>
                </div>
            `;
        }).join('');

        return `
            <div class="glass-card strategy-engine-card" style="--strategy-signal:${signalColor};">
                <div class="strategy-engine-head">
                    <div>
                        <div class="strategy-engine-name">${strategyEscape(engineName)}</div>
                        <div class="strategy-engine-en">${strategyEscape(eng.name_en)}</div>
                    </div>
                    <div class="strategy-engine-status">
                        <span style="border-color:${badgeColor}; color:${badgeColor}; background:${badgeColor}22;">状态: ${strategyEscape(translatedStatus)}</span>
                        <strong style="color:${signalColor};">&gt; ${strategyEscape(translatedSignal)}</strong>
                    </div>
                </div>
                <div class="strategy-engine-desc">${strategyEscape(translatedDesc)}</div>
                ${qualityHtml}
                <div class="strategy-detail-stack">${detailsHtml}</div>
                <div class="strategy-holdings-box">
                    <div class="strategy-holdings-title">目标配置比例 <span>TARGET ALLOCATION</span></div>
                    ${holdingsHtml}
                </div>
            </div>
        `;
    }).join('');
}

function renderStrategyMetrics(metricsContainer, metrics) {
    if (!metricsContainer) return;
    metricsContainer.innerHTML = `
        <div class="metric-cell"><span>策略年内收益 <small>STRATEGY YTD</small></span><strong style="color:#10b981;">${strategyEscape(metrics.strategy_ytd)}</strong></div>
        <div class="metric-cell"><span>基准年内收益 <small>BENCHMARK YTD</small></span><strong style="color:var(--text-primary);">${strategyEscape(metrics.benchmark_ytd)}</strong></div>
        <div class="metric-cell"><span>最大回撤 <small>MAX DRAWDOWN</small></span><strong style="color:#ef4444;">${strategyEscape(metrics.max_drawdown)}</strong></div>
        <div class="metric-cell"><span>夏普比率 <small>SHARPE RATIO</small></span><strong style="color:#38bdf8;">${strategyEscape(metrics.sharpe_ratio)}</strong></div>
    `;
}

function renderStrategyEquityChart(chartDom, backtest) {
    if (!chartDom || !window.echarts) return;
    let eqChart = echarts.getInstanceByDom(chartDom);
    if (!eqChart) eqChart = echarts.init(chartDom);
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
        legend: { data: ['策略组合', '基准组合'], textStyle: { color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }, top: 0, right: 0 },
        grid: { left: '3%', right: '4%', bottom: '5%', top: '15%', containLabel: true },
        xAxis: {
            type: 'category',
            boundaryGap: false,
            data: backtest.dates,
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
                name: '策略组合',
                type: 'line',
                data: backtest.strategy_returns,
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
                name: '基准组合',
                type: 'line',
                data: backtest.benchmark_returns,
                itemStyle: { color: '#64748b' },
                lineStyle: { width: 2, type: 'dashed' },
                showSymbol: false
            }
        ]
    });
}

function renderStrategyUniverse(container, universe) {
    if (!container || !universe) return;
    let html = '';
    for (const [category, assets] of Object.entries(universe)) {
        let catColor = '#38bdf8';
        if(category.includes('A_SHARE')) catColor = '#ef4444';
        if(category.includes('OVERSEAS')) catColor = '#10b981';
        if(category.includes('THEME')) catColor = '#a855f7';
        if(category.includes('HEDGE')) catColor = '#eab308';

        html += `<div class="strategy-universe-bucket" style="--bucket-color:${catColor};">
            <div class="strategy-universe-title">${strategyEscape(STRATEGY_CATEGORY_MAP[category] || category.replace('_',' '))}</div>
            <div class="strategy-universe-assets">`;
        (Array.isArray(assets) ? assets : []).forEach(a => {
            const assetName = STRATEGY_SYMBOL_NAME_MAP[a.symbol] || a.name;
            html += `<div>
                <span>${strategyEscape(assetName)}</span>
                <strong>${strategyEscape(a.symbol)}</strong>
            </div>`;
        });
        html += `</div></div>`;
    }
    container.innerHTML = html;
}

async function initStrategyLab() {
    const view = document.getElementById('view-strategy');
    if (!view || !view.classList.contains('active')) return;
    const timeEl = document.getElementById('strategy-time');
    if(timeEl) {
        const now = new Date();
        timeEl.innerText = now.toLocaleTimeString('zh-CN', {hour12:false}) + '.' + now.getMilliseconds().toString().padStart(3,'0');
    }
    try {
        const res = await fetch('/api/institutional/strategies');
        const data = await res.json();

        renderStrategyEngines(document.getElementById('strategy-engines-container'), Array.isArray(data.engines) ? data.engines : []);

        const metricsContainer = document.getElementById('strategy-metrics-container');
        const eqChartDom = document.getElementById('chart-strategy-equity');
        const backtestReady = hasStrategyBacktestSeries(data.backtest);
        if (!backtestReady) {
            renderStrategyBacktestUnavailable(metricsContainer, eqChartDom, data.backtest && data.backtest.error);
        } else {
            renderStrategyMetrics(metricsContainer, data.backtest.metrics);
            renderStrategyEquityChart(eqChartDom, data.backtest);
        }

        renderStrategyUniverse(document.getElementById('strategy-universe-container'), data.universe);
    } catch (e) {
        console.error('Failed to init Strategy Lab:', e);
    }
}

// ==========================================
// [HUB] DECISION HUB LOGIC
// ==========================================
