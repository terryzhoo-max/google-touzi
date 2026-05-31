// main.js - Legacy dashboard/panel renderers. Core bootstrap, API, and portfolio state live in static/js/core/.
async function initDashboard() {
    try {
        const d = await fetchJsonWithRetry('/api/macro/decision');
        // Signal ring
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
        // Regime badge
        const rb = document.getElementById('regime-badge');
        if (rb) {
            const fac = d.factors.find(f => f.name === '当前象限' || /regime|象限/i.test(f.name || ''));
            rb.textContent = fac ? fac.detail : '--';
            rb.style.background = d.color + '20';
            rb.style.color = d.color;
            rb.style.border = `1px solid ${d.color}40`;
        }
        const rd = document.getElementById('regime-detail');
        if (rd) {
            rd.textContent = d.factors.map(f => `${f.name}: ${f.score}`).join(' / ');
        }
        // Allocation bars
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
            ad.textContent = `EQ ${w.spy}% / FI ${w.tlt}% / GLD ${w.gld}% / CASH ${w.cash}%`;
        }
        // Alert banner
        const banner = document.getElementById('alert-banner');
        const count = document.getElementById('alert-count');
        const list = document.getElementById('alert-list');
        if (banner && d.active_warnings && d.active_warnings.length > 0) {
            banner.style.display = 'block';
            banner.classList.add('has-warnings');
            if (count) count.textContent = d.active_warnings.length;
            if (list) renderAlertList(list, d.active_warnings);
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
        const degraded = hd.degraded_sources || [];
        const hitPct = Math.round((hd.cache?.hit_ratio || 0) * 100);
        const circuitOpen = hd.circuit ? Object.entries(hd.circuit).filter(([,v])=>v.state==='open').map(([k])=>k) : [];
        if (circuitOpen.length > 0) {
            setFreshnessStatus({
                state: 'error',
                text: `Circuit open: ${circuitOpen.join(',')} | cache hit ${hitPct}%`,
            });
        } else if (degraded.length > 0) {
            setFreshnessStatus({
                state: 'degraded',
                text: `Degraded: ${degraded.join(', ')} | cache hit ${hitPct}%`,
            });
        } else {
            setFreshnessStatus({
                state: 'healthy',
                text: `Healthy | cache hit ${hitPct}% | alerts ${hd.active_alerts}`,
            });
        }
    } catch (e) {
        console.error('Health check failed:', e);
    }
}
// Shared panel helpers
function renderAllocationWeightRows(model) {
    const allocationModelWeights = document.getElementById('allocation-model-weights');
    if (!allocationModelWeights) return;
    const current = model.current_weights || {};
    const target = model.target_weights || {};
    const rows = Object.keys(target)
        .sort((a, b) => Number(target[b] || 0) - Number(target[a] || 0))
        .slice(0, 6);
    if (!rows.length) {
        allocationModelWeights.textContent = '--';
        return;
    }
    clearChildren(allocationModelWeights);
    rows.forEach(symbol => {
        const current_weight = Number(current[symbol] || 0);
        const target_weight = Number(target[symbol] || 0);
        const delta = target_weight - current_weight;
        const row = document.createElement('span');
        row.textContent = `${symbol} ${Math.round(current_weight * 1000) / 10}% -> ${Math.round(target_weight * 1000) / 10}% (${delta >= 0 ? '+' : ''}${Math.round(delta * 1000) / 10}%)`;
        row.style.display = 'block';
        allocationModelWeights.appendChild(row);
    });
}
function renderAllocationTradeRows(model) {
    const allocationModelTrades = document.getElementById('allocation-model-trades');
    if (!allocationModelTrades) return;
    const trades = model.proposed_trades || [];
    allocationModelTrades.textContent = trades.length
        ? trades.slice(0, 4).map(row => `${row.symbol} ${row.delta_weight > 0 ? '+' : ''}${Math.round(row.delta_weight * 1000) / 10}%`).join(' / ')
        : 'no trade';
}
function renderAllocationEvidenceRows(model) {
    const allocationModelEvidence = document.getElementById('allocation-model-evidence');
    if (!allocationModelEvidence) return;
    const evidence = model.evidence_chain || [];
    allocationModelEvidence.textContent = evidence.length
        ? evidence.slice(0, 3).map(row => row.code || row.message || 'evidence').join(' / ')
        : '--';
}
function renderAllocationReviewSchedule(model) {
    setFlowText('allocation-model-review', (model.review_schedule || []).join(' / ') || '--');
}
function renderAllocationModel(model) {
    const panel = document.getElementById('allocation-model-panel');
    if (!panel) return;
    if (!model) return;
    setFlowText('allocation-model-version', model.model_version || '--');
    setFlowText('allocation-model-hash', shortHash(model.model_hash));
    const riskDelta = model.expected_effect?.var_95_delta_pct ?? 0;
    setFlowText('allocation-model-risk-delta', `${riskDelta}%`);
    setFlowText('allocation-model-stress-delta', `${model.expected_effect?.worst_scenario_delta_pct ?? '--'}%`);
    setFlowText('allocation-model-turnover', `${model.expected_effect?.turnover_pct ?? '--'}%`);
    const cStatus = model.constraint_result?.status || '--';
    setFlowText('allocation-model-constraint', cStatus);
    renderAllocationReviewSchedule(model);
    renderAllocationTradeTable(model);
    renderAllocationEvidenceRows(model);
    // Zone indicator
    const mStatus = model.status || 'unknown';
    const zone = document.getElementById('allocation-model-zone');
    if (zone) {
        let zt, zb, zc, za;
        if (mStatus === 'allow') {
            zt='Allow rebalance'; zb='rgba(34,197,94,0.12)'; zc='#22c55e'; za='Risk budget is available; execute target weight adjustment by signal.';
        } else if (mStatus === 'limited') {
            zt='Staged execution'; zb='rgba(251,191,36,0.12)'; zc='#fbbf24'; za='Compliance warning or risk near limit; execute in stages.';
        } else {
            zt='Observe only'; zb='rgba(239,68,68,0.12)'; zc='#ef4444'; za='Compliance block or stress deterioration; pause rebalance until conditions improve.';
        }
        zone.innerHTML = `${zt} <span style="font-size:0.65rem;font-weight:400;color:${zc};margin-left:8px;">${za}</span>`;
        zone.style.background=zb; zone.style.color=zc;
        zone.style.fontWeight='700'; zone.style.fontSize='0.85rem';
        zone.style.textTransform='uppercase'; zone.style.letterSpacing='1px';
        zone.style.padding='6px 16px'; zone.style.borderRadius='6px';
        zone.style.border=`1px solid ${zc}30`;
    }
    // color constraint cell
    const cs = document.getElementById('allocation-model-constraint');
    if (cs) {
        if (cStatus === 'pass') cs.className = 'risk-low';
        else if (cStatus === 'block') cs.className = 'risk-high';
        else cs.className = 'risk-medium';
    }
}
function renderAllocationTradeTable(model) {
    const el = document.getElementById('allocation-model-trades-table');
    if (!el) return;
    const trades = model.proposed_trades || [];
    if (!trades.length) { el.innerHTML = '<div style="color:#64748b;font-size:0.75rem;padding:8px;">No recommended rebalance</div>'; return; }
    el.innerHTML = `<table class="institutional-table"><thead><tr><th>标的</th><th>当前</th><th>目标</th><th>变化</th><th>信号</th></tr></thead><tbody>` +
        trades.map(t => {
            const isBuy = t.delta_weight > 0;
            const color = isBuy ? '#22c55e' : '#ef4444';
            const label = isBuy ? 'BUY' : 'SELL';
            return `<tr>
                <td>${t.symbol}</td>
                <td>${(t.current_weight*100).toFixed(1)}%</td>
                <td>${(t.target_weight*100).toFixed(1)}%</td>
                <td style="color:${color};font-weight:600;">${isBuy?'+':''}${(t.delta_weight*100).toFixed(1)}%</td>
                <td><span style="background:${color}20;color:${color};padding:1px 8px;border-radius:3px;font-size:0.65rem;font-weight:700;">${label}</span></td>
            </tr>`;
        }).join('') + '</tbody></table>';
}
const ACTION_ZH = {
    "Proceed with proposed rebalance.": "Proceed with proposed rebalance (PROCEED)",
    "Do not execute the proposed rebalance.": "Do not execute proposed rebalance (BLOCK)",
    "Wait for better execution window.": "建议暂缓执行，等待更优窗口 (WAIT)",
    "Requires manual review.": "Requires manual risk review (REVIEW)"
};
const REASON_ZH = {
    "scenario_loss_high": "尾部风险超限 (Scenario Loss)",
    "constraint_cash_below_minimum": "Cash minimum constraint warning",
    "portfolio_china_exposure": "亚太敞口异常暴露 (China Exposure)",
    "concentration_limit_breach": "Single asset concentration breach",
    "factor_volatility_high": "Factor volatility is elevated",
    "compliance_passed": "Compliance and risk controls passed"
};
async function initInstitutionalDecision() {
    const panel = document.getElementById('view-institutional');
    if (!panel) return;
    try {
        const data = await fetchJsonWithRetry('/api/institutional/decision');
        if (data && data.l3_routing && data.l3_routing.symbol_names) {
            window.symbolNamesCache = data.l3_routing.symbol_names;
        }
        const auditResp = await fetch('/api/institutional/audit/decisions?limit=10');


        // Fetch AI CRO review asynchronously without blocking
        const aiStatus = document.getElementById('ai-cro-status');
        const aiText = document.getElementById('ai-cro-text');
        if (aiStatus) aiStatus.textContent = 'EVALUATING...';
        fetch('/api/institutional/ai_compliance_review')
            .then(res => res.json())
            .then(aiData => {
                if (aiStatus) aiStatus.textContent = 'REPORT READY';
                if (aiText) {
                    aiText.innerHTML = renderSafeAIInsight(aiData.insight);
                    aiText.style.opacity = 0;
                    aiText.style.animation = "fadeIn 1s forwards";
                }
            })
            .catch(err => {
                if (aiStatus) aiStatus.textContent = 'EVALUATION FAILED';
                if (aiText) aiText.innerHTML = '<span style="color:#ef4444;">Failed to connect to AI CRO engine.</span>';
            });
        const auditData = await auditResp.json();

        const ticket = data.decision_ticket || {};
        const action = data.recommended_action || {};
        const risk = data.risk || {};
        const worst = data.scenarios?.worst_scenario || {};
        const portfolio = data.portfolio || ticket.portfolio_summary || {};
        const explanation = data.decision_explanation || {};
        const factor_risk = data.factor_risk || {};
        const active_risk = data.active_risk || {};
        const compliance = data.compliance || {};
        const attribution = data.attribution || {};
        if (typeof initBrinsonAttribution === 'function') initBrinsonAttribution();
        const tradesAlert = document.getElementById('decision-trades-alert');
        if (tradesAlert) {
            const trades = ticket.proposed_trades || [];
            if (trades.length > 0) {
                tradesAlert.style.display = 'flex';
                tradesAlert.innerHTML = trades.map(t => {
                    const isBuy = t.action === 'buy';
                    const color = isBuy ? '#22c55e' : '#ef4444';
                    const bg = isBuy ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)';
                    return `<span style="font-family:var(--font-mono); font-size:0.75rem; color:${color}; background:${bg}; padding:4px 8px; border-radius:4px; border:1px solid ${color}55;">${isBuy ? 'BUY' : 'SELL'} ${t.ticker} ${(t.weight * 100).toFixed(1)}%</span>`;
                }).join('');
            } else {
                tradesAlert.style.display = 'none';
                tradesAlert.innerHTML = '';
            }
        }
        // Risk Profile
        setFlowText('decision-var', `${risk.var_95_pct ?? '--'}%`);
        setFlowText('decision-worst', `${worst.portfolio_loss_pct ?? '--'}%`);
        setFlowText('decision-primary-driver', explanation.primary_driver?.code || '--');
        setFlowText('decision-concentration', portfolio.concentration_level || '--');
        // Factor Exposure
        setFlowText('workbench-top-factor', formatTopFactor(factor_risk));
        setFlowText('workbench-tracking-error', `${active_risk.tracking_error_proxy_pct ?? '--'}%`);
        const activeEl = document.getElementById('workbench-largest-active');
        if (activeEl) activeEl.innerHTML = formatLargestActiveHTML(active_risk);
        // Audit Trail Table
        const tbody = document.getElementById('audit-log-table-body');
        if (tbody) {
            const decisions = auditData.decisions || [];
            if (decisions.length === 0) {
                tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:20px; color:var(--text-tertiary);">No audit records found</td></tr>`;
            } else {
                tbody.innerHTML = decisions.map(d => {
                    const timeStr = new Date(d.created_at * 1000).toLocaleTimeString([], {hour12: false});
                    const dateStr = new Date(d.created_at * 1000).toLocaleDateString([], {month:'2-digit', day:'2-digit'});
                    const tid = (d.ticket_id || '').slice(0, 12);

                    let compColor = '#22c55e', compBg = 'rgba(34,197,94,0.1)';
                    if (d.compliance_status === 'block') { compColor = '#ef4444'; compBg = 'rgba(239,68,68,0.1)'; }
                    else if (d.compliance_status === 'warn') { compColor = '#fbbf24'; compBg = 'rgba(251,191,36,0.1)'; }

                    return `<tr>
                        <td style="padding-left:16px; font-family:var(--font-mono); font-size:0.8rem; color:var(--text-secondary);">${dateStr} ${timeStr}</td>
                        <td style="font-family:var(--font-mono); font-size:0.8rem; color:var(--text-tertiary);">${tid}</td>
                        <td style="font-weight:700;">${d.score}</td>
                        <td><span style="padding:2px 8px; border-radius:4px; font-size:0.7rem; font-weight:700; color:${compColor}; background:${compBg}; text-transform:uppercase;">${d.compliance_status}</span></td>
                        <td style="font-size:0.8rem; color:var(--text-secondary);">${d.action_status || d.decision_status}</td>
                    </tr>`;
                }).join('');
            }
        }
    } catch (error) {
        console.error('Error fetching institutional decision:', error);
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
                name: '股权风险溢价',
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
                    name: 'VIX volatility',
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
        const data = await fetchJsonWithRetry('/api/macro/signals');
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
    myChart.showLoading({ text: '鎷夊彇鏈熼檺缁撴瀯...', color: '#fbbf24', textColor: '#fff', maskColor: 'rgba(20, 20, 25, 0.8)' });
    try {
        const data = await fetchJsonWithRetry('/api/macro/yield_curve');
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
            legend: { data: ['鍒╁樊 (bp)', '闆惰酱'], textStyle: { color: '#94a3b8' }, top: 0 },
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
                    name: '鍒╁樊 (bp)', type: 'line', smooth: true,
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
                    name: '闆惰酱', type: 'line',
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
    myChart.showLoading({ text: 'Running allocation simulation...', color: '#4ade80', textColor: '#fff', maskColor: 'rgba(20, 20, 25, 0.8)' });

    try {
        const allocData = await fetchJsonWithRetry('/api/macro/allocation');
        myChart.hideLoading();
        const ind = document.getElementById('alloc-indicator');
        const ins = document.getElementById('alloc-insight');
        if (ind && ins) {
            ind.innerText = allocData.regime;
            ind.style.color = '#4ade80';
            ind.style.borderColor = '#4ade80';
            ind.style.boxShadow = `0 0 10px rgba(74, 222, 128, 0.4)`;
            ins.innerText = `Macro anchors: VIX=${allocData.vix_ref} | 10Y=${allocData.tnx_ref}% | DXY=${allocData.dxy_ref}. Engine generated current macro allocation.`;
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
                    name: '璧勪骇閰嶇疆寤鸿',
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
    myChart.showLoading({ text: 'Calculating risk matrix...', color: '#ef4444', textColor: '#fff', maskColor: 'rgba(20, 20, 25, 0.8)' });

    try {
        const corrData = await fetchJsonWithRetry('/api/macro/correlation');
        myChart.hideLoading();
        if (corrData.error) throw new Error(corrData.error);
        const ind = document.getElementById('corr-indicator');
        const ins = document.getElementById('corr-insight');
        const banner = document.getElementById('corr-action-banner');
        const actionText = document.getElementById('corr-extreme-action');

        if (ind && ins) {
            ind.innerText = corrData.state;
            const color = safeCssColor(corrData.color, '#ef4444');
            ind.style.color = color;
            ind.style.borderColor = color;
            ind.style.boxShadow = `0 0 10px ${color}40`;
            ins.textContent = corrData.insight;
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
    myChart.showLoading({ text: 'Calculating optimization...', color: '#7000FF', textColor: '#fff', maskColor: 'rgba(20, 20, 25, 0.8)' });
    try {
        const data = await fetchJsonWithRetry('/api/macro/efficient_frontier');
        myChart.hideLoading();
        if (data.error) throw new Error(data.error);
        const ind = document.getElementById('ef-indicator');
        const ins = document.getElementById('ef-insight');
        if (ind) { ind.innerText = '鍓嶆部璁＄畻瀹屾垚'; ind.style.color = '#a78bfa'; ind.style.borderColor = '#a78bfa'; }
        if (ins) ins.innerText = data.insight;
        const option = {
            backgroundColor: 'transparent',
            tooltip: { trigger: 'item', formatter: p => `${p.seriesName}<br/>鏀剁泭: ${p.value[0]}%  |  娉㈠姩: ${p.value[1]}%` },
            grid: { left: '8%', right: '5%', top: '5%', bottom: '8%' },
            xAxis: { name: 'Annualized Volatility (%)', nameTextStyle: { color: '#94a3b8' }, axisLabel: { color: '#94a3b8', formatter: '{value}%' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
            yAxis: { name: 'Annualized Return (%)', nameTextStyle: { color: '#94a3b8' }, axisLabel: { color: '#94a3b8', formatter: '{value}%' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
            series: [
                {
                    name: '闅忔満缁勫悎', type: 'scatter',
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
                    name: '鍒囩嚎缁勫悎', type: 'scatter',
                    symbolSize: 16, symbol: 'triangle',
                    itemStyle: { color: '#4ade80' },
                    data: [[data.tangency.ret, data.tangency.vol]],
                    label: { show: true, formatter: 'Tangency portfolio', position: 'top', color: '#4ade80', fontSize: 12 },
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
        const data = await fetchJsonWithRetry('/api/macro/scenario');
        ind.innerText = 'Scenario test complete';
        ind.style.color = '#fbbf24';
        ind.style.borderColor = '#fbbf24';
        if (ins) ins.innerText = data.insight;
        renderScenarioGrid(grid, data.scenarios);
    } catch (e) {
        console.error("Scenario test failed:", e);
        ind.innerText = '鎺ㄦ紨澶辫触';
        ind.style.color = '#ef4444';
    }
}
async function initMonteCarloChart() {
    const chartDom = document.getElementById('mc-chart');
    if (!chartDom) return;
    const myChart = echarts.init(chartDom, 'dark');
    myChart.showLoading({ text: 'Running Monte Carlo simulation...', color: '#00F0FF', textColor: '#fff', maskColor: 'rgba(20, 20, 25, 0.8)' });

    try {
        const mcData = await fetchJsonWithRetry('/api/macro/montecarlo');
        myChart.hideLoading();
        if (mcData.error) throw new Error(mcData.error);
        const ind = document.getElementById('mc-indicator');
        const ins = document.getElementById('mc-insight');
        if (ind && ins) {
            ind.innerText = "鎺ㄦ紨瀹屾垚 (1000 Paths)";
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
                    name: '鏋佸瘨搴曠嚎 (VaR P5)',
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
                    name: '涔愯鏋侀檺 (P95)',
                    type: 'line',
                    smooth: true,
                    symbol: 'none',
                    lineStyle: { width: 1, color: '#4ade80' },
                    data: mcData.p95
                },
                {
                    name: 'Median Forecast (P50)',
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
const rotationPanelConfigs = [
    {
        domId: 'sector-chart',
        apiUrl: '/api/macro/sector_rotation',
        indicatorId: 'sr-indicator',
        insightId: 'sr-insight',
        successText: '行业轮动已加载',
        theme: 'default',
    },
    {
        domId: 'theme-chart',
        apiUrl: '/api/macro/theme_rotation',
        indicatorId: 'tr-indicator',
        insightId: 'tr-insight',
        successText: '政策主题已加载',
        theme: 'policy',
    },
    {
        domId: 'domestic-etf-chart',
        apiUrl: '/api/macro/domestic_etf',
        indicatorId: 'de-indicator',
        insightId: 'de-insight',
        successText: 'A股宽基已加载',
        theme: 'etf',
    },
    {
        domId: 'global-etf-chart',
        apiUrl: '/api/macro/global_etf',
        indicatorId: 'ge-indicator',
        insightId: 'ge-insight',
        successText: '全球ETF已加载',
        theme: 'global',
    },
];
function initRotationPanels() {
    rotationPanelConfigs.forEach((config, index) => {
        window.setTimeout(() => initTreemapChart(config), index * 350);
    });
}
async function initTreemapChart(config) {
    const { domId, apiUrl, indicatorId, insightId, successText, theme } = config;
    const chartDom = document.getElementById(domId);
    const panel = document.querySelector(`[data-rotation-panel="${domId}"]`);
    if (!chartDom || !panel) return;
    let activePeriod = window.currentRotationPeriod || 'ret_20d';
    let items = [];
    chartDom.innerHTML = '<div class="rotation-empty">轮动引擎计算中...</div>';
    try {
        const payload = await fetchJsonWithRetry(apiUrl, 3, 650);
        if (payload.error) throw new Error(payload.error);
        items = normalizeRotationItems(payload);
        if (!items.length) throw new Error('No rotation data returned');
        setRotationStatus(indicatorId, successText, 'ok');
        const insight = document.getElementById(insightId);
        if (insight) insight.textContent = payload.insight || buildRotationInsight(items, activePeriod);
        bindRotationControls(panel, chartDom, items, theme, activePeriod, nextPeriod => {
            activePeriod = nextPeriod;
            renderRotationPanel(panel, chartDom, items, theme, activePeriod);
        });
        renderRotationPanel(panel, chartDom, items, theme, activePeriod);
    } catch (e) {
        setRotationStatus(indicatorId, '加载失败', 'error');
        const insight = document.getElementById(insightId);
        if (insight) insight.textContent = `数据源异常：${e.message}`;
        chartDom.innerHTML = '<div class="rotation-empty" style="color:#ef4444; padding:12px; font-family:var(--font-mono);">[SYS_ERR] 引擎演算失败</div>';
        console.error(domId + ' failed:', e);
    }
}
function normalizeRotationItems(payload) {
    const raw = payload.sectors || payload.items || [];
    return raw.map(item => ({
        code: item.code || '',
        name: item.name || item.code || '--',
        value: Number(item.value || item.last_close || Math.max(Math.abs(item.ret_20d || 0), 1)),
        ret_5d: Number(item.ret_5d || 0),
        ret_20d: Number(item.ret_20d || 0),
        ret_60d: Number(item.ret_60d || 0),
    })).filter(item => item.name !== '--');
}
function bindRotationControls(panel, chart, items, theme, activePeriod, onPeriodChange) {
    const buttons = panel.querySelectorAll('.rotation-controls button[data-period]');
    buttons.forEach(button => {
        button.onclick = () => {
            buttons.forEach(btn => btn.classList.remove('is-active'));
            button.classList.add('is-active');
            onPeriodChange(button.dataset.period || activePeriod);
        };
    });
}
function renderRotationPanel(panel, chartDom, items, theme, periodKey) {
    const ranked = [...items].sort((a, b) => b[periodKey] - a[periodKey]);
    const top = ranked.slice(0, 5);
    const bottom = ranked.slice(-5).reverse();
    const positives = items.filter(item => item[periodKey] > 0).length;
    const breadth = Math.round((positives / Math.max(items.length, 1)) * 100);
    const marketRead = breadth >= 65 ? '强势扩散' : (breadth <= 35 ? '弱势收缩' : '结构分化');
    setPanelText(panel, 'market-read', marketRead);
    setPanelText(panel, 'coverage', `${items.length}/${items.length}`);
    setPanelText(panel, 'leader', top[0]?.name || '--');
    setPanelText(panel, 'laggard', bottom[0]?.name || '--');
    renderRankList(panel, 'top', top, periodKey);
    renderRankList(panel, 'bottom', bottom, periodKey);
    renderSparklineTable(chartDom, ranked, theme, periodKey);
}
function setPanelText(panel, suffix, value) {
    const id = `${panel.dataset.rotationPanel}-${suffix}`;
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}
function renderRankList(panel, suffix, rows, periodKey) {
    const id = `${panel.dataset.rotationPanel}-${suffix}`;
    const el = document.getElementById(id);
    if (!el) return;
    el.innerHTML = rows.map(item => {
        const val = item[periodKey];
        const cls = val >= 0 ? 'is-positive' : 'is-negative';
        return `<li><span>${item.name}</span><strong class="${cls}">${formatPct(val)}</strong></li>`;
    }).join('');
}
function renderSparklineTable(chartDom, items, theme, periodKey) {
    const cols = ['ret_5d', 'ret_20d', 'ret_60d'];
    const colLabels = ['5D', '20D', '60D'];

    // Calculate global max absolute return for proper cross-asset visual scaling within the panel
    const globalMaxAbs = Math.max(...items.flatMap(a => cols.map(k => Math.abs(Number(a[k]||0)))), 0.01);

    const tableHtml = `<div style="overflow-y:auto; height:100%; border:1px solid rgba(255,255,255,0.08); border-radius:6px; background:rgba(0,0,0,0.2); box-shadow:inset 0 0 20px rgba(0,0,0,0.5);">
        <table class="institutional-table" style="margin:0; width:100%;">
            <thead style="position:sticky; top:0; z-index:10; background:rgba(15,23,42,0.95); backdrop-filter:blur(8px); border-bottom:1px solid rgba(255,255,255,0.1);">
                <tr>
                    <th style="padding:12px 16px; text-align:left;">标的 / 板块</th>
                    <th style="text-align:left;">动量信号</th>
                    <th style="text-align:center;">趋势剖面 (5D / 60D)</th>
                </tr>
            </thead>
            <tbody>` +
        items.map(a => {
            const dir = cols.filter(k=>(a[k]||0)>0).length;
            const arrow = dir>=3 ? '强势增配' : dir>=2 ? '偏强观察' : dir<=0 ? '弱势减配' : '偏弱防守';
            const arrowColor = dir>=2 ? '#10b981' : dir<=0 ? '#ef4444' : '#f59e0b';
            const arrowBg = dir>=2 ? 'rgba(16,185,129,0.15)' : dir<=0 ? 'rgba(239,68,68,0.15)' : 'rgba(245,158,11,0.15)';
            const rowBg = a[periodKey] < -5 ? 'rgba(239,68,68,0.04)' : a[periodKey] > 5 ? 'rgba(16,185,129,0.03)' : 'transparent';

            const sparklines = cols.map((k, idx) => {
                const val = Number(a[k]||0);
                const h = Math.round((Math.abs(val) / globalMaxAbs) * 20);
                const isPos = val >= 0;
                const bg = isPos ? 'linear-gradient(0deg, rgba(16,185,129,0.2) 0%, rgba(16,185,129,0.8) 100%)' : 'linear-gradient(180deg, rgba(239,68,68,0.2) 0%, rgba(239,68,68,0.8) 100%)';
                const sign = isPos ? '+' : '';
                const valColor = isPos ? '#34d399' : '#f87171';
                const isTarget = k === periodKey;
                const borderHighlight = isTarget ? `border-bottom: 2px solid ${valColor};` : '';

                const barStyle = isPos
                    ? `bottom:50%; height:${Math.max(h, 2)}px; border-radius:2px 2px 0 0;`
                    : `top:50%; height:${Math.max(h, 2)}px; border-radius:0 0 2px 2px;`;

                const labelStyle = isPos
                    ? `bottom:calc(50% + ${Math.max(h, 2) + 2}px);`
                    : `top:calc(50% + ${Math.max(h, 2) + 2}px);`;

                return `<div style="display:flex; flex-direction:column; align-items:center; height:60px; width:40px; position:relative; ${borderHighlight}">
                    <div style="font-size:0.65rem; font-family:var(--font-mono); font-weight:${isTarget?'800':'600'}; color:${valColor}; position:absolute; ${labelStyle} text-shadow:0 0 6px ${valColor}40; line-height:1;">${sign}${val.toFixed(1)}</div>
                    <div style="position:absolute; width:12px; height:1px; background:rgba(255,255,255,0.15); top:50%; z-index:1;"></div>
                    <div style="position:absolute; width:8px; ${barStyle} background:${bg}; box-shadow:0 0 4px ${isPos?'rgba(16,185,129,0.4)':'rgba(239,68,68,0.4)'}; z-index:2;"></div>
                    <div style="font-size:0.6rem; color:${isTarget?'#e2e8f0':'var(--text-tertiary)'}; position:absolute; bottom:0; font-weight:${isTarget?'800':'600'}; line-height:1;">${colLabels[idx]}</div>
                </div>`;
            }).join('');
            return `<tr style="background:${rowBg}; border-bottom:1px solid rgba(255,255,255,0.03);">
                <td style="padding-left:16px; font-weight:700; color:var(--text-primary); font-size:0.85rem; letter-spacing:0.5px;">${a.name}</td>
                <td style="text-align:left;"><span style="background:${arrowBg}; color:${arrowColor}; border: 1px solid ${arrowColor}60; padding:4px 8px; border-radius:4px; font-size:0.65rem; font-weight:800; letter-spacing:1px; box-shadow: 0 0 10px ${arrowBg};">${arrow}</span></td>
                <td style="padding-right:16px;">
                    <div style="display:flex; gap:16px; justify-content:center; align-items:flex-end; height:50px; margin-top:14px; margin-bottom:4px;">
                        ${sparklines}
                    </div>
                </td>
            </tr>`;
        }).join('') + `</tbody></table></div>`;

    chartDom.innerHTML = tableHtml;
}
function rotationColor(value, theme) {
    const v = Math.max(-12, Math.min(12, Number(value) || 0));
    const intensity = Math.min(1, Math.abs(v) / 8);
    const palettes = {
        default: { pos: [22, 163, 74], neg: [220, 38, 38], neu: [71, 85, 105] },
        policy: { pos: [37, 99, 235], neg: [217, 119, 6], neu: [71, 85, 105] },
        etf: { pos: [22, 163, 74], neg: [220, 38, 38], neu: [71, 85, 105] },
        global: { pos: [14, 116, 144], neg: [185, 28, 28], neu: [71, 85, 105] },
    };
    const p = palettes[theme] || palettes.default;
    const base = v > 0 ? p.pos : (v < 0 ? p.neg : p.neu);
    const alpha = 0.38 + intensity * 0.52;
    return `rgba(${base[0]}, ${base[1]}, ${base[2]}, ${alpha})`;
}
function formatPct(value) {
    const n = Number(value) || 0;
    return `${n > 0 ? '+' : ''}${n.toFixed(2)}%`;
}
function buildRotationInsight(items, periodKey) {
    const ranked = [...items].sort((a, b) => b[periodKey] - a[periodKey]);
    const top = ranked.slice(0, 3).map(item => item.name).join(', ');
    const bottom = ranked.slice(-3).reverse().map(item => item.name).join(', ');
    return `近端领涨: ${top || '--'} | 领跌: ${bottom || '--'}`;
}
function setRotationStatus(indicatorId, text, status) {
    const el = document.getElementById(indicatorId);
    if (!el) return;
    el.textContent = text;
    el.classList.toggle('is-error', status === 'error');
    el.classList.toggle('is-ok', status === 'ok');
}
async function initChinaMacro() {
    const gd = document.getElementById('china-macro-grid');
    if (!gd) return;
    try {
        const d = await fetchJsonWithRetry('/api/macro/china_macro');
        const labels={cpi:'CPI同比',pmi:'制造业PMI',m2:'M2同比',gdp:'GDP增速'};
        gd.innerHTML = Object.entries(labels).map(([k,lb]) => {
            const v = d[k];
            if (!v) return '<div class="china-macro-tile"><div style="color:#64748b;font-size:0.7rem;">'+lb+'</div><div style="color:#94a3b8;">暂无数据</div></div>';
            let chartId = 'cm-chart-'+k;
            setTimeout(()=>{
                const el=document.getElementById(chartId);if(!el)return;
                const mc=echarts.init(el,'dark');
                mc.setOption({backgroundColor:'transparent',grid:{left:0,right:0,top:5,bottom:0},xAxis:{show:false,data:v.dates},yAxis:{show:false,min:'dataMin',max:'dataMax'},
                    series:[{type:'line',data:v.values,smooth:true,symbol:'none',lineStyle:{width:2,color:v.color},
                        areaStyle:{color:new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:v.color+'60'},{offset:1,color:'rgba(0,0,0,0)'}])}}]});
            },100);
            return `<div class="china-macro-tile">
                <div style="color:#64748b;font-size:0.7rem;margin-bottom:4px;">${lb}</div>
                <div style="font-size:1.4rem;font-weight:700;color:${v.color};font-family:var(--font-mono);">${v.current}%</div>
                <div style="font-size:0.7rem;color:${v.color};margin-top:2px;">${v.signal}</div>
                <div id="${chartId}" style="height:80px;margin-top:6px;"></div>
            </div>`;
        }).join('');
        document.getElementById('cm-indicator').innerText='Updated '+d.updated;
        document.getElementById('cm-insight').innerText=`CPI ${d.cpi?.current}% (${d.cpi?.signal}) | PMI ${d.pmi?.current} (${d.pmi?.signal}) | M2 ${d.m2?.current}% (${d.m2?.signal}) | GDP ${d.gdp?.current}% (${d.gdp?.signal})`;
    }catch(e){console.error('China macro:',e);}
}
async function initMarketBreadth() {
    const cd = document.getElementById('breadth-chart');
    if (!cd) return;
    const mc = echarts.init(cd, 'dark');
    try {
        const d = await fetchJsonWithRetry('/api/macro/market_breadth');
        const flow = d.flow || d.ad_ratio || [];
        const cumulative = d.cumulative || d.ad_line || [];
        const today = d.today || {};
        const currentFlow = Number(today.current_flow ?? today.up ?? 0);
        const flow5d = Number(today.flow_5d ?? 0);
        const flow20d = Number(today.flow_20d ?? 0);
        setFlowText('mb-current-flow', formatMoneyFlow(currentFlow));
        setFlowText('mb-flow-5d', formatMoneyFlow(flow5d));
        setFlowText('mb-flow-20d', formatMoneyFlow(flow20d));
        setFlowText('mb-flow-signal', d.signal || '--');
        const indicator = document.getElementById('mb-indicator');
        if (indicator) {
            indicator.innerText = d.signal || 'Updated';
            indicator.classList.toggle('is-error', !flow.length);
            indicator.classList.toggle('is-ok', flow.length > 0);
        }
        document.getElementById('mb-insight').innerText = d.insight;
        mc.setOption({
            backgroundColor: 'transparent',
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(15, 23, 42, 0.96)',
                borderColor: 'rgba(148, 163, 184, 0.22)',
                textStyle: { color: '#e5e7eb' },
                axisPointer: { type: 'cross' },
                formatter: params => {
                    const lines = params.map(p => `${p.marker}${p.seriesName}: ${formatMoneyFlow(p.value)}`).join('<br/>');
                    return `<div class="chart-tooltip-title">${params[0]?.axisValue || ''}</div>${lines}`;
                }
            },
            legend: {data:['累计净流入','单日净流入'],textStyle:{color:'#94a3b8'},top:0},
            grid:{left:'3%',right:'4%',top:'16%',bottom:'3%',containLabel:true},
            xAxis:{type:'category',data:cumulative.map(v=>formatTradeDate(v.date)),axisLabel:{color:'#94a3b8'}},
            yAxis:[{type:'value',name:'累计',splitLine:{lineStyle:{color:'rgba(255,255,255,0.05)'}},axisLabel:{color:'#94a3b8'}},
                   {type:'value',name:'单日',axisLabel:{color:'#94a3b8'}}],
            series:[
                {name:'累计净流入',type:'line',data:cumulative.map(v=>v.value),smooth:true,symbol:'none',lineStyle:{width:2,color:'#2563eb'},areaStyle:{color:'rgba(37,99,235,0.12)'}},
                {name:'单日净流入',type:'bar',yAxisIndex:1,data:flow.map(v=>({value:v.value,itemStyle:{color:v.value>=0?'#16a34a':'#dc2626'}})),barMaxWidth:14},
            ]
        });
        window.addEventListener('resize',()=>mc.resize());
    }catch(e){console.error('Market breadth:',e);}
}
function setFlowText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}
function formatMoneyFlow(value) {
    const n = Number(value) || 0;
    return `${n > 0 ? '+' : ''}${n.toFixed(1)}亿`;
}
function formatTradeDate(value) {
    const s = String(value || '');
    return s.length === 8 ? `${s.slice(4, 6)}-${s.slice(6, 8)}` : s;
}
async function initFedProb() {
    const cd=document.getElementById('fed-chart'); if(!cd)return;
    const mc=echarts.init(cd,'dark');
    try{
        const d=await fetchJsonWithRetry('/api/macro/fed_prob');
        document.getElementById('fed-indicator').innerText=d.signal;
        document.getElementById('fed-insight').innerText=d.insight;
        mc.setOption({
            backgroundColor:'transparent',
            tooltip:{trigger:'axis'},grid:{left:'3%',right:'4%',top:'5%',bottom:'3%',containLabel:true},
            xAxis:{type:'category',data:d.rate_path.map(v=>v.date),axisLabel:{color:'#94a3b8',formatter:v=>v.slice(0,7)}},
            yAxis:{type:'value',name:'%',axisLabel:{color:'#94a3b8'}},
            series:[{name:'鑱旈偊鍩洪噾鍒╃巼',type:'line',data:d.rate_path.map(v=>v.rate),smooth:true,symbol:'none',
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
        // Global assets takes ~21s to warm cache due to 14 sequential API calls (1.5s rate limit each)
        const d=await fetchJsonWithRetry('/api/macro/global_assets', 20, 1500);
        // Backend composite sentiment
        const sig = d.composite || {};
        document.getElementById('ga-indicator').innerHTML =
            `Updated ${d.updated} <span style="display:inline-flex;align-items:center;gap:4px;margin-left:8px;padding:2px 10px;background:${sig.color||'#64748b'}20;border:1px solid ${sig.color||'#64748b'}30;border-radius:999px;color:${sig.color||'#64748b'};">${sig.label}</span>`;
        if (!d.assets || !d.assets.length) { el.innerHTML='<div style="color:#64748b;padding:12px;">暂无数据</div>'; return; }
        const cols=['daily','weekly','monthly','quarterly','ytd'];
        const colLabels=['1D','1W','1M','1Q','YTD'];

        // Calculate global max absolute return for proper cross-asset visual scaling
        const globalMaxAbs = Math.max(...d.assets.flatMap(a => cols.map(k => Math.abs(Number(a[k]||0)))), 0.01);
        const tableHtml = `<div style="overflow-y:auto; height:100%; max-height: 480px; border:1px solid rgba(255,255,255,0.08); border-radius:6px; background:rgba(0,0,0,0.2); box-shadow:inset 0 0 20px rgba(0,0,0,0.5);">
            <table class="institutional-table" style="margin:0; width:100%;">
                <thead style="position:sticky; top:0; z-index:10; background:rgba(15,23,42,0.95); backdrop-filter:blur(8px); border-bottom:1px solid rgba(255,255,255,0.1);">
                    <tr>
                        <th style="padding:12px 16px; text-align:left;">资产/指数 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">ASSET</span></th>
                        <th style="text-align:left;">资产类别 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">CLASS</span></th>
                    <th style="text-align:left;">动量信号 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">MOMENTUM</span></th>
                        <th style="text-align:center;">趋势轮廓 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">TREND PROFILE (1D &rarr; YTD)</span></th>
                    </tr>
                </thead>
                <tbody>` +
            d.assets.map(a=>{
                const dir = cols.filter(k=>(a[k]||0)>0).length;
                const arrow = dir>=4 ? 'STRONG BUY' : dir>=3 ? 'BUY' : dir<=1 ? 'STRONG SELL' : 'SELL';
                const arrowColor = dir>=3 ? '#10b981' : dir<=1 ? '#ef4444' : '#f59e0b';
                const arrowBg = dir>=3 ? 'rgba(16,185,129,0.15)' : dir<=1 ? 'rgba(239,68,68,0.15)' : 'rgba(245,158,11,0.15)';
                const rowBg = (a.quarterly||0) < -5 ? 'rgba(239,68,68,0.04)' : (a.quarterly||0) > 5 ? 'rgba(16,185,129,0.03)' : 'transparent';

                // CSS Micro Bar Chart Generation
                const sparklines = cols.map((k, idx) => {
                    const val = Number(a[k]||0);
                    const h = Math.round((Math.abs(val) / globalMaxAbs) * 20); // Max height 20px per half
                    const isPos = val >= 0;
                    const bg = isPos ? 'linear-gradient(0deg, rgba(16,185,129,0.2) 0%, rgba(16,185,129,0.8) 100%)' : 'linear-gradient(180deg, rgba(239,68,68,0.2) 0%, rgba(239,68,68,0.8) 100%)';
                    const sign = isPos ? '+' : '';
                    const valColor = isPos ? '#34d399' : '#f87171';

                    const barStyle = isPos
                        ? `bottom:50%; height:${Math.max(h, 2)}px; border-radius:2px 2px 0 0;`
                        : `top:50%; height:${Math.max(h, 2)}px; border-radius:0 0 2px 2px;`;

                    const labelStyle = isPos
                        ? `bottom:calc(50% + ${Math.max(h, 2) + 2}px);`
                        : `top:calc(50% + ${Math.max(h, 2) + 2}px);`;

                    return `<div style="display:flex; flex-direction:column; align-items:center; height:60px; width:40px; position:relative;">
                        <div style="font-size:0.65rem; font-family:var(--font-mono); font-weight:600; color:${valColor}; position:absolute; ${labelStyle} text-shadow:0 0 6px ${valColor}40; line-height:1;">${sign}${val.toFixed(1)}</div>
                        <div style="position:absolute; width:12px; height:1px; background:rgba(255,255,255,0.15); top:50%; z-index:1;"></div>
                        <div style="position:absolute; width:8px; ${barStyle} background:${bg}; box-shadow:0 0 4px ${isPos?'rgba(16,185,129,0.4)':'rgba(239,68,68,0.4)'}; z-index:2;"></div>
                        <div style="font-size:0.6rem; color:var(--text-tertiary); position:absolute; bottom:0; font-weight:600; line-height:1;">${colLabels[idx]}</div>
                    </div>`;
                }).join('');
                const score = Number(a.score || 0);
                const rsRating = Number(a.rs_rating || 0);

                const rsColor = rsRating >= 70 ? '#10b981' : rsRating >= 30 ? '#f59e0b' : '#ef4444';
                const rsBg = rsRating >= 70 ? 'rgba(16,185,129,0.15)' : rsRating >= 30 ? 'rgba(245,158,11,0.15)' : 'rgba(239,68,68,0.15)';

                const rsPill = `<span style="background:${rsBg}; color:${rsColor}; padding:3px 6px; border-radius:4px; font-family:var(--font-mono); font-size:0.65rem; font-weight:800; border:1px solid ${rsColor}40; box-shadow:0 0 6px ${rsBg}; letter-spacing:0.5px;" title="Momentum Factor: ${score.toFixed(2)}">RS ${rsRating}</span>`;

                return `<tr style="background:${rowBg}; border-bottom:1px solid rgba(255,255,255,0.03);">
                    <td style="padding-left:16px; font-weight:700; color:var(--text-primary); font-size:0.85rem; letter-spacing:0.5px;">${a.name}</td>
                    <td style="text-align:left;"><span style="background:rgba(255,255,255,0.05); padding:3px 6px; border-radius:4px; font-size:0.7rem; color:var(--text-secondary); border:1px solid rgba(255,255,255,0.08);">${a.cat}</span></td>
                    <td style="text-align:left;">
                        <div style="display:flex; align-items:center; gap:8px;">
                            <span style="background:${arrowBg}; color:${arrowColor}; border: 1px solid ${arrowColor}60; padding:4px 8px; border-radius:4px; font-size:0.65rem; font-weight:800; letter-spacing:1px; box-shadow: 0 0 10px ${arrowBg}; width:80px; text-align:center;">${arrow}</span>
                            ${rsPill}
                        </div>
                    </td>
                    <td style="padding-right:16px;">
                        <div style="display:flex; gap:16px; justify-content:center; align-items:flex-end; height:50px; margin-top:14px; margin-bottom:4px;">
                            ${sparklines}
                        </div>
                    </td>
                </tr>`;
            }).join('') + `</tbody></table></div>`;

        el.innerHTML = tableHtml;
    }catch(e){console.error('Global assets:',e); el.innerHTML='<div style="color:#ef4444;padding:12px;font-family:var(--font-mono);">[SYS_ERR] Data stream unavailable or circuit breaker active</div>';}
}
function valuationEscape(value) {
    return (window.escapeHTML || (v => String(v ?? '').replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[c])))(value);
}

function valuationPercentile(item) {
    return Number(item.pe_pct ?? item.price_pct ?? 0) || 0;
}

function valuationTone(pct) {
    if (pct >= 95) return { label: '泡沫区间', className: 'is-extreme', action: '禁止追高，进入减仓/对冲观察清单' };
    if (pct >= 70) return { label: '高估', className: 'is-high', action: '降低新增仓位，等待回撤或盈利修复' };
    if (pct >= 50) return { label: '合理偏高', className: 'is-watch', action: '维持中性配置，使用分批与止盈纪律' };
    if (pct >= 25) return { label: '合理偏低', className: 'is-normal', action: '可保留基准配置，关注基本面确认' };
    return { label: '低估', className: 'is-low', action: '纳入左侧配置池，仍需流动性与趋势确认' };
}

function buildValuationSummary(items) {
    const total = items.length || 1;
    const high = items.filter(item => valuationPercentile(item) >= 70).length;
    const extreme = items.filter(item => valuationPercentile(item) >= 95).length;
    const avgPct = items.length
        ? items.reduce((sum, item) => sum + valuationPercentile(item), 0) / items.length
        : 0;
    let stance = '中性观察';
    let className = 'is-watch';
    let action = '维持基准权重，优先比较估值分位与趋势强弱是否同向。';
    if (extreme >= 2 || high / total > 0.6) {
        stance = '估值拥挤';
        className = 'is-extreme';
        action = '控制组合贝塔，优先处理高分位资产的止盈、对冲与替代配置。';
    } else if (high / total > 0.3) {
        stance = '估值偏贵';
        className = 'is-high';
        action = '新增资金保持克制，等待风险溢价修复或盈利上修确认。';
    } else if (avgPct < 35) {
        stance = '估值偏低';
        className = 'is-low';
        action = '可建立观察仓，但仍需成交量、汇率和宏观因子交叉验证。';
    }
    return { high, extreme, avgPct: avgPct.toFixed(1), stance, className, action };
}

function renderValuationInsight(payload, items) {
    const summary = buildValuationSummary(items);
    const insight = valuationEscape(payload.insight || '估值数据暂不可用');
    return `
        <div class="valuation-summary ${summary.className}">
            <div>
                <div class="valuation-summary-kicker">Institutional Read-through</div>
                <div class="valuation-summary-title">${summary.stance}</div>
                <div class="valuation-summary-copy">${summary.action}</div>
            </div>
            <div class="valuation-summary-metrics">
                <span>高分位 ${summary.high}/${items.length}</span>
                <span>极端 ${summary.extreme}</span>
                <span>均值 ${summary.avgPct}%</span>
            </div>
        </div>
        <div class="valuation-scale" aria-label="估值分位色阶">
            <span class="is-low">低估 &lt;25</span>
            <span class="is-normal">合理 25-50</span>
            <span class="is-watch">偏高 50-70</span>
            <span class="is-high">高估 70-95</span>
            <span class="is-extreme">极端 &gt;95</span>
        </div>
        <div class="valuation-raw-line">${insight}</div>
    `;
}

function renderValuationMetric(label, value, pct, signal, color, isPrimary = false) {
    const tone = valuationTone(Number(pct) || 0);
    const width = Math.max(2, Math.min(100, Number(pct) || 0));
    const barColor = safeCssColor(color, '#f59e0b');
    return `
        <div class="valuation-metric ${isPrimary ? 'is-primary' : ''}">
            <div class="valuation-metric-row">
                <span>${valuationEscape(label)} ${valuationEscape(value)}</span>
                <strong>${valuationEscape(pct)}% · ${valuationEscape(signal || tone.label)}</strong>
            </div>
            <div class="valuation-bar" aria-hidden="true">
                <div class="valuation-bar-fill" style="width:${width}%;background:${barColor};"></div>
            </div>
        </div>
    `;
}

function renderValuationCard(item) {
    const pct = valuationPercentile(item);
    const tone = valuationTone(pct);
    const pctText = pct.toFixed(1);
    const name = valuationEscape(item.name);
    const category = valuationEscape(item.category || (item.metric_type === 'price' ? 'ETF' : 'INDEX'));
    const primarySignal = item.metric_type === 'price' ? item.price_signal : item.pe_signal;
    const primaryColor = safeCssColor(item.color, '#f59e0b');
    const primaryMetric = item.metric_type === 'price'
        ? renderValuationMetric('价格', item.price_current, item.price_pct, item.price_signal, primaryColor, true)
        : renderValuationMetric('PE', item.pe_current, item.pe_pct, item.pe_signal, primaryColor, true);
    const secondaryMetric = item.metric_type === 'price'
        ? `<div class="valuation-method">价格分位使用ETF近10年收盘价；不等同于底层指数PE/PB。</div>`
        : renderValuationMetric('PB', item.pb_current, item.pb_pct, item.pb_signal, primaryColor);

    return `
        <article class="valuation-card ${tone.className}">
            <div class="valuation-card-head">
                <div>
                    <div class="valuation-name">${name}</div>
                    <div class="valuation-action">${valuationEscape(tone.action)}</div>
                </div>
                <div class="valuation-card-side">
                    <div class="valuation-pct-readout"><span>${pctText}</span><small>%</small></div>
                    <div class="valuation-badges">
                        <span>${category}</span>
                        <strong>${valuationEscape(primarySignal || tone.label)}</strong>
                    </div>
                </div>
            </div>
            ${primaryMetric}
            ${secondaryMetric}
        </article>
    `;
}

async function initValuation() {
    const gd = document.getElementById('valuation-grid');
    if (!gd) return;
    try {
        const d = await fetchJsonWithRetry('/api/macro/valuation');
        const indicator = document.getElementById('val-indicator');
        if (indicator) indicator.textContent = `Updated ${d.updated || '--'}`;
        const items = d.indices || [];
        const insight = document.getElementById('val-insight');
        if (insight) insight.innerHTML = renderValuationInsight(d, items);

        const sortByRisk = (a, b) => valuationPercentile(b) - valuationPercentile(a);
        const indexItems = items.filter(item => item.metric_type !== 'price').sort(sortByRisk);
        const etfItems = items.filter(item => item.metric_type === 'price').sort(sortByRisk);
        gd.innerHTML = `
            <section class="valuation-section">
                <div class="valuation-section-title">A股指数：PE/PB 分位</div>
                <div class="valuation-card-grid">${indexItems.map(renderValuationCard).join('') || '<div class="valuation-empty">暂无指数估值数据</div>'}</div>
            </section>
            <section class="valuation-section">
                <div class="valuation-section-title">跨境宽基ETF：价格分位</div>
                <div class="valuation-card-grid">${etfItems.map(renderValuationCard).join('') || '<div class="valuation-empty">暂无ETF价格分位数据</div>'}</div>
            </section>
        `;
    } catch (e) {
        console.error('Valuation:', e);
        gd.innerHTML = '<div class="valuation-empty is-error">估值数据加载失败</div>';
    }
}
async function initAlertCenter() {
    const el = document.getElementById('alert-rules-list');
    if (!el) return;
    const ind = document.getElementById('ac-indicator');
    try {
        const d = await fetchJsonWithRetry('/api/alerts/rules');
        const rules = d.rules || [];
        const triggered = rules.filter(r => r.last_triggered > Date.now()/1000 - 3600).length;
        if (ind) ind.innerText = triggered ? `${triggered} triggered` : 'Monitoring';
        el.innerHTML = rules.map(r => {
            const opLabel = {gt: '>', lt: '<', gte: '>=', lte: '<='}[r.operator] || r.operator;
            return `<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;border-bottom:1px solid rgba(255,255,255,0.04);font-size:0.78rem;">
                <div style="display:flex;align-items:center;gap:10px;">
                    <span style="color:${r.enabled?'#22c55e':'#64748b'};font-size:0.65rem;">${r.enabled?'ON':'OFF'}</span>
                    <span style="color:#e2e8f0;">${r.name}</span>
                    <span style="color:#64748b;font-family:var(--font-mono);font-size:0.68rem;">${opLabel} ${r.threshold}</span>
                    ${r.push_wx ? '<span style="color:#7000FF;font-size:0.6rem;">WX</span>' : ''}
                </div>
                <span style="color:${r.last_triggered>Date.now()/1000-3600?'#ef4444':'#64748b'};font-size:0.65rem;">${r.last_triggered>Date.now()/1000-3600?'Recently triggered':'Standby'}</span>
            </div>`;
        }).join('');
    } catch (e) {
        console.error('Alert center:', e);
    }
}
function surpriseEscape(value) {
    return (window.escapeHTML || (v => String(v ?? '').replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[c])))(value);
}

function surpriseTone(current) {
    const value = Number(current) || 0;
    if (value > 1.5) return { className: 'is-upside', label: '超预期扩张', action: '利好顺周期盈利预期，但需警惕利率上行约束估值。' };
    if (value > 0) return { className: 'is-mild-upside', label: '温和改善', action: '基本面边际修复，可作为风险资产持仓的辅助确认。' };
    if (value > -1.5) return { className: 'is-mild-downside', label: '温和走弱', action: '维持观察，等待信贷、PMI或盈利数据给出方向确认。' };
    return { className: 'is-downside', label: '下修压力', action: '降低增长敏感资产暴露，优先检查防御和现金缓冲。' };
}

function renderSurpriseInsight(data) {
    const current = Number(data.current || 0);
    const tone = surpriseTone(current);
    const signal = surpriseEscape(data.signal || tone.label);
    const stance = surpriseEscape(data.stance || tone.label);
    const insight = surpriseEscape(data.insight || '--');
    return `
        <div class="surprise-readout ${tone.className}">
            <div>
                <div class="surprise-kicker">Macro Data Pulse</div>
                <div class="surprise-title">${stance}</div>
                <div class="surprise-copy">${insight}</div>
            </div>
            <div class="surprise-score">
                <span>${current >= 0 ? '+' : ''}${current.toFixed(1)}</span>
                <small>CESI proxy</small>
            </div>
        </div>
        <div class="surprise-action">${surpriseEscape(tone.action)}</div>
        <div class="surprise-signal-line">${signal}</div>
    `;
}

async function initSurpriseIndex() {
    const cd = document.getElementById('surprise-chart');
    if (!cd) return;
    const mc = echarts.init(cd, 'dark');
    try {
        const d = await fetchJsonWithRetry('/api/macro/surprise_index');
        const color = safeCssColor(d.color, '#fbbf24');
        const tone = surpriseTone(d.current);
        const indicator = document.getElementById('si-indicator');
        if (indicator) {
            indicator.textContent = d.signal || tone.label;
            indicator.style.color = color;
            indicator.style.background = `${color}18`;
            indicator.style.border = `1px solid ${color}40`;
        }
        const insight = document.getElementById('si-insight');
        if (insight) insight.innerHTML = renderSurpriseInsight(d);
        mc.setOption({
            backgroundColor: 'transparent',
            tooltip: {
                trigger: 'axis',
                backgroundColor: '#090d16',
                borderColor: 'rgba(255,255,255,0.12)',
                textStyle: { color: '#e2e8f0', fontFamily: 'var(--font-mono)' }
            },
            grid: { left: '3%', right: '4%', top: '10%', bottom: '4%', containLabel: true },
            xAxis: {
                type: 'category',
                data: d.dates || [],
                axisLine: { lineStyle: { color: 'rgba(255,255,255,0.08)' } },
                axisTick: { show: false },
                axisLabel: { color: '#64748b', fontSize: 10 }
            },
            yAxis: {
                type: 'value',
                splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
                axisLabel: { color: '#64748b', fontSize: 10 }
            },
            series: [{
                name: '累计宏观意外指数',
                type: 'line',
                data: d.values || [],
                smooth: true,
                symbol: 'circle',
                symbolSize: 4,
                showSymbol: false,
                lineStyle: { width: 2.5, color },
                areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: `${color}38` },
                    { offset: 1, color: 'rgba(0,0,0,0)' }
                ]) },
                markLine: {
                    silent: true,
                    symbol: 'none',
                    label: { color: '#64748b', formatter: 'neutral' },
                    data: [{ yAxis: 0 }],
                    lineStyle: { color: '#64748b', type: 'dashed' }
                }
            }]
        });
        window.addEventListener('resize', () => mc.resize());
    } catch (e) { console.error('Surprise index:', e); }
}
async function initPortfolio() {
    try {
        const d = await fetchJsonWithRetry('/api/portfolio/summary');
        if (!d.holdings || !d.holdings.length) return;
        document.getElementById('portfolio-card').style.display = 'block';
        document.getElementById('pf-total').textContent = `Market value: $${d.total_value.toLocaleString()} | Cost: $${d.total_cost.toLocaleString()}`;
        const pnlEl = document.getElementById('pf-pnl');
        pnlEl.textContent = `${d.total_pnl >= 0 ? '+' : ''}$${d.total_pnl.toLocaleString()} (${d.total_pnl_pct > 0 ? '+' : ''}${d.total_pnl_pct}%)`;
        pnlEl.style.color = d.total_pnl >= 0 ? '#22c55e' : '#ef4444';
        document.getElementById('portfolio-table').innerHTML = `<table class="institutional-table"><thead><tr><th>Asset</th><th>Position</th><th>Cost</th><th>Price</th><th>Market Value</th><th>P&L</th></tr></thead><tbody>` +
            d.holdings.map(h => {
                const nameStr = h.name || '--';
                const symbolStr = h.symbol || '--';
                const assetCell = `<div style="display:flex; flex-direction:column; gap:2px;"><span style="font-weight:700; color:var(--text-primary); font-size:0.9rem;">${nameStr}</span><span style="font-family:var(--font-mono); font-size:0.7rem; color:var(--text-tertiary);">${symbolStr}</span></div>`;
                return `<tr><td>${assetCell}</td><td>${h.qty}</td><td>${h.cost}</td><td>${h.current}</td><td>${h.market_value.toLocaleString()}</td><td style="color:${h.pnl_pct>=0?'#22c55e':'#ef4444'};font-weight:600;">${h.pnl_pct>0?'+':''}${h.pnl_pct}%</td></tr>`;
            }).join('') + '</tbody></table>';
    } catch (e) { console.error('Portfolio:', e); }
}
async function initMarginMonitor() {
    const cd = document.getElementById('margin-chart');
    if (!cd) return;
    const mc = echarts.init(cd, 'dark');
    try {
        const d = await fetchJsonWithRetry('/api/macro/margin');
        const mgInd = document.getElementById('mg-indicator');
        if (mgInd) {
            mgInd.innerHTML = `${d.trend || '--'} <span style="margin-left:8px;padding:2px 8px;background:${d.zone_color}20;border-radius:3px;color:${d.zone_color};font-size:0.65rem;font-weight:700;box-shadow: 0 0 8px ${d.zone_color}40;">${d.zone||''}</span>`;
        }

        // Highlight numerical insights
        document.getElementById('mg-insight').innerHTML =
            `两融余额 <span style="color:var(--text-primary);font-family:var(--font-mono);font-weight:700;">${d.total}</span> / ` +
            `融资 <span style="color:#f97316;font-family:var(--font-mono);font-weight:700;">${d.current_rz}</span> / ` +
            `融券 <span style="color:#ef4444;font-family:var(--font-mono);font-weight:700;">${d.current_rq}</span> / ` +
            `券资比 <span style="color:var(--text-secondary);font-family:var(--font-mono);">${d.ratio}%</span>`;

        mc.setOption({
            backgroundColor: 'transparent',
            tooltip: { trigger: 'axis', axisPointer: { type: 'cross', label: { backgroundColor: '#1e293b' } } },
            legend: { data: ['融资余额', '融券余额'], textStyle: { color: '#94a3b8' }, top: 0, right: 0 },
            grid: { left: '2%', right: '2%', top: '15%', bottom: '3%', containLabel: true },
            xAxis: {
                type: 'category', data: d.dates,
                axisLabel: { color: '#64748b', fontSize: 10 },
                axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } }
            },
            yAxis: [
                {
                    type: 'value', name: '融资', nameTextStyle: { color: '#64748b', fontSize: 10 },
                    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.03)', type: 'dashed' } },
                    axisLabel: { color: '#94a3b8', fontSize: 10 },
                    scale: true
                },
                {
                    type: 'value', name: '融券', nameTextStyle: { color: '#64748b', fontSize: 10 },
                    splitLine: { show: false },
                    axisLabel: { color: '#94a3b8', fontSize: 10 },
                    scale: true
                }
            ],
            series: [
                {
                    name: '融资余额', type: 'line', yAxisIndex: 0,
                    data: d.rz_balance, symbol: 'none', smooth: true,
                    lineStyle: { color: '#f97316', width: 2 },
                    areaStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{offset: 0, color: 'rgba(249,115,22,0.3)'},{offset: 1, color: 'rgba(0,0,0,0)'}])
                    }
                },
                {
                    name: '融券余额', type: 'bar', yAxisIndex: 1,
                    data: d.rq_balance, itemStyle: { color: '#ef4444', borderRadius: [2,2,0,0] },
                    barWidth: '35%'
                }
            ]
        });
        window.addEventListener('resize', () => mc.resize());
    } catch (e) { console.error('Margin:', e); }
}
async function initDividendLeaders() {
    const el = document.getElementById('dividend-table');
    if (!el) return;
    try {
        const d = await fetchJsonWithRetry('/api/macro/dividend');
        document.getElementById('dv-indicator').innerText = d.updated || '--';
        document.getElementById('dv-insight').innerText = d.insight || '--';

        const tableHtml = `<div style="overflow-y:auto; height:100%; border:1px solid rgba(255,255,255,0.05); border-radius:4px; margin-top:8px;">
            <table class="institutional-table" style="margin:0;">
                <thead style="position:sticky; top:0; z-index:1;">
                    <tr><th style="padding-left:16px;">ASSET</th><th>YIELD</th><th>PE</th><th>PB</th><th>MKT CAP</th></tr>
                </thead>
                <tbody>` +
            (d.stocks||[]).map(s => {
                const codeParts = (s.code || '').split('.');
                const formattedCode = codeParts.length === 2
                    ? `<span style="font-family:var(--font-mono);color:var(--text-secondary);font-size:0.7rem;letter-spacing:0.5px;">${codeParts[0]}</span><span style="color:var(--text-tertiary);font-size:0.6rem;margin-left:4px;padding:1px 3px;background:rgba(255,255,255,0.05);border-radius:2px;">${codeParts[1]}</span>`
                    : `<span style="font-family:var(--font-mono);color:var(--text-secondary);font-size:0.7rem;">${s.code}</span>`;

                const assetName = s.name || '--';
                const assetCell = `<div style="display:flex; flex-direction:column; gap:2px; justify-content:center; min-height: 36px;">
                    <span style="color:var(--text-primary);font-weight:700;font-size:0.85rem;letter-spacing:0.5px;">${assetName}</span>
                    <div>${formattedCode}</div>
                </div>`;
                const yieldPct = Math.min((Number(s.div_yield) / 12) * 100, 100);
                const barColor = s.div_yield >= 8 ? 'rgba(16,185,129,0.2)' : 'rgba(52,211,153,0.1)';
                const textColor = s.div_yield >= 8 ? '#10b981' : '#34d399';
                const yieldStyle = s.div_yield >= 8
                    ? `color:${textColor};font-weight:800;text-shadow:0 0 10px rgba(16,185,129,0.4);`
                    : `color:${textColor};font-weight:600;`;

                const yieldCell = `<div style="position:relative; width:100%; display:flex; align-items:center; min-height: 24px;">
                    <div style="position:absolute; left:0; top:2px; bottom:2px; width:${yieldPct}%; background:${barColor}; border-radius:2px; z-index:0;"></div>
                    <span style="position:relative; z-index:1; padding-left:4px; ${yieldStyle} font-family:var(--font-mono);">${Number(s.div_yield).toFixed(2)}%</span>
                </div>`;

                const peVal = Number(s.pe);
                const peStyle = peVal < 10
                    ? `<span style="color:#60a5fa;background:rgba(96,165,250,0.1);padding:2px 6px;border-radius:4px;font-weight:600;">${peVal.toFixed(1)}</span>`
                    : `<span style="color:var(--text-secondary);">${peVal.toFixed(1)}</span>`;

                const pbVal = Number(s.pb);
                const pbStyle = pbVal < 1.0
                    ? `<span style="color:#c084fc;background:rgba(192,132,252,0.1);padding:2px 6px;border-radius:4px;font-weight:600;">${pbVal.toFixed(2)}</span>`
                    : `<span style="color:var(--text-secondary);">${pbVal.toFixed(2)}</span>`;

                const mvStr = Number(s.mv).toLocaleString('en-US', {minimumFractionDigits: 1, maximumFractionDigits: 1});
                return `<tr style="transition:background 0.2s; cursor:pointer;" onmouseover="this.style.background='rgba(255,255,255,0.02)'" onmouseout="this.style.background='transparent'">
                    <td style="padding-left:16px;">${assetCell}</td>
                    <td style="padding:4px;">${yieldCell}</td>
                    <td style="font-family:var(--font-mono);">${peStyle}</td>
                    <td style="font-family:var(--font-mono);">${pbStyle}</td>
                    <td style="font-family:var(--font-mono);color:var(--text-primary);font-weight:600;">${mvStr}</td>
                </tr>`;
            }).join('') + `</tbody></table></div>`;

        el.innerHTML = tableHtml;
    } catch (e) { console.error('Dividend:', e); }
}
async function initGenAI() {
    const tw = document.getElementById('ai-text');
    const ind = document.getElementById('ai-indicator');
    if (!tw || !ind) return;
    try {
        const data = await fetchJsonWithRetry('/api/macro/ai_insight');

        ind.innerText = "DeepSeek 官方智算中心推演完成";
        ind.style.color = "#7000FF";
        ind.style.borderColor = "#7000FF";
        ind.style.boxShadow = `0 0 10px rgba(112, 0, 255, 0.4)`;

        tw.innerHTML = renderSafeAIInsight(data.insight);
        tw.style.opacity = 0;
        tw.style.animation = "fadeIn 1s forwards";

    } catch (e) {
        console.error("Gen-AI failed:", e);
        tw.innerText = "LLM connection timed out. Check network or API key.";
        ind.innerText = "鎺ㄦ紨澶辫触";
        ind.style.color = "#ef4444";
    }
}
async function initBacktest() {
    const chartDom = document.getElementById('backtest-chart');
    const ind = document.getElementById('bt-indicator');
    if (!chartDom || !ind) return;

    let myChart = echarts.init(chartDom);

    try {
        const data = await fetchJsonWithRetry('/api/macro/backtest');

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
                weightsSpan.innerText = `EQ ${state.w_spy}% | FI ${state.w_tlt}% | GLD ${state.w_gld}% | CASH ${state.w_cash}%`;

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

        ind.innerText = "18 骞村叏閲忓洖娴嬪凡瀹屾垚";
        ind.className = "status-indicator live";

        const option = {
            backgroundColor: 'transparent',
            tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
            legend: {
                data: ['AlphaCore 瀵瑰啿绛栫暐', 'Benchmark (SPY)'],
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
                    name: 'AlphaCore 瀵瑰啿绛栫暐',
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
        chartDom.innerHTML = "<div style='color:#ef4444; padding:20px;'>Local time-series database connection failed.</div>";
    }
}
// --- Terminal UI Controls ---
function switchView(viewId) {
    // Compatibility redirect for legacy view-simu / simu routes to the portfolio sandbox.
    if (viewId === 'view-simu' || viewId === 'simu') {
        viewId = 'view-portfolio';
        setTimeout(() => {
            if (typeof switchSandboxTab === 'function') {
                switchSandboxTab('tab-rebalance-sandbox');
            }
        }, 20);
    }

    // Compatibility redirect for legacy view-ai / ai routes to decision hub.
    if (viewId === 'view-ai' || viewId === 'ai') {
        viewId = 'view-hub';
    }
    const panel = document.getElementById(viewId);
    if (!panel) return false;
    if (window.location.hash !== `#${viewId}` && window.history && window.history.replaceState) {
        window.history.replaceState(null, '', `#${viewId}`);
    }
    document.body.classList.remove('route-hash-active');
    document.querySelectorAll('.view-panel').forEach(p => {
        p.classList.remove('active');
        p.classList.remove('route-active-view');
        p.style.display = 'none';
    });
    document.querySelectorAll('.terminal-nav a').forEach(a => a.classList.remove('active'));

    panel.classList.add('active');
    panel.classList.add('route-active-view');
    panel.style.display = 'block';
    document.body.classList.add('route-hash-active');
    const main = document.querySelector('.terminal-main');
    const resetScroll = () => {
        if (main) main.scrollTop = 0;
        window.scrollTo(0, 0);
    };
    resetScroll();
    requestAnimationFrame(resetScroll);
    setTimeout(resetScroll, 50);
    const navLink = document.querySelector(`.terminal-nav a[href='#${viewId}']`);
    if (navLink) navLink.classList.add('active');

    // Resize charts in the active view
    setTimeout(() => {
        if (window.echarts) {
            const doms = panel.querySelectorAll('.chart-container, [id^="chart-"], [id$="-chart"]');
            doms.forEach(dom => {
                const chart = echarts.getInstanceByDom(dom);
                if (chart) chart.resize();
            });
        }
    }, 50);
    if (viewId === 'view-portfolio') {
        // Entering portfolio sandbox: resize charts in the active sandbox tab.
        setTimeout(() => {
            const activePanel = document.querySelector('.sandbox-tab-panel:not([style*="display:none"]):not([style*="display: none"])');
            if (activePanel && window.echarts) {
                const chartDoms = activePanel.querySelectorAll('.chart-container, [id^="chart-"], [id$="-chart"]');
                chartDoms.forEach(dom => {
                    const chart = echarts.getInstanceByDom(dom);
                    if (chart) chart.resize();
                });
            }
        }, 80);

        if (typeof initPortfolioLedger === 'function') {
            initPortfolioLedger();
        }
    } else if (viewId === 'view-risk') {
        if (typeof initFactorRisk === 'function') {
            initFactorRisk();
        }
    } else if (viewId === 'view-stress') {
        if (typeof initStressTesting === 'function') {
            initStressTesting();
        }
    } else if (viewId === 'view-strategy') {
        if (typeof initStrategyLab === 'function') {
            initStrategyLab();
        }
    } else if (viewId === 'view-hub') {
        if (typeof initDecisionHub === 'function') {
            initDecisionHub();
        }
        if (typeof initStrategyLab === 'function') {
            initStrategyLab();
        }
    }
    return false;
}
window.switchView = switchView;
// Portfolio sandbox sub-tab controls
window.switchSandboxTab = function(tabId) {
    const targetPanel = document.getElementById(tabId);
    if (!targetPanel) return;
    // Hide all sandbox tab panels
    document.querySelectorAll('.sandbox-tab-panel').forEach(panel => {
        panel.style.display = 'none';
    });

    // Show the selected sandbox sub-panel.
    targetPanel.style.display = 'block';

    // Reset tab navigation buttons.
    document.querySelectorAll('.sandbox-tab-btn').forEach(btn => {
        btn.classList.remove('active');
        btn.style.background = 'transparent';
        btn.style.color = 'var(--text-secondary)';
        btn.style.borderColor = 'transparent';
        btn.style.boxShadow = 'none';
    });

    // Highlight the tab that owns the selected panel.
    const activeBtn = Array.from(document.querySelectorAll('.sandbox-tab-btn')).find(btn => {
        return btn.dataset.tab === tabId;
    });
    if (activeBtn) {
        activeBtn.classList.add('active');
        activeBtn.style.background = 'rgba(0, 255, 204, 0.08)';
        activeBtn.style.color = '#00ffcc';
        activeBtn.style.borderColor = 'rgba(0, 255, 204, 0.3)';
        activeBtn.style.boxShadow = '0 0 10px rgba(0, 255, 204, 0.1)';
    }
    // Redraw ECharts according to active tab
    setTimeout(() => {
        if (window.echarts) {
            const chartDoms = targetPanel.querySelectorAll('.chart-container, [id^="chart-"], [id$="-chart"]');
            chartDoms.forEach(dom => {
                const chart = echarts.getInstanceByDom(dom);
                if (chart) chart.resize();
            });
        }
    }, 50);
        // Reload and refresh data as needed
    if (tabId === 'tab-static-holdings') {
        if (typeof initPortfolioLedger === 'function') {
            initPortfolioLedger();
        }
    } else if (tabId === 'tab-rebalance-sandbox') {
        if (typeof initSimuSandbox === 'function') {
            initSimuSandbox();
        }
    } else if (tabId === 'tab-crisis-replication') {
        if (typeof initHistoricalScenarios === 'function') {
            initHistoricalScenarios();
        }
    }
};
window.currentRotationPeriod = 'ret_20d';
window.setRotationPeriod = function(period, evt) {
    window.currentRotationPeriod = period;
    document.querySelectorAll('#global-rotation-controls button').forEach(btn => btn.classList.remove('is-active'));
    const target = evt?.currentTarget || evt?.target || window.event?.target;
    if (target) target.classList.add('is-active');
    // We assume initRotationPanels or similar handles reading window.currentRotationPeriod
    if(typeof initRotationPanels === 'function') {
        initRotationPanels();
    } else if (typeof initSectorRotation === 'function') {
        initSectorRotation(); // Fallback
    }
}
function getRoutableViewFromHash() {
    const initialView = decodeURIComponent(window.location.hash || '').replace(/^#/, '');
    const panel = initialView ? document.getElementById(initialView) : null;
    return panel && panel.classList.contains('view-panel') ? initialView : null;
}
function activateViewFromHash() {
    const initialView = getRoutableViewFromHash();
    if (initialView) switchView(initialView);
}
function activateInitialView() {
    activateViewFromHash();
}
// Institutional, portfolio, execution, and scenario panel handlers live in static/js/panels/institutional.js.
