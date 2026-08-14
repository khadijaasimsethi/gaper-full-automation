import logging
import json
import uuid
import time
import random
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
import google.generativeai as genai
from src.gaper_scraper import get_brand_profile
import config
import urllib.parse
import os

IS_HEADLESS = os.environ.get("PLAYWRIGHT_HEADLESS", "false").lower() == "true"
logger = logging.getLogger(__name__)
GEMINI_MODEL = "gemini-flash-latest"

SESSION_DIR = Path(config.BASE_DIR) / "sessions"
SESSION_DIR.mkdir(exist_ok=True)
SCREENSHOT_DIR = Path(config.BASE_DIR) / "output" / "listing_screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

# Drop your logo file here (any name) and it gets auto-uploaded whenever a
# directory's form has a file/image upload field for it. If this folder is
# empty or missing, logo upload fields are simply skipped (nothing breaks).
LOGO_DIR = Path(config.BASE_DIR) / "assets"
LOGO_DIR.mkdir(parents=True, exist_ok=True)

_active_sessions = {}
_writer_sessions = {}


def _content_to_html_with_link(content: str) -> str:
    """
    Converts generated content containing a markdown-style link
    [anchor text](url) into real HTML so contenteditable/rich-text
    editors (Blogger, WordPress, etc.) render it as an actual clickable
    <a> tag instead of literal bracket text.
    """
    import re
    import html

    # Escape the plain text first, then re-insert the link as real HTML,
    # then convert newlines to <br> since contenteditable ignores \n.
    md_link_pattern = re.compile(r"\[([^\]]+)\]\((https?://[^\)]+)\)")

    match = md_link_pattern.search(content)
    if not match:
        # No markdown link found - just escape and convert newlines.
        escaped = html.escape(content)
        return escaped.replace("\n", "<br>")

    before = html.escape(content[:match.start()])
    after = html.escape(content[match.end():])
    anchor_text = html.escape(match.group(1))
    url = match.group(2)

    html_out = f'{before}<a href="{url}">{anchor_text}</a>{after}'
    return html_out.replace("\n", "<br>")
def list_saved_sessions() -> list:
    """Return all domain names with saved browser sessions."""
    sessions = []
    for d in SESSION_DIR.iterdir():
        if d.is_dir() and d.name.startswith("generic_"):
            domain = d.name.replace("generic_", "").replace("_profile", "").replace("_", ".")
            sessions.append(domain)
    return sorted(sessions)


def get_saved_session(domain: str) -> bool:
    """Check if a saved session exists for a given domain."""
    for d in SESSION_DIR.iterdir():
        if d.is_dir() and domain.replace(".", "_") in d.name:
            return True
    return False


def _find_logo_file() -> str:
    """First image file found in /assets, or None if you haven't added one yet."""
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.svg", "*.webp"):
        matches = list(LOGO_DIR.glob(ext))
        if matches:
            return str(matches[0])
    return None


def _get_proxy():
    """Get a random proxy from the pool"""
    if not hasattr(config, "PROXY_LIST") or not config.PROXY_LIST:
        return None
    proxy = random.choice(config.PROXY_LIST)
    return {
        "server": f"http://{proxy['ip']}:{proxy['port']}",
        "username": proxy.get("username"),
        "password": proxy.get("password"),
    }


def _solve_captcha_with_2captcha(screenshot_bytes: bytes, page_url: str) -> str:
    """Solve CAPTCHA using 2Captcha"""
    import base64
    import requests

    if not config.CAPTCHA_API_KEY:
        return None

    screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
    data = {
        "key": config.CAPTCHA_API_KEY,
        "method": "base64",
        "body": screenshot_base64,
        "json": 1,
        "cloudflare": 1,
    }
    try:
        response = requests.post("https://2captcha.com/in.php", data=data, timeout=15)
        result = response.json()
    except Exception:
        return None

    if result.get("status") != 1:
        return None

    captcha_id = result.get("request")
    for _ in range(24):
        time.sleep(5)
        try:
            resp = requests.get("https://2captcha.com/res.php", params={
                "key": config.CAPTCHA_API_KEY, "action": "get", "id": captcha_id, "json": 1
            }, timeout=10)
            data = resp.json()
        except Exception:
            continue
        if data.get("status") == 1:
            return data.get("request")
        if data.get("request") != "CAPCHA_NOT_READY":
            break
    return None


