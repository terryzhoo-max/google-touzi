import re

with open(r'd:\FIONA\google touzi\static\index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Add Navigation Link
nav_link = '''<a href="#view-simu" onclick="switchView('view-simu')" class="nav-link">
                    <span class="nav-cmd">[SIMU]</span> 交易沙盘
                </a>'''
new_nav_link = nav_link + '''
                <a href="#view-strategy" onclick="switchView('view-strategy')" class="nav-link">
                    <span class="nav-cmd">[STRA]</span> 策略工厂
                </a>'''
html = html.replace(nav_link, new_nav_link)

# 2. Add View Panel
view_panel = '''
        <!-- ==============================================
             [STRA] 策略工厂 (Strategy Lab)
        =============================================== -->
        <div id="view-strategy" class="view-panel" style="display:none;">
            <div class="terminal-header" style="margin-bottom:24px;">
                <h2>[STRA] 策略工厂 <span style="font-size:0.5em; color:var(--text-tertiary); font-weight:400; letter-spacing:2px; margin-left:12px;">GLOBAL MACRO STRATEGY LAB</span></h2>
                <div class="terminal-time" id="strategy-time">00:00:00</div>
            </div>

            <!-- Dashboard Split Layout -->
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:24px;">
                
                <!-- Left: Quant Engines -->
                <div style="display:flex; flex-direction:column; gap:16px;">
                    <div class="institutional-section-label" style="margin-bottom: 8px; font-size: 0.8rem; color: var(--text-tertiary); display:flex; align-items:center; gap:8px;">
                        <span style="width:8px; height:8px; background-color:var(--text-tertiary); border-radius:50%;"></span>
                        QUANTITATIVE ENGINES <span style="font-size:0.8em; font-weight:400;">量化引擎阵列</span>
                    </div>
                    <div id="strategy-engines-container" style="display:flex; flex-direction:column; gap:16px;">
                        <!-- Filled by JS -->
                        <div class="glass-card" style="padding:24px; text-align:center; color:var(--text-tertiary);">
                            <div class="spinner" style="margin:0 auto 12px;"></div>
                            INITIALIZING ENGINES...
                        </div>
                    </div>
                </div>

                <!-- Right: Backtest Matrix -->
                <div style="display:flex; flex-direction:column; gap:16px;">
                    <div class="institutional-section-label" style="margin-bottom: 8px; font-size: 0.8rem; color: var(--text-tertiary); display:flex; align-items:center; gap:8px;">
                        <span style="width:8px; height:8px; background-color:var(--accent-primary); border-radius:50%; box-shadow:0 0 8px var(--accent-primary);"></span>
                        BACKTEST PERFORMANCE <span style="font-size:0.8em; font-weight:400;">合成回测矩阵</span>
                    </div>
                    
                    <div class="glass-card" style="flex-grow:1; display:flex; flex-direction:column; min-height:400px;">
                        <div class="card-header" style="justify-content:space-between;">
                            <h3>COMPOUND EQUITY CURVE <span style="font-size:0.7em; color:var(--text-tertiary); font-weight:400; margin-left:8px; letter-spacing:1px;">合成净值曲线 (1Y)</span></h3>
                        </div>
                        <div class="terminal-grid-4" id="strategy-metrics-container" style="margin-bottom:16px;">
                            <!-- Filled by JS -->
                        </div>
                        <div id="chart-strategy-equity" class="chart-container" style="flex-grow:1; min-height:300px; width:100%;"></div>
                    </div>
                    
                    <div class="glass-card">
                        <div class="card-header">
                            <h3>ETF UNIVERSE <span style="font-size:0.7em; color:var(--text-tertiary); font-weight:400; margin-left:8px; letter-spacing:1px;">监控资产池</span></h3>
                        </div>
                        <div style="display:flex; gap:16px; flex-wrap:wrap;" id="strategy-universe-container">
                            <!-- Filled by JS -->
                        </div>
                    </div>
                </div>
            </div>
        </div>
'''

html = html.replace('</main>', view_panel + '\n    </main>')

with open(r'd:\FIONA\google touzi\static\index.html', 'w', encoding='utf-8') as f:
    f.write(html)
