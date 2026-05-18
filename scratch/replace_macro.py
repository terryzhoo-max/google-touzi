import os

file_path = r"d:\FIONA\google touzi\static\index.html"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

replacements = {
    '<th style="padding:12px 16px; text-align:left;">ASSET</th>': '<th style="padding:12px 16px; text-align:left;">资产/指数 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">ASSET</span></th>',
    '<th style="text-align:left;">CLASS</th>': '<th style="text-align:left;">资产类别 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">CLASS</span></th>',
    '<th style="text-align:left;">MOMENTUM</th>': '<th style="text-align:left;">动量状态 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">MOMENTUM</span></th>',
    '<th style="text-align:center;">TREND PROFILE (1D → YTD)</th>': '<th style="text-align:center;">趋势截面 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">TREND PROFILE (1D → YTD)</span></th>',
    '<tr><th style="padding-left:16px;">ASSET</th><th>YIELD</th><th>PE</th><th>PB</th><th>MKT CAP(亿)</th></tr>': '<tr><th style="padding-left:16px;">标的 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">ASSET</span></th><th>股息率 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">YIELD</span></th><th>市盈率 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">PE</span></th><th>市净率 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">PB</span></th><th>总市值(亿) <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">MKT CAP</span></th></tr>'
}

for old, new in replacements.items():
    content = content.replace(old, new)
    
with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Table headers replaced successfully!")
