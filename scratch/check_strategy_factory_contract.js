const fs = require('fs');

const strategy = fs.readFileSync('core/strategy_lab.py', 'utf8');
const main = fs.readFileSync('static/main.js', 'utf8');
const strategyPanel = fs.readFileSync('static/js/panels/strategy.js', 'utf8');

const checks = [
  {
    name: 'strategy policy hash is exposed',
    pass: /strategy_policy_hash|config_hash|policy_hash/.test(strategy),
  },
  {
    name: 'strategy dashboard exposes data quality',
    pass: /data_quality/.test(strategy) && /degraded_reason/.test(strategy),
  },
  {
    name: 'risk parity degraded path does not emit directional overweight signal',
    pass: !/except Exception[\s\S]{0,500}signal = "OVERWEIGHT OVERSEAS"/.test(strategy),
  },
  {
    name: 'beta hedging is marked placeholder or non-tradeable',
    pass: /placeholder|tradeable|not_tradeable|model_mode/.test(strategy),
  },
  {
    name: 'frontend handles unavailable strategy backtest',
    pass: /renderStrategyBacktestUnavailable/.test(strategyPanel) && /data\.backtest\.error/.test(strategyPanel),
  },
  {
    name: 'frontend guards strategy engine arrays',
    pass: /Array\.isArray\(eng\.details\)/.test(strategyPanel) && /Array\.isArray\(eng\.holdings\)/.test(strategyPanel),
  },
];

const failed = checks.filter(check => !check.pass);
for (const check of checks) {
  console.log(`${check.pass ? 'PASS' : 'FAIL'} ${check.name}`);
}
if (failed.length) {
  process.exit(1);
}
