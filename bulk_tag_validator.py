import warnings
warnings.filterwarnings("ignore")
import asyncio
import pandas as pd
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import os
import time
import re
import sys

stealth_obj = Stealth()
CONCURRENCY = 3  # Stable concurrency

COOKIE_SELECTORS = [
    '#onetrust-accept-btn-handler',
    '#accept-recommended-btn-handler',
    'button[title="Accept All"]',
    'button[title="Accept"]',
    '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',
    '#CybotCookiebotDialogBodyButtonAccept',
    '#truste-consent-button',
    '#didomi-notice-agree-button',
    '.cc-accept', '.cc-btn.cc-allow',
    '#cookie-accept', '#accept-cookies',
    '[data-action="accept"]',
    'button[aria-label="Accept all cookies"]',
    'button[aria-label="Accept cookies"]',
    'button[aria-label="accept and close"]',
]

COOKIE_TEXT_PATTERNS = [
    "Accept All", "Accept all", "ACCEPT ALL",
    "Accept Cookies", "Accept cookies",
    "Allow All", "Allow all",
    "I Accept", "I agree",
    "Agree", "OK", "Got it",
    "Accept & Close", "Accept and close",
    "Consent", "Continue",
]

async def accept_cookies(page):
    """Aggressively try to accept cookie consent banners."""
    for sel in COOKIE_SELECTORS:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=200):
                await el.click(timeout=2000)
                return True
        except: pass
    for text in COOKIE_TEXT_PATTERNS:
        try:
            btn = page.get_by_role("button", name=text, exact=False).first
            if await btn.is_visible(timeout=200):
                await btn.click(timeout=2000)
                return True
        except: pass
    return False