async def _handle_captcha(page) -> bool:
    """Detect and solve CAPTCHA if present"""
    try:
        page_url = page.url

        if "challenge" in page_url.lower() or "cloudflare" in page_url.lower():
            print("🛡️ Cloudflare detected! Solving with 2Captcha...")
            try:
                await page.wait_for_timeout(3000)
                screenshot = await page.screenshot(full_page=True)
            except Exception:
                return False
            token = _solve_captcha_with_2captcha(screenshot, page_url)
            if token:
                try:
                    await page.evaluate(f"""
                        document.cookie = 'cf_clearance={token}; path=/; max-age=3600';
                        location.reload();
                    """)
                    await page.wait_for_timeout(5000)
                    print("✅ Cloudflare bypassed!")
                    return True
                except Exception:
                    pass
            return False

        try:
            turnstile = page.locator('.cf-turnstile').first
            if await turnstile.count() > 0:
                print("🛡️ Turnstile detected!")
                site_key = await turnstile.get_attribute("data-sitekey")
                if site_key and config.CAPTCHA_API_KEY:
                    import requests
                    data = {
                        "key": config.CAPTCHA_API_KEY, "method": "turnstile",
                        "sitekey": site_key, "pageurl": page_url, "json": 1,
                    }
                    response = requests.post("https://2captcha.com/in.php", data=data, timeout=15)
                    result = response.json()
                    if result.get("status") == 1:
                        captcha_id = result.get("request")
                        for _ in range(24):
                            time.sleep(5)
                            resp = requests.get("https://2captcha.com/res.php", params={
                                "key": config.CAPTCHA_API_KEY, "action": "get", "id": captcha_id, "json": 1
                            })
                            data = resp.json()
                            if data.get("status") == 1:
                                token = data.get("request")
                                try:
                                    await page.evaluate(f"""
                                        const cb = window.turnstileCallback || window.TurnstileCallback;
                                        if (cb) cb('{token}');
                                        document.querySelector('.cf-turnstile').innerHTML = '';
                                    """)
                                    await page.wait_for_timeout(2000)
                                    print("✅ Turnstile solved!")
                                    return True
                                except Exception:
                                    pass
                                return False
                            if data.get("request") != "CAPCHA_NOT_READY":
                                break
                return False
        except Exception:
            pass

        try:
            recaptcha = page.locator('[data-sitekey]').first
            if await recaptcha.count() > 0:
                site_key = await recaptcha.get_attribute("data-sitekey")
                if site_key and config.CAPTCHA_API_KEY:
                    print(f"🔑 reCAPTCHA detected: {site_key[:20]}...")
                    import requests
                    data = {
                        "key": config.CAPTCHA_API_KEY, "method": "userrecaptcha",
                        "googlekey": site_key, "pageurl": page_url, "json": 1,
                    }
                    response = requests.post("https://2captcha.com/in.php", data=data, timeout=15)
                    result = response.json()
                    if result.get("status") == 1:
                        captcha_id = result.get("request")
                        for _ in range(24):
                            time.sleep(5)
                            resp = requests.get("https://2captcha.com/res.php", params={
                                "key": config.CAPTCHA_API_KEY, "action": "get", "id": captcha_id, "json": 1
                            })
                            data = resp.json()
                            if data.get("status") == 1:
                                token = data.get("request")
                                try:
                                    await page.evaluate(f"""
                                        document.querySelector('[data-sitekey]').innerHTML = '';
                                        const cb = window.__grecaptcha_callback || window.recaptchaCallback;
                                        if (cb) cb('{token}');
                                    """)
                                    await page.wait_for_timeout(2000)
                                    print("✅ reCAPTCHA solved!")
                                    return True
                                except Exception:
                                    pass
                                return False
                            if data.get("request") != "CAPCHA_NOT_READY":
                                break
                return False
        except Exception:
            pass

    except Exception as e:
        print(f"CAPTCHA handling failed: {e}")

    return False


async def _get_browser_context_async(platform_name: str):
    """
    Async browser context with proxy support.
    Viewport bumped to 1600x950 and window maximized so action buttons
    (like Blogger's Publish, which sits far top-right) are never clipped
    outside the visible area.
    """
    p = await async_playwright().start()
    profile_dir = SESSION_DIR / f"generic_{platform_name.replace('.', '_')}_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    proxy = _get_proxy()
    if proxy:
        print(f"🌐 Using proxy: {proxy['server']}")

    context = await p.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir),
        headless=IS_HEADLESS,
        viewport={"width": 1600, "height": 950},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        proxy=proxy,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--start-maximized",
        ],
        ignore_default_args=["--enable-automation"],
    )

    page = await context.new_page()

    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        delete navigator.__proto__.webdriver;
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
    """)

    return p, context, page


def _build_brand_data() -> dict:
    """
    Everything a typical 'submit your product' directory form might ask
    for - not just name/URL.
    """
    brand = get_brand_profile()
    usps = brand.get("usps", "") or ""
    tagline = usps.split("\n")[0] if usps else "AI-native implementation partner."
    description = brand.get("description", "") or "Gaper is an AI-native implementation partner."
    return {
        "product_name": "Gaper",
        "product_url": "https://gaper.io",
        "tagline": tagline[:100],
        "description": description[:500],
        "short_description": "AI-powered hiring platform matching companies with vetted remote developers within 24 hours.",
        "category_tags": "AI agents, developer staffing, remote work, automation, SaaS",
        "keywords": "AI hiring, remote developers, staff augmentation, AI implementation, developer staffing",
        "contact_email": "pr@gaper.io",
        "website": "https://gaper.io",
        "company_name": "Gaper",
        "industry": "Software Development & AI",
        "pricing": "Flexible monthly contracts",
        "pricing_model": "Custom / Contact for pricing",
        "location": "Remote / Global",
        "founded_year": getattr(config, "GAPER_FOUNDED_YEAR", ""),
        "founder_name": getattr(config, "GAPER_FOUNDER_NAME", ""),
        "twitter_handle": "@gaper_io",
        "social_linkedin": "https://linkedin.com/company/gaper-io",
        "social_twitter": "https://twitter.com/gaper_io",
        "github_url": getattr(config, "GAPER_GITHUB_URL", ""),
        "demo_video_url": getattr(config, "GAPER_DEMO_VIDEO_URL", ""),
        "logo_url": brand.get("logo_url", "https://gaper.io/favicon.ico"),
        "logo_file_path": _find_logo_file(),
    }


def _ask_gemini_to_map_fields(elements: list, brand_data: dict) -> dict:
    """Gemini maps fields - ALWAYS returns dict"""
    try:
        genai.configure(api_key=config.GEMINI_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL)
        prompt = f"""
