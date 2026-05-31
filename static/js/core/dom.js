(function (app) {
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

    function getSymbolChineseName(symbol) {
        if (window.symbolNamesCache && window.symbolNamesCache[symbol]) {
            return window.symbolNamesCache[symbol];
        }
        if (window.portfolioData && window.portfolioData.positions) {
            const p = window.portfolioData.positions.find(pos => pos.symbol === symbol);
            if (p && p.name) return p.name;
        }
        const assetZH = {
        'CSI300_ETF': 'CSI 300 ETF',
        'CSI300': 'CSI 300 Index',
        '688981': 'SMIC',
        '600519': 'Kweichow Moutai',
        'CASH': 'Cash'
        };
        if (assetZH[symbol]) return assetZH[symbol];
        const base = String(symbol || '').split('.')[0];
        if (assetZH[base]) return assetZH[base];
        return symbol;
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

    function formatLargestActiveHTML(activeRisk) {
        const row = (activeRisk?.largest_active_exposures || [])[0];
        if (!row) return '--';
        const symbol = row.symbol || '';
        const pct = `${Math.round((row.active_weight || 0) * 1000) / 10}%`;
        const name = getSymbolChineseName(symbol);
        return `<span style="font-size:1.05rem; font-weight:800; color:var(--text-primary); font-family:var(--font-sans);">${name}</span><span style="font-family:var(--font-mono); font-size:0.7rem; color:var(--text-tertiary); margin-left:6px; font-weight:400;">(${symbol})</span><span style="font-family:var(--font-mono); font-size:1.15rem; font-weight:800; color:var(--accent-primary); margin-left:10px; text-shadow:0 0 10px rgba(56,189,248,0.4);">${pct}</span>`;
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
            .replace(/(risk|warning|alert|drawdown)/gi, '<span class="ai-keyword-risk">$1</span>')
            .replace(/(bullish|buy|positive|long)/gi, '<span class="ai-keyword-positive">$1</span>')
            .replace(/(VIX|10Y|DXY|SPY|TLT)/g, '<span class="ai-keyword-ticker">$1</span>');
        if (!window.DOMPurify) {
            return escapeHTML(insight);
        }
        return DOMPurify.sanitize(highlightedHTML, {
            ALLOWED_TAGS: ['p', 'strong', 'em', 'ul', 'ol', 'li', 'br', 'span'],
            ALLOWED_ATTR: ['class'],
        });
    }

    Object.assign(window, {
        clearChildren,
        safeCssColor,
        safeLevelClass,
        appendTextBlock,
        renderAlertList,
        renderScenarioMetric,
        renderScenarioGrid,
        formatTopExposure,
        formatReasonCodes,
        shortHash,
        getSymbolChineseName,
        formatTopFactor,
        formatLargestActive,
        formatLargestActiveHTML,
        formatComplianceIssues,
        formatAttribution,
        formatEvidence,
        escapeHTML,
        renderSafeAIInsight,
    });

    app.dom = {
        clearChildren,
        safeCssColor,
        safeLevelClass,
        appendTextBlock,
        renderAlertList,
        renderScenarioMetric,
        renderScenarioGrid,
        escapeHTML,
        renderSafeAIInsight,
    };
    app.formatters = {
        formatTopExposure,
        formatReasonCodes,
        shortHash,
        getSymbolChineseName,
        formatTopFactor,
        formatLargestActive,
        formatLargestActiveHTML,
        formatComplianceIssues,
        formatAttribution,
        formatEvidence,
    };
})(window.AlphaCore);
