// decision_hub.js - AlphaCore focused panel module.
function repairHubText(value) {
    if (value === null || value === undefined) return '';
    if (typeof value !== 'string') return value;
    const looksMojibake = /[\u00c0-\u00ff\u0080-\u009f]/.test(value);
    if (!looksMojibake) return value;
    try {
        const bytes = Uint8Array.from(Array.from(value, ch => ch.charCodeAt(0) & 0xff));
        return new TextDecoder('utf-8', { fatal: false }).decode(bytes);
    } catch (_) {
        return value;
    }
}

function hubCnStatus(status) {
    const map = {
        HARD_BLOCK: '硬性阻断',
        SOFT_WARNING: '风险预警',
        PASS: '通过',
        APPROVED: '通过',
        NEUTRAL: '中性',
        BULLISH: '进攻',
        DEFENSIVE: '防御',
        MAINTAIN: '维持',
        BUY: '买入',
        SELL: '卖出',
        HOLD: '持有',
        INCREASE: '增配',
        DECREASE: '减配'
    };
    return map[status] || repairHubText(status);
}

function hubSignalCn(rawSignal) {
    const map = {
        BULLISH: '看多',
        BEARISH: '看空',
        'A-SHARE BULLISH': 'A股看多',
        'A-SHARE CAUTION': 'A股谨慎',
        'DEFENSIVE TILT': '防御倾斜',
        'HEDGE ACTIVE': '对冲开启',
        'HEDGE INACTIVE': '对冲关闭',
        'OVERWEIGHT OVERSEAS': '超配海外资产',
        'OVERWEIGHT A-SHARE': '超配A股',
        'PLACEHOLDER - NOT TRADEABLE': '信号观察，不可交易',
        'BULLISH ON GOLD': '看多黄金',
        'NEUTRAL ON GOLD': '黄金中性',
        NO_SIGNAL: '暂无信号'
    };
    return map[rawSignal] || repairHubText(rawSignal);
}

function hubTranslateRisk(raw) {
    const text = repairHubText(raw);
    if (text.startsWith('region_limit_exceeded:')) return `区域敞口上限突破：${text.split(':')[1]}`;
    if (text.startsWith('strategy_limit_exceeded:')) return `策略敞口上限突破：${text.split(':')[1]}`;
    if (text.startsWith('position_limit_exceeded:')) return `单一持仓上限突破：${text.split(':')[1]}`;
    if (text.startsWith('trade_size_exceeded:')) return `单笔交易规模超限：${text.split(':')[1]}`;
    if (text === 'turnover_exceeded') return '换手率超限';
    if (text === 'no_new_risk_when_risk_high') return '高风险状态下禁止新增风险';
    if (text === 'fallback_data_non_defensive_action') return '降级数据状态下禁止非防御动作';
    return text;
}