You are an AI assistant that fills out product/startup directory submission forms.

BRAND DATA TO FILL:
{json.dumps(brand_data, indent=2)}

FORM ELEMENTS FOUND:
{json.dumps(elements, indent=2)}

Some elements are file/image upload inputs (type: "file") - for those, if
the field is clearly for a logo/screenshot/product image, map it to
"logo_file_path". Leave any brand_data value that is null/empty unmapped
rather than forcing a field to use it.

Return ONLY JSON with field_mappings and submit_button_idx.
Each field_mapping is: {{"gaper_idx": <int>, "brand_data_key": "<key from BRAND DATA>"}}
"""
        response = model.generate_content(prompt)
        raw = response.text.strip()
        print(f"🔎 Gemini raw response (first 500 chars): {raw[:500]}")

        if raw.startswith("```json"):
            raw = raw[7:]
        elif raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]

        result = json.loads(raw.strip())
        if not isinstance(result, dict):
            return {"field_mappings": [], "submit_button_idx": None}
        if "field_mappings" not in result:
            result["field_mappings"] = []
        if "submit_button_idx" not in result:
            result["submit_button_idx"] = None
        return result
    except Exception as e:
        print(f"⚠️ Gemini mapping error: {e}")
        return {"field_mappings": [], "submit_button_idx": None}


async def _click_submit_trigger_if_needed(page) -> bool:
    """
    Most directory URLs land on a general homepage, not the actual
    submission form - the real form is usually one click away behind a
    'Submit your product/tool/startup' link or button.
    """
    triggers = [
        'a:has-text("Submit your")', 'button:has-text("Submit your")',
        'a:has-text("Add your")', 'button:has-text("Add your")',
        'a:has-text("List your")', 'button:has-text("List your")',
        'a:has-text("Get listed")', 'button:has-text("Get listed")',
        'a:has-text("Add a tool")', 'a:has-text("Add a product")',
        'a:has-text("Add a startup")', 'a:has-text("Submit tool")',
        'a:has-text("Submit product")', 'a:has-text("Submit startup")',
        'a:has-text("Submit")', 'button:has-text("Submit")',
        'a[href*="submit" i]',
    ]
    for sel in triggers:
        try:
            el = page.locator(sel).first
            if await el.count() > 0 and await el.is_visible():
                await el.click(timeout=3000)
                await page.wait_for_timeout(2500)
                print(f"  ↪️  Clicked '{sel}' to reach the actual submission form.")
                return True
        except Exception:
            continue
    return False


async def start_generic_listing_async(url: str, platform_name: str = None) -> dict:
    """Async listing - with MANUAL login confirmation (CLI-only path, used by the Listing Pitcher tab)."""
    platform_name = platform_name or url.split("/")[2]
    session_id = str(uuid.uuid4())[:8]

    p = None
    context = None
    page = None

    try:
        p, context, page = await _get_browser_context_async(platform_name)

        print(f"\n🌐 Opening {url}...")
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(2000)
        await _handle_captcha(page)

        current_url = page.url.lower()
        if "login" in current_url or "signin" in current_url or "signup" in current_url:
            print("\n" + "=" * 50)
            print("🔐 LOGIN REQUIRED")
            print("=" * 50)
            print("1. Login manually in the browser window")
            print("2. If email verification, check your email")
            print("3. Complete login")
            print("4. COME BACK TO THIS TERMINAL and press ENTER")
            print("=" * 50)
            input("\n👉 Press ENTER after you have COMPLETED login...\n")
            print("✅ User confirmed login! Refreshing page...")

            try:
                all_pages = context.pages
                if len(all_pages) > 1:
                    page = all_pages[-1]
                    print(f"↪️  Detected {len(all_pages)} open tabs after login - continuing on the newest one.")
            except Exception:
                pass

            try:
                await page.reload(wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)
            except Exception as e:
                print(f"⚠️ Reload failed: {e}")
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)

            print("✅ Page refreshed! Continuing...")

        await page.wait_for_timeout(3000)

        try:
            quick_check = await page.locator("input:not([type='hidden']), textarea").count()
        except Exception:
            quick_check = 0
        if quick_check < 2:
            clicked = await _click_submit_trigger_if_needed(page)
            if clicked:
                await page.wait_for_timeout(2000)

        try:
            elements = await page.eval_on_selector_all(
                "input:not([type='hidden']):not([type='submit']), textarea, select, button",
                """
                (els) => els.map((el, idx) => {
                    el.setAttribute('data-gaper-idx', idx);
                    let labelText = '';
                    if (el.labels && el.labels.length) {
                        labelText = el.labels[0].innerText;
                    } else if (el.id) {
                        const lbl = document.querySelector(`label[for="${el.id}"]`);
                        if (lbl) labelText = lbl.innerText;
                    }
                    const rect = el.getBoundingClientRect();
                    return {
                        gaper_idx: idx,
                        tag: el.tagName.toLowerCase(),
                        type: el.type || null,
                        name: el.name || null,
                        id: el.id || null,
                        placeholder: el.placeholder || null,
                        aria_label: el.getAttribute('aria-label'),
                        label_text: (labelText || '').trim().slice(0, 100),
                        button_text: (el.tagName.toLowerCase() === 'button') ? (el.innerText || '').slice(0, 60) : null,
                        visible: rect.width > 0 && rect.height > 0
                    };
                })
                """
            )
        except Exception as e:
            print(f"⚠️ Element detection error: {e}")
            elements = []

        elements = [e for e in elements if e.get("visible")]
        print(f"🔍 Found {len(elements)} form elements")

        if not elements:
            print("⚠️ No form elements found! Keeping browser open for manual review.")
            screenshot_path = SCREENSHOT_DIR / f"{session_id}_no_form.png"
            try:
                await page.screenshot(path=str(screenshot_path), full_page=True)
            except Exception:
                pass
            _active_sessions[session_id] = {
                "playwright": p, "context": context, "page": page,
                "submit_button_idx": None, "platform_name": platform_name, "url": url,
            }
            return {
                "status": "awaiting_approval", "session_id": session_id, "platform_name": platform_name,
                "filled_fields": [], "notes": "⚠️ No form found. Please fill and submit manually in browser.",
                "screenshot_path": str(screenshot_path) if screenshot_path else None,
            }

        brand_data = _build_brand_data()
        print("🤖 Gemini mapping fields...")
        mapping = _ask_gemini_to_map_fields(elements, brand_data)
        if not isinstance(mapping, dict):
            mapping = {"field_mappings": [], "submit_button_idx": None}
        print(f"📋 Gemini mapped {len(mapping.get('field_mappings', []))} fields")

        filled = []
        for fm in mapping.get("field_mappings", []):
            idx = fm.get("gaper_idx")
            key = fm.get("brand_data_key")
            value = brand_data.get(key)
            if value is None or value == "":
                continue
            selector = f'[data-gaper-idx="{idx}"]'
            try:
                el = page.locator(selector)
                tag = await el.evaluate("el => el.tagName.toLowerCase()")
                input_type = await el.evaluate("el => el.type || ''")

                if input_type == "file":
                    if key == "logo_file_path" and value:
                        await el.set_input_files(str(value))
                        filled.append(key)
                        print(f"  ✅ Uploaded: {key}")
                    continue

                if tag in ("input", "textarea"):
                    await el.fill(str(value))
                    filled.append(key)
                    print(f"  ✅ Filled: {key}")
                elif tag == "select":
                    await el.select_option(label=str(value))
                    filled.append(key)
                    print(f"  ✅ Filled: {key}")
            except Exception as e:
                print(f"  ⚠️ Could not fill {key}: {e}")

        submit_idx = mapping.get("submit_button_idx")
        if submit_idx is not None and filled:
            try:
                submit_el = page.locator(f'[data-gaper-idx="{submit_idx}"]')
                await submit_el.click(timeout=8000)
                print("✅ Clicked Submit!")
                await page.wait_for_timeout(5000)
                await _handle_captcha(page)

                landed_url = page.url
                screenshot_path = SCREENSHOT_DIR / f"{session_id}_submitted.png"
                try:
                    await page.screenshot(path=str(screenshot_path), full_page=True)
                except Exception:
                    pass

                await context.close()
                await p.stop()

                return {
                    "status": "success", "session_id": session_id, "platform_name": platform_name,
                    "filled_fields": filled, "detail": f"✅ Submitted on {platform_name}",
                    "posted_url": landed_url,
                    "screenshot_path": str(screenshot_path) if screenshot_path else None,
                }
            except Exception as e:
                print(f"⚠️ Submit click failed: {e}")
        else:
            if submit_idx is None:
                print("⚠️ No submit button found - please click Submit manually.")
            else:
                print("⚠️ Nothing was filled, so submit was skipped - please fill and click Submit manually.")

        screenshot_path = SCREENSHOT_DIR / f"{session_id}_filled.png"
        try:
            await page.screenshot(path=str(screenshot_path), full_page=True)
        except Exception:
            pass

        _active_sessions[session_id] = {
            "playwright": p, "context": context, "page": page,
            "submit_button_idx": submit_idx, "platform_name": platform_name, "url": url,
        }
        return {
            "status": "awaiting_approval", "session_id": session_id, "platform_name": platform_name,
            "filled_fields": filled, "notes": "Fields filled. Click 'Confirm Submit' in dashboard or Submit manually.",
            "screenshot_path": str(screenshot_path) if screenshot_path else None,
        }

    except Exception as e:
        print(f"❌ Error: {e}")
        if context and page:
            try:
                screenshot_path = SCREENSHOT_DIR / f"{session_id}_error.png"
                await page.screenshot(path=str(screenshot_path), full_page=True)
                _active_sessions[session_id] = {
                    "playwright": p, "context": context, "page": page,
                    "submit_button_idx": None, "platform_name": platform_name, "url": url,
                }
                return {
                    "status": "awaiting_approval", "session_id": session_id, "platform_name": platform_name,
                    "filled_fields": [], "notes": f"⚠️ Error: {str(e)[:100]}. Browser open for manual.",
                    "screenshot_path": str(screenshot_path),
                }
            except Exception:
                pass
        try:
            if context:
                await context.close()
            if p:
                await p.stop()
        except Exception:
            pass
        return {"status": "failed", "detail": str(e)}


async def confirm_generic_listing_async(session_id: str) -> dict:
    """Confirm and submit the listing"""
    session = _active_sessions.get(session_id)
    if not session:
        return {"status": "failed", "detail": "Session not found"}

    page = session.get("page")
    submit_idx = session.get("submit_button_idx")
    if not page:
        return {"status": "failed", "detail": "Page not found"}

    try:
        try:
            await page.evaluate("1")
        except Exception:
            return {"status": "failed", "detail": "Browser page is closed"}

        if submit_idx is not None:
            submit_el = page.locator(f'[data-gaper-idx="{submit_idx}"]')
            await submit_el.click(timeout=8000)
            await page.wait_for_timeout(4000)
            await _handle_captcha(page)
            landed_url = page.url
            result = {
                "status": "success", "detail": f"✅ Submitted on {session['platform_name']}",
                "posted_url": landed_url,
            }
        else:
            result = {"status": "failed", "detail": "No submit button found - submit manually"}
    except Exception as e:
        result = {"status": "failed", "detail": str(e)}
    finally:
        try:
            await session["context"].close()
            await session["playwright"].stop()
        except Exception:
            pass
        del _active_sessions[session_id]

    return result


def confirm_generic_listing(session_id: str) -> dict:
    """Sync wrapper"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(confirm_generic_listing_async(session_id))


