// main.js - Logic and Chart Initialization

document.addEventListener("DOMContentLoaded", () => {
    const totalPanels = 21;
    let loadedCount = 0;
    const updateProgress = () => {
        loadedCount++;
        const fi = document.getElementById('freshness-indicator');
        if (fi && loadedCount <= totalPanels) {
            fi.textContent = `加载面板中... ${loadedCount}/${totalPanels}`;
            if (loadedCount >= totalPanels) fi.textContent = '● 数据正常';
        }
    };
    const track = (fn) => async () => { try { await fn(); } catch(e) {} finally { updateProgress(); } };

    // Phase 0: immediate — Dashboard + core macro
    scheduleInitializers([
        [track(initDashboard), 0],
        [track(initERPChart), 80],
        [track(initSpreadChart), 160],
        [track(initSignals), 240],
        // Phase 1: 0.5-1.5s — primary panels
        [track(initYieldCurve), 500],
        [track(initAllocationChart), 650],
        [track(initCorrelationChart), 800],
        [track(initPortfolio), 300],
        [track(initChinaMacro), 1000],
        [track(initSurpriseIndex), 1050],
        [track(initMarginMonitor), 1100],
        [track(initDividendLeaders), 1150],
        [track(initAlertCenter), 1000],
        [track(initMarketBreadth), 1100],
        [track(initFedProb), 1200],
        // Phase 2: 1.5-2.5s — visual panels
        [track(initMonteCarloChart), 1500],
        [track(initGlobalAssets), 1700],
        [track(initValuation), 1900],
        [track(initScenarioTest), 2100],
        // Phase 3: 2.5-4s — heavy computation
        [track(initEfficientFrontier), 2500],
        [track(initRotationPanels), 2800],
        [track(initBacktest), 3200],
        // Phase 4: 4s+ — institutional blocks
        [track(initInstitutionalDecision), 4000],
        [track(initPortfolioLedger), 4500],
        [track(initGenAI), 5000],
    ]);

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

function scheduleInitializers(jobs) {
    jobs.forEach(([job, delay]) => {
        window.setTimeout(() => {
            try {
                job();
            } catch (error) {
                console.error('Initializer failed:', error);
            }
        }, delay);
    });
}

async function initDashboard() {
    try {
        const d = await fetchJsonWithRetry('/api/macro/decision');

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
        const fi = document.getElementById('freshness-indicator');
        if (fi) {
            const degraded = hd.degraded_sources || [];
            const hitPct = Math.round((hd.cache?.hit_ratio || 0) * 100);
            const circuitOpen = hd.circuit ? Object.entries(hd.circuit).filter(([,v])=>v.state==='open').map(([k])=>k) : [];
            if (circuitOpen.length > 0) {
                fi.textContent = `🔴 Circuit open: ${circuitOpen.join(',')} | cache hit ${hitPct}%`;
                fi.style.color = '#ef4444';
            } else if (degraded.length > 0) {
                fi.textContent = `⚠️ Degraded: ${degraded.join(', ')} | cache hit ${hitPct}%`;
                fi.style.color = '#fbbf24';
            } else {
                fi.textContent = `● Healthy | cache hit ${hitPct}% | alerts ${hd.active_alerts}`;
                fi.style.color = '#4ade80';
            }
        }
    } catch (e) {
        console.error('Health check failed:', e);
    }
}

// ── shared panel helper ──────────────────────────────────
function clearChildren(el) {
    while (el.firstChild) {
        el.removeChild(el.firstChild);
    }
}

function safeCssColor(value, fallback = '#94a3b8') {
    const text = String(value || '').trim();
    return /^#[0-9a-fA-F]{3,8}$/.test(text) ? text : fallback;
}

function safeLevelClass(value) {
    const level = String(value || 'info').toLowerCase();
    return ['info', 'warning', 'warn', 'error', 'critical'].includes(level) ? level : 'info';
}

function appendTextBlock(parent, text, styles = {}) {
    const el = document.createElement('div');
    el.textContent = text ?? '';
    Object.assign(el.style, styles);
    parent.appendChild(el);
    return el;
}

function renderAlertList(list, warnings) {
    clearChildren(list);
    (warnings || []).forEach(warning => {
        const row = document.createElement('div');
        row.className = `alert-${safeLevelClass(warning.level)}`;
        row.textContent = `> ${warning.text || ''}`;
        list.appendChild(row);
    });
}

function renderScenarioMetric(parent, label, value, color) {
    const box = document.createElement('div');
    appendTextBlock(box, label, { fontSize: '0.65rem', color: '#94a3b8' });
    appendTextBlock(box, value, {
        fontFamily: 'var(--font-mono)',
        fontSize: '1.2rem',
        fontWeight: 'bold',
        color,
    });
    parent.appendChild(box);
}

function renderScenarioGrid(grid, scenarios) {
    clearChildren(grid);
    (scenarios || []).forEach(scenario => {
        const color = safeCssColor(scenario.color);
        const portRet = Number(scenario.port_ret || 0);
        const benchRet = Number(scenario.bench_ret || 0);
        const isWin = portRet > benchRet;
        const beat = (portRet - benchRet).toFixed(1);

        const card = document.createElement('div');
        Object.assign(card.style, {
            background: 'rgba(255,255,255,0.02)',
            border: `1px solid ${color}40`,
            borderRadius: '8px',
            padding: '16px',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
        });

        appendTextBlock(card, scenario.name || '--', { fontSize: '0.95rem', fontWeight: 'bold', color: '#e2e8f0' });
        appendTextBlock(card, scenario.period || '--', { fontSize: '0.7rem', color: '#94a3b8' });
        appendTextBlock(card, scenario.desc || '', { fontSize: '0.75rem', color: '#64748b', lineHeight: '1.5' });

        const metrics = document.createElement('div');
        Object.assign(metrics.style, {
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '8px',
            marginTop: '5px',
            paddingTop: '10px',
            borderTop: '1px solid rgba(255,255,255,0.05)',
        });
        renderScenarioMetric(metrics, 'Strategy return', `${portRet}%`, color);
        renderScenarioMetric(metrics, 'Benchmark return', `${benchRet}%`, '#ef4444');
        card.appendChild(metrics);

        appendTextBlock(card, `Strategy ${isWin ? 'leads' : 'lags'} benchmark ${isWin ? '+' : ''}${beat}%`, {
            fontSize: '0.7rem',
            color: isWin ? '#4ade80' : '#ef4444',
            fontWeight: '600',
        });
        appendTextBlock(card, scenario.verdict || '', {
            fontSize: '0.7rem',
            padding: '3px 8px',
            background: `${color}20`,
            borderRadius: '4px',
            color,
            alignSelf: 'flex-start',
        });

        grid.appendChild(card);
    });
}

function formatTopExposure(exposure) {
    const rows = Object.entries(exposure || {})
        .map(([name, weight]) => [name, Number(weight) || 0])
        .filter(([, weight]) => weight > 0)
        .sort((a, b) => b[1] - a[1]);

    if (!rows.length) return '--';

    return rows
        .slice(0, 2)
        .map(([name, weight]) => `${name} ${Math.round(weight * 100)}%`)
        .join(' / ');
}

function formatReasonCodes(reasonCodes) {
    const codes = (reasonCodes || []).map(item => item.code).filter(Boolean);
    if (!codes.length) return '--';
    return codes.slice(0, 3).join(' / ');
}

function shortHash(value) {
    const text = String(value || '');
    return text ? text.slice(0, 12) : '--';
}

function formatTopFactor(factorRisk) {
    const top = factorRisk?.top_factor || {};
    if (!top.factor_name) return '--';
    const exposure = Number(top.exposure || 0);
    return `${top.factor_group}:${top.factor_name} ${Math.round(exposure * 100)}%`;
}

function formatLargestActive(activeRisk) {
    const row = (activeRisk?.largest_active_exposures || [])[0];
    if (!row) return '--';
    return `${row.symbol} ${Math.round((row.active_weight || 0) * 1000) / 10}%`;
}

function formatComplianceIssues(compliance) {
    const violations = compliance?.violations || [];
    const warnings = compliance?.warnings || [];
    const issues = violations.length ? violations : warnings;
    return issues.length ? issues.slice(0, 3).join(' / ') : 'clear';
}

function formatAttribution(attribution) {
    if (!attribution) return '--';
    const decision = Number(attribution.decision_effect || 0);
    const allocation = Number(attribution.allocation_effect || 0);
    const selection = Number(attribution.selection_effect || 0);
    return `D ${Math.round(decision * 10000) / 100}bp / A ${Math.round(allocation * 10000) / 100}bp / S ${Math.round(selection * 10000) / 100}bp`;
}

function formatEvidence(evidenceChain) {
    const items = evidenceChain?.items || [];
    const weak = items.filter(item => item.direction === 'below_threshold');
    const sourceMode = evidenceChain?.source_quality?.mode || 'unknown';
    return `${sourceMode} / ${weak.length} watch`;
}

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

    // ── Zone indicator ──
    const mStatus = model.status || 'unknown';
    const zone = document.getElementById('allocation-model-zone');
    if (zone) {
        let zt, zb, zc, za;
        if (mStatus === 'allow') {
            zt='● 允许调仓'; zb='rgba(34,197,94,0.12)'; zc='#22c55e'; za='风险预算充足，建议按信号执行权重调整';
        } else if (mStatus === 'limited') {
            zt='● 分批执行'; zb='rgba(251,191,36,0.12)'; zc='#fbbf24'; za='合规警告或风险接近上限，建议分步执行';
        } else {
            zt='● 观察不调'; zb='rgba(239,68,68,0.12)'; zc='#ef4444'; za='合规拦截或压力恶化，暂停调仓等待改善';
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
    if (!trades.length) { el.innerHTML = '<div style="color:#64748b;font-size:0.75rem;padding:8px;">无建议调仓</div>'; return; }
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
    "Proceed with proposed rebalance.": "准予执行该调仓计划 (PROCEED)",
    "Do not execute the proposed rebalance.": "拒绝/中止该调仓计划 (BLOCK)",
    "Wait for better execution window.": "建议暂缓执行寻找更佳窗口 (WAIT)",
    "Requires manual review.": "需要人工风控介入复核 (REVIEW)"
};

const REASON_ZH = {
    "scenario_loss_high": "尾部风险超限 (Scenario Loss)",
    "constraint_cash_below_minimum": "现金流耗竭警告 (Cash Minimum)",
    "portfolio_china_exposure": "亚太敞口异常暴露 (China Exposure)",
    "concentration_limit_breach": "单一资产集中度超限 (Concentration)",
    "factor_volatility_high": "组合波动率因子过高 (Factor Volatility)",
    "compliance_passed": "各项合规/风控指标均达标 (Compliance Passed)"
};

async function initInstitutionalDecision() {
    const panel = document.getElementById('view-institutional');
    if (!panel) return;

    try {
        const data = await fetchJsonWithRetry('/api/institutional/decision');
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

        // Score Gauge
        const score = ticket.score ?? 0;
        const perc = score / 100;
        const arc = document.getElementById('decision-gauge-arc');
        if (arc) {
            const len = 327 * Math.max(0.02, perc);
            arc.setAttribute('stroke-dasharray', `${len} ${327 - len}`);
            const gaugeColor = score >= 80 ? '#22c55e' : score >= 60 ? '#fbbf24' : score >= 40 ? '#f97316' : '#ef4444';
            arc.setAttribute('stroke', gaugeColor);
        }
        const gtxt = document.getElementById('decision-gauge-text');
        if (gtxt) { gtxt.textContent = score; gtxt.style.color = score >= 80 ? '#22c55e' : score >= 60 ? '#fbbf24' : '#ef4444'; }
        
        // Hero Action
        const actionHero = document.getElementById('decision-action-hero');
        if (actionHero) {
            const actText = action.action || ticket.suggested_action || '--';
            const mappedText = ACTION_ZH[actText] || actText;
            const ticketStatus = ticket.decision_status || '';
            if (ticketStatus === 'allow') actionHero.style.color = '#22c55e';
            else if (ticketStatus === 'observe' || ticketStatus === 'block') actionHero.style.color = '#ef4444';
            else actionHero.style.color = '#fbbf24';
            actionHero.textContent = mappedText;
        }
        
        const reasonHero = document.getElementById('decision-reason-hero');
        if (reasonHero) {
            const codes = explanation.reason_codes || [];
            const driver = explanation.primary_driver?.code || '';
            const text = codes.length 
                ? codes.map(c => { const code = c.code || c; return REASON_ZH[code] || code; }).join('  |  ') 
                : (REASON_ZH[driver] || driver || '--');
            reasonHero.innerHTML = `<span style="color:var(--text-tertiary);">▸</span> <span>${text}</span>`;
        }
        
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
        setFlowText('workbench-largest-active', formatLargestActive(active_risk));

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

function initPanel({url, indicatorId, insightId, onData, onError}) {
    fetchJsonWithRetry(url).then(d=>{
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
        const data = await fetchJsonWithRetry(`/api/macro/${endpoint}`);
        return data;
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
    myChart.showLoading({ text: '拉取期限结构...', color: '#fbbf24', textColor: '#fff', maskColor: 'rgba(20, 20, 25, 0.8)' });

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
        const allocData = await fetchJsonWithRetry('/api/macro/allocation');
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
    myChart.showLoading({ text: '优化计算中...', color: '#7000FF', textColor: '#fff', maskColor: 'rgba(20, 20, 25, 0.8)' });

    try {
        const data = await fetchJsonWithRetry('/api/macro/efficient_frontier');
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
        const data = await fetchJsonWithRetry('/api/macro/scenario');

        ind.innerText = '三情景穿透完成';
        ind.style.color = '#fbbf24';
        ind.style.borderColor = '#fbbf24';
        if (ins) ins.innerText = data.insight;

        renderScenarioGrid(grid, data.scenarios);

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
        const mcData = await fetchJsonWithRetry('/api/macro/montecarlo');
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

const rotationPanelConfigs = [
    {
        domId: 'sector-chart',
        apiUrl: '/api/macro/sector_rotation',
        indicatorId: 'sr-indicator',
        insightId: 'sr-insight',
        successText: '31行业已加载',
        theme: 'default',
    },
    {
        domId: 'theme-chart',
        apiUrl: '/api/macro/theme_rotation',
        indicatorId: 'tr-indicator',
        insightId: 'tr-insight',
        successText: '政策主线已加载',
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
        successText: '全球宽基已加载',
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

    let activePeriod = 'ret_20d';
    let items = [];

    chartDom.innerHTML = '<div style="height:100%; display:flex; align-items:center; justify-content:center; color:#2563eb; font-family:var(--font-mono); font-size:0.9rem;">引擎演算中...</div>';

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

async function fetchJsonWithRetry(url, attempts = 25, delayMs = 1500) {
    let lastError;
    for (let attempt = 1; attempt <= attempts; attempt++) {
        try {
            const response = await fetch(url, { cache: 'no-store' });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const data = await response.json();
            // Handle backend cold cache syncing state
            if (data && data.status === "syncing") {
                console.log(`[Syncing] ${url} is building cache (attempt ${attempt}/${attempts})...`);
                throw new Error("Data syncing");
            }
            return data;
        } catch (error) {
            lastError = error;
            if (attempt < attempts) {
                await sleep(delayMs);
            }
        }
    }
    throw lastError;
}

function sleep(ms) {
    return new Promise(resolve => window.setTimeout(resolve, ms));
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
                    <th style="padding:12px 16px; text-align:left;">ASSET / SECTOR</th>
                    <th style="text-align:left;">MOMENTUM</th>
                    <th style="text-align:center;">TREND PROFILE (5D → 60D)</th>
                </tr>
            </thead>
            <tbody>` +
        items.map(a => {
            const dir = cols.filter(k=>(a[k]||0)>0).length;
            const arrow = dir>=3 ? 'STRONG BUY' : dir>=2 ? 'BUY' : dir<=0 ? 'STRONG SELL' : 'SELL';
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
            indicator.innerText = d.signal || '已更新';
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
            legend: {data:['累计净流入','每日净流入'],textStyle:{color:'#94a3b8'},top:0},
            grid:{left:'3%',right:'4%',top:'16%',bottom:'3%',containLabel:true},
            xAxis:{type:'category',data:cumulative.map(v=>formatTradeDate(v.date)),axisLabel:{color:'#94a3b8'}},
            yAxis:[{type:'value',name:'累计/亿',splitLine:{lineStyle:{color:'rgba(255,255,255,0.05)'}},axisLabel:{color:'#94a3b8'}},
                   {type:'value',name:'单日/亿',axisLabel:{color:'#94a3b8'}}],
            series:[
                {name:'累计净流入',type:'line',data:cumulative.map(v=>v.value),smooth:true,symbol:'none',lineStyle:{width:2,color:'#2563eb'},areaStyle:{color:'rgba(37,99,235,0.12)'}},
                {name:'每日净流入',type:'bar',yAxisIndex:1,data:flow.map(v=>({value:v.value,itemStyle:{color:v.value>=0?'#16a34a':'#dc2626'}})),barMaxWidth:14},
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
        // Global assets takes ~21s to warm cache due to 14 sequential API calls (1.5s rate limit each)
        const d=await fetchJsonWithRetry('/api/macro/global_assets', 20, 1500);

        // ── Backend composite sentiment ──
        const sig = d.composite || {};
        document.getElementById('ga-indicator').innerHTML =
            `已更新 ${d.updated} <span style="display:inline-flex;align-items:center;gap:4px;margin-left:8px;padding:2px 10px;background:${sig.color||'#64748b'}20;border:1px solid ${sig.color||'#64748b'}30;border-radius:4px;font-size:0.7rem;font-weight:600;color:${sig.color||'#64748b'};box-shadow: 0 0 8px ${sig.color||'#64748b'}40;">${sig.zone||'--'} ${sig.pct_up||0}%↑</span>`;

        if (!d.assets || !d.assets.length) { el.innerHTML='<div style="color:#64748b;padding:12px;">暂无数据</div>'; return; }
        const cols=['daily','weekly','monthly','quarterly','ytd'];
        const colLabels=['1D','1W','1M','1Q','YTD'];
        
        // Calculate global max absolute return for proper cross-asset visual scaling
        const globalMaxAbs = Math.max(...d.assets.flatMap(a => cols.map(k => Math.abs(Number(a[k]||0)))), 0.01);

        const tableHtml = `<div style="overflow-y:auto; height:100%; max-height: 480px; border:1px solid rgba(255,255,255,0.08); border-radius:6px; background:rgba(0,0,0,0.2); box-shadow:inset 0 0 20px rgba(0,0,0,0.5);">
            <table class="institutional-table" style="margin:0; width:100%;">
                <thead style="position:sticky; top:0; z-index:10; background:rgba(15,23,42,0.95); backdrop-filter:blur(8px); border-bottom:1px solid rgba(255,255,255,0.1);">
                    <tr>
                        <th style="padding:12px 16px; text-align:left;">ASSET</th>
                        <th style="text-align:left;">CLASS</th>
                        <th style="text-align:left;">MOMENTUM</th>
                        <th style="text-align:center;">TREND PROFILE (1D → YTD)</th>
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
    }catch(e){console.error('Global assets:',e); el.innerHTML='<div style="color:#ef4444;padding:12px;font-family:var(--font-mono);">[SYS_ERR] 数据流断开或触发断路器保护</div>';}
}

async function initValuation() {
    const gd=document.getElementById('valuation-grid'); if(!gd)return;
    try{
        const d=await fetchJsonWithRetry('/api/macro/valuation');
        document.getElementById('val-indicator').innerText='已更新 '+d.updated;

        // ── Composite Zone Indicator ──
        const items = d.indices || [];
        const extreme = items.filter(i => (i.pe_pct||i.price_pct||0) > 95).length;
        const high = items.filter(i => (i.pe_pct||i.price_pct||0) > 70).length;
        const total = items.length;
        let zt, zb, zc, za;
        if (extreme >= 2 || (high/total) > 0.6) {
            zt='● 整体高估'; zb='rgba(239,68,68,0.12)'; zc='#ef4444';
            za=`${high}/${total} 标的在 70% 分位以上${extreme>0?'，'+extreme+'个极端泡沫':''}`;
        } else if (high/total > 0.3) {
            zt='● 估值偏高'; zb='rgba(249,115,22,0.12)'; zc='#f97316';
            za=`${high}/${total} 标的在 70% 分位以上`;
        } else {
            zt='● 估值合理'; zb='rgba(34,197,94,0.12)'; zc='#22c55e';
            za=`仅 ${high}/${total} 标的在 70% 分位以上`;
        }
        document.getElementById('val-insight').innerHTML =
            `${d.insight}<br><span style="display:inline-flex;align-items:center;gap:6px;margin-top:4px;padding:4px 12px;background:${zb};border:1px solid ${zc}30;border-radius:4px;font-size:0.72rem;font-weight:600;color:${zc};">${zt} ${za}</span>`;

        gd.innerHTML=items.map(i=>{
            const isExtreme = (i.pe_pct||i.price_pct||0) > 95;
            const extremeBorder = isExtreme ? 'border-color:rgba(239,68,68,0.4)!important;box-shadow:0 0 12px rgba(239,68,68,0.15);' : '';
            if (i.metric_type === 'price') {
                const pct = Number(i.price_pct || 0);
                const barW = Math.max(2, pct);
                const isExt2 = pct > 95;
                const extStyle = isExt2 ? 'border-color:rgba(239,68,68,0.4)!important;box-shadow:0 0 12px rgba(239,68,68,0.15);animation:alertPulse 3s infinite;' : '';
                return `<div style="background:rgba(255,255,255,0.02);${extStyle}border:1px solid rgba(255,255,255,0.05);border-radius:8px;padding:16px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;gap:8px;">
                        <div style="font-weight:bold;color:#e2e8f0;font-size:0.95rem;">${i.name}${isExt2?' <span style="color:#ef4444;font-size:0.6rem;">⚠极端</span>':''}</div>
                        <div style="font-size:0.65rem;color:#64748b;font-family:var(--font-mono);border:1px solid rgba(255,255,255,0.08);border-radius:4px;padding:2px 6px;">${i.category || 'ETF'}</div>
                    </div>
                    <div style="display:flex;justify-content:space-between;font-size:0.75rem;color:#94a3b8;margin-bottom:4px;"><span>价格 ${i.price_current}</span><span>分位 ${pct}% ${i.price_signal}</span></div>
                    <div style="height:10px;background:rgba(255,255,255,0.05);border-radius:5px;overflow:hidden;margin-bottom:12px;">
                        <div style="width:${barW}%;height:100%;background:${i.color};border-radius:5px;transition:width 0.6s;"></div>
                    </div>
                    <div style="font-size:0.72rem;color:#64748b;line-height:1.5;">口径：近 10 年 ETF 收盘价历史分位，不等同于底层指数 PE/PB。</div>
                </div>`;
            }
            const pct=i.pe_pct; const barW=Math.max(2,pct);
            const isExt3 = pct > 95;
            const extStyle3 = isExt3 ? 'border-color:rgba(239,68,68,0.4)!important;box-shadow:0 0 12px rgba(239,68,68,0.15);animation:alertPulse 3s infinite;' : '';
            return `<div style="background:rgba(255,255,255,0.02);${extStyle3}border:1px solid rgba(255,255,255,0.05);border-radius:8px;padding:16px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;gap:8px;">
                    <div style="font-weight:bold;color:#e2e8f0;font-size:0.95rem;">${i.name}${isExt3?' <span style="color:#ef4444;font-size:0.6rem;">⚠极端</span>':''}</div>
                    <div style="font-size:0.65rem;color:#64748b;font-family:var(--font-mono);border:1px solid rgba(255,255,255,0.08);border-radius:4px;padding:2px 6px;">${i.category || 'INDEX'}</div>
                </div>
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

async function initAlertCenter() {
    const el = document.getElementById('alert-rules-list');
    if (!el) return;
    const ind = document.getElementById('ac-indicator');
    try {
        const d = await fetchJsonWithRetry('/api/alerts/rules');
        const rules = d.rules || [];
        const triggered = rules.filter(r => r.last_triggered > Date.now()/1000 - 3600).length;
        if (ind) ind.innerText = triggered ? `⚠ ${triggered} triggered` : '监控中';
        el.innerHTML = rules.map(r => {
            const opLabel = {gt: '>', lt: '<', gte: '≥', lte: '≤'}[r.operator] || r.operator;
            return `<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;border-bottom:1px solid rgba(255,255,255,0.04);font-size:0.78rem;">
                <div style="display:flex;align-items:center;gap:10px;">
                    <span style="color:${r.enabled?'#22c55e':'#64748b'};font-size:0.65rem;">${r.enabled?'●':'○'}</span>
                    <span style="color:#e2e8f0;">${r.name}</span>
                    <span style="color:#64748b;font-family:var(--font-mono);font-size:0.68rem;">${opLabel} ${r.threshold}</span>
                    ${r.push_wx ? '<span style="color:#7000FF;font-size:0.6rem;">📱微信</span>' : ''}
                </div>
                <span style="color:${r.last_triggered>Date.now()/1000-3600?'#ef4444':'#64748b'};font-size:0.65rem;">${r.last_triggered>Date.now()/1000-3600?'最近触发':'待命中'}</span>
            </div>`;
        }).join('');
    } catch (e) {
        console.error('Alert center:', e);
    }
}

async function initSurpriseIndex() {
    const cd = document.getElementById('surprise-chart');
    if (!cd) return;
    const mc = echarts.init(cd, 'dark');
    try {
        const d = await fetchJsonWithRetry('/api/macro/surprise_index');
        document.getElementById('si-indicator').innerText = d.signal || '--';
        document.getElementById('si-insight').innerText = d.insight || '--';
        mc.setOption({
            backgroundColor: 'transparent',
            tooltip: { trigger: 'axis' },
            grid: { left: '3%', right: '4%', top: '5%', bottom: '3%', containLabel: true },
            xAxis: { type: 'category', data: d.dates, axisLabel: { color: '#94a3b8' } },
            yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }, axisLabel: { color: '#94a3b8' } },
            series: [{
                name: '累计意外指数', type: 'line', data: d.values, smooth: true, symbol: 'none',
                lineStyle: { width: 2, color: d.color || '#fbbf24' },
                areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: (d.color || '#fbbf24') + '40' }, { offset: 1, color: 'rgba(0,0,0,0)' }
                ]) },
                markLine: { silent: true, data: [{ yAxis: 0 }], lineStyle: { color: '#64748b', type: 'dashed' } }
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
        document.getElementById('pf-total').textContent = `总市值 ¥${d.total_value.toLocaleString()} | 成本 ¥${d.total_cost.toLocaleString()}`;
        const pnlEl = document.getElementById('pf-pnl');
        pnlEl.textContent = `${d.total_pnl >= 0 ? '+' : ''}¥${d.total_pnl.toLocaleString()} (${d.total_pnl_pct > 0 ? '+' : ''}${d.total_pnl_pct}%)`;
        pnlEl.style.color = d.total_pnl >= 0 ? '#22c55e' : '#ef4444';
        document.getElementById('portfolio-table').innerHTML = `<table class="institutional-table"><thead><tr><th>标的</th><th>持仓</th><th>成本</th><th>现价</th><th>市值</th><th>盈亏</th></tr></thead><tbody>` +
            d.holdings.map(h => `<tr><td>${h.name||h.symbol}</td><td>${h.qty}</td><td>${h.cost}</td><td>${h.current}</td><td>${h.market_value.toLocaleString()}</td><td style="color:${h.pnl_pct>=0?'#22c55e':'#ef4444'};font-weight:600;">${h.pnl_pct>0?'+':''}${h.pnl_pct}%</td></tr>`).join('') + '</tbody></table>';
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
            `两融余额 <span style="color:var(--text-primary);font-family:var(--font-mono);font-weight:700;">${d.total}亿</span> · ` +
            `融资 <span style="color:#f97316;font-family:var(--font-mono);font-weight:700;">${d.current_rz}亿</span> · ` +
            `融券 <span style="color:#ef4444;font-family:var(--font-mono);font-weight:700;">${d.current_rq}亿</span> · ` +
            `券资比 <span style="color:var(--text-secondary);font-family:var(--font-mono);">${d.ratio}%</span>`;
            
        mc.setOption({
            backgroundColor: 'transparent',
            tooltip: { trigger: 'axis', axisPointer: { type: 'cross', label: { backgroundColor: '#1e293b' } } },
            legend: { data: ['融资余额(亿)', '融券余额(亿)'], textStyle: { color: '#94a3b8' }, top: 0, right: 0 },
            grid: { left: '2%', right: '2%', top: '15%', bottom: '3%', containLabel: true },
            xAxis: { 
                type: 'category', data: d.dates, 
                axisLabel: { color: '#64748b', fontSize: 10 },
                axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } }
            },
            yAxis: [
                { 
                    type: 'value', name: '融资(亿)', nameTextStyle: { color: '#64748b', fontSize: 10 },
                    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.03)', type: 'dashed' } },
                    axisLabel: { color: '#94a3b8', fontSize: 10 },
                    scale: true
                },
                { 
                    type: 'value', name: '融券(亿)', nameTextStyle: { color: '#64748b', fontSize: 10 },
                    splitLine: { show: false },
                    axisLabel: { color: '#94a3b8', fontSize: 10 },
                    scale: true
                }
            ],
            series: [
                { 
                    name: '融资余额(亿)', type: 'line', yAxisIndex: 0,
                    data: d.rz_balance, symbol: 'none', smooth: true,
                    lineStyle: { color: '#f97316', width: 2 },
                    areaStyle: { 
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{offset: 0, color: 'rgba(249,115,22,0.3)'},{offset: 1, color: 'rgba(0,0,0,0)'}])
                    }
                },
                { 
                    name: '融券余额(亿)', type: 'bar', yAxisIndex: 1,
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
                    <tr><th style="padding-left:16px;">ASSET</th><th>YIELD</th><th>PE</th><th>PB</th><th>MKT CAP(亿)</th></tr>
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
        tw.innerText = "大模型连接超时，请检查网络或 API Key。";
        ind.innerText = "推演失败";
        ind.style.color = "#ef4444";
    }
}

function escapeHTML(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    })[char]);
}

function renderSafeAIInsight(insight) {
    const markdownHTML = window.marked ? marked.parse(String(insight || '')) : escapeHTML(insight);
    const highlightedHTML = markdownHTML
        .replace(/(清仓|风险|平仓|双杀|警告)/g, '<span class="ai-keyword-risk">$1</span>')
        .replace(/(做多|看涨|买入|正收益)/g, '<span class="ai-keyword-positive">$1</span>')
        .replace(/(VIX|10Y|DXY|SPY|TLT)/g, '<span class="ai-keyword-ticker">$1</span>');

    if (!window.DOMPurify) {
        return escapeHTML(insight);
    }

    return DOMPurify.sanitize(highlightedHTML);
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


// --- Terminal UI Controls ---
function switchView(viewId) {
    document.querySelectorAll('.view-panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.terminal-nav a').forEach(a => a.classList.remove('active'));
    document.getElementById(viewId).classList.add('active');
    document.querySelector(`.terminal-nav a[href='#${viewId}']`).classList.add('active');
    
    // Resize charts in the active view
    setTimeout(() => {
        if(window.echarts) {
            const doms = document.getElementById(viewId).querySelectorAll('.chart-container');
            doms.forEach(dom => {
                const chart = echarts.getInstanceByDom(dom);
                if (chart) chart.resize();
            });
        }
    }, 50);

    if (viewId === 'view-simu') {
        if (typeof initSimuSandbox === 'function') {
            initSimuSandbox();
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
        initStrategyLab();
    } else if (viewId === 'view-hub') {
        initDecisionHub();
    
        if (typeof initStrategyLab === 'function') {
            initStrategyLab();
        }
    }
}

window.currentRotationPeriod = 'ret_20d';
window.setRotationPeriod = function(period) {
    window.currentRotationPeriod = period;
    document.querySelectorAll('#global-rotation-controls button').forEach(btn => btn.classList.remove('is-active'));
    event.target.classList.add('is-active');
    // We assume initRotationPanels or similar handles reading window.currentRotationPeriod
    if(typeof initRotationPanels === 'function') {
        initRotationPanels();
    } else if (typeof initSectorRotation === 'function') {
        initSectorRotation(); // Fallback
    }
}


function importTDX() {
    const fileInput = document.getElementById('tdx-file-input');
    if (fileInput) fileInput.click();
}

async function handleTDXUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    // There are multiple buttons with onclick="importTDX()" (in AUDT and PORT)
    // We'll update all of them visually during the upload
    const btns = document.querySelectorAll('button[onclick="importTDX()"]');
    const originalTexts = [];
    btns.forEach((btn, i) => {
        originalTexts[i] = btn.innerText;
        btn.innerText = '[IMPORTING...]';
        btn.style.opacity = '0.7';
    });
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch('/api/institutional/import_tdx', {
            method: 'POST',
            body: formData
        });
        if (response.ok) {
            btns.forEach((btn, i) => {
                btn.innerText = '[SYNC SUCCESS]';
                btn.style.background = '#22c55e'; // Green
                setTimeout(() => {
                    btn.innerText = originalTexts[i];
                    btn.style.background = 'var(--accent-primary)';
                    btn.style.opacity = '1';
                }, 1500);
            });
            setTimeout(() => {
                // Refresh the panel
                if(document.getElementById('view-institutional').classList.contains('active')) {
                    initInstitutionalDecision();
                }
                if(document.getElementById('view-portfolio').classList.contains('active')) {
                    initPortfolioLedger();
                }
            }, 1500);
        } else {
            throw new Error('Import failed');
        }
    } catch (e) {
        console.error('TDX import error:', e);
        btns.forEach((btn, i) => {
            btn.innerText = '[SYNC FAILED]';
            btn.style.background = '#ef4444'; // Red
            setTimeout(() => {
                btn.innerText = originalTexts[i];
                btn.style.background = 'var(--accent-primary)';
                btn.style.opacity = '1';
            }, 2000);
        });
    }
    
    // Clear input so same file can be selected again if needed
    event.target.value = '';
}

async function initPortfolioLedger() {
    try {
        const data = await fetchJsonWithRetry('/api/institutional/portfolio_raw');
        const positions = data.positions || [];
        
        const mvEl = document.getElementById('port-total-mv');
        const pnlEl = document.getElementById('port-total-pnl');
        const cashEl = document.getElementById('port-total-cash');
        const tbody = document.getElementById('port-ledger-body');
        
        if (!tbody) return;
        
        let totalMv = 0;
        let totalPnl = 0;
        let totalCash = 0;
        
        let rowsHtml = '';
        
        let assetAllocation = {};
        
        // PnL Badge Formatter
        const fmtPnLBadge = (val, pct) => {
            if (val === 0) return `<span style="color:var(--text-tertiary);">-</span>`;
            const color = val > 0 ? '#10b981' : '#f43f5e';
            const sign = val > 0 ? '+' : '';
            const intensity = Math.min(Math.abs(pct) / 10.0, 1); // 10% is max heat
            const bgRgb = val > 0 ? `16,185,129` : `244,63,94`;
            const bgStr = `rgba(${bgRgb}, ${Math.max(intensity * 0.35, 0.1)})`;
            const borderStr = `1px solid rgba(${bgRgb}, ${Math.max(intensity, 0.2)})`;
            
            return `<span style="display:inline-block; background:${bgStr}; color:${color}; font-family:var(--font-mono); font-weight:800; text-align:right; padding:4px 8px; border-radius:4px; border-right:${borderStr}; box-sizing:border-box; text-shadow:0 0 8px rgba(${bgRgb},0.4);">${sign}${val.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})} (${sign}${pct.toFixed(2)}%)</span>`;
        };

        if (positions.length === 0) {
            rowsHtml = '<tr><td colspan="7" style="text-align:center; padding:20px; color:var(--text-tertiary);">No portfolio data available. Sync TDX to begin.</td></tr>';
        } else {
            positions.sort((a, b) => b.market_value - a.market_value);
            
            positions.forEach(pos => {
                totalMv += pos.market_value || 0;
                if (pos.asset_class === 'cash') {
                    totalCash += pos.market_value || 0;
                } else {
                    totalPnl += pos.float_pnl || 0;
                }
                
                // Accumulate asset allocation
                const aclass = pos.asset_class || 'unknown';
                if (!assetAllocation[aclass]) assetAllocation[aclass] = 0;
                assetAllocation[aclass] += (pos.market_value || 0);
                
                // Add a subtle weight bar indicator under the market value
                const weightPct = totalMv > 0 ? ((pos.market_value || 0) / totalMv * 100).toFixed(1) : 0;
                const weightBar = `<div style="width:100%; height:2px; background:rgba(255,255,255,0.05); margin-top:4px; border-radius:1px;"><div style="width:${weightPct}%; height:100%; background:var(--accent-primary); border-radius:1px; box-shadow:0 0 4px var(--accent-primary);"></div></div>`;
                
                rowsHtml += `
                    <tr class="clickable-row" onclick="openActionModal('${pos.symbol}', '${pos.name || ''}', ${pos.quantity || 0}, ${pos.current_price || 0})">
                        <td style="padding-left:16px;">
                            <div style="display:flex; flex-direction:column; gap:2px;">
                                <span style="font-family:var(--font-mono); font-weight:700; color:var(--text-primary); font-size:0.85rem;">${pos.symbol}</span>
                                <span style="font-size:0.7rem; color:var(--text-tertiary);">${pos.name}</span>
                            </div>
                        </td>
                        <td><span style="font-size:0.65rem; padding:2px 6px; border-radius:3px; background:rgba(255,255,255,0.05); color:var(--text-secondary); text-transform:uppercase; letter-spacing:0.5px;">${pos.asset_class}</span></td>
                        <td style="text-align:right; font-family:var(--font-mono);">${(pos.quantity || 0).toLocaleString()}</td>
                        <td style="text-align:right; font-family:var(--font-mono); color:var(--text-tertiary);">${(pos.cost_basis || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                        <td style="text-align:right; font-family:var(--font-mono);">${(pos.current_price || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                        <td style="text-align:right; font-family:var(--font-mono); font-weight:600;">
                            <div>${(pos.market_value || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</div>
                            ${weightBar}
                        </td>
                        <td style="text-align:right; padding-right:16px; font-family:var(--font-mono);">
                            ${fmtPnLBadge(pos.float_pnl || 0, pos.pnl_pct || 0)}
                        </td>
                    </tr>
                `;
            });
        }
        
        if (mvEl) mvEl.textContent = '¥ ' + totalMv.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
        if (pnlEl) {
            pnlEl.textContent = (totalPnl > 0 ? '+' : '') + totalPnl.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
            pnlEl.style.color = totalPnl >= 0 ? '#10b981' : '#f43f5e';
            pnlEl.style.textShadow = totalPnl >= 0 ? '0 0 15px rgba(16,185,129,0.4)' : '0 0 15px rgba(244,63,94,0.4)';
        }
        if (cashEl) cashEl.textContent = '¥ ' + totalCash.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
        
        tbody.innerHTML = rowsHtml;
        
        // --- ECharts L2 Visualization ---
        
        // 1. Asset Allocation Chart
        const allocChartDom = document.getElementById('chart-port-allocation');
        if (allocChartDom && window.echarts) {
            let allocChart = echarts.getInstanceByDom(allocChartDom);
            if (!allocChart) allocChart = echarts.init(allocChartDom);
            
            const assetZH = {
                'EQUITY': '权益资产',
                'BOND': '固定收益',
                'CASH': '现金流',
                'GOLD': '避险金属',
                'COMMODITY': '大宗商品',
                'CRYPTO': '数字资产'
            };
            
            const allocData = Object.keys(assetAllocation).map(key => {
                const k = key.toUpperCase();
                return {
                    name: k,
                    value: assetAllocation[key],
                    name_zh: assetZH[k] || ''
                };
            });
            
            allocChart.setOption({
                tooltip: { 
                    className: 'terminal-hud-tooltip',
                    trigger: 'item',
                    formatter: function(params) {
                        const d = params.data;
                        const zh = d.name_zh ? `<span style="font-size:0.8em; color:var(--text-tertiary); margin-left:8px;">${d.name_zh}</span>` : '';
                        return `<div class="hud-title" style="border-bottom-color:${params.color};">${d.name}${zh}</div>
                                <div class="hud-value" style="color:${params.color};">¥${d.value.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})} <span style="font-size:0.5em; opacity:0.8;">(${params.percent}%)</span></div>`;
                    }
                },
                title: {
                    text: 'ALLOCATION',
                    subtext: '¥' + (totalMv/10000).toFixed(0) + 'w',
                    left: 'center',
                    top: 'center',
                    textStyle: { color: 'var(--text-secondary)', fontSize: 10, fontFamily: 'var(--font-mono)' },
                    subtextStyle: { color: 'var(--accent-primary)', fontSize: 16, fontWeight: 'bold', fontFamily: 'var(--font-mono)', textShadow: '0 0 10px rgba(56,189,248,0.5)' }
                },
                series: [{
                    type: 'pie',
                    radius: ['55%', '80%'],
                    itemStyle: { borderRadius: 4, borderColor: 'rgba(0,0,0,0.5)', borderWidth: 2 },
                    label: { show: false },
                    data: allocData
                }],
                color: ['#00f0ff', '#10b981', '#a855f7', '#f59e0b', '#3b82f6', '#f43f5e']
            });
        }
        
        // 2. Top PnL Attribution Chart
        const attrChartDom = document.getElementById('chart-port-attribution');
        if (attrChartDom && window.echarts) {
            let attrChart = echarts.getInstanceByDom(attrChartDom);
            if (!attrChart) attrChart = echarts.init(attrChartDom);
            
            // Filter out cash and sort by absolute PnL
            const sortedByPnl = [...positions].filter(p => p.asset_class !== 'cash')
                .sort((a,b) => Math.abs(b.float_pnl || 0) - Math.abs(a.float_pnl || 0))
                .slice(0, 5);
            
            attrChart.setOption({
                tooltip: { 
                    className: 'terminal-hud-tooltip',
                    trigger: 'axis', 
                    axisPointer: {type:'shadow'},
                    formatter: function(params) {
                        const p = params[0];
                        return `<div class="hud-title">${p.name}</div><div class="hud-value" style="color:${p.value >= 0 ? '#10b981' : '#f43f5e'}">${p.value >= 0 ? '+' : ''}${p.value.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</div>`;
                    }
                },
                grid: { left: '10%', right: '10%', bottom: '5%', top: '5%', containLabel: true },
                xAxis: { 
                    type: 'value', 
                    splitLine: { show: true, lineStyle: { color: 'rgba(255,255,255,0.05)', type: 'dashed' } }, 
                    axisLabel: { color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', fontSize: 10 },
                    axisLine: { show: true, lineStyle: { color: 'rgba(255,255,255,0.3)', width: 2 } }
                },
                yAxis: { 
                    type: 'category', 
                    data: sortedByPnl.map(p => p.name ? `${p.symbol} ${p.name}` : p.symbol).reverse(), 
                    axisLabel: { color: '#e2e8f0', fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 'bold' },
                    axisLine: { show: false },
                    axisTick: { show: false }
                },
                series: [{
                    name: 'P&L',
                    type: 'bar',
                    barWidth: '45%',
                    data: sortedByPnl.map(p => {
                        const val = p.float_pnl || 0;
                        return {
                            value: val,
                            itemStyle: { 
                                borderRadius: 3,
                                color: new echarts.graphic.LinearGradient(1, 0, 0, 0, [
                                    { offset: 0, color: val >= 0 ? 'rgba(16,185,129,0.9)' : 'rgba(244,63,94,0.3)' },
                                    { offset: 1, color: val >= 0 ? 'rgba(16,185,129,0.3)' : 'rgba(244,63,94,0.9)' }
                                ]),
                                shadowBlur: 10,
                                shadowColor: val >= 0 ? 'rgba(16,185,129,0.4)' : 'rgba(244,63,94,0.4)'
                            }
                        };
                    }).reverse()
                }]
            });
        }
        
    } catch (e) {
        console.error('Failed to init portfolio ledger:', e);
    }
}

// --- [SIMU] Pre-Trade Sandbox State & Engine ---
let simuBasePortfolio = [];
let simuTrades = []; 
let simuMode = 'qty'; // 'qty' or 'weight'
let simuFrictionRate = 0.0015; // 15bps per trade

async function initSimuSandbox() {
    try {
        const res = await fetch('/api/institutional/portfolio_raw');
        if(!res.ok) return;
        const data = await res.json();
        simuBasePortfolio = data.positions || [];
        recomputeSandbox();
    } catch (e) {
        console.error('Failed to init sandbox', e);
    }
}

window.toggleSimuMode = function() {
    const radio = document.querySelector('input[name="simu-mode"]:checked');
    if (radio) {
        simuMode = radio.value;
        const input = document.getElementById('simu-input-val');
        if (simuMode === 'weight') {
            input.placeholder = "TARGET WT (%)";
        } else {
            input.placeholder = "QTY";
        }
    }
};

window.resetSimuSandbox = function() {
    simuTrades = [];
    recomputeSandbox();
};

window.addSimuTrade = function() {
    const ticker = document.getElementById('simu-ticker').value.toUpperCase().trim();
    const action = document.getElementById('simu-action').value;
    const valInput = parseFloat(document.getElementById('simu-input-val').value);
    
    if(!ticker || isNaN(valInput) || valInput <= 0) return;
    
    simuTrades.push({
        id: Date.now(),
        ticker: ticker,
        action: action,
        val: valInput,
        mode: simuMode
    });
    
    document.getElementById('simu-ticker').value = '';
    document.getElementById('simu-input-val').value = '';
    
    recomputeSandbox();
};

window.removeSimuTrade = function(id) {
    simuTrades = simuTrades.filter(t => t.id !== id);
    recomputeSandbox();
};

window.executeSimuCLI = function() {
    const inputEl = document.getElementById('simu-cli-input');
    const cmd = inputEl.value.trim().toUpperCase();
    if (!cmd) return;
    
    // Pattern 1: BUY 600519 1000
    // Pattern 2: SELL 600519 1000
    // Pattern 3: TGT 600519 5%
    const parts = cmd.split(/\s+/);
    if (parts.length < 3) return;
    
    const action = parts[0];
    const ticker = parts[1];
    const valStr = parts[2];
    
    let mode, parsedAction, valInput;
    if (action === 'TGT') {
        mode = 'weight';
        parsedAction = 'BUY'; // Action ignored in weight mode
        valInput = parseFloat(valStr.replace('%', ''));
    } else if (action === 'BUY' || action === 'SELL') {
        mode = 'qty';
        parsedAction = action;
        valInput = parseFloat(valStr);
    } else {
        return;
    }
    
    if (isNaN(valInput) || valInput < 0) return;
    
    simuTrades.push({
        id: Date.now(),
        ticker: ticker,
        action: parsedAction,
        val: valInput,
        mode: mode
    });
    
    inputEl.value = '';
    recomputeSandbox();
};

window.exportSimuCSV = function() {
    if (simuTrades.length === 0) return;
    let csvContent = "data:text/csv;charset=utf-8,";
    csvContent += "TICKER,ACTION,MODE,VALUE,EST_QTY,EST_COST\n";
    
    simuTrades.forEach(t => {
        const estQty = (t._calcQty || 0).toFixed(0);
        const estCost = (t._estCost || 0).toFixed(2);
        csvContent += `${t.ticker},${t.action},${t.mode},${t.val},${estQty},${estCost}\n`;
    });
    
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `alpha_core_trades_${new Date().getTime()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
};

window.injectSimuCashPrompt = function() {
    const amount = prompt("请输入划拨资金数额 (输入正数代表入金，负数代表出金):", "1000000");
    if (amount) {
        const val = parseFloat(amount);
        if (!isNaN(val)) {
            // Find cash pos in base portfolio and modify it
            let cashPos = simuBasePortfolio.find(p => p.asset_class === 'cash');
            if (cashPos) {
                cashPos.quantity += val;
                cashPos.market_value += val;
            } else {
                simuBasePortfolio.push({ symbol: 'CASH', name: '现金', asset_class: 'cash', quantity: val, current_price: 1.0, market_value: val });
            }
            recomputeSandbox();
        }
    }
};

window.setSimuFrictionPrompt = function() {
    const rate = prompt("请设定双边摩擦系数 (例如 万五请输入 0.0005，千1.5 请输入 0.0015):", simuFrictionRate.toString());
    if (rate) {
        const val = parseFloat(rate);
        if (!isNaN(val) && val >= 0) {
            simuFrictionRate = val;
            recomputeSandbox();
        }
    }
};

function recomputeSandbox() {
    if(!simuBasePortfolio || simuBasePortfolio.length === 0) return;
    
    let proj = JSON.parse(JSON.stringify(simuBasePortfolio));
    let baseCash = 0;
    let baseMv = 0;
    
    proj.forEach(p => {
        if (p.asset_class === 'cash') baseCash += (p.market_value || 0);
        baseMv += (p.market_value || 0);
    });
    
    let cashImpact = 0;
    let totalFriction = 0;
    let complianceFailed = false;
    let complianceMsgs = [];
    
    simuTrades.forEach(t => {
        let pos = proj.find(p => p.symbol === t.ticker);
        if (!pos) {
            pos = { symbol: t.ticker, name: t.ticker, asset_class: 'equity', quantity: 0, current_price: 10.0, market_value: 0 };
            proj.push(pos);
        }
        
        let tradeQty = 0;
        let isBuy = true;
        
        if (t.mode === 'qty') {
            tradeQty = t.val;
            isBuy = (t.action === 'BUY');
        } else if (t.mode === 'weight') {
            const currentWt = baseMv > 0 ? (pos.market_value / baseMv) : 0;
            const targetWt = t.val / 100.0;
            const targetValue = targetWt * baseMv;
            const valDiff = targetValue - pos.market_value;
            tradeQty = Math.abs(valDiff / pos.current_price);
            isBuy = valDiff >= 0;
        }
        
        t._calcQty = tradeQty;
        t._isBuy = isBuy;
        
        const cost = tradeQty * pos.current_price;
        t._estCost = cost;
        const friction = cost * simuFrictionRate;
        totalFriction += friction;
        
        if (isBuy) {
            pos.quantity += tradeQty;
            pos.market_value += cost;
            cashImpact -= cost;
        } else {
            if (pos.quantity < tradeQty) {
                complianceFailed = true;
                complianceMsgs.push(`裸卖空熔断: ${t.ticker}`);
            }
            pos.quantity = Math.max(0, pos.quantity - tradeQty);
            pos.market_value = Math.max(0, pos.market_value - cost);
            cashImpact += cost;
        }
    });
    
    const postTradeCash = baseCash + cashImpact - totalFriction;
    if (postTradeCash < 0) {
        complianceFailed = true;
        complianceMsgs.push('现金流透支');
    }
    
    let projMv = 0;
    proj.forEach(p => {
        if (p.asset_class !== 'cash') {
            projMv += p.market_value;
        }
    });
    projMv += postTradeCash; 
    
    let cashPos = proj.find(p => p.asset_class === 'cash');
    if (cashPos) {
        cashPos.quantity = postTradeCash;
        cashPos.market_value = postTradeCash;
    } else if (postTradeCash !== 0) {
        proj.push({ symbol: 'CASH', name: '现金', asset_class: 'cash', quantity: postTradeCash, current_price: 1.0, market_value: postTradeCash });
    }
    
    proj.forEach(p => {
        p._baseWt = baseMv > 0 ? ((simuBasePortfolio.find(bp => bp.symbol === p.symbol)?.market_value || 0) / baseMv) : 0;
        p._projWt = projMv > 0 ? (p.market_value / projMv) : 0;
        p._drift = p._projWt - p._baseWt;
        
        if (p.asset_class !== 'cash' && p._projWt > 0.3) {
            complianceFailed = true;
            complianceMsgs.push(`高集中度风险: ${p.symbol}`);
        }
    });
    
    document.getElementById('simu-proj-mv').textContent = projMv.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
    const deltaMv = projMv - baseMv;
    const deltaSign = deltaMv >= 0 ? '+' : '';
    document.getElementById('simu-mv-delta').textContent = deltaSign + deltaMv.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
    document.getElementById('simu-mv-delta').style.color = deltaMv >= 0 ? 'var(--success)' : 'var(--danger)';
    
    document.getElementById('simu-post-cash').textContent = postTradeCash.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
    const cashCard = document.getElementById('simu-cash-card');
    if (postTradeCash < 0) {
        cashCard.style.border = '1px solid rgba(239, 68, 68, 0.4)';
        cashCard.className = 'glass-card glow-fail';
        document.getElementById('simu-post-cash').style.color = 'var(--danger)';
    } else {
        cashCard.style.border = '1px solid var(--glass-border)';
        cashCard.className = 'glass-card';
        document.getElementById('simu-post-cash').style.color = 'var(--text-primary)';
    }
    
    document.getElementById('simu-fric-cost').textContent = `Est. Friction: ¥${totalFriction.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}`;
    
    const compEl = document.getElementById('simu-compliance');
    const turnCard = document.getElementById('simu-turnover-card');
    if (complianceFailed) {
        compEl.innerHTML = `[ FAILED ]<br><span style="font-size:0.6em; font-weight:400; color:var(--text-tertiary);">${complianceMsgs[0]}</span>`;
        compEl.style.color = 'var(--danger)';
        turnCard.style.border = '1px solid rgba(239, 68, 68, 0.4)';
        turnCard.className = 'glass-card glow-fail';
    } else {
        compEl.textContent = '[ PASS ]';
        compEl.style.color = 'var(--success)';
        turnCard.style.border = '1px solid rgba(34, 197, 94, 0.2)';
        turnCard.className = 'glass-card glow-pass';
    }
    
    let tHtml = '';
    simuTrades.forEach(t => {
        const badgeBg = t._isBuy ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)';
        const badgeColor = t._isBuy ? 'var(--success)' : 'var(--danger)';
        const badgeBorder = t._isBuy ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)';
        const actionStr = `<span style="background:${badgeBg}; color:${badgeColor}; border:1px solid ${badgeBorder}; padding:2px 6px; border-radius:3px; font-size:0.65rem; font-weight:800; letter-spacing:1px; box-shadow: inset 0 1px 0 rgba(255,255,255,0.1);">${t.action}</span>`;
        const valStr = t.mode === 'weight' ? `TGT WT: ${t.val}%` : `QTY: ${t.val}`;
        tHtml += `
            <tr>
                <td>${actionStr}</td>
                <td style="font-family:var(--font-mono); font-weight:700;">${t.ticker}</td>
                <td style="text-align:right; font-family:var(--font-mono); font-size:0.7rem;">${valStr}</td>
                <td style="text-align:right; font-family:var(--font-mono); color:var(--text-tertiary);">¥${t._estCost.toLocaleString(undefined, {maximumFractionDigits:0})}</td>
                <td><button onclick="window.removeSimuTrade(${t.id})" style="background:transparent; border:none; color:var(--danger); cursor:pointer;">×</button></td>
            </tr>
        `;
    });
    document.getElementById('simu-trades-body').innerHTML = tHtml;
    
    let lHtml = '';
    proj.sort((a,b) => b.market_value - a.market_value).forEach(p => {
        const baseQty = simuBasePortfolio.find(bp => bp.symbol === p.symbol)?.quantity || 0;
        const deltaQty = p.quantity - baseQty;
        const drift = p._drift * 100;
        const driftColor = drift > 0.01 ? 'var(--success)' : (drift < -0.01 ? 'var(--danger)' : 'var(--text-tertiary)');
        const driftSign = drift > 0.01 ? '+' : '';
        
        const wtBarWidth = Math.min(100, p._projWt * 100);
        const driftBarWidth = Math.min(100, Math.abs(drift) * 5); // 1% drift = 5% bar width for visibility
        const driftBg = drift > 0 ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)';
        
        lHtml += `
            <tr class="clickable-row" style="transition: background-color 0.2s ease;" onclick="openActionModal('${p.symbol}', '${p.name || ''}', ${p.quantity || 0}, ${p.current_price || 0})">
                <td style="padding-left:16px;">
                    <div style="display:flex; flex-direction:column; gap:2px;">
                        <span style="font-family:var(--font-mono); font-weight:700; color:var(--text-primary); font-size:0.85rem;">${p.symbol}</span>
                        <span style="font-size:0.7rem; color:var(--text-tertiary);">${p.name || '-'}</span>
                    </div>
                </td>
                <td style="text-align:right; font-family:var(--font-mono); color:var(--text-tertiary);">${baseQty.toLocaleString(undefined, {maximumFractionDigits:0})}</td>
                <td style="text-align:right; font-family:var(--font-mono); color:${deltaQty !== 0 ? 'var(--accent-primary)' : 'var(--text-tertiary)'};">${deltaQty > 0 ? '+' : ''}${deltaQty.toLocaleString(undefined, {maximumFractionDigits:0})}</td>
                <td style="text-align:right; font-family:var(--font-mono); font-weight:700; color:${deltaQty !== 0 ? '#fff' : 'var(--text-primary)'};">${p.quantity.toLocaleString(undefined, {maximumFractionDigits:0})}</td>
                <td style="text-align:right; font-family:var(--font-mono);">${p.market_value.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                <td style="text-align:right; font-family:var(--font-mono); color:var(--text-tertiary);">${(p._baseWt*100).toFixed(2)}%</td>
                <td style="text-align:right; font-family:var(--font-mono); font-weight:700; position:relative; padding:0 8px;">
                    <div style="position:absolute; right:8px; top:8px; bottom:8px; width:${wtBarWidth}%; background:rgba(255,255,255,0.05); border-radius:2px; z-index:0;"></div>
                    <span style="position:relative; z-index:1;">${(p._projWt*100).toFixed(2)}%</span>
                </td>
                <td style="text-align:right; padding-right:16px; font-family:var(--font-mono); color:${driftColor}; position:relative;">
                    <div style="position:absolute; right:16px; top:8px; bottom:8px; width:${driftBarWidth}%; background:${driftBg}; border-radius:2px; z-index:0;"></div>
                    <span style="position:relative; z-index:1;">${driftSign}${drift.toFixed(2)}%</span>
                </td>
            </tr>
        `;
    });
    document.getElementById('simu-ledger-body').innerHTML = lHtml;
    
    renderSimuChart(simuBasePortfolio, proj);
}

function renderSimuChart(baseArr, projArr) {
    const chartDom = document.getElementById('chart-simu-allocation');
    if (!chartDom || !window.echarts) return;
    
    let chart = echarts.getInstanceByDom(chartDom);
    if (!chart) chart = echarts.init(chartDom);
    
    const baseGroups = {};
    baseArr.forEach(p => {
        const ac = p.asset_class || 'unknown';
        baseGroups[ac] = (baseGroups[ac] || 0) + p.market_value;
    });
    const baseData = Object.keys(baseGroups).map(k => ({name: k.toUpperCase(), value: baseGroups[k]}));
    
    const projGroups = {};
    projArr.forEach(p => {
        const ac = p.asset_class || 'unknown';
        projGroups[ac] = (projGroups[ac] || 0) + p.market_value;
    });
    const projData = Object.keys(projGroups).map(k => ({name: k.toUpperCase(), value: projGroups[k]}));
    
    chart.setOption({
        tooltip: { trigger: 'item', backgroundColor: 'rgba(0,0,0,0.8)', borderColor: 'rgba(255,255,255,0.1)', textStyle: {color: '#fff'}, formatter: '{a} <br/>{b}: ¥{c} ({d}%)' },
        series: [
            {
                name: 'Current Allocation',
                type: 'pie',
                radius: ['30%', '50%'],
                itemStyle: { borderColor: '#0f172a', borderWidth: 1, opacity: 0.5 },
                label: { position: 'inner', fontSize: 10, color: '#64748b', formatter: '{b}' },
                data: baseData
            },
            {
                name: 'Projected Allocation',
                type: 'pie',
                radius: ['55%', '80%'],
                itemStyle: { borderColor: '#0f172a', borderWidth: 2 },
                label: { color: '#94a3b8', formatter: '{b}\\n{d}%' },
                data: projData
            }
        ]
    });
}

// --- Interactive Order Routing Modal ---
let currentActionContext = null;

window.openActionModal = function(ticker, name, qty, price) {
    currentActionContext = { ticker, name, qty, price };
    
    document.getElementById('modal-ticker').textContent = ticker;
    document.getElementById('modal-name').textContent = name || '-';
    document.getElementById('modal-curr-qty').textContent = qty.toLocaleString(undefined, {maximumFractionDigits:0});
    document.getElementById('modal-input-qty').value = '';
    
    document.getElementById('quick-action-modal').style.display = 'flex';
    // Auto focus the input after a tiny delay so the modal animation completes
    setTimeout(() => {
        document.getElementById('modal-input-qty').focus();
    }, 50);
};

window.closeActionModal = function() {
    document.getElementById('quick-action-modal').style.display = 'none';
    currentActionContext = null;
};

function injectTradeFromModal(action, qty) {
    if (!currentActionContext || qty <= 0) return;
    
    simuTrades.push({
        id: Date.now(),
        ticker: currentActionContext.ticker,
        action: action,
        val: qty,
        mode: 'qty'
    });
    
    recomputeSandbox();
    closeActionModal();
    
    // Automatically switch to SIMU tab if not already there, so user sees the result
    if (!document.getElementById('view-simu').classList.contains('active')) {
        switchView('simu');
    }
}

window.executeActionModalBuy = function() {
    const val = parseFloat(document.getElementById('modal-input-qty').value);
    if (!isNaN(val) && val > 0) {
        injectTradeFromModal('BUY', val);
    }
};

window.executeActionModalSell = function() {
    const val = parseFloat(document.getElementById('modal-input-qty').value);
    if (!isNaN(val) && val > 0) {
        injectTradeFromModal('SELL', val);
    }
};

window.executeActionModalTP = function() {
    if (!currentActionContext || currentActionContext.qty <= 0) return;
    const sellQty = Math.floor(currentActionContext.qty * 0.5); // Sell 50%
    if (sellQty > 0) {
        injectTradeFromModal('SELL', sellQty);
    }
};

window.executeActionModalSL = function() {
    if (!currentActionContext || currentActionContext.qty <= 0) return;
    injectTradeFromModal('SELL', currentActionContext.qty); // Sell 100%
};


// ==========================================
// MODULE 2: BARRA FACTOR RISK ATTRIBUTION
// ==========================================

window.factorRiskData = null;
let factorRadarChart = null;
let factorStyleChart = null;

window.initFactorRisk = async function() {
    document.getElementById('factor-ledger-body').innerHTML = `<tr><td colspan="6" style="text-align:center; padding:20px; color:var(--text-tertiary);">Computing multi-factor matrix...</td></tr>`;
    
    try {
        const response = await fetch('/api/institutional/factors');
        if (!response.ok) throw new Error('API Error');
        const data = await response.json();
        window.factorRiskData = data;
        renderFactorRisk(data);
    } catch (e) {
        console.error(e);
        document.getElementById('factor-ledger-body').innerHTML = `<tr><td colspan="6" style="text-align:center; padding:20px; color:var(--danger);">Error loading factor engine</td></tr>`;
        document.getElementById('factor-engine-status').textContent = 'ENGINE FAULT';
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
        domEl.textContent = `${data.top_factor.factor_group.toUpperCase()} : ${data.top_factor.factor_name.toUpperCase()}`;
    } else {
        domEl.textContent = "N/A";
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
        { name: 'Equity Beta', max: 1.5, min: -1.5 },
        { name: 'Liquidity', max: 0.5, min: -0.5 },
        { name: 'Dollar', max: 0.5, min: -0.5 },
        { name: 'Rate', max: 0.5, min: -0.5 },
        { name: 'Inflation', max: 1.0, min: -1.0 }
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
                let s = `<div style="font-weight:bold; margin-bottom:5px; color:var(--accent-primary);">MACRO SCENARIO SENSITIVITY</div>`;
                s += `<div>Equity Beta: ${values[0].toFixed(2)} <span style="color:#aaa;font-size:0.8em;">(Market +10% -> Port +${(values[0]*10).toFixed(1)}%)</span></div>`;
                s += `<div>Dollar Sens: ${values[2].toFixed(2)} <span style="color:#aaa;font-size:0.8em;">(DXY +5% -> Port ${(values[2]*5 > 0 ? '+' : '')}${(values[2]*5).toFixed(1)}%)</span></div>`;
                s += `<div>Inflation Sens: ${values[4].toFixed(2)}</div>`;
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
                name: 'Portfolio Exposure',
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
    
    const names = items.map(i => i.name.toUpperCase());
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
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:20px; color:var(--text-tertiary);">No positions mapped</td></tr>`;
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
            <tr class="clickable-row" style="transition: background-color 0.2s ease;" onclick="openActionModal('${pos.symbol}', '${name}', ${qty}, ${price})">
                <td style="padding-left:16px;">
                    <div style="display:flex; flex-direction:column; gap:2px;">
                        <span style="font-family:var(--font-mono); font-weight:700; color:var(--text-primary); font-size:0.85rem;">${pos.symbol}</span>
                        <span style="font-size:0.7rem; color:var(--text-tertiary);">${name}</span>
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


// --- [STRE] Historical Scenario Stress Testing ---

async function initStressTesting() {
    try {
        const statusEl = document.getElementById('stress-engine-status');
        if(statusEl) {
            statusEl.innerText = 'CALCULATING VAR...';
            statusEl.style.background = 'rgba(239,68,68,0.1)';
        }

        const res = await fetchJsonWithRetry('/api/institutional/scenarios');
        
        if(statusEl) {
            statusEl.innerText = 'STRESS ENGINE ONLINE';
            statusEl.style.background = 'rgba(239,68,68,0.2)';
        }

        renderStressTesting(res);
    } catch (e) {
        console.error('Failed to init stress testing:', e);
        const statusEl = document.getElementById('stress-engine-status');
        if(statusEl) {
            statusEl.innerText = 'ENGINE FAILED';
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
        const zh = worst.name_zh ? `<span style="font-size:0.65em; color:var(--text-tertiary); letter-spacing:1px; margin-left:8px;">${worst.name_zh}</span>` : '';
        worstNameEl.innerHTML = `${worst.name ? worst.name.toUpperCase() : '--'}${zh}`;
    }
    if (drawdownEl) drawdownEl.innerText = lossPct.toFixed(2) + '%';

    if (resiliencyEl) {
        let grade = 'D';
        let color = '#ef4444';
        if (lossPct >= -5.0) { grade = 'A'; color = '#10b981'; }
        else if (lossPct >= -10.0) { grade = 'B'; color = '#f59e0b'; }
        else if (lossPct >= -15.0) { grade = 'C'; color = '#f97316'; }
        
        resiliencyEl.innerText = grade + ' GRADE';
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
                    const title = scenario ? (scenario.name.toUpperCase() + ' <span style="font-size:0.8em; color:var(--text-tertiary); margin-left:8px;">' + (scenario.name_zh || '') + '</span>') : p.name;
                    return `<div class="hud-title">${title}</div><div class="hud-value">${p.value > 0 ? '+' : ''}${p.value}%</div>`;
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
                data: sortedScenarios.map(s => s.name_zh ? `${s.name} | ${s.name_zh}` : s.name), 
                axisLabel: { color: '#e2e8f0', fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 'bold' },
                axisLine: { show: false },
                axisTick: { show: false },
                splitArea: { show: true, areaStyle: { color: ['rgba(255,255,255,0.02)', 'transparent'] } }
            },
            series: [{
                name: 'Drawdown',
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
        const rowClass = isWorst ? 'clickable-row pulsing-danger-row' : 'clickable-row';
        
        html += `
            <tr class="${rowClass}" style="transition: background-color 0.2s ease;">
                <td style="padding-left:16px;">
                    <div style="display:flex; flex-direction:column; gap:2px;">
                        <span style="font-family:var(--font-mono); font-weight:700; color:var(--text-primary); font-size:0.85rem; text-transform:uppercase;">${s.name}</span>
                        <span style="font-size:0.75rem; color:var(--text-tertiary); letter-spacing:1px;">${s.name_zh || ''}</span>
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


// ==========================================
// [HUB] DECISION HUB LOGIC
// ==========================================
async function initDecisionHub() {
    const hubTime = document.getElementById('hub-time');
    if (hubTime) hubTime.textContent = new Date().toLocaleTimeString('en-US', {hour12: false});
    
    try {
        const response = await fetch('/api/institutional/decision_hub');
        const data = await response.json();
        
        // ----------------------------------------------------------------
        // Render L1 Macro (High-density 2x2 Grid with Glows)
        // ----------------------------------------------------------------
        const l1 = document.getElementById('hub-l1-content');
        if (l1) {
            const macro = data.l1_macro;
            const isStress = macro.vix_level > 25;
            const isCalm = macro.vix_level < 20;
            const scoreColor = macro.score > 70 ? '#22c55e' : (macro.score > 40 ? '#f59e0b' : '#ef4444');
            const regimeGlow = isStress ? 'rgba(239, 68, 68, 0.15)' : (isCalm ? 'rgba(34, 197, 94, 0.15)' : 'rgba(100, 116, 139, 0.1)');
            const regimeBorder = isStress ? '#ef4444' : (isCalm ? '#22c55e' : '#64748b');
            
            l1.style.display = 'grid';
            l1.style.gridTemplateColumns = '1fr 1fr';
            l1.style.gap = '12px';
            l1.innerHTML = `
                <div style="background:${regimeGlow}; border:1px solid ${regimeBorder}50; border-radius:6px; padding:12px; display:flex; flex-direction:column; justify-content:center; align-items:center; box-shadow:inset 0 0 20px ${regimeGlow};">
                    <span style="font-size:0.75rem; color:var(--text-tertiary); margin-bottom:4px; letter-spacing:1px;">宏观周期</span>
                    <strong style="color:${regimeBorder}; font-size:1.2rem; text-shadow:0 0 10px ${regimeBorder}80;">${macro.regime}</strong>
                </div>
                <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.05); border-radius:6px; padding:12px; display:flex; flex-direction:column; justify-content:center; align-items:center;">
                    <span style="font-size:0.75rem; color:var(--text-tertiary); margin-bottom:4px; letter-spacing:1px;">恐慌指数</span>
                    <strong style="font-family:var(--font-mono); font-size:1.2rem; color:var(--text-primary);">${macro.vix_level.toFixed(2)}</strong>
                </div>
                <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.05); border-radius:6px; padding:12px; display:flex; flex-direction:column; justify-content:center; align-items:center;">
                    <span style="font-size:0.75rem; color:var(--text-tertiary); margin-bottom:4px; letter-spacing:1px;">宏观得分</span>
                    <strong style="font-family:var(--font-mono); font-size:1.2rem; color:${scoreColor};">${macro.score}</strong>
                </div>
                <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.05); border-radius:6px; padding:12px; display:flex; flex-direction:column; justify-content:center; align-items:center;">
                    <span style="font-size:0.75rem; color:var(--text-tertiary); margin-bottom:4px; letter-spacing:1px;">权益上限</span>
                    <strong style="font-family:var(--font-mono); font-size:1.2rem; color:var(--text-primary);">${(macro.max_equity_exposure * 100).toFixed(0)}%</strong>
                </div>
                <div style="grid-column: span 2; margin-top:4px; padding:12px; background:rgba(0,0,0,0.3); border-radius:6px; border-left:4px solid ${isStress?'#ef4444':'#3b82f6'}; display:flex; justify-content:space-between; align-items:center;">
                    <span style="color:var(--text-secondary); font-size:0.85rem; letter-spacing:1px;">宏观指引:</span>
                    <strong style="font-family:var(--font-mono); font-size:1rem; color:${isStress?'#ef4444':'#60a5fa'}; text-shadow:0 0 10px ${isStress?'#ef4444':'#60a5fa'}40;">${macro.recommended_action}</strong>
                </div>
            `;
        }
        
        // ----------------------------------------------------------------
        // Render L2 Quant Signals
        // ----------------------------------------------------------------
        const l2 = document.getElementById('hub-l2-content');
        if (l2) {
            let html = '<div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; height:100%;">';
            data.l2_signals.forEach(sig => {
                const isBull = sig.signal > 0;
                const isBear = sig.signal < 0;
                const sColor = isBull ? '#22c55e' : (isBear ? '#ef4444' : '#64748b');
                const gradStart = isBull ? 'rgba(34,197,94,0.15)' : (isBear ? 'rgba(239,68,68,0.15)' : 'rgba(100,116,139,0.15)');
                const gradEnd = isBull ? 'rgba(34,197,94,0.02)' : (isBear ? 'rgba(239,68,68,0.02)' : 'rgba(100,116,139,0.02)');
                const th = sig.top_holding || {};
                const topStr = th.name ? `${th.name}` : '--';
                
                html += `
                    <div style="background:linear-gradient(135deg, ${gradStart} 0%, ${gradEnd} 100%); border:1px solid ${sColor}40; padding:16px 12px; border-radius:8px; display:flex; flex-direction:column; justify-content:space-between; position:relative; overflow:hidden;">
                        <!-- Glowing accent line at top -->
                        <div style="position:absolute; top:0; left:0; width:100%; height:2px; background:linear-gradient(90deg, transparent, ${sColor}, transparent);"></div>
                        
                        <span style="font-weight:bold; color:var(--text-primary); font-size:0.85rem; margin-bottom:12px; letter-spacing:0.5px; z-index:1;">${sig.source}</span>
                        
                        <div style="display:flex; justify-content:space-between; align-items:flex-end; z-index:1;">
                            <div style="display:flex; flex-direction:column;">
                                <span style="font-size:0.65rem; color:var(--text-tertiary); letter-spacing:1px; margin-bottom:2px;">核心持仓</span>
                                <span style="font-size:0.85rem; color:var(--text-secondary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:120px;">${topStr}</span>
                            </div>
                            <span style="color:${sColor}; font-family:var(--font-mono); font-weight:900; font-size:1.3rem; text-shadow:0 0 15px ${sColor}A0;">${sig.signal > 0 ? '+' : ''}${sig.signal}</span>
                        </div>
                    </div>
                `;
            });
            html += '</div>';
            l2.innerHTML = html;
        }
        
        // ----------------------------------------------------------------
        // Render L3 Routing & Allocation Chart
        // ----------------------------------------------------------------
        const rationaleEl = document.getElementById('hub-l3-rationale');
        if (rationaleEl) {
            rationaleEl.innerHTML = `<div style="display:inline-flex; align-items:center; background:rgba(56,189,248,0.1); padding:6px 12px; border-radius:4px; border:1px solid rgba(56,189,248,0.2);"><span style="color:#38bdf8; margin-right:8px; font-size:1.2em;">⬢</span> <span style="color:var(--text-secondary);">${data.l3_routing.rationale}</span></div>`;
        }
        
        const chartDom = document.getElementById('chart-hub-l3-alloc');
        if (chartDom && window.echarts) {
            let allocChart = echarts.getInstanceByDom(chartDom);
            if (!allocChart) allocChart = echarts.init(chartDom);
            
            const tgt = data.l3_routing.target_weights || {};
            const cur = data.l3_routing.before_weights || {};
            
            const symbols = Array.from(new Set([...Object.keys(tgt), ...Object.keys(cur)]));
            const curData = symbols.map(s => (cur[s] || 0) * 100);
            const tgtData = symbols.map(s => (tgt[s] || 0) * 100);
            
            allocChart.setOption({
                tooltip: {
                    trigger: 'axis',
                    backgroundColor: 'rgba(11, 13, 19, 0.9)',
                    borderColor: 'rgba(255,255,255,0.1)',
                    textStyle: { color: '#fff' },
                    axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(255,255,255,0.02)' } },
                    formatter: function(params) {
                        let res = `<div style="font-weight:bold; margin-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:6px; font-family:var(--font-mono);">${params[0].axisValue}</div>`;
                        params.forEach(p => {
                            res += `<div style="display:flex; justify-content:space-between; gap:16px; margin-bottom:4px;">
                                <span style="display:flex; align-items:center;"><span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${p.color.colorStops ? p.color.colorStops[0].color : p.color}; margin-right:8px;"></span><span style="color:var(--text-secondary);">${p.seriesName}</span></span>
                                <strong style="font-family:var(--font-mono);">${p.value.toFixed(1)}%</strong>
                            </div>`;
                        });
                        return res;
                    }
                },
                legend: {
                    data: ['当前仓位', '目标仓位'],
                    textStyle: { color: 'var(--text-secondary)', fontSize: 11 },
                    top: 0,
                    right: 0,
                    icon: 'roundRect'
                },
                grid: { left: '2%', right: '2%', bottom: '2%', top: '35px', containLabel: true },
                xAxis: {
                    type: 'category',
                    data: symbols,
                    axisLabel: { color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', fontSize: 10, interval: 0, rotate: 30 },
                    axisTick: { show: false },
                    axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } }
                },
                yAxis: {
                    type: 'value',
                    axisLabel: { color: 'var(--text-tertiary)', formatter: '{value}%', fontFamily: 'var(--font-mono)', fontSize: 10 },
                    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.03)', type: 'dashed' } }
                },
                series: [
                    {
                        name: '当前仓位',
                        type: 'bar',
                        data: curData,
                        itemStyle: { color: 'rgba(100, 116, 139, 0.3)', borderRadius: [2, 2, 0, 0], borderColor: 'rgba(100, 116, 139, 0.8)', borderWidth: 1 },
                        barWidth: '30%',
                        barGap: '15%'
                    },
                    {
                        name: '目标仓位',
                        type: 'bar',
                        data: tgtData,
                        itemStyle: { 
                            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                                { offset: 0, color: '#a855f7' },
                                { offset: 1, color: '#3b82f6' }
                            ]),
                            borderRadius: [3, 3, 0, 0],
                            shadowBlur: 10,
                            shadowColor: 'rgba(168, 85, 247, 0.4)'
                        },
                        barWidth: '30%'
                    }
                ]
            });
            window.addEventListener('resize', () => allocChart.resize());
        }
        
        // ----------------------------------------------------------------
        // Render L4 Compliance Gate
        // ----------------------------------------------------------------
        const l4 = document.getElementById('hub-l4-content');
        const l4Card = document.getElementById('hub-l4-card');
        if (l4) {
            const comp = data.l4_compliance;
            const isBlock = comp.gate_status === 'HARD_BLOCK';
            const isWarn = comp.gate_status === 'SOFT_WARNING';
            const statusColor = isBlock ? '#ef4444' : (isWarn ? '#f59e0b' : '#22c55e');
            
            // Apply warning tape styling if blocked
            if (isBlock) {
                l4Card.style.background = 'repeating-linear-gradient(45deg, rgba(239, 68, 68, 0.05), rgba(239, 68, 68, 0.05) 10px, rgba(0, 0, 0, 0) 10px, rgba(0, 0, 0, 0) 20px)';
                l4Card.style.border = '1px solid rgba(239,68,68,0.3)';
                l4Card.style.boxShadow = '0 0 30px rgba(239,68,68,0.1) inset';
            } else if (isWarn) {
                l4Card.style.border = '1px solid rgba(245,158,11,0.3)';
            } else {
                l4Card.style.border = '1px solid rgba(34,197,94,0.3)';
            }
            
            l4Card.style.borderLeft = `4px solid ${statusColor}`;
            
            let html = `
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div style="display:flex; align-items:center; gap:12px;">
                        <div style="width:12px; height:12px; border-radius:50%; background:${statusColor}; box-shadow:0 0 10px ${statusColor}; animation: modalFadeIn 1s infinite alternate;"></div>
                        <div style="font-size:1.3rem; font-weight:900; color:${statusColor}; font-family:var(--font-mono); letter-spacing:2px; text-shadow:0 0 15px ${statusColor}80;">
                            [ ${comp.gate_status} ]
                        </div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:0.65rem; color:var(--text-tertiary); letter-spacing:1px;">风控合规评分</div>
                        <div style="font-size:1.8rem; font-weight:900; color:var(--text-primary); font-family:var(--font-mono); line-height:1;">${comp.score}</div>
                    </div>
                </div>
                <div style="width:100%; height:4px; background:rgba(255,255,255,0.05); margin-top:16px; margin-bottom:16px; border-radius:2px; overflow:hidden;">
                    <div style="height:100%; width:${comp.score}%; background:${statusColor}; transition:width 1.5s cubic-bezier(0.4, 0, 0.2, 1); box-shadow:0 0 10px ${statusColor};"></div>
                </div>
            `;
            
            if (comp.violations && comp.violations.length > 0) {
                html += `
                    <div style="margin-top:auto; background:rgba(0,0,0,0.4); border:1px solid rgba(239,68,68,0.2); border-radius:4px; padding:12px; font-family:var(--font-mono); font-size:0.8rem;">
                        <div style="color:#ef4444; margin-bottom:8px; font-weight:bold; letter-spacing:1px; display:flex; align-items:center; gap:6px;">
                            <i class="fas fa-exclamation-triangle"></i> 触发硬性风控拦截:
                        </div>
                        <ul style="margin:0; padding-left:20px; color:#fca5a5; line-height:1.6;">
                            ${comp.violations.map(v => `<li>> ${v}</li>`).join('')}
                        </ul>
                    </div>
                `;
            } else if (comp.warnings && comp.warnings.length > 0) {
                html += `
                    <div style="margin-top:auto; background:rgba(0,0,0,0.4); border:1px solid rgba(245,158,11,0.2); border-radius:4px; padding:12px; font-family:var(--font-mono); font-size:0.8rem;">
                        <div style="color:#f59e0b; margin-bottom:8px; font-weight:bold; letter-spacing:1px;">! 触发软性风控预警:</div>
                        <ul style="margin:0; padding-left:20px; color:#fcd34d; line-height:1.6;">
                            ${comp.warnings.map(v => `<li>> ${v}</li>`).join('')}
                        </ul>
                    </div>
                `;
            } else {
                html += `
                    <div style="margin-top:auto; background:rgba(0,0,0,0.4); border:1px solid rgba(34,197,94,0.2); border-radius:4px; padding:12px; font-family:var(--font-mono); font-size:0.8rem; color:#86efac; display:flex; align-items:center; gap:8px;">
                        <i class="fas fa-check-circle" style="color:#22c55e;"></i> 全量风控规则检验通过
                    </div>
                `;
            }
            
            html += `
                <div style="display:flex; justify-content:space-between; color:var(--text-tertiary); font-family:var(--font-mono); font-size:0.75rem; margin-top:8px;">
                    <span>预估换仓换手率:</span>
                    <strong style="color:var(--text-secondary);">${(comp.turnover * 100).toFixed(1)}%</strong>
                </div>
            `;
            
            l4.innerHTML = html;
        }
        
        // ----------------------------------------------------------------
        // Render L5 AI-CIO Synthesis
        // ----------------------------------------------------------------
        const l5 = document.getElementById('hub-l5-content');
        const l5Card = document.getElementById('hub-l5-card');
        if (l5) {
            const memo = data.l5_ai_memo;
            const isBlocked = memo.headline.includes('BLOCKED');
            const isWarned = memo.headline.includes('WARN');
            const memoColor = isBlocked ? '#ef4444' : (isWarned ? '#f59e0b' : '#a855f7'); // Use purple for AI insight
            
            // Frosted glass effect for AI memo
            l5Card.style.borderTop = `1px solid ${memoColor}80`;
            l5Card.style.boxShadow = `0 -10px 30px ${memoColor}15`;
            
            l5.style.border = `1px solid ${memoColor}30`;
            l5.style.background = `linear-gradient(180deg, ${memoColor}10 0%, rgba(0,0,0,0.5) 100%)`;
            l5.style.backdropFilter = 'blur(16px)';
            
            l5.innerHTML = `
                <div style="display:flex; align-items:center; gap:16px; margin-bottom:16px; border-bottom:1px solid rgba(255,255,255,0.05); padding-bottom:16px;">
                    <div style="width:48px; height:48px; border-radius:12px; background:${memoColor}20; border:1px solid ${memoColor}40; display:flex; justify-content:center; align-items:center; color:${memoColor}; font-size:1.5rem; box-shadow:0 0 15px ${memoColor}40;">
                        <i class="fas fa-robot"></i>
                    </div>
                    <div>
                        <div style="font-size:0.7rem; color:var(--text-tertiary); letter-spacing:2px; font-family:var(--font-mono); margin-bottom:4px;">AI-CIO 决策归因协议</div>
                        <h2 style="color:${memoColor}; margin:0; font-size:1.3rem; letter-spacing:1px; text-shadow:0 0 15px ${memoColor}80;">${memo.headline}</h2>
                    </div>
                </div>
                <div style="padding:0 8px;">
                    <p style="margin-bottom:0; font-size:1.05rem; line-height:1.8; color:var(--text-primary); text-align:justify; position:relative;">
                        <span style="color:${memoColor}; font-family:var(--font-mono); margin-right:8px;">></span>${memo.memo}
                        <span style="display:inline-block; width:8px; height:18px; background:${memoColor}; margin-left:8px; vertical-align:middle; animation: modalFadeIn 0.8s infinite alternate;"></span>
                    </p>
                </div>
            `;
        }
        
    } catch (e) {
        console.error("Decision Hub Error", e);
        const l1 = document.getElementById('hub-l1-content');
        if (l1) l1.innerHTML = `<div style="color:#ef4444;">Failed to load Decision Hub data. Check connection to core.</div>`;
    }
}