async function initDecisionHub() {
    console.log('Initializing Decision Hub Dashboard...');
    const root = document.getElementById('view-hub');
    if (!root) {
        console.error('view-hub not found');
        return;
    }

    root.classList.add('hub-workspace');
    root.classList.add('active');
    root.classList.add('route-active-view');
    root.innerHTML = `
        <section class="hub-hero">
            <div>
                <div class="hub-eyebrow">INSTITUTIONAL DECISION OPERATING SYSTEM</div>
                <h2 class="hub-title">全球机构决策中枢</h2>
                <p class="hub-subtitle">宏观基准、量化信号、资金路由、合规门禁与投委会纪要的统一工作台</p>
                <div class="hub-meta-row">
                    <span id="hub-timestamp">更新时间 --:--:--</span>
                    <span>组合账本：默认机构账本</span>
                </div>
            </div>
            <div id="hub-status-badge" class="hub-status-badge">系统联机</div>
        </section>

        <section class="hub-grid hub-grid-top">
            <article class="glass-card hub-card hub-card-blue" id="hub-l1-card">
                <div class="hub-card-header">
                    <div>
                        <span class="hub-layer">L1 MACRO REGIME</span>
                        <h3>宏观基准锚定</h3>
                    </div>
                    <span class="hub-chip">基准层</span>
                </div>
                <div id="hub-l1-content" class="hub-metric-grid"><div class="loading-spinner"></div></div>
            </article>

            <article class="glass-card hub-card hub-card-purple" id="hub-l2-card">
                <div class="hub-card-header">
                    <div>
                        <span class="hub-layer">L2 QUANT ENGINES</span>
                        <h3>量化信号阵列</h3>
                    </div>
                    <span class="hub-chip">信号层</span>
                </div>
                <div id="hub-l2-content" class="hub-signal-grid"><div class="loading-spinner"></div></div>
            </article>
        </section>

        <section class="hub-grid hub-grid-middle">
            <article class="glass-card hub-card hub-card-cyan" id="hub-l3-card">
                <div class="hub-card-header">
                    <div>
                        <span class="hub-layer">L3 ROUTER & ALLOCATOR</span>
                        <h3>资金路由与目标仓位</h3>
                    </div>
                    <span class="hub-chip">配置层</span>
                </div>
                <div id="hub-l3-rationale" class="hub-rationale"></div>
                <div id="chart-hub-l3-alloc" class="chart-container hub-alloc-chart"></div>
            </article>

            <article class="glass-card hub-card hub-card-green" id="hub-l4-card">
                <div class="hub-card-header">
                    <div>
                        <span class="hub-layer">L4 COMPLIANCE GATE</span>
                        <h3>风控合规门禁</h3>
                    </div>
                    <span class="hub-chip">治理层</span>
                </div>
                <div id="hub-l4-content" class="hub-compliance"><div class="loading-spinner"></div></div>
            </article>
        </section>

        <article class="glass-card hub-card hub-card-gold" id="hub-l5-card">
            <div class="hub-card-header">
                <div>
                    <span class="hub-layer">L5 AI-CIO SYNTHESIS & NARRATIVE</span>
                    <h3>投委会结论与智能投研纪要</h3>
                </div>
                <span id="ai-indicator" class="status-indicator"></span>
            </div>
            <div id="hub-l5-content" class="hub-memo-stack"><div class="loading-spinner"></div></div>
        </article>
    `;

    fetch('/api/institutional/decision_hub')
        .then(r => r.json())
        .then(data => renderDecisionHub(data))
        .catch(err => {
            console.error(err);
            const l1 = document.getElementById('hub-l1-content');
            if (l1) l1.innerHTML = '<div class="error-msg">决策引擎连接失败，请检查后端服务。</div>';
        });
}

function renderDecisionHub(data) {
    if (data.error) {
        const l1 = document.getElementById('hub-l1-content');
        if (l1) l1.innerHTML = `<div class="error-msg">${repairHubText(data.error)}</div>`;
        return;
    }

    const timestamp = document.getElementById('hub-timestamp');
    if (timestamp && data.timestamp) {
        const d = new Date(data.timestamp * 1000);
        timestamp.textContent = `更新时间 ${d.toLocaleString('zh-CN', { hour12: false })}`;
    }

    const badge = document.getElementById('hub-status-badge');
    if (badge) {
        const status = data.global_status || data.l4_compliance?.gate_status || 'ACTIVE';
        badge.textContent = `${hubCnStatus(status)} · ${status}`;
        badge.dataset.status = status;
    }

    renderHubL1(data);
    renderHubL2(data);
    renderHubL3(data);
    renderHubL4(data);
    renderHubL5(data);
}

function renderHubL1(data) {
    const l1 = document.getElementById('hub-l1-content');
    if (!l1) return;
    const macro = data.l1_macro || {};
    const regime = macro.regime || 'NEUTRAL';
    const regimeTone = regime === 'DEFENSIVE' ? 'danger' : (regime === 'BULLISH' ? 'blue' : 'green');

    l1.innerHTML = `
        <div class="hub-metric hub-metric-${regimeTone}">
            <span>宏观周期</span>
            <strong>${hubCnStatus(regime)}</strong>
            <small>${regime}</small>
        </div>
        <div class="hub-metric">
            <span>恐慌指数 VIX</span>
            <strong>${macro.vix_level !== undefined ? macro.vix_level.toFixed(2) : '--'}</strong>
            <small>Volatility</small>
        </div>
        <div class="hub-metric">
            <span>宏观动量分</span>
            <strong>${macro.score ?? macro.macro_score ?? '--'}</strong>
            <small>Macro Score</small>
        </div>
        <div class="hub-metric">
            <span>权益风险预算</span>
            <strong>${macro.max_equity_exposure !== undefined ? (macro.max_equity_exposure * 100).toFixed(0) + '%' : '--'}</strong>
            <small>Equity Budget</small>
        </div>
        <div class="hub-action-strip">
            <span>建议动作</span>
            <strong>${hubCnStatus(macro.recommended_action || 'MAINTAIN')} · ${macro.recommended_action || 'MAINTAIN'}</strong>
        </div>
    `;
}