async def cancel_generic_listing_async(session_id: str) -> dict:
    """Cancel the listing session"""
    session = _active_sessions.pop(session_id, None)
    if session:
        try:
            await session["context"].close()
            await session["playwright"].stop()
        except Exception:
            pass
        return {"status": "cancelled"}
    return {"status": "not_found"}


def cancel_generic_listing(session_id: str) -> dict:
    """Sync wrapper"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(cancel_generic_listing_async(session_id))


# ============================================
# Shared field/button finding helpers
# ============================================

async def _get_visible_box(el):
    """
    Returns the bounding box ONLY if the element is genuinely visible
    and has a real, sane on-screen size - filters out near-invisible or
    off-screen tracking elements that a loose is_visible() check can miss.
    """
    try:
        if not await el.is_visible():
            return None
        box = await el.bounding_box()
        if not box:
            return None
        if box["width"] < 40 or box["height"] < 20:
            return None
        return box
    except Exception:
        return None


async def _find_main_content_field(page):
    """
    Finds the primary content-entry field on a simple paste/blog site
    (Rentry, Write.as, Pastebin-style pages) - the biggest visible,
    reasonably-sized textarea or contenteditable element.
    """
    candidates = await page.locator("textarea, div[contenteditable='true'], [role='textbox']").all()
    best = None
    best_area = 0
    for el in candidates:
        box = await _get_visible_box(el)
        if not box:
            continue
        area = box["width"] * box["height"]
        if area > best_area:
            best_area = area
            best = el
    return best


async def _find_main_content_field_incl_frames(page, retries: int = 3, wait_ms: int = 1500):
    """
    Looks for the main editable content field on the current page,
    including inside iframes (some editors - Blogger, some WordPress
    themes - put the real editable area inside an iframe, and some,
    like Blogger's new editor, make the <body> of that iframe itself
    contenteditable rather than a nested <div>).
    Retries a few times with a short wait since the iframe often isn't
    fully attached/rendered the instant the page "looks" ready.
    Returns (field, scope) where scope is the page or frame it was found in.
    """
    frame_selector = "textarea, div[contenteditable='true'], body[contenteditable='true'], [role='textbox'], [contenteditable='true']"

    for attempt in range(retries):
        field = await _find_main_content_field(page)
        if field:
            try:
                tag = await field.evaluate("el => el.tagName")
                print(f"  🔍 Main content field found on top-level page: <{tag}>")
            except Exception:
                pass
            return field, page

        for frame in page.frames:
            if frame == page.main_frame:
                continue
            try:
                candidates = await frame.locator(frame_selector).all()
                best, best_area = None, 0
                for el in candidates:
                    box = await _get_visible_box(el)
                    if not box:
                        continue
                    area = box["width"] * box["height"]
                    if area > best_area:
                        best_area, best = area, el
                if best:
                    tag = await best.evaluate("el => el.tagName")
                    print(f"  🔍 Main content field found inside iframe (<{tag}>): {frame.url}")
                    return best, frame
            except Exception:
                continue

        if attempt < retries - 1:
            print(f"  ⏳ No field found yet (attempt {attempt + 1}/{retries}), waiting for iframe to load...")
            await page.wait_for_timeout(wait_ms)

    return None, page


async def _click_new_post_trigger_if_needed(page) -> bool:
    """
    Many CMS-style sites (Blogger, WordPress, Ghost, Medium) land you on
    a dashboard/blog-list after login, not directly in a post editor.
    Includes Blogger's icon-only floating action button (no visible text).
    """
    triggers = [
        'a:has-text("Start Writing")', 'button:has-text("Start Writing")',
        'a:has-text("Start writing")', 'button:has-text("Start writing")',
        'a:has-text("Get Started")', 'button:has-text("Get Started")',
        '[aria-label="Create Post"]', '[aria-label="New Post"]',
        '[aria-label="Create a new post"]', '[data-tooltip="Create new post"]',
        'a[href*="blogger.com/blog/post/new"]',
        'div[role="button"][aria-label*="post" i]',
        'a:has-text("New Post")', 'button:has-text("New Post")',
        'a:has-text("New post")', 'button:has-text("New post")',
        'a:has-text("Write")', 'button:has-text("Write")',
        'a:has-text("Compose")', 'button:has-text("Compose")',
        'a:has-text("Create post")', 'button:has-text("Create post")',
        'a:has-text("Add post")', 'button:has-text("Add post")',
        '[aria-label*="New post" i]', '[title*="New post" i]',
        'a[href*="post/new" i]', 'a[href*="new-story" i]', 'a[href*="new-post" i]',
    ]
    for sel in triggers:
        try:
            el = page.locator(sel).first
            if await el.count() > 0 and await el.is_visible():
                await el.click(timeout=5000)
                await page.wait_for_timeout(2500)
                print(f"  ↪️  Clicked '{sel}' to reach the post editor.")
                return True
        except Exception:
            continue
    return False


async def _find_submit_trigger(scope):
    """
    Find a Post/Publish/Save/Submit-style button. Checks real <button>/
    <input type=submit> elements first, then broader role="button" or
    id/class-based matches, since many modern editors (Blogger included)
    use non-<button> clickable elements for their main action.
    """
    triggers = [
        'button:has-text("Publish")', 'button:has-text("Post")',
        'button:has-text("Save")', 'button:has-text("Submit")',
        'button:has-text("Create")', 'input[type="submit"]',
        'button[type="submit"]',
        '[role="button"]:has-text("Publish")',
        '[role="button"]:has-text("Post")',
        '#publishButton', '[data-tooltip="Publish"]', '[aria-label="Publish"]',
        '[id*="publish" i]', '[class*="publish" i][role="button"]',
        'div:has-text("Publish"):not(:has(button)):not(:has(div))',
        'span:has-text("Publish"):not(:has(*))',
    ]
    for sel in triggers:
        try:
            els = scope.locator(sel)
            count = await els.count()
            for i in range(min(count, 5)):
                el = els.nth(i)
                box = await _get_visible_box(el)
                if box:
                    print(f"  🔘 Found submit trigger: '{sel}' (match #{i})")
                    return el
        except Exception:
            continue
    return None


async def start_generic_content_post_async(url: str, content: str, platform_name: str = None) -> dict:
    """
    For simple no-login-usually paste/blog sites (Rentry, Write.as, etc.)
    where the goal is to actually POST real generated content, not fill
    a multi-field directory form.
    """
    platform_name = platform_name or url.split("/")[2]
    session_id = str(uuid.uuid4())[:8]
    p = None
    context = None
    page = None

    try:
        p, context, page = await _get_browser_context_async(platform_name)
        print(f"\n🌐 Opening {url} for content posting...")
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(2000)
        await _handle_captcha(page)

        current_url = page.url.lower()
        if "login" in current_url or "signin" in current_url or "signup" in current_url:
            print("\n🔐 LOGIN REQUIRED - login manually, then press ENTER here.\n")
            input("👉 Press ENTER after you have COMPLETED login...\n")
            try:
                all_pages = context.pages
                if len(all_pages) > 1:
                    page = all_pages[-1]
            except Exception:
                pass
            await page.reload(wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)

        field = await _find_main_content_field(page)
        if not field:
            screenshot_path = SCREENSHOT_DIR / f"{session_id}_no_field.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)
            await context.close()
            await p.stop()
            return {"status": "failed", "detail": "No content field found on page.", "screenshot_path": str(screenshot_path)}

        await field.click()
        await field.fill(content)
        await page.wait_for_timeout(500)

        submit_el = await _find_submit_trigger(page)
        if submit_el:
            await submit_el.click(timeout=8000)
            await page.wait_for_timeout(3000)

        landed_url = page.url
        screenshot_path = SCREENSHOT_DIR / f"{session_id}_posted.png"
        try:
            await page.screenshot(path=str(screenshot_path), full_page=True)
        except Exception:
            pass

        await context.close()
        await p.stop()

        return {
            "status": "success" if submit_el else "awaiting_manual",
            "platform_name": platform_name, "posted_url": landed_url,
            "detail": f"✅ Posted on {platform_name}" if submit_el else "Content filled, no submit button found - finish manually.",
            "screenshot_path": str(screenshot_path),
        }

    except Exception as e:
        print(f"❌ Error posting content: {e}")
        try:
            if context:
                await context.close()
            if p:
                await p.stop()
        except Exception:
            pass
        return {"status": "failed", "detail": str(e)}


def start_generic_content_post(url: str, content: str, platform_name: str = None) -> dict:
    """Sync wrapper."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(start_generic_content_post_async(url, content, platform_name))


