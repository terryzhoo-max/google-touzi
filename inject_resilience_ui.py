import re
import codecs

with codecs.open('static/main.js', 'r', 'utf-8') as f:
    full_content = f.read()

# We will append the resilience logic at the end of main.js
resilience_js = """
// ── INSTITUTIONAL RESILIENCE & ALERT COMMAND CENTER ──
(function() {
    console.log("Initializing Institutional Resilience Layer...");

    // 1. Inject the Command Center Modal into Body
    const modalHtml = `
        <div id="resilience-modal-backdrop" style="display:none; position:fixed; top:0; left:0; width:100vw; height:100vh; background:rgba(0,0,0,0.6); backdrop-filter:blur(4px); z-index:9998; opacity:0; transition:opacity 0.3s;"></div>
        <div id="resilience-command-center" style="display:none; position:fixed; top:50%; left:50%; transform:translate(-50%, -45%); width:600px; max-width:90vw; max-height:85vh; background:rgba(15, 23, 42, 0.95); border:1px solid rgba(255,255,255,0.1); border-radius:12px; z-index:9999; box-shadow:0 25px 50px -12px rgba(0,0,0,0.5); flex-direction:column; opacity:0; transition:all 0.3s cubic-bezier(0.16, 1, 0.3, 1);">
            <div style="padding:16px 20px; border-bottom:1px solid rgba(255,255,255,0.05); display:flex; justify-content:space-between; align-items:center; background:rgba(0,0,0,0.2); border-radius:12px 12px 0 0;">
                <h3 style="margin:0; color:var(--text-primary); font-size:1.1rem; letter-spacing:1px; display:flex; align-items:center; gap:8px;">
                    <i class="fas fa-shield-alt" style="color:#a855f7;"></i> 系统风控与告警中心 <span style="font-size:0.7rem; color:var(--text-tertiary); font-family:var(--font-mono); font-weight:normal; margin-left:8px;">COMMAND CENTER V1</span>
                </h3>
                <button id="resilience-close-btn" style="background:transparent; border:none; color:var(--text-tertiary); cursor:pointer; font-size:1.2rem; padding:4px;">&times;</button>
            </div>
            
            <div style="display:flex; border-bottom:1px solid rgba(255,255,255,0.05);">
                <button class="resilience-tab active" data-target="health-tab" style="flex:1; padding:12px; background:rgba(255,255,255,0.02); border:none; color:var(--text-primary); font-weight:bold; cursor:pointer; border-bottom:2px solid #a855f7;">系统健康度 (HEALTH)</button>
                <button class="resilience-tab" data-target="alerts-tab" style="flex:1; padding:12px; background:transparent; border:none; color:var(--text-secondary); cursor:pointer; border-bottom:2px solid transparent;">告警规则配置 (ALERTS)</button>
            </div>

            <div style="flex:1; overflow-y:auto; padding:20px;">
                <!-- Health Tab -->
                <div id="health-tab" class="resilience-tab-content">
                    <div id="health-loading" style="text-align:center; padding:20px; color:var(--text-tertiary);"><div class="loading-spinner"></div> 检测中...</div>
                    <div id="health-content" style="display:none; font-family:var(--font-mono); font-size:0.85rem; color:var(--text-secondary);"></div>
                </div>

                <!-- Alerts Tab -->
                <div id="alerts-tab" class="resilience-tab-content" style="display:none;">
                    <div id="alerts-loading" style="text-align:center; padding:20px; color:var(--text-tertiary);"><div class="loading-spinner"></div> 读取规则...</div>
                    <div id="alerts-content" style="display:none;"></div>
                    <div style="margin-top:20px; text-align:right;">
                        <button id="save-alerts-btn" style="background:#a855f7; color:#fff; border:none; padding:8px 16px; border-radius:4px; font-weight:bold; cursor:pointer; font-family:var(--font-sans); box-shadow:0 0 15px rgba(168,85,247,0.3);">保存并生效 (SAVE)</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Only inject if not exists
    if (!document.getElementById('resilience-command-center')) {
        const div = document.createElement('div');
        div.innerHTML = modalHtml;
        document.body.appendChild(div);
    }

    const modal = document.getElementById('resilience-command-center');
    const backdrop = document.getElementById('resilience-modal-backdrop');
    let currentRules = [];

    // UI Toggles
    const openModal = () => {
        backdrop.style.display = 'block';
        modal.style.display = 'flex';
        setTimeout(() => { backdrop.style.opacity = '1'; modal.style.opacity = '1'; modal.style.transform = 'translate(-50%, -50%)'; }, 10);
        renderHealthTab();
        renderAlertsTab();
    };

    const closeModal = () => {
        backdrop.style.opacity = '0';
        modal.style.opacity = '0';
        modal.style.transform = 'translate(-50%, -45%)';
        setTimeout(() => { backdrop.style.display = 'none'; modal.style.display = 'none'; }, 300);
    };

    document.getElementById('resilience-close-btn').addEventListener('click', closeModal);
    backdrop.addEventListener('click', closeModal);

    // Tab switching
    document.querySelectorAll('.resilience-tab').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.resilience-tab').forEach(b => {
                b.classList.remove('active');
                b.style.background = 'transparent';
                b.style.color = 'var(--text-secondary)';
                b.style.borderBottom = '2px solid transparent';
            });
            const target = e.target;
            target.classList.add('active');
            target.style.background = 'rgba(255,255,255,0.02)';
            target.style.color = 'var(--text-primary)';
            target.style.borderBottom = '2px solid #a855f7';

            document.querySelectorAll('.resilience-tab-content').forEach(c => c.style.display = 'none');
            document.getElementById(target.getAttribute('data-target')).style.display = 'block';
        });
    });

    // 2. Health Check & Badge Logic
    const updateBadge = (statusObj) => {
        const badge = document.getElementById('hub-status-badge');
        if (!badge) return; // Might not be rendered yet

        // Overwrite default badge styling so it acts like a button
        badge.style.cursor = 'pointer';
        badge.title = "点击进入风控指挥中心";
        badge.onclick = openModal;

        let color = '#22c55e';
        let text = 'SYSTEM ACTIVE';
        let bg = 'rgba(34,197,94,0.1)';
        
        if (statusObj.status === 'degraded' || (statusObj.degraded_sources && statusObj.degraded_sources.length > 0)) {
            color = '#f59e0b';
            text = 'SYSTEM DEGRADED';
            bg = 'rgba(245,158,11,0.1)';
            badge.style.animation = 'modalFadeIn 2s infinite alternate';
        } else if (statusObj.active_alerts > 0) {
            color = '#ef4444';
            text = 'ALERTS TRIGGERED';
            bg = 'rgba(239,68,68,0.1)';
            badge.style.animation = 'modalFadeIn 1s infinite alternate';
        } else {
            badge.style.animation = 'none';
        }

        badge.style.color = color;
        badge.style.borderColor = color + '40';
        badge.style.background = bg;
        badge.style.boxShadow = `0 0 10px ${bg} inset`;
        badge.innerHTML = `<span style="margin-right:6px;"><i class="fas fa-shield-alt"></i></span> ` + text;
    };

    let lastHealthData = null;

    const fetchHealthState = () => {
        fetch('/api/health')
            .then(r => r.json())
            .then(data => {
                lastHealthData = data;
                updateBadge(data);
            })
            .catch(err => console.error("Health check failed", err));
    };

    // Render Health Data
    const renderHealthTab = () => {
        const loading = document.getElementById('health-loading');
        const content = document.getElementById('health-content');
        if (!lastHealthData) {
            loading.style.display = 'block'; content.style.display = 'none'; return;
        }
        loading.style.display = 'none'; content.style.display = 'block';
        
        let html = `<div style="margin-bottom:16px;"><strong style="color:var(--text-primary);">数据源状态 (Sources)</strong></div>`;
        html += `<div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">`;
        
        const sources = lastHealthData.sources || {};
        const circuit = lastHealthData.circuit || {};
        
        Object.keys(sources).forEach(k => {
            const s = sources[k];
            const cb = circuit[k] || {state: 'closed'};
            const isDegraded = s.error_rate > 0.3 || cb.state !== 'closed';
            const color = isDegraded ? '#f59e0b' : '#22c55e';
            
            html += `
                <div style="background:rgba(255,255,255,0.02); border:1px solid ${color}30; border-radius:6px; padding:12px; border-left:3px solid ${color};">
                    <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                        <span style="font-weight:bold; color:var(--text-primary); text-transform:uppercase;">${k}</span>
                        <span style="color:${color}; font-weight:bold;">${cb.state === 'open' ? '熔断 (OPEN)' : '正常'}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; color:var(--text-tertiary); font-size:0.75rem;">
                        <span>成功率: ${((1 - (s.error_rate || 0))*100).toFixed(0)}%</span>
                        <span>延迟: ${s.avg_ms}ms</span>
                    </div>
                </div>
            `;
        });
        html += `</div>`;
        content.innerHTML = html;
    };

    // Render Alerts Data
    const renderAlertsTab = () => {
        const loading = document.getElementById('alerts-loading');
        const content = document.getElementById('alerts-content');
        
        loading.style.display = 'block'; content.style.display = 'none';
        
        fetch('/api/alerts/rules')
            .then(r => r.json())
            .then(data => {
                currentRules = data.rules || [];
                loading.style.display = 'none'; content.style.display = 'block';
                
                let html = `<div style="display:flex; flex-direction:column; gap:8px;">`;
                currentRules.forEach((r, idx) => {
                    html += `
                        <div style="background:rgba(255,255,255,0.02); border:1px solid var(--row-border); border-radius:6px; padding:12px; display:flex; flex-direction:column; gap:8px;">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <strong style="color:var(--text-primary); font-size:0.95rem;">${r.name} <span style="font-family:var(--font-mono); color:var(--text-tertiary); font-size:0.7rem; margin-left:8px; font-weight:normal;">[${r.id}]</span></strong>
                                <label style="display:flex; align-items:center; cursor:pointer;">
                                    <input type="checkbox" id="rule-en-${idx}" ${r.enabled ? 'checked' : ''} style="accent-color:#a855f7; width:16px; height:16px; margin-right:8px;">
                                    <span style="color:var(--text-secondary); font-size:0.85rem;">启用</span>
                                </label>
                            </div>
                            <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(0,0,0,0.2); padding:8px; border-radius:4px; font-family:var(--font-mono); font-size:0.85rem;">
                                <div style="color:var(--text-secondary);">
                                    <span style="color:#38bdf8;">${r.field}</span> 
                                    <span style="color:#f472b6;">${r.operator}</span>
                                </div>
                                <div>
                                    <input type="number" id="rule-th-${idx}" value="${r.threshold}" step="0.1" style="width:80px; background:transparent; border:1px solid var(--row-border); color:var(--accent-primary); font-family:var(--font-mono); font-weight:bold; padding:4px; border-radius:4px; text-align:right;">
                                </div>
                            </div>
                        </div>
                    `;
                });
                html += `</div>`;
                content.innerHTML = html;
            });
    };

    // Save Alerts
    document.getElementById('save-alerts-btn').addEventListener('click', () => {
        const btn = document.getElementById('save-alerts-btn');
        btn.innerText = '保存中...';
        btn.style.opacity = '0.7';
        
        const updatedRules = currentRules.map((r, idx) => {
            return {
                ...r,
                enabled: document.getElementById(`rule-en-${idx}`).checked,
                threshold: parseFloat(document.getElementById(`rule-th-${idx}`).value)
            };
        });

        fetch('/api/alerts/rules', {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({rules: updatedRules})
        })
        .then(r => r.json())
        .then(data => {
            btn.innerText = '已保存 ✓';
            btn.style.background = '#22c55e';
            btn.style.boxShadow = '0 0 15px rgba(34,197,94,0.3)';
            setTimeout(() => {
                btn.innerText = '保存并生效 (SAVE)';
                btn.style.background = '#a855f7';
                btn.style.boxShadow = '0 0 15px rgba(168,85,247,0.3)';
                btn.style.opacity = '1';
                closeModal();
            }, 1500);
        })
        .catch(err => {
            console.error("Save failed", err);
            btn.innerText = '保存失败!';
            btn.style.background = '#ef4444';
        });
    });

    // Start Polling
    fetchHealthState();
    setInterval(fetchHealthState, 60000); // 60s
    
    // Monkey patch the global render function if needed to re-bind the badge after L1-L5 renders
    // We observe the hub-root for changes
    const observer = new MutationObserver((mutations) => {
        for (let m of mutations) {
            if (m.addedNodes.length > 0) {
                const badge = document.getElementById('hub-status-badge');
                if (badge && !badge.onclick) {
                    if (lastHealthData) updateBadge(lastHealthData);
                }
            }
        }
    });
    const root = document.getElementById('hub-root');
    // If hub-root isn't immediately available, observe body and attach later.
    if (root) {
        observer.observe(root, {childList: true, subtree: true});
    } else {
        const rootObserver = new MutationObserver(() => {
            const r = document.getElementById('hub-root');
            if (r) {
                observer.observe(r, {childList: true, subtree: true});
                rootObserver.disconnect();
            }
        });
        rootObserver.observe(document.body, {childList: true, subtree: true});
    }

})();
"""

if "INSTITUTIONAL RESILIENCE & ALERT COMMAND CENTER" not in full_content:
    new_content = full_content + "\n" + resilience_js
    with codecs.open('static/main.js', 'w', 'utf-8') as f:
        f.write(new_content)
    print("✅ Successfully injected Institutional Resilience Layer into static/main.js")
else:
    print("ℹ️ Institutional Resilience Layer already exists in static/main.js")
