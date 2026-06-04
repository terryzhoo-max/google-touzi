// portfolio_workbench.js - AlphaCore frontend panel module.
function importTDX() {
    const fileInput = document.getElementById('tdx-file-input');
    if (fileInput) fileInput.click();
}
async function handleTDXUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    // There are multiple import buttons (in AUDT and PORT)
    // We'll update all of them visually during the upload
    const btns = document.querySelectorAll('button[data-action="import-tdx"]');
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
function formatCny(value, options = {}) {
    return `\u00a5${Number(value || 0).toLocaleString(undefined, options)}`;
}
function formatCompactCny(value) {
    const num = Number(value || 0);
    const abs = Math.abs(num);
    const sign = num > 0 ? '+' : (num < 0 ? '-' : '');
    if (abs >= 100000000) return `${sign}\u00a5${(abs / 100000000).toFixed(2)}亿`;
    if (abs >= 10000) return `${sign}\u00a5${(abs / 10000).toFixed(2)}万`;
    return `${sign}\u00a5${abs.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
}
function firstFiniteNumber(values) {
    for (const value of values) {
        if (value === null || value === undefined || value === '') continue;
        const normalized = typeof value === 'string' ? value.replace(/[,％%]/g, '') : value;
        const num = Number(normalized);
        if (Number.isFinite(num)) return num;
    }
    return null;
}
function resolvePositionPnl(pos) {
    const directPnl = firstFiniteNumber([
        pos.float_pnl,
        pos.unrealized_pnl,
        pos.unrealized_profit,
        pos.pnl_abs,
        pos.profit_loss,
        pos.floating_pnl,
        pos.position_pnl
    ]);
    if (directPnl !== null) return { value: directPnl, source: 'direct' };

    const marketValue = firstFiniteNumber([pos.market_value]);
    const costBasis = firstFiniteNumber([pos.cost_basis]);
    const costLooksLikeTotalBasis = marketValue !== null && costBasis !== null && costBasis > marketValue * 0.05 && costBasis < marketValue * 20;
    if (costLooksLikeTotalBasis) {
        return { value: marketValue - costBasis, source: 'derived' };
    }

    return { value: null, source: 'missing' };
}
function assetClassLabel(assetClass) {
    const key = String(assetClass || 'unknown').toUpperCase();
    const labels = {
        EQUITY: '权益资产',
        BOND: '固定收益',
        CASH: '现金',
        GOLD: '避险金属',
        COMMODITY: '大宗商品',
        CRYPTO: '数字资产',
        UNKNOWN: '未分类'
    };
    return labels[key] || key;
}
async function initPortfolioLedger() {
    if (window.currentPortfolio === 'ALL') {
        try {
            const net = await fetchJsonWithRetry('/api/institutional/global_risk_net');
            const contribs = net.portfolio_contributions || [];

            const mvEl = document.getElementById('port-total-mv');
            const pnlEl = document.getElementById('port-total-pnl');
            const cashEl = document.getElementById('port-total-cash');
            const tbody = document.getElementById('port-ledger-body');

            if (mvEl) mvEl.textContent = formatCny(net.total_market_value, {maximumFractionDigits: 0});
            if (pnlEl) pnlEl.textContent = '组合风险监控';
            if (cashEl) cashEl.textContent = '--';

            if (tbody) {
                tbody.innerHTML = contribs.map(c => {
                    const color = c.worst_scenario_loss_pct < -10 ? '#ef4444' : '#10b981';
                    return `<tr>
                        <td style="padding-left:16px;"><span style="font-weight:700; color:#fff;">${c.portfolio_name}</span></td>
                        <td style="font-family:var(--font-mono);">${c.weight_pct.toFixed(2)}%</td>
                        <td colspan="2" style="color:var(--text-secondary);">${c.worst_scenario_name}</td>
                        <td colspan="2" style="text-align:right; font-family:var(--font-mono); color:${color}; font-weight:700;">${c.worst_scenario_loss_pct.toFixed(2)}%</td>
                    </tr>`;
                }).join('');
            }
        } catch (e) {
            console.error('Failed to load global risk net for ledger:', e);
        }
        return;
    }
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
            rowsHtml = '<tr><td colspan="11" style="text-align:center; padding:20px; color:var(--text-tertiary);">暂无持仓数据，请先同步 TDX 持仓。</td></tr>';
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

                // Extra columns for institutional risk/liquidity metrics
                const advVal = pos.adv_20d ? pos.adv_20d.toLocaleString(undefined, {maximumFractionDigits:0}) : '--';
                const dtlVal = pos.days_to_liquidate !== undefined ? pos.days_to_liquidate.toFixed(2) : '--';
                const mctrVal = pos.mctr !== undefined ? (pos.mctr * 100).toFixed(2) + '%' : '--';
                const riskPctVal = pos.normalized_risk_contribution !== undefined ? (pos.normalized_risk_contribution * 100).toFixed(2) + '%' : '--';
                rowsHtml += `
                    <tr class="clickable-row" data-action="open-action-modal" data-symbol="${escapeHTML(pos.symbol)}" data-name="${escapeHTML(pos.name || '')}" data-qty="${pos.quantity || 0}" data-price="${pos.current_price || 0}">
                        <td style="padding-left:16px;">
                            <div style="display:flex; flex-direction:column; gap:2px;">
                                <span style="font-weight:700; color:var(--text-primary); font-size:0.95rem;">${pos.name || pos.symbol}</span>
                                <span style="font-family:var(--font-mono); font-size:0.7rem; color:var(--text-tertiary);">${pos.symbol}</span>
                            </div>
                        </td>
                        <td><span style="font-size:0.65rem; padding:2px 6px; border-radius:3px; background:rgba(255,255,255,0.05); color:var(--text-secondary); text-transform:uppercase; letter-spacing:0.5px;">${assetClassLabel(pos.asset_class)}</span></td>
                        <td style="text-align:right; font-family:var(--font-mono);">${(pos.quantity || 0).toLocaleString()}</td>
                        <td style="text-align:right; font-family:var(--font-mono); color:var(--text-tertiary);">${(pos.cost_basis || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                        <td style="text-align:right; font-family:var(--font-mono);">${(pos.current_price || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</td>
                        <td style="text-align:right; font-family:var(--font-mono); font-weight:600;">
                            <div>${(pos.market_value || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}</div>
                            ${weightBar}
                        </td>
                        <td style="text-align:right; font-family:var(--font-mono); color:var(--text-secondary);">${advVal}</td>
                        <td style="text-align:right; font-family:var(--font-mono); color:var(--text-secondary);">${dtlVal}</td>
                        <td style="text-align:right; font-family:var(--font-mono); color:var(--accent-secondary);">${mctrVal}</td>
                        <td style="text-align:right; font-family:var(--font-mono); color:var(--accent-primary);">${riskPctVal}</td>
                        <td style="text-align:right; padding-right:16px; font-family:var(--font-mono);">
                            ${fmtPnLBadge(pos.float_pnl || 0, pos.pnl_pct || 0)}
                        </td>
                    </tr>
                `;
            });
        }

        if (mvEl) mvEl.textContent = formatCny(totalMv, {minimumFractionDigits:2, maximumFractionDigits:2});
        if (pnlEl) {
            pnlEl.textContent = (totalPnl > 0 ? '+' : '') + totalPnl.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
            pnlEl.style.color = totalPnl >= 0 ? '#10b981' : '#f43f5e';
            pnlEl.style.textShadow = totalPnl >= 0 ? '0 0 15px rgba(16,185,129,0.4)' : '0 0 15px rgba(244,63,94,0.4)';
        }
        if (cashEl) cashEl.textContent = formatCny(totalCash, {minimumFractionDigits:2, maximumFractionDigits:2});

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
                'CASH': '现金',
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
                        const en = d.name_zh ? `<span style="font-size:0.8em; color:var(--text-tertiary); margin-left:8px; font-family:var(--font-mono);">${d.name}</span>` : '';
                        return `<div class="hud-title" style="border-bottom-color:${params.color};">${d.name_zh || d.name}${en}</div>
                                <div class="hud-value" style="color:${params.color};">${formatCny(d.value, {minimumFractionDigits:2, maximumFractionDigits:2})} <span style="font-size:0.5em; opacity:0.8;">(${params.percent}%)</span></div>`;
                    }
                },
                title: {
                    text: '资产配置',
                    subtext: `\u00a5${(totalMv/10000).toFixed(0)}万`,
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

            const pnlAttributionRows = [...positions]
                .filter(p => String(p.asset_class || '').toLowerCase() !== 'cash')
                .map(p => {
                    const pnl = resolvePositionPnl(p);
                    return {
                        symbol: p.symbol || '--',
                        name: p.name || p.symbol || '--',
                        label: p.name ? `${p.symbol} ${p.name}` : (p.symbol || '--'),
                        value: pnl.value,
                        pnlSource: pnl.source,
                        pnlPct: firstFiniteNumber([p.pnl_pct, p.pnl_percent, p.unrealized_pnl_pct]),
                        marketValue: firstFiniteNumber([p.market_value]) || 0
                    };
                });

            const fullBookPnlRows = pnlAttributionRows.filter(row => row.value !== null);
            const missingPnlCount = pnlAttributionRows.length - fullBookPnlRows.length;
            const pnlMaterialityFloor = Math.max(1, totalMv * 0.000001);
            const attributableRows = fullBookPnlRows
                .filter(row => Math.abs(row.value) >= pnlMaterialityFloor)
                .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
                .slice(0, 6);

            const netContribution = fullBookPnlRows.reduce((sum, row) => sum + row.value, 0);
            const positiveContribution = fullBookPnlRows.reduce((sum, row) => sum + Math.max(row.value, 0), 0);
            const negativeContribution = fullBookPnlRows.reduce((sum, row) => sum + Math.min(row.value, 0), 0);
            const fullBookAbsContribution = fullBookPnlRows.reduce((sum, row) => sum + Math.abs(row.value), 0);
            const topAbsContribution = attributableRows.reduce((sum, row) => sum + Math.abs(row.value), 0);
            const maxAbsContribution = Math.max(pnlMaterialityFloor, ...attributableRows.map(row => Math.abs(row.value)));
            const hasGain = attributableRows.some(row => row.value > 0);
            const hasLoss = attributableRows.some(row => row.value < 0);
            const axisLimit = maxAbsContribution * 1.18;

            const netEl = document.getElementById('port-attr-net');
            const posEl = document.getElementById('port-attr-positive');
            const negEl = document.getElementById('port-attr-negative');
            const qualityEl = document.getElementById('port-attr-quality');

            if (!fullBookPnlRows.length) {
                if (netEl) {
                    netEl.textContent = 'N/A';
                    netEl.style.color = 'var(--text-tertiary)';
                }
                if (posEl) posEl.textContent = 'N/A';
                if (negEl) negEl.textContent = 'N/A';
                if (qualityEl) {
                    qualityEl.textContent = 'P&L DATA GAP';
                    qualityEl.dataset.state = 'warn';
                }
                attrChart.clear();
                attrChart.setOption({
                    graphic: {
                        type: 'text',
                        left: 'center',
                        top: 'middle',
                        style: {
                            text: 'P&L DATA GAP · FLOATING P&L FIELD MISSING',
                            fill: '#f59e0b',
                            font: '700 12px var(--font-mono)'
                        }
                    }
                });
                return;
            }

            if (netEl) {
                netEl.textContent = formatCompactCny(netContribution);
                netEl.style.color = netContribution > 0 ? 'var(--success)' : (netContribution < 0 ? 'var(--danger)' : 'var(--text-tertiary)');
            }
            if (posEl) posEl.textContent = formatCompactCny(positiveContribution);
            if (negEl) negEl.textContent = formatCompactCny(negativeContribution);
            if (qualityEl) {
                const coverage = fullBookAbsContribution > 0 ? (topAbsContribution / fullBookAbsContribution * 100) : 0;
                qualityEl.textContent = attributableRows.length
                    ? `TOP ${attributableRows.length} / COVER ${coverage.toFixed(0)}%${missingPnlCount ? ` / ${missingPnlCount} GAP` : ''}`
                    : 'BELOW MATERIALITY';
                qualityEl.dataset.state = missingPnlCount ? 'warn' : 'ok';
            }

            if (!attributableRows.length) {
                attrChart.clear();
                attrChart.setOption({
                    graphic: {
                        type: 'text',
                        left: 'center',
                        top: 'middle',
                        style: {
                            text: 'BELOW MATERIALITY · NO POSITION EXCEEDS P&L THRESHOLD',
                            fill: '#64748b',
                            font: '700 12px var(--font-mono)'
                        }
                    }
                });
                return;
            }

            attrChart.clear();
            attrChart.setOption({
                tooltip: {
                    className: 'terminal-hud-tooltip',
                    trigger: 'axis',
                    axisPointer: { type: 'line', lineStyle: { color: 'rgba(226,232,240,0.3)', type: 'dashed' } },
                    formatter: function(params) {
                        const p = params[0];
                        const d = p.data || {};
                        const color = p.value > 0 ? '#10b981' : '#f43f5e';
                        const impactShare = fullBookAbsContribution > 0 ? (Math.abs(p.value) / fullBookAbsContribution * 100).toFixed(1) : '0.0';
                        const pctLine = d.pnlPct !== null ? `P&L ${d.pnlPct > 0 ? '+' : ''}${d.pnlPct.toFixed(2)}%` : `MV ${formatCompactCny(d.marketValue)}`;
                        return `<div class="hud-title" style="border-bottom-color:${color};">${d.symbol || p.name} ${d.name || ''}</div>
                                <div class="hud-value" style="color:${color};">${formatCompactCny(p.value)}</div>
                                <div style="margin-top:8px; color:var(--text-tertiary); font-family:var(--font-mono); font-size:0.72rem;">
                                    ${p.value > 0 ? 'GAIN CONTRIBUTION' : 'LOSS DRAG'} / ${impactShare}% OF BOOK IMPACT · ${pctLine}
                                </div>`;
                    }
                },
                grid: { left: '3%', right: '8%', bottom: '6%', top: '9%', containLabel: true },
                xAxis: {
                    type: 'value',
                    min: hasGain && hasLoss ? -axisLimit : (hasLoss ? -axisLimit : 0),
                    max: hasGain && hasLoss ? axisLimit : (hasGain ? axisLimit : 0),
                    splitNumber: 4,
                    splitLine: { show: true, lineStyle: { color: 'rgba(148,163,184,0.08)', type: 'dashed' } },
                    axisLabel: {
                        color: 'var(--text-tertiary)',
                        fontFamily: 'var(--font-mono)',
                        fontSize: 10,
                        formatter: value => value === 0 ? 'ZERO P&L' : formatCompactCny(value).replace('\u00a5', '')
                    },
                    axisLine: { show: true, lineStyle: { color: 'rgba(226,232,240,0.18)', width: 1 } }
                },
                yAxis: {
                    type: 'category',
                    data: attributableRows.map(row => row.label).reverse(),
                    axisLabel: {
                        color: '#e2e8f0',
                        fontFamily: 'var(--font-mono)',
                        fontSize: 11,
                        fontWeight: 700,
                        width: 112,
                        overflow: 'truncate'
                    },
                    axisLine: { show: false },
                    axisTick: { show: false }
                },
                series: [{
                    name: 'P&L',
                    type: 'bar',
                    barWidth: 14,
                    label: {
                        show: true,
                        color: '#cbd5e1',
                        fontFamily: 'var(--font-mono)',
                        fontSize: 10,
                        formatter: params => formatCompactCny(params.value)
                    },
                    markLine: {
                        symbol: 'none',
                        silent: true,
                        label: {
                            formatter: 'ZERO',
                            color: 'rgba(148,163,184,0.75)',
                            fontFamily: 'var(--font-mono)',
                            fontSize: 9
                        },
                        lineStyle: { color: 'rgba(226,232,240,0.34)', width: 1 },
                        data: [{ xAxis: 0 }]
                    },
                    data: attributableRows.map(row => {
                        const val = row.value;
                        return {
                            value: val,
                            symbol: row.symbol,
                            name: row.name,
                            pnlPct: row.pnlPct,
                            pnlSource: row.pnlSource,
                            marketValue: row.marketValue,
                            label: { position: val > 0 ? 'right' : 'left' },
                            itemStyle: {
                                borderRadius: val > 0 ? [0, 4, 4, 0] : [4, 0, 0, 4],
                                color: new echarts.graphic.LinearGradient(1, 0, 0, 0, [
                                    { offset: 0, color: val > 0 ? 'rgba(16,185,129,0.95)' : 'rgba(244,63,94,0.20)' },
                                    { offset: 1, color: val > 0 ? 'rgba(16,185,129,0.22)' : 'rgba(244,63,94,0.95)' }
                                ]),
                                shadowBlur: 12,
                                shadowColor: val > 0 ? 'rgba(16,185,129,0.36)' : 'rgba(244,63,94,0.36)'
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
    const amount = prompt("输入现金划拨金额（正数为申购/转入，负数为赎回/转出）：", "1000000");
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
    const rate = prompt("设置双边交易摩擦率（5 bps 输入 0.0005，15 bps 输入 0.0015）：", simuFrictionRate.toString());
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
        t._name = pos.name;

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
                complianceMsgs.push(`禁止裸卖空: ${t.ticker} ${pos.name}`);
            }
            pos.quantity = Math.max(0, pos.quantity - tradeQty);
            pos.market_value = Math.max(0, pos.market_value - cost);
            cashImpact += cost;
        }
    });

    const postTradeCash = baseCash + cashImpact - totalFriction;
    if (postTradeCash < 0) {
        complianceFailed = true;
            complianceMsgs.push('现金透支');
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
            complianceMsgs.push(`高集中度风险: ${p.symbol} ${p.name}`);
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

    document.getElementById('simu-fric-cost').textContent = `预估交易摩擦: ¥${totalFriction.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}`;

    const compEl = document.getElementById('simu-compliance');
    const turnCard = document.getElementById('simu-turnover-card');
    if (complianceFailed) {
        compEl.innerHTML = `[ 未通过 ]<br><span style="font-size:0.6em; font-weight:400; color:var(--text-tertiary);">${complianceMsgs[0]}</span>`;
        compEl.style.color = 'var(--danger)';
        turnCard.style.border = '1px solid rgba(239, 68, 68, 0.4)';
        turnCard.className = 'glass-card glow-fail';
    } else {
        compEl.textContent = '[ 通过 ]';
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
                <td style="font-family:var(--font-mono); font-weight:700;">${t.ticker} <span style="font-weight:400; color:var(--text-tertiary); font-size:0.85em; margin-left:4px;">${t._name !== t.ticker ? t._name : ''}</span></td>
                <td style="text-align:right; font-family:var(--font-mono); font-size:0.7rem;">${valStr}</td>
                <td style="text-align:right; font-family:var(--font-mono); color:var(--text-tertiary);">¥${t._estCost.toLocaleString(undefined, {maximumFractionDigits:0})}</td>
                <td><button data-action="remove-simu-trade" data-trade-id="${t.id}" style="background:transparent; border:none; color:var(--danger); cursor:pointer;">删除</button></td>
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
            <tr class="clickable-row" style="transition: background-color 0.2s ease;" data-action="open-action-modal" data-symbol="${escapeHTML(p.symbol)}" data-name="${escapeHTML(p.name || '')}" data-qty="${p.quantity || 0}" data-price="${p.current_price || 0}">
                <td style="padding-left:16px;">
                    <div style="display:flex; flex-direction:column; gap:2px;">
                        <span style="font-weight:700; color:var(--text-primary); font-size:0.95rem;">${p.name || p.symbol}</span>
                        <span style="font-family:var(--font-mono); font-size:0.7rem; color:var(--text-tertiary);">${p.symbol}</span>
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

    // Friction cost audit bar & radar integration
    const targetWeights = {};
    proj.forEach(p => {
        targetWeights[p.symbol] = p._projWt;
    });

    fetch('/api/institutional/sandbox/friction', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ target_weights: targetWeights })
    })
    .then(r => r.json())
    .then(dataFric => {
        if (dataFric && !dataFric.error) {
            const commEl = document.getElementById('simu-audit-commission');
            const impEl = document.getElementById('simu-audit-impact');
            const totEl = document.getElementById('simu-audit-total-cost');
            const netAumEl = document.getElementById('simu-audit-net-aum');

            if (commEl) commEl.textContent = formatCny(dataFric.commission_cost, {minimumFractionDigits:2, maximumFractionDigits:2});
            if (impEl) impEl.textContent = formatCny(dataFric.market_impact_cost, {minimumFractionDigits:2, maximumFractionDigits:2});
            if (totEl) totEl.textContent = `${formatCny(dataFric.total_friction_cost, {minimumFractionDigits:2, maximumFractionDigits:2})} (${dataFric.total_cost_bps.toFixed(2)} bps)`;
            if (netAumEl) netAumEl.textContent = formatCny(dataFric.net_projected_aum, {minimumFractionDigits:2, maximumFractionDigits:2});

            // Warn about participation limits if any
            const radar = document.getElementById('simu-liquidity-radar');
            const radarContent = document.getElementById('simu-radar-content');
            if (radar && radarContent) {
                const warnings = dataFric.details.filter(d => d.warning_level === 'RED' || d.warning_level === 'YELLOW');
                if (warnings.length > 0) {
                    radar.style.display = 'block';
                    radarContent.innerHTML = warnings.map(w => `<div>[WARN] <strong>${w.symbol}</strong>: ADV participation ${(w.participation_rate * 100).toFixed(2)}% - ${w.warning_msg}</div>`).join('');
                } else {
                    radar.style.display = 'none';
                }
            }
        }
    })
    .catch(e => console.error('Failed to calculate simulated transaction costs', e));
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
                name: '当前配置',
                type: 'pie',
                radius: ['30%', '50%'],
                itemStyle: { borderColor: '#0f172a', borderWidth: 1, opacity: 0.5 },
                label: { position: 'inner', fontSize: 10, color: '#64748b', formatter: '{b}' },
                data: baseData
            },
            {
                name: '模拟配置',
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
async function injectTradeFromModal(action, qty) {
    if (!currentActionContext || qty <= 0) return;

    // UI state: disable buttons
    const btns = document.querySelectorAll('.modal-action-btn');
    btns.forEach(b => b.disabled = true);
    const originalText = btns[0].innerText;
    btns[0].innerText = 'EXECUTING...';
    try {
        const response = await fetch('/api/execute', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                ticker: currentActionContext.ticker,
                action: action,
                qty: parseFloat(qty)
            })
        });
        const result = await response.json();
        if(result.status === 'success') {
            // refresh execution history immediately
            if(window.refreshAuditTrail) window.refreshAuditTrail();
        } else {
            alert('[SYS_ERROR] Gateway Execution Failed: ' + (result.error || 'Unknown error'));
        }
    } catch(e) {
        alert('[SYS_ERROR] Gateway Offline or Unreachable.');
    } finally {
        btns.forEach(b => b.disabled = false);
        btns[0].innerText = originalText;
        closeActionModal();
        const viewPort = document.getElementById('view-portfolio');
        if (viewPort && !viewPort.classList.contains('active')) {
            switchView('view-portfolio');
            setTimeout(() => {
                if (typeof switchSandboxTab === 'function') {
                    switchSandboxTab('tab-rebalance-sandbox');
                }
            }, 50);
        } else {
            const activeSubTab = document.getElementById('tab-rebalance-sandbox');
            if (activeSubTab && activeSubTab.style.display === 'none') {
                if (typeof switchSandboxTab === 'function') {
                    switchSandboxTab('tab-rebalance-sandbox');
                }
            }
        }
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