# ============================================
# UNIVERSAL URL WRITER - session-based, generic for ANY url
# Works for: no-login sites (auto, immediate), login-required sites
# (pause for login, then auto), and dashboard-style sites like Blogger
# where you need to click "New Post"/navigate yourself first (pause,
# then auto). All three end the same way: agent finds the field, writes
# on-topic content with an embedded Gaper link, publishes, and verifies.
# ============================================

def _looks_like_login_page(page_url: str) -> bool:
    patterns = ["login", "signin", "sign-in", "signup", "sign-up", "register", "/auth"]
    return any(p in page_url.lower() for p in patterns)


async def _write_and_publish_async(context, p, page, url: str, domain: str, topic: str, session_id: str) -> dict:
    """
    Final step, shared by all paths: finds the field on whatever the
    CURRENT page/state is, generates on-topic content with an embedded
    Gaper backlink, types it, publishes, and verifies the result
    actually landed somewhere real (not a login page).
    """
    from src.url_router import _generate_post_content
    from src.gaper_scraper import get_brand_profile

    # If nothing obvious is visible yet, give a dashboard-style site one
    # chance to open its editor via a "New Post"-style trigger before
    # searching for the field.
    field, field_scope = await _find_main_content_field_incl_frames(page)
    if not field:
        clicked = await _click_new_post_trigger_if_needed(page)
        if clicked:
            await page.wait_for_timeout(1500)
            field, field_scope = await _find_main_content_field_incl_frames(page)

    use_active_element = False
    if not field:
        # Fallback: the user may have manually clicked into the title/body
        # field themselves before hitting Continue (common on editors our
        # auto-detection doesn't recognize). If something editable is
        # currently focused anywhere on the page or in any iframe, just
        # type directly into it instead of giving up.
        for scope in [page] + list(page.frames):
            try:
                is_editable = await scope.evaluate("""
                    () => {
                        const el = document.activeElement;
                        if (!el) return false;
                        const tag = el.tagName.toLowerCase();
                        return tag === 'textarea' || tag === 'input' || el.isContentEditable === true;
                    }
                """)
                if is_editable:
                    field_scope = scope
                    use_active_element = True
                    print(f"  🎯 Using currently-focused element (user clicked into it manually).")
                    break
            except Exception:
                continue

    if not field and not use_active_element:
        screenshot_path = SCREENSHOT_DIR / f"{session_id}_no_field.png"
        try:
            await page.screenshot(path=str(screenshot_path), full_page=True)
        except Exception:
            pass
        _writer_sessions[session_id] = {
            "playwright": p, "context": context, "page": page,
            "url": url, "domain": domain, "topic": topic, "reason": "navigate",
        }
        return {
            "status": "waiting_for_user",
            "session_id": session_id,
            "domain": domain,
            "reason": "navigate",
            "detail": "Could not find a content field. Click into the title or body field yourself in the browser, then click Continue.",
            "screenshot_path": str(screenshot_path),
        }

    brand = get_brand_profile()
    content = _generate_post_content(topic or "AI agents and production workflows", brand.get("description", ""))

    typed_ok = False

    if use_active_element:
        print(f"  ✍️  Typing directly into the manually-focused field...")
        try:
            await page.keyboard.type(content, delay=5)
            typed_ok = True
            print(f"  ✅ keyboard.type() into focused element succeeded")
        except Exception as err_active:
            print(f"  ❌ keyboard.type() into focused element failed: {err_active}")
    else:
        print(f"  ✍️  Scrolling field into view...")
        try:
            await field.scroll_into_view_if_needed(timeout=5000)
        except Exception as err_scroll:
            print(f"  ⚠️ scroll_into_view failed: {err_scroll}")

        print(f"  ✍️  Attempting to click editor field...")
        try:
            await field.click(timeout=5000)
        except Exception as err_click:
            print(f"  ⚠️ Click on field failed: {err_click}")

        print(f"  ✍️  Attempting field.fill()...")
        try:
            await field.fill(content, timeout=6000)
            typed_ok = True
            print(f"  ✅ field.fill() succeeded")
        except Exception as err_fill:
            print(f"  ⚠️ field.fill() failed ({err_fill}), trying keyboard.type()...")

        if not typed_ok:
            try:
                await field.click(timeout=5000)
                await page.keyboard.type(content, delay=5)
                typed_ok = True
                print(f"  ✅ keyboard.type() succeeded")
            except Exception as err_type:
                print(f"  ❌ keyboard.type() also failed: {err_type}")
                screenshot_path = SCREENSHOT_DIR / f"{session_id}_type_failed.png"
                try:
                    await page.screenshot(path=str(screenshot_path), full_page=True)
                except Exception:
                    pass
                await context.close()
                await p.stop()
                return {"status": "failed", "detail": f"Could not type into editor field: {err_type}", "screenshot_path": str(screenshot_path)}

    await page.wait_for_timeout(800)

    # Verify something is ACTUALLY visible in the field now, not just
    # that fill()/type() didn't throw - a silent no-op is exactly what
    # produced "typed successfully" with a blank screen before.
    try:
        current_text = await field.inner_text() if await field.evaluate("el => el.tagName") != "TEXTAREA" else await field.input_value()
    except Exception:
        current_text = None
    if not current_text or len(current_text.strip()) < 10:
        print(f"  ⚠️ Field appears empty after typing (got: {current_text!r}) - typing likely landed on the wrong element.")
        screenshot_path = SCREENSHOT_DIR / f"{session_id}_empty_after_type.png"
        try:
            await page.screenshot(path=str(screenshot_path), full_page=True)
        except Exception:
            pass
        _writer_sessions[session_id] = {
            "playwright": p, "context": context, "page": page,
            "url": url, "domain": domain, "topic": topic, "reason": "navigate",
        }
        return {
            "status": "waiting_for_user",
            "session_id": session_id,
            "domain": domain,
            "reason": "navigate",
            "detail": "Typing did not land in the visible editor (field still looks empty). Click directly into the post body yourself in the browser, then click Continue and it will retry.",
            "screenshot_path": str(screenshot_path),
        }

    submit_el = await _find_submit_trigger(field_scope)
    if not submit_el and field_scope != page:
        submit_el = await _find_submit_trigger(page)

    if not submit_el:
        screenshot_path = SCREENSHOT_DIR / f"{session_id}_no_submit.png"
        try:
            await page.screenshot(path=str(screenshot_path), full_page=True)
        except Exception:
            pass
        return {
            "status": "awaiting_manual",
            "session_id": session_id,
            "detail": "Content written but no Publish/Post/Submit button was found automatically. Publish manually in the open browser.",
            "screenshot_path": str(screenshot_path),
        }

    try:
        await submit_el.scroll_into_view_if_needed(timeout=5000)
    except Exception:
        pass

    try:
        await submit_el.click(timeout=8000)
    except Exception as e:
        return {"status": "failed", "detail": f"Found a Publish button but clicking it failed: {e}"}

    await page.wait_for_timeout(2500)
    landed_url = page.url

    if _looks_like_login_page(landed_url):
        screenshot_path = SCREENSHOT_DIR / f"{session_id}_login_redirect.png"
        try:
            await page.screenshot(path=str(screenshot_path), full_page=True)
        except Exception:
            pass
        await context.close()
        await p.stop()
        return {
            "status": "failed",
            "detail": f"'{domain}' redirected to a login/signup page after publish - nothing was actually published ({landed_url}).",
            "screenshot_path": str(screenshot_path),
        }

    from src.database import SessionLocal, PostedBacklink
    db = SessionLocal()
    try:
        db.add(PostedBacklink(
            platform=domain, target_url=landed_url,
            content=content, status="live",
            note="Published via Universal URL Writer.",
        ))
        db.commit()
    finally:
        db.close()

    screenshot_path = SCREENSHOT_DIR / f"{session_id}_published.png"
    try:
        await page.screenshot(path=str(screenshot_path), full_page=True)
    except Exception:
        pass

    await context.close()
    await p.stop()

    return {
        "status": "success",
        "detail": f"Published new article on {domain}",
        "posted_url": landed_url,
        "screenshot_path": str(screenshot_path),
    }


