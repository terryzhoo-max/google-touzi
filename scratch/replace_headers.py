import re

with open('d:\\FIONA\\google touzi\\static\\main.js', 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()

# Replace the table headers
def replacer(match):
    return '''<tr>
                        <th style="padding:12px 16px; text-align:left;">资产/指数 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">ASSET</span></th>
                        <th style="text-align:left;">资产类别 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">CLASS</span></th>
                        <th style="text-align:left;">动量状态 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">MOMENTUM</span></th>
                        <th style="text-align:center;">趋势轮廓 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">TREND PROFILE (1D &rarr; YTD)</span></th>
                    </tr>'''

pattern = r'<tr>\s*<th style="padding:12px 16px; text-align:left;">[^<]*ASSET</th>\s*<th style="text-align:left;">[^<]*CLASS</th>\s*<th style="text-align:left;">[^<]*MOMENTUM</th>\s*<th style="text-align:center;">[^<]*TREND PROFILE \(1D [^<]* YTD\)</th>\s*</tr>'
text, count = re.subn(pattern, replacer, text, flags=re.DOTALL)

if count > 0:
    with open('d:\\FIONA\\google touzi\\static\\main.js', 'w', encoding='utf-8') as f:
        f.write(text)
    print(f'Successfully replaced {count} occurrence(s).')
else:
    print('Pattern not found in main.js. Let me print the surrounding area:')
    m = re.search(r'<thead.*?</thead>', text, flags=re.DOTALL)
    if m:
        print(m.group(0))
    else:
        print('thead not found')
