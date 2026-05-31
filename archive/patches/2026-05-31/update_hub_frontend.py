from bs4 import BeautifulSoup
import re

html_path = r'd:\FIONA\google touzi\static\index.html'

with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Inject navigation link
nav_link = """
                <a href="#view-hub" onclick="switchView('view-hub')">
                    <span class="nav-cmd">[HUB]</span> DECISION HUB <span style="font-size:0.7em; color:var(--text-tertiary); margin-left:8px; font-weight:400; letter-spacing:1px;">决策中枢</span>
                </a>
"""
if '[HUB]' not in html:
    html = html.replace("</nav>", nav_link + "            </nav>")

# 2. Inject View Panel
hub_panel = """
        <!-- ==============================================
             [HUB] 全局决策中枢 (Global Decision Hub)
        =============================================== -->
        <div id="view-hub" class="view-panel">
            <div class="terminal-header" style="margin-bottom:24px;">
                <h2>[HUB] 全局决策中枢 <span style="font-size:0.5em; color:var(--text-tertiary); font-weight:400; letter-spacing:2px; margin-left:12px;">GLOBAL DECISION MATRIX</span></h2>
                <div class="terminal-time" id="hub-time">00:00:00</div>
            </div>

            <div style="display:flex; flex-direction:column; gap:20px;">
                <!-- Funnel Layer 1 & 2 -->
                <div style="display:flex; gap:20px;">
                    <div class="glass-card" style="flex:1;">
                        <div class="card-header">
                            <h3>L1: MACRO REGIME <span style="font-size:0.7em; color:var(--text-tertiary); margin-left:8px;">宏观基准锚定</span></h3>
                        </div>
                        <div id="hub-l1-content" style="font-size:0.9rem; line-height:1.6; color:var(--text-secondary);">
                            LOADING L1 DATA...
                        </div>
                    </div>
                    <div class="glass-card" style="flex:1;">
                        <div class="card-header">
                            <h3>L2: QUANT ENGINES <span style="font-size:0.7em; color:var(--text-tertiary); margin-left:8px;">量化信号阵列</span></h3>
                        </div>
                        <div id="hub-l2-content" style="font-size:0.9rem; line-height:1.6; color:var(--text-secondary);">
                            LOADING L2 DATA...
                        </div>
                    </div>
                </div>
                
                <!-- Funnel Layer 3 & 4 -->
                <div style="display:flex; gap:20px;">
                    <div class="glass-card" style="flex:1; border-left:4px solid #3b82f6;">
                        <div class="card-header">
                            <h3>L3: ROUTER & ALLOCATOR <span style="font-size:0.7em; color:var(--text-tertiary); margin-left:8px;">资金路由分配</span></h3>
                        </div>
                        <div id="hub-l3-content" style="font-size:0.9rem; line-height:1.6; color:var(--text-secondary);">
                            LOADING L3 DATA...
                        </div>
                    </div>
                    <div class="glass-card" id="hub-l4-card" style="flex:1;">
                        <div class="card-header">
                            <h3>L4: COMPLIANCE GATE <span style="font-size:0.7em; color:var(--text-tertiary); margin-left:8px;">风控合规门禁</span></h3>
                        </div>
                        <div id="hub-l4-content" style="font-size:0.9rem; line-height:1.6; color:var(--text-secondary);">
                            LOADING L4 DATA...
                        </div>
                    </div>
                </div>

                <!-- Funnel Layer 5 -->
                <div class="glass-card" id="hub-l5-card" style="border-top:4px solid #8b5cf6;">
                    <div class="card-header">
                        <h3>L5: AI-CIO SYNTHESIS <span style="font-size:0.7em; color:var(--text-tertiary); margin-left:8px;">大模型投委会归因</span></h3>
                    </div>
                    <div id="hub-l5-content" style="font-size:1rem; line-height:1.6; color:var(--text-primary); padding:16px; background:rgba(0,0,0,0.3); border-radius:8px;">
                        LOADING L5 MEMO...
                    </div>
                </div>
            </div>
        </div>
"""
if 'id="view-hub"' not in html:
    html = html.replace("</main>", hub_panel + "        </main>")

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)

print("Updated HTML.")

js_path = r'd:\FIONA\google touzi\static\main.js'
with open(js_path, 'r', encoding='utf-8') as f:
    js = f.read()

# Inject into switchView
if "viewId === 'view-hub'" not in js:
    js = js.replace("} else if (viewId === 'view-strategy') {", """} else if (viewId === 'view-strategy') {
        initStrategyLab();
    } else if (viewId === 'view-hub') {
        initDecisionHub();
    """)
    
