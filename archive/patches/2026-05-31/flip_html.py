import re
import codecs

with codecs.open('static/index.html', 'r', 'utf-8') as f:
    html = f.read()

# 1. Flip sidebar links
# From: <span class="nav-cmd">[MACR]</span> MACRO <span style="...">宏观监控</span>
# To: <span class="zh-primary" style="margin-right:8px;">宏观监控</span> <span class="en-sub">[MACR] MACRO</span>

def sidebar_replacer(match):
    cmd = match.group(1)
    en = match.group(2).strip()
    zh = match.group(3).strip()
    return f'<span class="zh-primary" style="margin-right:8px;">{zh}</span> <span class="en-sub">[{cmd}] {en}</span>'

html = re.sub(
    r'<span class="nav-cmd">\[(.*?)\]</span>(.*?)(?:<span[^>]*>|<div[^>]*>)\s*([\u4e00-\u9fa5]+)\s*(?:</span>|</div>)',
    sidebar_replacer,
    html
)

# 2. Flip panel headers
# From: <h2>MACRO DASHBOARD</h2>
#       <div>Global Regime · Liquidity · Rates · Valuations</div> (or similar)
# To: <h2>宏观监控阵列 <span class="en-sub">MACRO DASHBOARD</span></h2>
#     <div>Global Regime · Liquidity · Rates · Valuations</div>

html = html.replace(
    '<h2>MACRO DASHBOARD</h2>',
    '<h2>宏观监控引擎 <span class="en-sub">MACRO DASHBOARD</span></h2>'
)
html = html.replace(
    '<h2>ROTATION DASHBOARD</h2>',
    '<h2>资产轮动中枢 <span class="en-sub">ROTATION DASHBOARD</span></h2>'
)
html = html.replace(
    '<h2>FACTOR ATTRIBUTION</h2>',
    '<h2>风险因子归因 <span class="en-sub">FACTOR ATTRIBUTION</span></h2>'
)
html = html.replace(
    '<h2>STRESS TESTING</h2>',
    '<h2>极限压力测试 <span class="en-sub">STRESS TESTING</span></h2>'
)
html = html.replace(
    '<h2>PORTFOLIO LIVE</h2>',
    '<h2>实时投资组合 <span class="en-sub">PORTFOLIO LIVE</span></h2>'
)
html = html.replace(
    '<h2>AI-CIO SYNTHESIS</h2>',
    '<h2>智能投研引擎 <span class="en-sub">AI-CIO SYNTHESIS</span></h2>'
)
html = html.replace(
    '<h2>STRATEGY LAB</h2>',
    '<h2>策略回测工坊 <span class="en-sub">STRATEGY LAB</span></h2>'
)
html = html.replace(
    '<h2>SANDBOX (Execution Simulator)</h2>',
    '<h2>交易执行沙盘 <span class="en-sub">SANDBOX SIMULATOR</span></h2>'
)
html = html.replace(
    '<h2>COMPLIANCE AUDIT LOG</h2>',
    '<h2>合规审计日志 <span class="en-sub">COMPLIANCE AUDIT</span></h2>'
)
html = html.replace(
    '<h2>[HUB] 全局决策中枢 <span style="font-size:0.5em; color:var(--text-tertiary); font-weight:400; letter-spacing:2px; margin-left:12px;">GLOBAL DECISION MATRIX</span></h2>',
    '<h2>全局决策中枢 <span class="en-sub">GLOBAL DECISION MATRIX</span></h2>'
)


# Revert standard sidebar nav if they don't match exactly but generally we want them clean:
with codecs.open('static/index.html', 'w', 'utf-8') as f:
    f.write(html)

print("index.html successfully updated to Chinese primary typography.")