function renderHubL2(data) {
    const l2 = document.getElementById('hub-l2-content');
    if (!l2) return;
    const sigs = data.l2_signals || [];
    if (sigs.length === 0) {
        l2.innerHTML = '<div class="hub-empty">暂无量化信号。</div>';
        return;
    }

    l2.innerHTML = sigs.map(s => {
        const valColor = s.signal > 0.5 ? 'positive' : (s.signal < -0.5 ? 'negative' : 'neutral');
        const rawSignal = s.raw_text || (s.signal > 0.5 ? 'BULLISH' : (s.signal < -0.5 ? 'BEARISH' : 'NO_SIGNAL'));
        const holding = s.top_holding || {};
        const targetName = typeof holding === 'object'
            ? repairHubText(holding.name || holding.symbol || '--')
            : repairHubText(holding || '--');
        const targetSymbol = typeof holding === 'object' ? (holding.symbol || '') : '';
        const sourceZh = repairHubText(s.source_zh || s.source || 'Unknown');

        return `
            <div class="hub-signal-card hub-signal-${valColor}">
                <div>
                    <strong>${sourceZh}</strong>
                    <small>${s.source || ''}</small>
                </div>
                <div class="hub-signal-body">
                    <span>
                        顶配标的
                        <b>${targetName}</b>
                        <small>${targetSymbol}</small>
                    </span>
                    <em>${hubSignalCn(rawSignal)}<small>${rawSignal}</small></em>
                </div>
            </div>
        `;
    }).join('');
}

function renderHubL3(data) {
    const rationaleEl = document.getElementById('hub-l3-rationale');
    const routing = data.l3_routing || {};
    if (rationaleEl) {
        rationaleEl.innerHTML = `<span>配置解释</span><strong>${repairHubText(routing.rationale || '等待资产配置模型输出。')}</strong>`;
    }

    const chartDom = document.getElementById('chart-hub-l3-alloc');
    if (chartDom && window.echarts) {
        let allocChart = echarts.getInstanceByDom(chartDom);
        if (!allocChart) allocChart = echarts.init(chartDom);

        const tgt = routing.target_weights || {};
        const cur = routing.before_weights || {};
        const symNames = routing.symbol_names || {};
        const symbols = Array.from(new Set([...Object.keys(tgt), ...Object.keys(cur)]));
        const xAxisLabels = symbols.map(s => repairHubText(symNames[s] || s));
        const curData = symbols.map(s => (cur[s] || 0) * 100);
        const tgtData = symbols.map(s => (tgt[s] || 0) * 100);

        allocChart.setOption({
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(11, 13, 19, 0.95)',
                borderColor: 'rgba(148,163,184,0.2)',
                textStyle: { color: '#f8fafc' },
                axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(59,130,246,0.08)' } },
                formatter: function(params) {
                    let res = `<div style="font-weight:700;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid rgba(255,255,255,0.1);">${params[0].axisValue}</div>`;
                    params.forEach(p => {
                        res += `<div style="display:flex;justify-content:space-between;gap:18px;margin-bottom:4px;"><span>${p.seriesName}</span><strong>${p.value.toFixed(1)}%</strong></div>`;
                    });
                    return res;
                }
            },
            grid: { top: 36, right: 18, bottom: 24, left: 42, containLabel: true },
            xAxis: {
                type: 'category',
                data: xAxisLabels,
                axisLabel: { color: '#94a3b8', fontSize: 10, rotate: 28 },
                axisLine: { lineStyle: { color: 'rgba(255,255,255,0.12)' } }
            },
            yAxis: {
                type: 'value',
                axisLabel: { color: '#94a3b8', fontSize: 10, formatter: '{value}%' },
                splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)', type: 'dashed' } }
            },
            legend: {
                data: ['当前仓位', '目标仓位'],
                textStyle: { color: '#cbd5e1', fontSize: 11 },
                top: 0,
                right: 0,
                icon: 'roundRect'
            },
            series: [
                {
                    name: '当前仓位',
                    type: 'bar',
                    data: curData,
                    itemStyle: { color: 'rgba(100,116,139,0.36)', borderRadius: [3, 3, 0, 0], borderColor: 'rgba(148,163,184,0.55)', borderWidth: 1 },
                    barWidth: '30%',
                    barGap: '16%'
                },
                {
                    name: '目标仓位',
                    type: 'bar',
                    data: tgtData,
                    itemStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: '#38bdf8' },
                            { offset: 1, color: '#2563eb' }
                        ]),
                        borderRadius: [3, 3, 0, 0],
                        shadowBlur: 12,
                        shadowColor: 'rgba(56,189,248,0.28)'
                    },
                    barWidth: '30%'
                }
            ]
        });
        window.addEventListener('resize', () => allocChart.resize());
        renderHubTrades(chartDom, routing, symbols, tgt, cur, symNames);
    }
}