async def start_universal_writer_async(url: str, topic: str = None) -> dict:
    """
    Step 1 for ANY url. See module docstring above for the full flow.
    """
    domain = urllib.parse.urlparse(url).netloc.lower()
    session_id = str(uuid.uuid4())[:8]

    p = None
    context = None
    page = None
    try:
        p, context, page = await _get_browser_context_async(domain)
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(2000)
        await _handle_captcha(page)

        has_login_input = False
        try:
            pw_fields = page.locator('input[type="password"]')
            pw_count = await pw_fields.count()
            for i in range(min(pw_count, 5)):
                box = await _get_visible_box(pw_fields.nth(i))
                if box:
                    has_login_input = True
                    break
        except Exception:
            pass
        needs_login = has_login_input or _looks_like_login_page(page.url)

        if needs_login:
            screenshot_path = SCREENSHOT_DIR / f"{session_id}_login_needed.png"
            try:
                await page.screenshot(path=str(screenshot_path), full_page=True)
            except Exception:
                pass
            _writer_sessions[session_id] = {
                "playwright": p, "context": context, "page": page,
                "url": url, "domain": domain, "topic": topic, "reason": "login",
            }
            return {
                "status": "waiting_for_user",
                "session_id": session_id,
                "domain": domain,
                "reason": "login",
                "detail": f"Log in or sign up to {domain} in the browser window that opened (session will be saved), then click Continue.",
                "screenshot_path": str(screenshot_path),
            }

        result = await _write_and_publish_async(context, p, page, url, domain, topic, session_id)
        return result

    except Exception as e:
        logger.error(f"[UniversalWriter] start failed: {e}")
        try:
            if context:
                await context.close()
            if p:
                await p.stop()
        except Exception:
            pass
        return {"status": "failed", "detail": str(e)}


