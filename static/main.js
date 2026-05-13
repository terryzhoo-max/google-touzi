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

async function initInstitutionalDecision() {
    const panel = document.getElementById('institutional-decision-panel');
    const workbench = document.getElementById('institutional-workbench');
    if (!panel) return;

    try {
        const data = await fetchJsonWithRetry('/api/institutional/decision');
        const [auditResp, auditVerifyResp, summaryResp, queueResp, scoreResp] = await Promise.all([
            fetch('/api/institutional/audit/decisions?limit=10'),
            fetch('/api/institutional/audit/verify?limit=10'),
            fetch('/api/institutional/reviews/summary'),
            fetch('/api/institutional/reviews/queue?limit=1'),
            fetch('/api/institutional/reviews/scores?limit=1')
        ]);
        const auditData = await auditResp.json();
        const auditVerifyData = await auditVerifyResp.json();
        const summaryData = await summaryResp.json();
        const queueData = await queueResp.json();
        const scoreData = await scoreResp.json();
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
        const evidence_chain = data.evidence_chain || {};
        const latestScore = (scoreData.scores || [])[0] || {};
        const topQueueItem = (queueData.queue || [])[0] || {};

        // ── Score Gauge ──
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
        document.getElementById('decision-gauge-label') && (document.getElementById('decision-gauge-label').style.color = '#64748b');

        // ── Hero action + reason ──
        const actionHero = document.getElementById('decision-action-hero');
        if (actionHero) {
            const actText = action.action || ticket.suggested_action || '';
            const ticketStatus = ticket.decision_status || '';
            if (ticketStatus === 'allow') actionHero.style.color = '#22c55e';
            else if (ticketStatus === 'observe') actionHero.style.color = '#ef4444';
            else actionHero.style.color = '#fbbf24';
            actionHero.textContent = actText || '--';
        }
        const reasonHero = document.getElementById('decision-reason-hero');
        if (reasonHero) {
            const codes = explanation.reason_codes || [];
            const driver = explanation.primary_driver?.code || '';
            reasonHero.textContent = codes.length ? codes.map(c => c.code || c).join('  |  ') : (driver || '--');
        }

        setFlowText('decision-var', `${risk.var_95_pct ?? '--'}%`);
        setFlowText('decision-worst', `${worst.portfolio_loss_pct ?? '--'}%`);
        setFlowText('decision-asset-exposure', formatTopExposure(portfolio.asset_class_exposure));
        setFlowText('decision-region-exposure', formatTopExposure(portfolio.region_exposure));
        setFlowText('decision-strategy-exposure', formatTopExposure(portfolio.strategy_exposure));
        setFlowText('decision-currency-exposure', formatTopExposure(portfolio.currency_exposure));
        setFlowText('decision-concentration', portfolio.concentration_level || '--');
        setFlowText('decision-primary-driver', explanation.primary_driver?.code || '--');
        setFlowText('decision-execution-readiness', explanation.execution_readiness || '--');
        // color-code risk/status cells
        ['decision-primary-driver', 'decision-concentration', 'decision-execution-readiness'].forEach(id => {
            const el = document.getElementById(id); if (!el) return;
            const v = el.textContent || '';
            if (/high|block|observe|fail/i.test(v)) { el.className = 'risk-high'; }
            else if (/medium|warn|limited|review/i.test(v)) { el.className = 'risk-medium'; }
            else if (/low|pass|allow|executable/i.test(v)) { el.className = 'risk-low'; }
        });
        // color-code compliance, audit cells
        ['decision-audit-integrity', 'decision-last-verdict'].forEach(id => {
            const el = document.getElementById(id); if (!el) return;
            const v = el.textContent || '';
            if (/passed|effective|clean/i.test(v)) { el.className = 'risk-low'; }
            else if (/failed|violation/i.test(v)) { el.className = 'risk-high'; }
        });
        setFlowText('decision-policy-version', explanation.policy_version || ticket.policy_version || data.policy?.version || '--');
        setFlowText('decision-policy-hash', shortHash(explanation.policy_hash || ticket.policy_hash || data.policy?.policy_hash));
        setFlowText('decision-audit-count', String((auditData.decisions || []).length));
        setFlowText(
            'decision-audit-integrity',
            auditVerifyData.status === 'empty'
                ? 'empty'
                : `${auditVerifyData.status || 'unknown'} ${Math.round((auditVerifyData.verified_rate ?? 0) * 100)}%`
        );
        setFlowText('decision-review-due', String(summaryData.summary?.due_count ?? 0));
        setFlowText(
            'decision-review-sla',
            `${summaryData.summary?.critical_due_count ?? 0}C / ${summaryData.summary?.elevated_due_count ?? 0}E`
        );
        setFlowText('decision-review-priority', topQueueItem.priority || 'none');
        setFlowText('decision-last-verdict', latestScore.verdict || 'none');
        setFlowText('decision-risk-improvement', action.risk_improvement || '等待风险改善测算。');
        setFlowText('decision-review', `复盘计划: ${(ticket.review_schedule || []).join(' / ')}`);
        renderAllocationModel(data.allocation_model || data);

        // ── Dashboard Guard Strip ──
        const gComp = document.getElementById('guard-compliance');
        const gFactor = document.getElementById('guard-factor');
        const gTrack = document.getElementById('guard-tracking');
        if (gComp) {
            const cs = compliance.status || '--';
            gComp.textContent = cs.toUpperCase();
            gComp.style.color = cs === 'pass' ? '#22c55e' : cs === 'block' ? '#ef4444' : '#fbbf24';
        }
        if (gFactor) {
            const tf = formatTopFactor(factor_risk);
            gFactor.textContent = tf || '--';
            gFactor.style.color = '#e2e8f0';
        }
        if (gTrack) {
            const te = active_risk.tracking_error_proxy_pct || '--';
            gTrack.textContent = te + '%';
            gTrack.style.color = parseFloat(te) > 6 ? '#ef4444' : parseFloat(te) > 3 ? '#fbbf24' : '#22c55e';
        }

        if (workbench) {
            // ── Workbench risk zone ──
            const wz = document.getElementById('workbench-risk-zone');
            const compStatus = compliance.status || '--';
            const trackingErr = parseFloat(active_risk.tracking_error_proxy_pct) || 0;
            if (wz) {
                let wzText, wzBg, wzColor, wzAction;
                if (compStatus === 'block' || trackingErr > 8) {
                    wzText = '● 高风险区'; wzBg = 'rgba(239,68,68,0.12)'; wzColor = '#ef4444';
                    wzAction = '合规拦截或跟踪误差过高，暂停新增风险敞口';
                } else if (compStatus === 'warn' || trackingErr > 4) {
                    wzText = '● 关注区'; wzBg = 'rgba(251,191,36,0.12)'; wzColor = '#fbbf24';
                    wzAction = '合规警告或主动风险偏高，建议小步调仓';
                } else {
                    wzText = '● 安全区'; wzBg = 'rgba(34,197,94,0.12)'; wzColor = '#22c55e';
                    wzAction = '因子风险可控，合规通过，可执行目标调仓';
                }
                wz.innerHTML = `${wzText} <span style="font-size:0.65rem;font-weight:400;color:${wzColor};margin-left:8px;">${wzAction}</span>`;
                wz.style.background = wzBg; wz.style.color = wzColor;
                wz.style.fontWeight = '700'; wz.style.fontSize = '0.85rem';
                wz.style.textTransform = 'uppercase'; wz.style.letterSpacing = '1px';
                wz.style.padding = '6px 16px'; wz.style.borderRadius = '6px';
                wz.style.border = `1px solid ${wzColor}30`;
            }

            const topFactor = formatTopFactor(factor_risk);
            setFlowText('workbench-top-factor', topFactor);
            if (factor_risk.top_factor?.exposure) {
                setFlowText('workbench-top-exposure', `暴露度 ${(factor_risk.top_factor.exposure*100).toFixed(1)}%`);
            }
            setFlowText('workbench-tracking-error', `${active_risk.tracking_error_proxy_pct ?? '--'}%`);
            setFlowText('workbench-largest-active', formatLargestActive(active_risk));
            setFlowText('workbench-compliance-status', compStatus);
            setFlowText('workbench-compliance-issues', formatComplianceIssues(compliance));
            setFlowText('workbench-attribution', formatAttribution(attribution));
            setFlowText('workbench-evidence', formatEvidence(evidence_chain));

            // compliance alert in workbench
            const wca = document.getElementById('workbench-compliance-alert');
            if (wca) {
                const violations = compliance.violations || [];
                const warnings = compliance.warnings || [];
                if (violations.length || warnings.length) {
                    wca.style.display = 'block';
                    wca.style.background = violations.length ? 'rgba(239,68,68,0.08)' : 'rgba(251,191,36,0.06)';
                    wca.style.border = `1px solid ${violations.length ? 'rgba(239,68,68,0.25)' : 'rgba(251,191,36,0.2)'}`;
                    wca.style.margin = '8px 0';
                    wca.style.padding = '8px 14px';
                    wca.style.borderRadius = '6px';
                    wca.style.fontSize = '0.72rem';
                    const parts = [
                        ...violations.map(v => `<span style="color:#ef4444;">▸ ${v}</span>`),
                        ...warnings.map(w => `<span style="color:#fbbf24;">▸ ${w}</span>`)
                    ];
                    wca.innerHTML = parts.join('<br>');
                }
            }

            // color compliance status cell
            const csEl = document.getElementById('workbench-compliance-status');
            if (csEl) {
                if (compStatus === 'pass') csEl.className = 'risk-low';
                else if (compStatus === 'block') csEl.className = 'risk-high';
                else csEl.className = 'risk-medium';
            }
        }

        const status = document.getElementById('decision-status');
        if (status) {
            status.innerText = ticket.decision_status || 'unknown';
            status.classList.toggle('is-ok', ticket.decision_status === 'allow');
            status.classList.toggle('is-error', ticket.decision_status === 'observe');
        }

        // ── Buy/Sell Zone Indicator ──────────────────────
        const zone = document.getElementById('decision-zone');
        if (zone) {
            const score = ticket.score ?? 0;
            const ticketStatus = ticket.decision_status || 'unknown';
            const compStatus = compliance.status || 'pass';
            const riskLevel = risk.risk_level || 'low';
            const gateFailures = ticket.gates_failed || [];

            let zoneText, zoneBg, zoneColor, zoneAction;
            if (score >= 80 && ticketStatus === 'allow' && compStatus !== 'block') {
                zoneText = '● 买入区间'; zoneBg = 'rgba(34,197,94,0.12)'; zoneColor = '#22c55e';
                zoneAction = 'risk budget充足，建议按目标权重执行调仓';
            } else if (score >= 60 && ticketStatus !== 'observe') {
                zoneText = '● 持有/观察'; zoneBg = 'rgba(251,191,36,0.12)'; zoneColor = '#fbbf24';
                zoneAction = '部分风险指标承压，建议分批小步执行';
            } else if (ticketStatus === 'observe' || compStatus === 'block') {
                zoneText = '● 卖出/减仓'; zoneBg = 'rgba(239,68,68,0.12)'; zoneColor = '#ef4444';
                zoneAction = '风险超标或合规拦截，不建议新增风险敞口';
            } else {
                zoneText = '● 中性/观望'; zoneBg = 'rgba(148,163,184,0.1)'; zoneColor = '#94a3b8';
                zoneAction = '等待数据质量改善后重新评估';
            }
            zone.innerHTML = `${zoneText} <span style="font-size:0.7rem;font-weight:400;color:${zoneColor};margin-left:8px;">${zoneAction}</span>`;
            zone.style.background = zoneBg;
            zone.style.color = zoneColor;
            zone.style.fontWeight = '700';
            zone.style.fontSize = '0.9rem';
            zone.style.textTransform = 'uppercase';
            zone.style.letterSpacing = '1px';
            zone.style.padding = '6px 16px';
            zone.style.borderRadius = '6px';
            zone.style.border = `1px solid ${zoneColor}30`;
        }

        // ── Compliance Alert Strip ────────────────────────
        const compAlert = document.getElementById('decision-compliance-alert');
        if (compAlert) {
            const violations = compliance.violations || [];
            const warnings = compliance.warnings || [];
            const compScore = compliance.score ?? null;
            const gates = ticket.gates_failed || [];
            const allIssues = [
                ...gates.map(g => ({text: g, level: 'danger'})),
                ...violations.map(v => ({text: v, level: 'danger'})),
                ...warnings.map(w => ({text: w, level: 'warning'}))
            ];

            compAlert.style.display = 'block';  // always visible

            if (allIssues.length > 0) {
                const isBlock = compStatus === 'block' || allIssues.some(i => i.level === 'danger' && i.text.includes('block'));
                compAlert.style.background = isBlock ? 'rgba(239,68,68,0.08)' : 'rgba(251,191,36,0.06)';
                compAlert.style.border = `1px solid ${isBlock ? 'rgba(239,68,68,0.25)' : 'rgba(251,191,36,0.2)'}`;
                const scoreStr = compScore !== null ? `评分 ${compScore}/100` : '';
                compAlert.innerHTML = `<div style="display:flex;align-items:center;gap:8px;margin-bottom:${allIssues.length>1?6:0}px;">
                    <span style="font-weight:700;color:${isBlock?'#ef4444':'#fbbf24'};">⚠ 合规门禁: ${compStatus.toUpperCase()}</span>
                    ${scoreStr ? `<span style="color:#64748b;font-size:0.7rem;">${scoreStr}</span>` : ''}
                </div>` +
                allIssues.map(i => `<div style="margin-left:8px;color:${i.level==='danger'?'#ef4444':'#fbbf24'};font-size:0.72rem;">▸ ${i.text}</div>`).join('');
            } else if (compStatus === 'pass' || compStatus === 'unknown' || !compStatus || compStatus === '--') {
                compAlert.style.background = 'rgba(34,197,94,0.04)';
                compAlert.style.border = '1px solid rgba(34,197,94,0.15)';
                compAlert.innerHTML = `<span style="color:#22c55e;font-size:0.72rem;">✓ 合规门禁通过 | 无风险超标</span>`;
            } else {
                compAlert.style.background = 'rgba(148,163,184,0.04)';
                compAlert.style.border = '1px solid rgba(148,163,184,0.12)';
                compAlert.innerHTML = `<span style="color:#94a3b8;font-size:0.72rem;">合规门禁: ${compStatus.toUpperCase()}</span>`;
            }
        }
    } catch (error) {
        console.error('Institutional decision failed:', error);
        setFlowText('decision-action', '决策引擎暂不可用');
        try {
            const fallback = await fetch('/api/institutional/allocation_model');
            const data = await fallback.json();
            renderAllocationModel(data.allocation_model || data);
        } catch (fallbackError) {
            console.error('Allocation model failed:', fallbackError);
        }
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