async def validate_tags(browser, url, index, total):
    results = {
        "URL": url,
        "Tealium_Loaded": "FAIL", "Tealium_Account": "", "Tealium_Profile": "", "Tealium_Env": "", "Tealium_View_Fired": "FAIL",
        "GTM_Loaded": "FAIL", "GTM_ID": "", "GA4_Fired": "FAIL", "GA4_Measurement_ID": "", "GA4_PageView": "FAIL",
        "Adobe_Loaded": "FAIL", "Adobe_ReportSuite": "", "Adobe_PageView": "FAIL", "Error": ""
    }

    # Tracking Flags
    flags = {
        "tealium_js": False, "tealium_collect": False,
        "gtm": False, "ga4": False, "ga4_pv": False,
        "adobe": False, "adobe_pv": False
    }
    tealium_accounts = []
    gtm_ids = set()
    ga4_ids = set()
    adobe_rsids = set()

    context = None
    try:
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await stealth_obj.apply_stealth_async(page)

        # 1. SETUP REQUEST LISTENER (CRITICAL: Before navigation)
        def handle_request(request):
            u = request.url
            low = u.lower()
            try:
                post = (request.post_data or "").lower()
            except:
                post = ""
            combined = low + " | " + post

            # Tealium
            if "tiqcdn.com" in low and "utag" in low:
                flags["tealium_js"] = True
                m = re.search(r'tiqcdn\.com/utag/([^/]+)/([^/]+)/([^/]+)/', u, re.I)
                if m: tealium_accounts.append({"account": m.group(1), "profile": m.group(2), "env": m.group(3)})
            if "tealiumiq.com" in low or ("tealium" in low and ("collect" in low or "v.gif" in low or "/event" in low)):
                flags["tealium_collect"] = True

            # GTM / GA4
            if "googletagmanager.com/gtm.js" in low:
                flags["gtm"] = True
                m = re.search(r'[?&]id=(GTM-[A-Z0-9]+)', u, re.I)
                if m: gtm_ids.add(m.group(1).upper())
            if "/g/collect" in low or (("google-analytics.com" in low or "analytics.google.com" in low) and "collect" in low):
                flags["ga4"] = True
                m = re.search(r'[?&]tid=(G-[A-Z0-9]+)', u, re.I)
                if not m: m = re.search(r'[?&]tid=(G-[A-Z0-9]+)', combined, re.I)
                if m: ga4_ids.add(m.group(1).upper())
                if "en=page_view" in combined: flags["ga4_pv"] = True

            # Adobe
            if "/b/ss/" in low or ".omtrdc.net" in low or ".2o7.net" in low or "metrics." in low:
                # Basic check for Adobe-like requests
                if "/b/ss/" in low or ".omtrdc.net" in low or ".2o7.net" in low:
                    flags["adobe"] = True
                    m = re.search(r'/b/ss/([^/]+)/', u)
                    if m: adobe_rsids.add(m.group(1))
                    if "pe=" not in combined: flags["adobe_pv"] = True
            
            if "appmeasurement" in low or "s_code" in low or "satellite-" in low or "launch-" in low:
                flags["adobe"] = True

        page.on("request", handle_request)

        sys.stdout.write(f"[{index}/{total}] Checking: {url}\n")
        sys.stdout.flush()

        # 2. NAVIGATE
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        except Exception as e:
            results["Error"] = "Timeout" if "Timeout" in str(e) else str(e)[:50]

        # 3. ACCEPT COOKIES
        await asyncio.sleep(2)
        await accept_cookies(page)

        # 4. WAIT FOR TAGS
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except: pass
        await asyncio.sleep(6) # Give extra time for late tags

        # 5. JS BACKUP SCAN
        try:
            utag_js = await page.evaluate("typeof window.utag !== 'undefined'")
            if utag_js: flags["tealium_js"] = True
            gtm_js = await page.evaluate("typeof window.google_tag_manager !== 'undefined'")
            if gtm_js: flags["gtm"] = True
            adobe_js = await page.evaluate("typeof window.s !== 'undefined' || typeof window._satellite !== 'undefined'")
            if adobe_js: flags["adobe"] = True
        except: pass

        # FINAL RESULTS MAPPING
        results["Tealium_Loaded"] = "PASS" if flags["tealium_js"] else "FAIL"
        results["Tealium_View_Fired"] = "PASS" if flags["tealium_collect"] else "FAIL"
        if tealium_accounts:
            results["Tealium_Account"] = tealium_accounts[0]["account"]
            results["Tealium_Profile"] = tealium_accounts[0]["profile"]
            results["Tealium_Env"] = tealium_accounts[0]["env"]
        
        results["GTM_Loaded"] = "PASS" if flags["gtm"] else "FAIL"
        results["GTM_ID"] = ", ".join(sorted(gtm_ids)) if gtm_ids else ""
        results["GA4_Fired"] = "PASS" if flags["ga4"] else "FAIL"
        results["GA4_Measurement_ID"] = ", ".join(sorted(ga4_ids)) if ga4_ids else ""
        results["GA4_PageView"] = "PASS" if flags["ga4_pv"] else "FAIL"
        
        results["Adobe_Loaded"] = "PASS" if flags["adobe"] else "FAIL"
        results["Adobe_ReportSuite"] = ", ".join(sorted(adobe_rsids)) if adobe_rsids else ""
        results["Adobe_PageView"] = "PASS" if flags["adobe_pv"] else "FAIL"

        sys.stdout.write(f"[{index}/{total}] Done: {url}\n")
        sys.stdout.flush()
        await page.close()
    except Exception as e:
        results["Error"] = f"Fatal: {str(e)[:50]}"
    finally:
        if context: await context.close()

    return results

async def main():
    print("Bulk Tag Validator Engine Started.")
    input_file = "input_sites.xlsx"
    output_file = "validation_results.xlsx"
    if not os.path.exists(input_file):
        print("Error: input_sites.xlsx not found.")
        return
    df = pd.read_excel(input_file)
    url_col = [c for c in df.columns if any(x in str(c).lower() for x in ['url', 'site', 'link'])][0]
    urls = [("https://" + str(u).strip() if not str(u).strip().startswith("http") else str(u).strip()) for u in df[url_col] if pd.notna(u)]
    total = len(urls)
    
    all_results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'])
        for i in range(0, total, CONCURRENCY):
            batch = urls[i:i + CONCURRENCY]
            tasks = [validate_tags(browser, u, i + j + 1, total) for j, u in enumerate(batch)]
            all_results.extend(await asyncio.gather(*tasks))
        await browser.close()
    
    pd.DataFrame(all_results).to_excel(output_file, index=False)
    print(f"Validation Complete. Saved to {output_file}")

if __name__ == "__main__":
    asyncio.run(main())
