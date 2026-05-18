import re
import os

file_path = r"d:\FIONA\google touzi\static\index.html"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

pattern = r"(<th[^>]*>)\s*([A-Za-z0-9_ &]+)\s*(<span[^>]*>)\s*([^<]+)\s*(</span>\s*</th>)"

def replacer(match):
    th_open = match.group(1)
    en_text = match.group(2).strip()
    span_open = match.group(3)
    zh_text = match.group(4).strip()
    span_close = match.group(5)
    return f"{th_open}{zh_text} {span_open}{en_text}{span_close}"

new_content = re.sub(pattern, replacer, content)

smart_cli_old = """                                    <tr>
                                        <th>ACTION</th>
                                        <th>TICKER</th>
                                        <th style="text-align:right;">QTY/WT</th>
                                        <th style="text-align:right;">EST COST</th>
                                        <th></th>
                                    </tr>"""

smart_cli_new = """                                    <tr>
                                        <th>方向 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">ACTION</span></th>
                                        <th>标的 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">TICKER</span></th>
                                        <th style="text-align:right;">数量/比例 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">QTY/WT</span></th>
                                        <th style="text-align:right;">预估成本 <span style="display:block; font-size:0.7em; color:var(--text-tertiary); font-weight:400;">EST COST</span></th>
                                        <th></th>
                                    </tr>"""

new_content = new_content.replace(smart_cli_old, smart_cli_new)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print("Headers swapped successfully!")