# Inject initDecisionHub
hub_js = """
// ==========================================
// [HUB] DECISION HUB LOGIC
// ==========================================
async function initDecisionHub() {
    const hubTime = document.getElementById('hub-time');
    if (hubTime) hubTime.textContent = new Date().toLocaleTimeString('en-US', {hour12: false});
    
    try {
        const response = await fetch('/api/institutional/decision_hub');
        const data = await response.json();
        
        // Render L1 Macro
        const l1 = document.getElementById('hub-l1-content');
        if (l1) {
            const macro = data.l1_macro;
            const isStress = macro.vix_level > 25;
            l1.innerHTML = `
                <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                    <span>Market Regime:</span>
                    <strong style="color:${isStress ? '#ef4444' : '#22c55e'}">${macro.regime}</strong>
                </div>
                <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                    <span>VIX Level:</span>
                    <strong>${macro.vix_level}</strong>
                </div>
                <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                    <span>Max Equity Ceiling:</span>
                    <strong>${(macro.max_equity_exposure * 100).toFixed(0)}%</strong>
                </div>
                <div style="margin-top:12px; padding:8px; background:rgba(239, 68, 68, 0.1); border:1px solid #ef4444; border-radius:4px;">
                    <span style="color:#ef4444; font-weight:bold;">ACTION:</span> ${macro.recommended_action}
                </div>
            `;
        }
        
        // Render L2 Quant Signals
        const l2 = document.getElementById('hub-l2-content');
        if (l2) {
            let html = '<ul style="list-style:none; padding:0; margin:0; display:flex; flex-direction:column; gap:8px;">';
            data.l2_signals.forEach(sig => {
                html += `
                    <li style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.03); padding:8px; border-radius:4px;">
                        <span style="font-weight:bold; color:var(--text-primary);">${sig.source}</span>
                        <span style="color:var(--text-tertiary); font-family:var(--font-mono);">${sig.signal}</span>
                    </li>
                `;
            });
            html += '</ul>';
            l2.innerHTML = html;
        }
        
        // Render L3 Routing
        const l3 = document.getElementById('hub-l3-content');
        if (l3) {
            const weights = data.l3_routing.target_weights;
            let html = `<div style="margin-bottom:12px; color:var(--text-primary); font-style:italic;">"${data.l3_routing.rationale}"</div>`;
            html += '<div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">';
            for (const [sym, weight] of Object.entries(weights)) {
                if (weight > 0) {
                    html += `
                        <div style="background:rgba(59, 130, 246, 0.1); border:1px solid rgba(59, 130, 246, 0.3); padding:8px; border-radius:4px; display:flex; justify-content:space-between;">
                            <span>${sym}</span>
                            <strong style="color:#60a5fa;">${(weight*100).toFixed(1)}%</strong>
                        </div>
                    `;
                }
            }
            html += '</div>';
            l3.innerHTML = html;
        }
        
        // Render L4 Compliance
        const l4 = document.getElementById('hub-l4-content');
        const l4Card = document.getElementById('hub-l4-card');
        if (l4) {
            const comp = data.l4_compliance;
            const isBlock = comp.gate_status === 'HARD_BLOCK';
            l4Card.style.borderLeft = isBlock ? '4px solid #ef4444' : '4px solid #22c55e';
            
            let html = `
                <div style="font-size:1.2rem; font-weight:bold; margin-bottom:12px; color:${isBlock ? '#ef4444' : '#22c55e'};">
                    STATUS: ${comp.gate_status}
                </div>
            `;
            if (isBlock) {
                html += '<div style="color:#ef4444; margin-bottom:8px;"><strong>VIOLATIONS:</strong></div><ul style="color:#ef4444; margin-bottom:12px; padding-left:20px;">';
                comp.violations.forEach(v => html += `<li>${v}</li>`);
                html += '</ul>';
                
                html += '<div style="color:#f59e0b; margin-bottom:8px;"><strong>REPAIR SUGGESTIONS:</strong></div><ul style="color:#f59e0b; padding-left:20px;">';
                comp.repair_suggestions.forEach(v => html += `<li>${v}</li>`);
                html += '</ul>';
            } else {
                html += '<div style="color:#22c55e;">No critical violations. Trade flow permitted.</div>';
            }
            l4.innerHTML = html;
        }
        
        // Render L5 AI Memo
        const l5 = document.getElementById('hub-l5-content');
        if (l5) {
            const memo = data.l5_ai_memo;
            l5.innerHTML = `
                <h2 style="color:${memo.headline.includes('BLOCKED') ? '#ef4444' : '#22c55e'}; margin-top:0;">${memo.headline}</h2>
                <p style="margin-bottom:0;">${memo.memo}</p>
            `;
        }
        
    } catch (e) {
        console.error("Decision Hub Error", e);
    }
}
"""
if 'async function initDecisionHub' not in js:
    js += '\n' + hub_js
    
with open(js_path, 'w', encoding='utf-8') as f:
    f.write(js)
    
print("Updated main.js")
