const fs = require('fs');

const index = fs.readFileSync('static/index.html', 'utf8');
const main = fs.readFileSync('static/main.js', 'utf8');
const events = fs.readFileSync('static/js/core/events.js', 'utf8');
const bootstrap = fs.readFileSync('static/js/core/bootstrap.js', 'utf8');
const styles = fs.readFileSync('static/styles.css', 'utf8');

const viewIds = [
  'view-macro',
  'view-rotation',
  'view-risk',
  'view-stress',
  'view-strategy',
  'view-portfolio',
  'view-hub',
  'view-institutional',
];

const checks = [
  {
    name: 'all nav view panels are present',
    pass: viewIds.every(id => new RegExp(`id="${id}"[^>]*class="view-panel`).test(index)),
  },
  {
    name: 'nav view panels are direct children of main',
    pass: (() => {
      const tagRe = /<\/?(main|div)\b[^>]*>/gi;
      const stack = [];
      let match;
      while ((match = tagRe.exec(index))) {
        const tag = match[0];
        const name = match[1].toLowerCase();
        if (tag.startsWith('</')) {
          const popped = stack.pop();
          if (!popped || popped.name !== name) return false;
          continue;
        }
        const id = (tag.match(/id="([^"]*)"/) || [])[1] || '';
        if (viewIds.includes(id)) {
          const parent = stack[stack.length - 1];
          if (!parent || parent.name !== 'main') return false;
        }
        stack.push({ name, id });
      }
      return true;
    })(),
  },
  {
    name: 'all nav clicks use delegated router action',
    pass: viewIds.every(id => index.includes(`data-action="switch-view" data-view="${id}"`)) &&
      /'switch-view'[\s\S]{0,140}event\.preventDefault\(\)[\s\S]{0,140}switchView\(target\.dataset\.view\)/.test(events),
  },
  {
    name: 'strategy nav entry is present',
    pass: /href="#view-strategy"[\s\S]{0,180}策略工厂/.test(index),
  },
  {
    name: 'strategy view panel is present',
    pass: /id="view-strategy"[^>]*class="view-panel"/.test(index),
  },
  {
    name: 'hash route opens strategy view on refresh/direct link',
    pass: /location\.hash/.test(main) && /switchView\(initialView/.test(main) && /hashchange/.test(bootstrap),
  },
  {
    name: 'nav clicks prevent default anchor-only fallback',
    pass: /data-action="switch-view" data-view="view-strategy"/.test(index) &&
      /'switch-view'[\s\S]{0,140}event\.preventDefault\(\)/.test(events),
  },
  {
    name: 'strategy script cache version was bumped',
    pass: /js\/panels\/strategy\.js\?v=2/.test(index),
  },
  {
    name: 'html has pre-main hash activation fallback',
    pass: /activateInitialHashView/.test(index) && /route-active-view/.test(index) && /requestAnimationFrame\(resetScroll\)/.test(index),
  },
  {
    name: 'sidebar nav can scroll if viewport is short',
    pass: /styles\.css\?v=18/.test(index) && /\.terminal-nav\s*\{[\s\S]*overflow-y:\s*auto/.test(styles),
  },
  {
    name: 'main router writes explicit panel display state',
    pass: /route-hash-active/.test(main) && /route-active-view/.test(main) && /panel\.style\.display\s*=\s*'block'/.test(main),
  },
  {
    name: 'route css forces only selected panel visible',
    pass: /body\.route-hash-active \.view-panel[\s\S]*display:\s*none !important/.test(styles) &&
      /body\.route-hash-active \.view-panel\.route-active-view[\s\S]*display:\s*block !important/.test(styles),
  },
];

const failed = checks.filter(check => !check.pass);
for (const check of checks) {
  console.log(`${check.pass ? 'PASS' : 'FAIL'} ${check.name}`);
}
if (failed.length) {
  process.exit(1);
}
