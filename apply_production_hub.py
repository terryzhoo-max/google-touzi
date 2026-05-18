import re
import codecs

new_js = """function initDecisionHub() {
    console.log("Initializing Decision Hub Dashboard...");
    const root = document.getElementById('hub-root');
    if (!root) {
        console.error("hub-root not found");
        return;
    }
    
    // Clear and set high-density layout
    root.innerHTML = '';
    root.style.display = 'flex';
    root.style.flexDirection = 'column';
    root.style.gap = '16px';
    root.style.padding = '20px';
    
    // Inject custom L1-L5 panels
    root.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <div>
                <h2 class="zh-primary" style="margin:0; font-size:1.6rem; color:var(--text-primary);">全局决策中枢 <span class="en-sub">[HUB] GLOBAL DECISION MATRIX</span></h2>
                <div style="font-family:var(--font-mono); font-size:0.8rem; color:var(--text-secondary); margin-top:4px;" id="hub-timestamp">--:--:--</div>
            </div>
            <div id="hub-status-badge" style="padding:4px 12px; background:rgba(34,197,94,0.1); border:1px solid rgba(34,197,94,0.3); border-radius:4px; color:#22c55e; font-family:var(--font-mono); font-size:0.8rem; font-weight:bold; box-shadow:0 0 10px rgba(34,197,94,0.1) inset;">
                SYSTEM ACTIVE
            </div>
        </div>
        
        <!-- Top Row: L1 & L2 -->
        <div style="display:flex; gap:16px; min-height:220px;">
            <div class="glass-card" id="hub-l1-card" style="flex:1; display:flex; flex-direction:column; border-left:4px solid #3b82f6;">
                <div class="card-header">
                    <h3 class="zh-primary">宏观基准锚定 <span class="en-sub">L1 MACRO REGIME</span></h3>
                </div>
                <div id="hub-l1-content" style="flex:1; display:flex; flex-wrap:wrap; gap:12px; align-items:center; justify-content:center;">
                    <div class="loading-spinner"></div> CALCULATING...
                </div>
            </div>
            <div class="glass-card" id="hub-l2-card" style="flex:1.5; display:flex; flex-direction:column; border-left:4px solid #a855f7;">
                <div class="card-header">
                    <h3 class="zh-primary">量化信号阵列 <span class="en-sub">L2 QUANT ENGINES</span></h3>
                </div>
                <div id="hub-l2-content" style="flex:1; display:grid; grid-template-columns:1fr 1fr; gap:12px; padding-top:8px;">
                    <div class="loading-spinner"></div>
                </div>
            </div>
        </div>
        
        <!-- Middle Row: L3 Allocator & L4 Compliance -->
        <div style="display:flex; gap:16px; min-height:360px;">
            <div class="glass-card" id="hub-l3-card" style="flex:1.5; border-left:4px solid #3b82f6; display:flex; flex-direction:column;">
                <div class="card-header">
                    <h3 class="zh-primary">资金路由分配 <span class="en-sub">L3 ROUTER & ALLOCATOR</span></h3>
                </div>
                <div id="hub-l3-rationale" style="margin-bottom:12px; font-size:0.85rem; color:var(--text-tertiary);"></div>
                <div id="chart-hub-l3-alloc" class="chart-container" style="flex:1; width:100%;"></div>
            </div>
            <div class="glass-card" id="hub-l4-card" style="flex:1; display:flex; flex-direction:column;">
                <div class="card-header">
                    <h3 class="zh-primary">风控合规门禁 <span class="en-sub">L4 COMPLIANCE GATE</span></h3>
                </div>
                <div id="hub-l4-content" style="flex:1; font-size:0.9rem; line-height:1.6; color:var(--text-secondary); display:flex; flex-direction:column; gap:12px;">
                    <div class="loading-spinner"></div>
                </div>
            </div>
        </div>
        
        <!-- Bottom Row: L5 AI Synthesis -->
        <div class="glass-card" id="hub-l5-card" style="border-left:4px solid #10b981;">
            <div class="card-header">
                <h3 class="zh-primary">智能投研裁决 <span class="en-sub">L5 AI-CIO SYNTHESIS</span></h3>
            </div>
            <div id="hub-l5-content" style="font-size:0.95rem; line-height:1.7; color:var(--text-secondary); min-height:80px; padding:8px 0;">
                <div class="loading-spinner"></div>
            </div>
        </div>
    `;

    // Fetch data and populate
    fetch('/api/institutional/decision_hub')
      .then(r => r.json())
      .then(data => {
          if (data.error) {
              document.getElementById('hub-l1-content').innerHTML = `<div class="error-msg">${data.error}</div>`;
              return;
          }
          
          // Update timestamp
          const d = new Date(data.timestamp * 1000);
          document.getElementById('hub-timestamp').innerText = d.toLocaleTimeString('zh-CN', {hour12:false});
          
          // ----------------------------------------------------------------
          // Render L1 Macro
          // ----------------------------------------------------------------
          const l1 = document.getElementById('hub-l1-content');
          if (l1) {
              const macro = data.l1_macro;
              const regimeColor = macro.regime === 'NEUTRAL' ? '#22c55e' : (macro.regime === 'DEFENSIVE' ? '#ef4444' : '#3b82f6');
              const regimeBg = macro.regime === 'NEUTRAL' ? 'rgba(34,197,94,0.1)' : (macro.regime === 'DEFENSIVE' ? 'rgba(239,68,68,0.1)' : 'rgba(59,130,246,0.1)');
              const regimeBorder = macro.regime === 'NEUTRAL' ? '#22c55e' : (macro.regime === 'DEFENSIVE' ? '#ef4444' : '#3b82f6');
              
              l1.innerHTML = `
                  <div style="flex:1; min-width:140px; background:${regimeBg}; border:1px solid ${regimeBorder}40; border-radius:6px; padding:16px; text-align:center; box-shadow:0 0 20px ${regimeBg} inset;">
                      <div style="font-size:0.75rem; color:var(--text-tertiary); margin-bottom:4px; letter-spacing:1px;">宏观周期</div>
                      <strong style="color:${regimeBorder}; font-size:1.2rem; text-shadow:0 0 10px ${regimeBorder}80;">${macro.regime}</strong>
                  </div>
                  <div style="flex:1; min-width:140px; background:rgba(255,255,255,0.02); border:1px solid var(--row-border); border-radius:6px; padding:16px; text-align:center;">
                      <div style="font-size:0.75rem; color:var(--text-tertiary); margin-bottom:4px; letter-spacing:1px;">恐慌指数(VIX)</div>
                      <strong style="color:var(--text-primary); font-size:1.2rem; font-family:var(--font-mono);">${macro.vix_level}</strong>
                  </div>
                  <div style="flex:1; min-width:140px; background:rgba(255,255,255,0.02); border:1px solid var(--row-border); border-radius:6px; padding:16px; text-align:center;">
                      <div style="font-size:0.75rem; color:var(--text-tertiary); margin-bottom:4px; letter-spacing:1px;">核心动能</div>
                      <strong style="color:var(--accent-secondary); font-size:1.2rem; font-family:var(--font-mono);">${macro.macro_score}</strong>
                  </div>
                  <div style="flex:1; min-width:140px; background:rgba(255,255,255,0.02); border:1px solid var(--row-border); border-radius:6px; padding:16px; text-align:center;">
                      <div style="font-size:0.75rem; color:var(--text-tertiary); margin-bottom:4px; letter-spacing:1px;">拥挤度水位</div>
                      <strong style="color:var(--text-primary); font-size:1.2rem; font-family:var(--font-mono);">${macro.crowding_level}%</strong>
                  </div>
                  <div style="width:100%; margin-top:8px; padding:12px; border-left:3px solid var(--accent-primary); background:rgba(59,130,246,0.05); font-family:var(--font-mono); font-size:0.85rem; color:var(--text-secondary); display:flex; justify-content:space-between;">
                      <span>流动性定性:</span>
                      <strong style="color:var(--accent-primary);">${macro.liquidity_state}</strong>
                  </div>
              `;
          }
          
          // ----------------------------------------------------------------
          // Render L2 Quant Signals
          // ----------------------------------------------------------------
          const l2 = document.getElementById('hub-l2-content');
          if (l2) {
              const sigs = data.l2_signals;
              let html = '';
              Object.keys(sigs).forEach(k => {
                  const s = sigs[k];
                  const valColor = s.signal > 0.5 ? '#22c55e' : (s.signal < -0.5 ? '#ef4444' : '#94a3b8');
                  const valText = s.signal > 0.5 ? (k.includes('par') ? 'OVERWEIGHT OVERSEAS' : 'BULLISH') : 
                                 (s.signal < -0.5 ? (k.includes('hedge') ? 'HEDGE ACTIVE' : 'BEARISH') : 
                                 (k.includes('hedge') ? 'HEDGE INACTIVE' : (k.includes('barbell') ? 'DEFENSIVE TILT' : 'A-SHARE CAUTION')));
                  let topSym = '--';
                  let topName = '';
                  if (s.top_holding) {
                      if (typeof s.top_holding === 'object') {
                          topSym = s.top_holding.symbol || '--';
                          topName = s.top_holding.name || '';
                      } else {
                          topSym = s.top_holding;
                          const fallbackNames = {
                              '513500.SH': '标普500ETF',
                              '510880.SH': '红利ETF',
                              '159601.SZ': 'A50ETF',
                              '510300.SH': '沪深300ETF',
                              '518880.SH': '黄金ETF',
                              '511260.SH': '十年国债ETF',
                              '511010.SH': '五年国债ETF',
                              '513100.SH': '纳指ETF'
                          };
                          if (data.l3_routing && data.l3_routing.symbol_names && data.l3_routing.symbol_names[topSym]) {
                              topName = data.l3_routing.symbol_names[topSym];
                          } else {
                              topName = fallbackNames[topSym] || '';
                          }
                      }
                  }
                  
                  const topDisplay = topName ? `<span style="color:var(--text-primary); font-weight:bold; font-size:0.85rem; margin-right:6px; letter-spacing:1px;">${topName}</span><span style="color:var(--text-tertiary); font-size:0.65rem; font-family:var(--font-mono); background:rgba(255,255,255,0.05); padding:2px 6px; border-radius:4px; border:1px solid rgba(255,255,255,0.05);">${topSym}</span>` : `<span style="color:var(--text-secondary); font-family:var(--font-mono);">${topSym}</span>`;
                  
                  const gradStart = s.signal > 0.5 ? 'rgba(34,197,94,0.08)' : (s.signal < -0.5 ? 'rgba(239,68,68,0.08)' : 'rgba(100,116,139,0.08)');
                  const gradEnd = 'rgba(255,255,255,0.01)';

                  html += `
                      <div style="background:linear-gradient(135deg, ${gradStart} 0%, ${gradEnd} 100%); border:1px solid var(--row-border); border-radius:8px; padding:12px; display:flex; flex-direction:column; justify-content:space-between; position:relative; overflow:hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
                          <div style="position:absolute; top:0; left:0; width:3px; height:100%; background:${valColor}; box-shadow:0 0 8px ${valColor};"></div>
                          <div style="font-size:0.75rem; font-weight:bold; color:var(--text-secondary); margin-bottom:12px; letter-spacing:1px; padding-left:6px; text-transform:uppercase;">
                              ${k.replace(/_/g, ' ')}
                          </div>
                          <div style="display:flex; justify-content:space-between; align-items:flex-end; padding-left:6px;">
                              <div style="display:flex; flex-direction:column;">
                                  <span style="font-size:0.65rem; color:var(--text-tertiary); letter-spacing:1px; margin-bottom:4px; display:flex; align-items:center; gap:4px;">
                                      <i class="fas fa-crosshairs" style="color:var(--accent-primary); font-size:0.6rem;"></i> 顶配锚定
                                  </span>
                                  <div style="display:flex; align-items:center;">${topDisplay}</div>
                              </div>
                              <div style="font-family:var(--font-mono); font-weight:900; font-size:0.95rem; color:${valColor}; text-shadow:0 0 12px ${valColor}50; background:rgba(0,0,0,0.2); padding:4px 8px; border-radius:6px; border:1px solid ${valColor}30;">
                                  ${valText}
                              </div>
                          </div>
                      </div>
                  `;
              });
              l2.innerHTML = html;
          }
          
          // ----------------------------------------------------------------
          // Render L3 Allocator
          // ----------------------------------------------------------------
          const rationaleEl = document.getElementById('hub-l3-rationale');
          if (rationaleEl) {
              rationaleEl.innerHTML = `<div style="display:inline-flex; align-items:center; background:rgba(56,189,248,0.1); padding:6px 12px; border-radius:4px; border:1px solid rgba(56,189,248,0.2);"><span style="color:#38bdf8; margin-right:8px; font-size:1.2em;"><i class="fas fa-info-circle"></i></span> <span style="color:var(--text-secondary);">${data.l3_routing.rationale}</span></div>`;
          }
          
          const chartDom = document.getElementById('chart-hub-l3-alloc');
          if (chartDom && window.echarts) {
              let allocChart = echarts.getInstanceByDom(chartDom);
              if (!allocChart) allocChart = echarts.init(chartDom);
              
              const tgt = data.l3_routing.target_weights || {};
              const cur = data.l3_routing.before_weights || {};
              const symNames = data.l3_routing.symbol_names || {};
              
              const symbols = Array.from(new Set([...Object.keys(tgt), ...Object.keys(cur)]));
              // Use names for X-Axis if available
              const xAxisLabels = symbols.map(s => symNames[s] || s);
              const curData = symbols.map(s => (cur[s] || 0) * 100);
              const tgtData = symbols.map(s => (tgt[s] || 0) * 100);
              
              allocChart.setOption({
                  tooltip: {
                      trigger: 'axis',
                      backgroundColor: 'rgba(11, 13, 19, 0.9)',
                      borderColor: 'rgba(255,255,255,0.1)',
                      textStyle: { color: '#fff' },
                      axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(255,255,255,0.02)' } },
                      formatter: function(params) {
                          let res = `<div style="font-weight:bold; margin-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:6px; font-family:var(--font-mono);">${params[0].axisValue}</div>`;
                          params.forEach(p => {
                              res += `<div style="display:flex; justify-content:space-between; gap:16px; margin-bottom:4px;">
                                  <span style="display:flex; align-items:center;"><span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${p.color.colorStops ? p.color.colorStops[0].color : p.color}; margin-right:8px;"></span><span style="color:var(--text-secondary);">${p.seriesName}</span></span>
                                  <strong style="font-family:var(--font-mono);">${p.value.toFixed(1)}%</strong>
                              </div>`;
                          });
                          return res;
                      }
                  },
                  grid: { top: 30, right: 20, bottom: 20, left: 40, containLabel: true },
                  xAxis: {
                      type: 'category',
                      data: xAxisLabels,
                      axisLabel: { color: '#64748b', fontSize: 10, rotate: 30 },
                      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } }
                  },
                  yAxis: {
                      type: 'value',
                      axisLabel: { color: '#64748b', fontSize: 10, formatter: '{value}%' },
                      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.03)', type: 'dashed' } }
                  },
                  legend: {
                      data: ['当前仓位', '目标仓位'],
                      textStyle: { color: '#94a3b8', fontSize: 11 },
                      top: 0,
                      right: 0,
                      icon: 'roundRect'
                  },
                  series: [
                      {
                          name: '当前仓位',
                          type: 'bar',
                          data: curData,
                          itemStyle: { color: 'rgba(100, 116, 139, 0.3)', borderRadius: [2, 2, 0, 0], borderColor: 'rgba(100, 116, 139, 0.8)', borderWidth: 1 },
                          barWidth: '30%',
                          barGap: '15%'
                      },
                      {
                          name: '目标仓位',
                          type: 'bar',
                          data: tgtData,
                          itemStyle: { 
                              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                                  { offset: 0, color: '#a855f7' },
                                  { offset: 1, color: '#3b82f6' }
                              ]),
                              borderRadius: [3, 3, 0, 0],
                              shadowBlur: 10,
                              shadowColor: 'rgba(168, 85, 247, 0.4)'
                          },
                          barWidth: '30%'
                      }
                  ]
              });
              window.addEventListener('resize', () => allocChart.resize());
              
              // --- INJECT TRADE DIRECTIVES WITH CHINESE NAMES ---
              let tradesContainer = document.getElementById('hub-l3-trades');
              if (!tradesContainer) {
                  tradesContainer = document.createElement('div');
                  tradesContainer.id = 'hub-l3-trades';
                  tradesContainer.style.marginTop = '12px';
                  tradesContainer.style.padding = '12px';
                  tradesContainer.style.background = 'rgba(0,0,0,0.2)';
                  tradesContainer.style.borderRadius = '6px';
                  tradesContainer.style.border = '1px solid rgba(255,255,255,0.05)';
                  chartDom.parentNode.appendChild(tradesContainer);
              }
              
              let tradesHtml = `<div style="font-size:0.75rem; color:var(--text-tertiary); margin-bottom:8px; letter-spacing:1px; display:flex; justify-content:space-between; align-items:center;">
                  <span>执行建议 (TRADE DIRECTIVES)</span>`;
              
              if (data.l3_routing.backtest_metrics && data.l3_routing.backtest_metrics.strat_sharpe !== undefined) {
                  const sharpe = data.l3_routing.backtest_metrics.strat_sharpe;
                  if (sharpe > 1.0) {
                      tradesHtml += `<span style="color:#22c55e; border:1px solid #22c55e50; padding:2px 6px; border-radius:4px; font-weight:bold;">高确信度 | 夏普: ${sharpe}</span>`;
                  } else {
                      tradesHtml += `<span style="color:#f59e0b; border:1px solid #f59e0b50; padding:2px 6px; border-radius:4px;">中等确信度 | 夏普: ${sharpe}</span>`;
                  }
              }
              tradesHtml += `</div><div style="display:flex; flex-wrap:wrap; gap:8px;">`;
              
              let hasTrades = false;
              const directives = data.l3_routing.trade_directives || [];
              if (directives.length > 0) {
                  hasTrades = true;
                  directives.forEach(d => {
                      const isBlocked = d.status === 'BLOCKED_BY_COMPLIANCE';
                      const actionText = d.action === 'BUY' ? '买入' : '卖出';
                      const sign = d.action === 'BUY' ? '+' : '-';
                      const baseColor = d.action === 'BUY' ? '#22c55e' : '#ef4444';
                      const bgColor = d.action === 'BUY' ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)';
                      
                      if (isBlocked) {
                          tradesHtml += `<span style="color:#64748b; border:1px solid #64748b50; background:rgba(100,116,139,0.1); padding:4px 8px; border-radius:4px; font-family:var(--font-mono); font-size:0.9rem; position:relative; overflow:hidden;">
                              <del>${actionText} ${d.name} ${sign}${d.amount_pct}%</del>
                              <span style="color:#ef4444; font-weight:bold; margin-left:6px; font-size:0.8rem;"><i class="fas fa-lock"></i> 熔断拦截</span>
                          </span>`;
                      } else {
                          tradesHtml += `<span style="color:${baseColor}; border:1px solid ${baseColor}; background:${bgColor}; padding:4px 8px; border-radius:4px; font-family:var(--font-mono); font-size:0.9rem; box-shadow:0 0 8px ${bgColor.replace('0.1', '0.2')};">
                              ${actionText} ${d.name} ${sign}${d.amount_pct}%
                          </span>`;
                      }
                  });
              }
              
              if (!hasTrades) {
                  tradesHtml += `<span style="color:var(--text-tertiary); font-style:italic; font-size:0.9rem;">无需调仓 (HOLD) - 仓位偏离极小</span>`;
              }
              tradesHtml += `</div>`;
              tradesContainer.innerHTML = tradesHtml;
          }
          
          // ----------------------------------------------------------------
          // Render L4 Compliance Gate
          // ----------------------------------------------------------------
          const l4 = document.getElementById('hub-l4-content');
          const l4Card = document.getElementById('hub-l4-card');
          if (l4) {
              const comp = data.l4_compliance;
              const isBlock = comp.gate_status === 'HARD_BLOCK';
              const isWarn = comp.gate_status === 'SOFT_WARNING';
              const statusColor = isBlock ? '#ef4444' : (isWarn ? '#f59e0b' : '#22c55e');
              
              // Institutional Translation Engine
              const translateRisk = (rawStr) => {
                  if (rawStr.startsWith('region_limit_exceeded:')) return '🚨 单一区域暴露超限: ' + rawStr.split(':')[1];
                  if (rawStr.startsWith('strategy_limit_exceeded:')) return '🚨 单一策略敞口超限: ' + rawStr.split(':')[1];
                  if (rawStr.startsWith('position_limit_exceeded:')) return '🚨 单一标的权重超限: ' + rawStr.split(':')[1];
                  if (rawStr.startsWith('trade_size_exceeded:')) return '⚠️ 单次调仓流动性规模超额: ' + rawStr.split(':')[1];
                  if (rawStr === 'turnover_exceeded') return '⚠️ 组合预估换手率超额限制';
                  if (rawStr === 'no_new_risk_when_risk_high') return '🔒 高波警戒期禁止风险敞口扩张';
                  if (rawStr === 'fallback_data_non_defensive_action') return '🔒 数据降级期间禁止非防御性建仓';
                  return rawStr;
              };
              
              // Apply warning tape styling if blocked
              if (isBlock) {
                  l4Card.style.background = 'repeating-linear-gradient(45deg, rgba(239, 68, 68, 0.05), rgba(239, 68, 68, 0.05) 10px, rgba(0, 0, 0, 0) 10px, rgba(0, 0, 0, 0) 20px)';
                  l4Card.style.border = '1px solid rgba(239,68,68,0.3)';
                  l4Card.style.boxShadow = '0 0 30px rgba(239,68,68,0.1) inset';
              } else if (isWarn) {
                  l4Card.style.background = 'repeating-linear-gradient(45deg, rgba(245, 158, 11, 0.03), rgba(245, 158, 11, 0.03) 10px, rgba(0, 0, 0, 0) 10px, rgba(0, 0, 0, 0) 20px)';
                  l4Card.style.border = '1px solid rgba(245,158,11,0.3)';
                  l4Card.style.boxShadow = '0 0 20px rgba(245,158,11,0.05) inset';
              } else {
                  l4Card.style.background = '';
                  l4Card.style.border = '1px solid rgba(34,197,94,0.3)';
                  l4Card.style.boxShadow = '';
              }
              
              l4Card.style.borderLeft = `4px solid ${statusColor}`;
              
              let html = `
                  <div style="display:flex; justify-content:space-between; align-items:center;">
                      <div style="display:flex; align-items:center; gap:12px;">
                          <div style="width:12px; height:12px; border-radius:50%; background:${statusColor}; box-shadow:0 0 10px ${statusColor}; animation: modalFadeIn 1s infinite alternate;"></div>
                          <div style="font-size:1.3rem; font-weight:900; color:${statusColor}; font-family:var(--font-mono); letter-spacing:2px; text-shadow:0 0 15px ${statusColor}80;">
                              [ ${comp.gate_status} ]
                          </div>
                      </div>
                      <div style="text-align:right;">
                          <div style="font-size:0.65rem; color:var(--text-tertiary); letter-spacing:1px;">风控合规评分</div>
                          <div style="font-size:1.8rem; font-weight:900; color:var(--text-primary); font-family:var(--font-mono); line-height:1;">${comp.score}</div>
                      </div>
                  </div>
                  <div style="width:100%; height:4px; background:rgba(255,255,255,0.05); margin-top:16px; margin-bottom:16px; border-radius:2px; overflow:hidden;">
                      <div style="height:100%; width:${comp.score}%; background:${statusColor}; transition:width 1.5s cubic-bezier(0.4, 0, 0.2, 1); box-shadow:0 0 10px ${statusColor};"></div>
                  </div>
              `;
              
              if (comp.violations && comp.violations.length > 0) {
                  html += `
                      <div style="margin-top:auto; background:rgba(0,0,0,0.4); border:1px solid rgba(239,68,68,0.2); border-radius:4px; padding:12px; font-family:var(--font-mono); font-size:0.8rem;">
                          <div style="color:#ef4444; margin-bottom:8px; font-weight:bold; letter-spacing:1px; display:flex; align-items:center; gap:6px;">
                              <i class="fas fa-ban"></i> 触发硬性风控拦截
                          </div>
                          <ul style="margin:0; padding-left:20px; color:#fca5a5; line-height:1.6;">
                              ${comp.violations.map(v => `<li>${translateRisk(v)}</li>`).join('')}
                          </ul>
                      </div>
                  `;
              } else if (comp.warnings && comp.warnings.length > 0) {
                  html += `
                      <div style="margin-top:auto; background:rgba(0,0,0,0.4); border:1px solid rgba(245,158,11,0.2); border-radius:4px; padding:12px; font-family:var(--font-mono); font-size:0.8rem;">
                          <div style="color:#f59e0b; margin-bottom:8px; font-weight:bold; letter-spacing:1px; display:flex; align-items:center; gap:6px;">
                              <i class="fas fa-exclamation-triangle"></i> 触发软性风控预警
                          </div>
                          <ul style="margin:0; padding-left:20px; color:#fcd34d; line-height:1.6;">
                              ${comp.warnings.map(v => `<li>${translateRisk(v)}</li>`).join('')}
                          </ul>
                      </div>
                  `;
              } else {
                  html += `
                      <div style="margin-top:auto; background:rgba(0,0,0,0.4); border:1px solid rgba(34,197,94,0.2); border-radius:4px; padding:12px; font-family:var(--font-mono); font-size:0.8rem; color:#86efac; display:flex; align-items:center; gap:8px;">
                          <i class="fas fa-check-circle" style="color:#22c55e;"></i> 全量风控规则检验通过
                      </div>
                  `;
              }
              
              html += `
                  <div style="display:flex; justify-content:space-between; color:var(--text-tertiary); font-family:var(--font-mono); font-size:0.75rem; margin-top:8px;">
                      <span>预估调仓换手率</span>
                      <strong style="color:var(--text-secondary);">${(comp.turnover * 100).toFixed(1)}%</strong>
                  </div>
              `;
              
              l4.innerHTML = html;
          }
          
          // ----------------------------------------------------------------
          // Render L5 AI-CIO Synthesis
          // ----------------------------------------------------------------
          const l5 = document.getElementById('hub-l5-content');
          const l5Card = document.getElementById('hub-l5-card');
          if (l5) {
              const memo = data.l5_ai_memo;
              let bg = 'transparent';
              if (memo.headline.includes('REJECTED')) {
                  bg = 'rgba(239, 68, 68, 0.05)';
                  l5Card.style.borderLeft = '4px solid #ef4444';
              } else if (memo.headline.includes('WARNING')) {
                  bg = 'rgba(245, 158, 11, 0.05)';
                  l5Card.style.borderLeft = '4px solid #f59e0b';
              }
              
              l5.innerHTML = `
                  <div style="background:${bg}; padding:12px; border-radius:4px; border:1px solid rgba(255,255,255,0.05);">
                      <div style="font-weight:bold; color:var(--text-primary); margin-bottom:8px; font-size:1.05rem; letter-spacing:1px;">
                          ${memo.headline}
                      </div>
                      <div style="font-family:var(--font-sans);">
                          ${memo.memo}
                      </div>
                  </div>
              `;
          }
      })
      .catch(err => {
          console.error(err);
          document.getElementById('hub-l1-content').innerHTML = `<div class="error-msg">决策引擎连接失败 (Connection Failed)</div>`;
      });
}
"""

with codecs.open('static/main.js', 'r', 'utf-8') as f:
    full_content = f.read()

# Replace the entire initDecisionHub function
new_full_content = re.sub(r'function initDecisionHub\(\) \{.*?(?=\nfunction |\n$|\Z)', new_js, full_content, flags=re.DOTALL)

with codecs.open('static/main.js', 'w', 'utf-8') as f:
    f.write(new_full_content)

print("Master script successfully injected production-grade UTF-8 content to static/main.js.")