async def continue_universal_writer_async(session_id: str) -> dict:
    """
    Step 2: called after the user has done whatever was needed manually
    (logged in, signed up, clicked 'New Post', navigated somewhere) and
    clicked Continue in the dashboard.
    """
    session = _writer_sessions.pop(session_id, None)
    if not session:
        return {"status": "failed", "detail": "Session not found or already used/expired."}

    p, context, page = session["playwright"], session["context"], session["page"]
    url, domain, topic, reason = session["url"], session["domain"], session["topic"], session.get("reason")

    try:
        try:
            all_pages = context.pages
            if len(all_pages) > 1:
                page = all_pages[-1]
        except Exception:
            pass

        if reason == "login":
            try:
                await page.reload(wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)
            except Exception:
                pass

            if _looks_like_login_page(page.url):
                screenshot_path = SCREENSHOT_DIR / f"{session_id}_still_login.png"
                try:
                    await page.screenshot(path=str(screenshot_path), full_page=True)
                except Exception:
                    pass
                _writer_sessions[session_id] = {
                    "playwright": p, "context": context, "page": page,
                    "url": url, "domain": domain, "topic": topic, "reason": "login",
                }
                return {
                    "status": "waiting_for_user",
                    "session_id": session_id,
                    "domain": domain,
                    "reason": "login",
                    "detail": f"Still looks like a login/signup page ({page.url}). Finish logging in, then click Continue again.",
                    "screenshot_path": str(screenshot_path),
                }

        return await _write_and_publish_async(context, p, page, url, domain, topic, session_id)

    except Exception as e:
        logger.error(f"[UniversalWriter] continue failed: {e}")
        try:
            await context.close()
            await p.stop()
        except Exception:
            pass
        return {"status": "failed", "detail": str(e)}


async def cancel_universal_writer_async(session_id: str) -> dict:
    session = _writer_sessions.pop(session_id, None)
    if session:
        try:
            await session["context"].close()
            await session["playwright"].stop()
        except Exception:
            pass
        return {"status": "cancelled"}
    return {"status": "not_found"}