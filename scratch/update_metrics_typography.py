import os

def run():
    file_path = 'static/main.js'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target = """            metricsContainer.innerHTML = `
                <div class="metric-cell"><span style="display:flex; flex-direction:column; line-height:1.3;">Strategy YTD <small style="font-size:0.85em; color:var(--text-tertiary);">策略本年收益</small></span><strong style="color:#10b981;">${m.strategy_ytd}</strong></div>
                <div class="metric-cell"><span style="display:flex; flex-direction:column; line-height:1.3;">Benchmark YTD <small style="font-size:0.85em; color:var(--text-tertiary);">基准本年收益</small></span><strong style="color:var(--text-primary);">${m.benchmark_ytd}</strong></div>
                <div class="metric-cell"><span style="display:flex; flex-direction:column; line-height:1.3;">Max Drawdown <small style="font-size:0.85em; color:var(--text-tertiary);">最大回撤</small></span><strong style="color:#ef4444;">${m.max_drawdown}</strong></div>
                <div class="metric-cell"><span style="display:flex; flex-direction:column; line-height:1.3;">Sharpe Ratio <small style="font-size:0.85em; color:var(--text-tertiary);">夏普比率</small></span><strong style="color:#38bdf8;">${m.sharpe_ratio}</strong></div>
            `;"""

    replacement = """            metricsContainer.innerHTML = `
                <div class="metric-cell"><span style="display:flex; flex-direction:column; line-height:1.3;">策略本年收益 <small style="font-size:0.75em; color:var(--text-tertiary); font-weight:400; letter-spacing:0.5px; text-transform:uppercase; margin-top:2px;">Strategy YTD</small></span><strong style="color:#10b981;">${m.strategy_ytd}</strong></div>
                <div class="metric-cell"><span style="display:flex; flex-direction:column; line-height:1.3;">基准本年收益 <small style="font-size:0.75em; color:var(--text-tertiary); font-weight:400; letter-spacing:0.5px; text-transform:uppercase; margin-top:2px;">Benchmark YTD</small></span><strong style="color:var(--text-primary);">${m.benchmark_ytd}</strong></div>
                <div class="metric-cell"><span style="display:flex; flex-direction:column; line-height:1.3;">最大回撤 <small style="font-size:0.75em; color:var(--text-tertiary); font-weight:400; letter-spacing:0.5px; text-transform:uppercase; margin-top:2px;">Max Drawdown</small></span><strong style="color:#ef4444;">${m.max_drawdown}</strong></div>
                <div class="metric-cell"><span style="display:flex; flex-direction:column; line-height:1.3;">夏普比率 <small style="font-size:0.75em; color:var(--text-tertiary); font-weight:400; letter-spacing:0.5px; text-transform:uppercase; margin-top:2px;">Sharpe Ratio</small></span><strong style="color:#38bdf8;">${m.sharpe_ratio}</strong></div>
            `;"""

    normalized_content = content.replace('\r\n', '\n')
    normalized_target = target.replace('\r\n', '\n')
    normalized_replacement = replacement.replace('\r\n', '\n')

    if normalized_target in normalized_content:
        new_content = normalized_content.replace(normalized_target, normalized_replacement)
        # Restore CRLF
        new_content = new_content.replace('\n', '\r\n')
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("SUCCESS: Strategy metrics visual hierarchy optimized!")
    else:
        print("ERROR: Target not found in file!")

if __name__ == '__main__':
    run()
