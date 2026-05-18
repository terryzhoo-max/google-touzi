import os

file_path = r"d:\FIONA\google touzi\static\main.js"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

replacements = {
    '<th style="padding:12px 16px; text-align:left;">ASSET / SECTOR</th>': '<th style="padding:12px 16px; text-align:left;">资产/板块 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">ASSET / SECTOR</span></th>',
    '<th style="text-align:left;">MOMENTUM</th>': '<th style="text-align:left;">动量状态 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">MOMENTUM</span></th>',
    '<th style="text-align:center;">TREND PROFILE (5D → 60D)</th>': '<th style="text-align:center;">趋势截面 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">TREND PROFILE (5D → 60D)</span></th>',
    '<th style="padding:12px 16px; text-align:left;">ASSET</th>': '<th style="padding:12px 16px; text-align:left;">资产/指数 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">ASSET</span></th>',
    '<th style="text-align:left;">CLASS</th>': '<th style="text-align:left;">资产类别 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">CLASS</span></th>',
    '<th style="text-align:center;">TREND PROFILE (1D → YTD)</th>': '<th style="text-align:center;">趋势截面 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">TREND PROFILE (1D → YTD)</span></th>',
    '<tr><th style="padding-left:16px;">ASSET</th><th>YIELD</th><th>PE</th><th>PB</th><th>MKT CAP(亿)</th></tr>': '<tr><th style="padding-left:16px;">标的 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">ASSET</span></th><th>股息率 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">YIELD</span></th><th>市盈率 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">PE</span></th><th>市净率 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">PB</span></th><th>总市值(亿) <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">MKT CAP</span></th></tr>',
    'el.innerHTML = `<table class="institutional-table"><thead><tr><th>资产</th><th>当前</th><th>目标</th><th>变化</th><th>信号</th></tr></thead><tbody>` +': 'el.innerHTML = `<table class="institutional-table"><thead><tr><th>资产 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">ASSET</span></th><th>当前 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">CURR</span></th><th>目标 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">TGT</span></th><th>变化 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">DELTA</span></th><th>信号 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">SIGNAL</span></th></tr></thead><tbody>` +',
    'document.getElementById(\'portfolio-table\').innerHTML = `<table class="institutional-table"><thead><tr><th>资产</th><th>占比</th><th>成本</th><th>现价</th><th>市值</th><th>盈亏</th></tr></thead><tbody>` +': 'document.getElementById(\'portfolio-table\').innerHTML = `<table class="institutional-table"><thead><tr><th>资产 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">ASSET</span></th><th>占比 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">WEIGHT</span></th><th>成本 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">COST</span></th><th>现价 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">PRICE</span></th><th>市值 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">MKT VAL</span></th><th>盈亏 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">P&L</span></th></tr></thead><tbody>` +'
}

for old, new in replacements.items():
    content = content.replace(old, new)
    
with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Table headers in main.js replaced successfully!")
