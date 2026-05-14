import re

with open(r'd:\FIONA\google touzi\static\main.js', 'r', encoding='utf-8') as f:
    content = f.read()

start_idx = content.find('async function initInstitutionalDecision() {')
if start_idx == -1:
    print('Not found')
    exit(1)

stack = 0
end_idx = -1
for i in range(start_idx, len(content)):
    if content[i] == '{': stack += 1
    elif content[i] == '}':
        stack -= 1
        if stack == 0:
            end_idx = i + 1
            break

if end_idx == -1:
    print('End not found')
    exit(1)

new_func = """async function initInstitutionalDecision() {
    const panel = document.getElementById('view-institutional');
    if (!panel) return;

    try {
        const data = await fetchJsonWithRetry('/api/institutional/decision');
        const auditResp = await fetch('/api/institutional/audit/decisions?limit=10');
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
            const ticketStatus = ticket.decision_status || '';
            if (ticketStatus === 'allow') actionHero.style.color = '#22c55e';
            else if (ticketStatus === 'observe') actionHero.style.color = '#ef4444';
            else actionHero.style.color = '#fbbf24';
            actionHero.textContent = actText;
        }
        
        const reasonHero = document.getElementById('decision-reason-hero');
        if (reasonHero) {
            const codes = explanation.reason_codes || [];
            const driver = explanation.primary_driver?.code || '';
            reasonHero.textContent = codes.length ? codes.map(c => c.code || c).join('  |  ') : (driver || '--');
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
}"""

content = content[:start_idx] + new_func + content[end_idx:]

with open(r'd:\FIONA\google touzi\static\main.js', 'w', encoding='utf-8') as f:
    f.write(content)
print('Replaced initInstitutionalDecision')
