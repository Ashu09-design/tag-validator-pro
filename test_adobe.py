import warnings; warnings.filterwarnings('ignore')
import asyncio, re, sys
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

COOKIE_SELECTORS = [
    '#onetrust-accept-btn-handler', '#accept-recommended-btn-handler',
    'button[title="Accept All"]', 'button[title="Accept"]',
    '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',
    '#truste-consent-button', '#didomi-notice-agree-button',
]
COOKIE_TEXT = ["Accept All", "Accept all", "Accept Cookies", "Allow All", "I Accept", "Agree", "OK", "Got it"]

async def accept_cookies(page):
    for sel in COOKIE_SELECTORS:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=200):
                await el.click(timeout=2000)
                print(f"  Cookie accepted via selector: {sel}")
                return True
        except: pass
    for text in COOKIE_TEXT:
        try:
            btn = page.get_by_role("button", name=text, exact=False).first
            if await btn.is_visible(timeout=200):
                await btn.click(timeout=2000)
                print(f"  Cookie accepted via text: {text}")
                return True
        except: pass
    try:
        clicked = await page.evaluate("""
            () => {
                const kw = ['accept', 'agree', 'allow', 'consent'];
                const btns = [...document.querySelectorAll('button, a[role="button"]')];
                for (const b of btns) {
                    const t = (b.innerText||'').toLowerCase().trim();
                    if (b.offsetParent && kw.some(k => t.includes(k))) { b.click(); return t; }
                }
                return false;
            }
        """)
        if clicked:
            print(f"  Cookie accepted via JS: {clicked}")
            return True
    except: pass
    print("  No cookie banner found")
    return False

async def test():
    urls = [
        'https://freseniusmedicalcare.com/en-us/',
        'https://freseniusmedicalcare.com/en/',
        'https://freseniusmedicalcare.com/de/',
    ]
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for url in urls:
            ctx = await browser.new_context(viewport={'width':1280,'height':800}, user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            page = await ctx.new_page()
            s = Stealth()
            await s.apply_stealth_async(page)
            all_urls = []
            cdp = await page.context.new_cdp_session(page)
            await cdp.send('Network.enable')
            cdp.on('Network.requestWillBeSent', lambda p: all_urls.append(p.get('request',{}).get('url','')))
            
            print(f"\n=== {url} ===")
            await page.goto(url, wait_until='domcontentloaded', timeout=25000)
            await asyncio.sleep(2)
            await accept_cookies(page)
            try:
                await page.wait_for_load_state('networkidle', timeout=10000)
            except: pass
            await asyncio.sleep(5)
            
            try:
                perf = await page.evaluate("() => performance.getEntriesByType('resource').map(r => r.name)")
                all_urls.extend(perf or [])
            except: pass
            
            rsids = set()
            adobe_pv = False
            for u in all_urls:
                if '/b/ss/' in u.lower():
                    m = re.search(r'/b/ss/([^/]+)/', u)
                    if m: rsids.add(m.group(1))
                    if 'pe=' not in u.lower():
                        adobe_pv = True
            
            print(f"  Total requests: {len(all_urls)}")
            print(f"  Report Suites: {rsids}")
            print(f"  Adobe PageView: {adobe_pv}")
            
            await cdp.detach()
            await ctx.close()
        await browser.close()

asyncio.run(test())
