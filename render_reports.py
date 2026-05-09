import os
import markdown
from datetime import datetime

os.makedirs('static/reports', exist_ok=True)

try:
    with open("report_template.html", "r", encoding="utf-8") as f:
        template = f.read()
except:
    template = "<html><body><h1>{{TITLE}}</h1><div>{{CONTENT}}</div></body></html>"

for f in os.listdir('reports'):
    if f.endswith('.md'):
        doc_id = f[:-3]
        
        with open(os.path.join('reports', f), "r", encoding="utf-8") as md_file:
            md_content = md_file.read()
            
        html_content = markdown.markdown(md_content, extensions=['fenced_code', 'tables'])

        title = doc_id.replace("_", " ").title()
        tag = "深度研报"
        if "liquidity_trap" in doc_id:
            title = "穿越流动性陷阱：一种量化视角的资产配置指南"
            tag = "宏观策略"
        elif "ah_premium" in doc_id:
            title = "解构 AH 股溢价的均值回归"
            tag = "信号解析"

        final_html = template.replace("{{TITLE}}", title)
        final_html = final_html.replace("{{TAG}}", tag)
        final_html = final_html.replace("{{DATE}}", datetime.now().strftime("%Y年%m月%d日"))
        final_html = final_html.replace("{{CONTENT}}", html_content)
        
        with open(os.path.join('static', 'reports', f'{doc_id}.html'), 'w', encoding='utf-8') as html_file:
            html_file.write(final_html)

print("Rendered reports correctly using template.")
