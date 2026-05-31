import codecs
import re

with codecs.open('static/main.js', 'r', 'utf-8') as f:
    text = f.read()

new_block = '''        impactChart.setOption({
            tooltip: { 
                className: 'terminal-hud-tooltip', 
                trigger: 'axis', 
                axisPointer: { type:'shadow', shadowStyle: { color: 'rgba(255,255,255,0.02)' } },
                backgroundColor: 'rgba(11, 13, 19, 0.95)',
                borderColor: 'var(--row-border)',
                textStyle: { color: '#fff' },
                formatter: function(params) {
                    const p = params[0];
                    // Find the original scenario to get name_zh
                    const scenario = sortedScenarios.find(s => (s.name + ' | ' + s.name_zh) === p.name || s.name === p.name);
                    const title = scenario ? (scenario.name.toUpperCase() + ' <span style="font-size:0.8em; color:var(--text-tertiary); margin-left:8px;">' + (scenario.name_zh || '') + '</span>') : p.name.split('|')[0];
                    return `<div class="hud-title" style="border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 4px; margin-bottom: 6px;">${title}</div>
                            <div class="hud-value" style="color:${p.value>0?'#10b981':'#ef4444'}; font-family:var(--font-mono); font-size:1.1rem; font-weight:bold;">
                                IMPACT: ${p.value > 0 ? '+' : ''}${p.value}%
                            </div>`;
                }
            },
            grid: { left: '2%', right: '8%', bottom: '5%', top: '5%', containLabel: true },
            xAxis: { 
                type: 'value', 
                splitLine: { show: true, lineStyle: { color: 'rgba(255,255,255,0.03)', type: 'dashed' } }, 
                axisLabel: { color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', fontSize: 10, formatter: '{value}%' },
                axisLine: { show: true, lineStyle: { color: 'rgba(255,255,255,0.2)', width: 1 } }
            },
            yAxis: { 
                type: 'category', 
                data: sortedScenarios.map(s => s.name_zh ? `${s.name} | ${s.name_zh}` : s.name), 
                axisLabel: { 
                    formatter: function(value) {
                        if(value.includes('|')) {
                            const parts = value.split('|');
                            return `{en|${parts[0]}}\\n{zh|${parts[1]}}`;
                        }
                        return `{en|${value}}`;
                    },
                    rich: {
                        en: { color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', fontSize: 10, align: 'right', fontWeight: 'bold' },
                        zh: { color: 'var(--text-tertiary)', fontSize: 11, align: 'right', padding: [4, 0, 0, 0] }
                    }
                },
                axisLine: { show: false },
                axisTick: { show: false },
                splitArea: { show: true, areaStyle: { color: ['rgba(255,255,255,0.01)', 'transparent'] } }
            },
            series: [{
                name: 'Drawdown',
                type: 'bar',
                barWidth: '55%',
                data: sortedScenarios.map(s => {
                    const val = s.portfolio_loss_pct;
                    const isWorst = (s.id === worst.id);
                    
                    let colorStops;
                    if (val >= 0) {
                        colorStops = [
                            { offset: 0, color: 'rgba(16,185,129,0.05)' },
                            { offset: 1, color: 'rgba(16,185,129,0.85)' }
                        ];
                    } else {
                        const danger = isWorst ? '239,68,68' : '244,63,94';
                        colorStops = [
                            { offset: 0, color: `rgba(${danger},${isWorst?0.95:0.7})` },
                            { offset: 1, color: `rgba(${danger},0.05)` }
                        ];
                    }

                    return {
                        value: val,
                        label: {
                            show: true,
                            position: val >= 0 ? 'right' : 'left',
                            distance: 8,
                            formatter: '{c}%',
                            fontFamily: 'var(--font-mono)',
                            fontWeight: 'bold',
                            color: val >= 0 ? '#10b981' : (isWorst ? '#ef4444' : '#fb7185'),
                            textShadowColor: 'rgba(0,0,0,0.8)',
                            textShadowBlur: 4
                        },
                        itemStyle: { 
                            borderRadius: [2, 2, 2, 2],
                            color: new echarts.graphic.LinearGradient(0, 0, 1, 0, colorStops),
                            shadowBlur: isWorst ? 15 : 0,
                            shadowColor: isWorst ? 'rgba(239,68,68,0.4)' : 'transparent',
                            borderColor: isWorst ? '#ef4444' : 'rgba(255,255,255,0.05)',
                            borderWidth: 1
                        }
                    };
                })
            }]
        });'''

old_block_regex = r"impactChart\.setOption\(\{[\s\S]*?\}\]\r?\n\s+\}\);"
new_text = re.sub(old_block_regex, new_block, text, count=1)

if new_text != text:
    with codecs.open('static/main.js', 'w', 'utf-8') as f:
        f.write(new_text)
    print('Successfully updated static/main.js')
else:
    print('Failed to replace. Regex did not match.')
