const { chromium } = require('playwright');
const path = require('path');

const taskDir = __dirname;
const targets = [
  ['#xhs-01', 'xhs-01-cover.png'],
  ['#xhs-02', 'xhs-02-pain.png'],
  ['#xhs-03', 'xhs-03-word-timing.png'],
  ['#xhs-04', 'xhs-04-pipeline.png'],
  ['#xhs-05', 'xhs-05-semantics.png'],
  ['#xhs-06', 'xhs-06-output.png'],
  ['#xhs-07', 'xhs-07-takeaway.png'],
];

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1200, height: 1600 }, deviceScaleFactor: 1 });
  await page.goto(`file://${path.join(taskDir, 'index.html')}`, { waitUntil: 'networkidle' });
  await page.evaluate(async () => {
    if (document.fonts && document.fonts.ready) await document.fonts.ready;
    if (window.lucide && typeof window.lucide.createIcons === 'function') window.lucide.createIcons();
  });
  await page.waitForTimeout(600);

  for (const [selector, filename] of targets) {
    const el = await page.$(selector);
    if (!el) throw new Error(`Missing target ${selector}`);
    await el.screenshot({ path: path.join(taskDir, 'output', filename) });
  }

  await browser.close();
})();