function renderHubTrades(chartDom, routing, symbols, tgt, cur, symNames) {
    let tradesContainer = document.getElementById('hub-l3-trades');
    if (!tradesContainer) {
        tradesContainer = document.createElement('div');
        tradesContainer.id = 'hub-l3-trades';
        tradesContainer.className = 'hub-trade-box';
        chartDom.parentNode.appendChild(tradesContainer);
    }

    const sharpe = routing.backtest_metrics?.strat_sharpe;
    let html = '<div class="hub-trade-head"><span>执行建议</span>';
    if (sharpe !== undefined) {
        html += `<strong>${sharpe > 1 ? '高置信' : '中等置信'} · Sharpe ${sharpe}</strong>`;
    }
    html += '</div><div class="hub-trade-list">';

    let hasTrades = false;
    symbols.forEach(s => {
        const diffPct = ((tgt[s] || 0) - (cur[s] || 0)) * 100;
        const name = repairHubText(symNames[s] || s);
        if (Math.abs(diffPct) > 0.5) {
            hasTrades = true;
            html += diffPct > 0
                ? `<span class="hub-trade-buy">买入 ${name} +${diffPct.toFixed(1)}%</span>`
                : `<span class="hub-trade-sell">卖出 ${name} ${diffPct.toFixed(1)}%</span>`;
        }
    });

    if (!hasTrades) {
        html += '<span class="hub-trade-hold">无需调仓：当前仓位与目标仓位偏离较小</span>';
    }
    tradesContainer.innerHTML = `${html}</div>`;
}

function renderHubL4(data) {
    const l4 = document.getElementById('hub-l4-content');
    const l4Card = document.getElementById('hub-l4-card');
    if (!l4) return;
    const comp = data.l4_compliance || {};
    const status = comp.gate_status || 'PASS';
    const isBlock = status === 'HARD_BLOCK';
    const isWarn = status === 'SOFT_WARNING';
    const tone = isBlock ? 'danger' : (isWarn ? 'warning' : 'success');
    if (l4Card) l4Card.dataset.tone = tone;

    let html = `
        <div class="hub-gate hub-gate-${tone}">
            <div>
                <span>门禁状态</span>
                <strong>${hubCnStatus(status)}</strong>
                <small>${status}</small>
            </div>
            <div>
                <span>合规评分</span>
                <strong>${comp.score ?? '--'}</strong>
                <small>Compliance Score</small>
            </div>
        </div>
        <div class="hub-score-track"><div style="width:${Math.max(0, Math.min(100, comp.score || 0))}%;"></div></div>
    `;

    const items = comp.violations?.length ? comp.violations : comp.warnings || [];
    if (items.length > 0) {
        html += `
            <div class="hub-risk-list hub-risk-${tone}">
                <strong>${isBlock ? '硬性风控阻断' : '软性风险预警'}</strong>
                <ul>${items.map(v => `<li>${hubTranslateRisk(v)}</li>`).join('')}</ul>
            </div>
        `;
    } else {
        html += '<div class="hub-risk-list hub-risk-success"><strong>全部风控规则通过</strong><p>未触发集中度、换手率或单笔交易规模约束。</p></div>';
    }

    html += `
        <div class="hub-turnover">
            <span>预计换手率</span>
            <strong>${comp.turnover !== undefined ? (comp.turnover * 100).toFixed(1) + '%' : '--'}</strong>
        </div>
    `;
    l4.innerHTML = html;
}

function renderHubL5(data) {
    const l5 = document.getElementById('hub-l5-content');
    const l5Card = document.getElementById('hub-l5-card');
    if (!l5) return;
    const memo = data.l5_ai_memo || {};
    const headline = repairHubText(memo.headline || '等待投委会纪要');
    const body = repairHubText(memo.memo || 'AI-CIO 正在等待宏观、量化、配置与合规层输出。');
    if (l5Card) {
        l5Card.dataset.tone = headline.includes('阻断') || headline.includes('BLOCKED') || headline.includes('REJECTED')
            ? 'danger'
            : (headline.includes('预警') || headline.includes('WARNING') ? 'warning' : 'success');
    }

    l5.innerHTML = `
        <div class="hub-memo">
            <span>投委会备忘录</span>
            <strong>${headline}</strong>
            <p>${body}</p>
        </div>
        <div class="hub-narrative">
            <span>实时综合研判</span>
            <div id="ai-typewriter">
                <div id="ai-text">正在载入宏观背景、因子解释与市场叙事...</div>
            </div>
        </div>
    `;

    setTimeout(() => {
        if (typeof initGenAI === 'function') initGenAI();
    }, 100);

    if (window.renderL6Blotter) {
        window.renderL6Blotter(data);
    }
}
