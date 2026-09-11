// Re-renders docs/alert-card.png from docs/alert-card.html.
//
//   cd docs && npm i playwright && node render-card.mjs
//
// The HTML is the source; the PNG is a build product checked in because the
// card is meant to be opened on a phone, where nobody is running a browser
// against a local file. Edit the HTML, re-run this, commit both.
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1080, height: 1200 },
                            deviceScaleFactor: 2 });
await p.goto('file://' + process.cwd() + '/alert-card.html');
await p.waitForTimeout(500);
await p.screenshot({ path: 'alert-card.png', fullPage: true });
await b.close();
