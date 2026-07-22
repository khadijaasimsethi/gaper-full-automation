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
                "key": config.CAPTCHA_API_KEY,
                "action": "get",
                "id": captcha_id,
                "json": 1
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

        # Check for Cloudflare challenge
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

        # Check for Turnstile
        try:
            turnstile = page.locator('.cf-turnstile').first
            if await turnstile.count() > 0:
                print("🛡️ Turnstile detected!")
                site_key = await turnstile.get_attribute("data-sitekey")
                if site_key and config.CAPTCHA_API_KEY:
                    import requests
                    data = {
                        "key": config.CAPTCHA_API_KEY,
                        "method": "turnstile",
                        "sitekey": site_key,
                        "pageurl": page_url,
                        "json": 1,
                    }
                    response = requests.post("https://2captcha.com/in.php", data=data, timeout=15)
                    result = response.json()
                    if result.get("status") == 1:
                        captcha_id = result.get("request")
                        for _ in range(24):
                            time.sleep(5)
                            resp = requests.get("https://2captcha.com/res.php", params={
                                "key": config.CAPTCHA_API_KEY,
                                "action": "get",
                                "id": captcha_id,
                                "json": 1
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

        # Check for reCAPTCHA
        try:
            recaptcha = page.locator('[data-sitekey]').first
            if await recaptcha.count() > 0:
                site_key = await recaptcha.get_attribute("data-sitekey")
                if site_key and config.CAPTCHA_API_KEY:
                    print(f"🔑 reCAPTCHA detected: {site_key[:20]}...")
                    import requests
                    data = {
                        "key": config.CAPTCHA_API_KEY,
                        "method": "userrecaptcha",
                        "googlekey": site_key,
                        "pageurl": page_url,
                        "json": 1,
                    }
                    response = requests.post("https://2captcha.com/in.php", data=data, timeout=15)
                    result = response.json()
                    if result.get("status") == 1:
                        captcha_id = result.get("request")
                        for _ in range(24):
                            time.sleep(5)
                            resp = requests.get("https://2captcha.com/res.php", params={
                                "key": config.CAPTCHA_API_KEY,
                                "action": "get",
                                "id": captcha_id,
                                "json": 1
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
    """Async browser context with proxy support"""
    p = await async_playwright().start()
    profile_dir = SESSION_DIR / f"generic_{platform_name.replace('.', '_')}_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    proxy = _get_proxy()
    if proxy:
        print(f"🌐 Using proxy: {proxy['server']}")

    context = await p.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir),
        headless=False,
        viewport={"width": 1366, "height": 768},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        proxy=proxy,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
        ],
        ignore_default_args=["--enable-automation"],
    )

    page = await context.new_page()

    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        delete navigator.__proto__.webdriver;
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });
        window.chrome = {
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {},
        };
    """)

    return p, context, page


def _build_brand_data() -> dict:
    """
    Everything a typical 'submit your product' directory form might ask
    for - not just name/URL. Add real values below (or wire more of them
    from BrandProfile / config.py) so the auto-fill has something real to
    put in fields like Twitter handle, pricing, founder name, etc.
    Fields left as placeholders here are safe to leave blank - Gemini
    just won't map anything to that brand_data key if the value looks
    like a placeholder, but better to fill in the real ones you have.
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
        "logo_file_path": _find_logo_file(),  # local file for upload fields, None if not set up yet
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
    'Submit your product/tool/startup' link or button. This finds and
    clicks that before scanning for form fields, instead of scanning
    whatever generic page we happened to land on.
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
    """Async listing - with MANUAL login confirmation"""
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

        # Handle CAPTCHA
        await _handle_captcha(page)

        # ============================================
        # ✅ FIXED LOGIN HANDLING
        # ============================================
        current_url = page.url.lower()
        if "login" in current_url or "signin" in current_url or "signup" in current_url:
            print("\n" + "="*50)
            print("🔐 LOGIN REQUIRED")
            print("="*50)
            print("1. Login manually in the browser window")
            print("2. If email verification, check your email")
            print("3. Complete login")
            print("4. COME BACK TO THIS TERMINAL and press ENTER")
            print("="*50)

            # ✅ WAIT FOR USER - NO AUTO TIMEOUT
            input("\n👉 Press ENTER after you have COMPLETED login...\n")

            print("✅ User confirmed login! Refreshing page...")

            # Some logins (e.g. "Sign in with Google") open a SEPARATE
            # popup/tab and finish there rather than on this original
            # tab - if the profile now has more open pages than we
            # started with, switch to whichever one is currently active
            # instead of blindly reloading a tab that might still be
            # stuck on the old login screen.
            try:
                all_pages = context.pages
                if len(all_pages) > 1:
                    page = all_pages[-1]
                    print(f"↪️  Detected {len(all_pages)} open tabs after login - continuing on the newest one.")
            except Exception:
                pass

            # ✅ Reload page to get fresh state
            try:
                await page.reload(wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)
            except Exception as e:
                print(f"⚠️ Reload failed: {e}")
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)

            print("✅ Page refreshed! Continuing...")

        await page.wait_for_timeout(3000)

        # Quick pre-check: does this page even look like a form yet?
        # If not, it's probably a homepage/listing page - try clicking a
        # "Submit"-style trigger to reach the real form before scanning.
        # This runs regardless of whether login happened above, so both
        # cases (login-required and no-login directories) are covered.
        try:
            quick_check = await page.locator("input:not([type='hidden']), textarea").count()
        except Exception:
            quick_check = 0
        if quick_check < 2:
            clicked = await _click_submit_trigger_if_needed(page)
            if clicked:
                await page.wait_for_timeout(2000)

        # Detect form elements
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
                "playwright": p,
                "context": context,
                "page": page,
                "submit_button_idx": None,
                "platform_name": platform_name,
                "url": url,
            }

            return {
                "status": "awaiting_approval",
                "session_id": session_id,
                "platform_name": platform_name,
                "filled_fields": [],
                "notes": "⚠️ No form found. Please fill and submit manually in browser.",
                "screenshot_path": str(screenshot_path) if screenshot_path else None,
            }

        # Gemini mapping
        brand_data = _build_brand_data()
        print("🤖 Gemini mapping fields...")
        mapping = _ask_gemini_to_map_fields(elements, brand_data)

        # ✅ SAFETY CHECK
        if not isinstance(mapping, dict):
            mapping = {"field_mappings": [], "submit_button_idx": None}

        print(f"📋 Gemini mapped {len(mapping.get('field_mappings', []))} fields")

        # Fill fields
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
                    # Logo/screenshot upload field - only works if you've
                    # dropped an image into the assets/ folder (see
                    # _find_logo_file). Skipped quietly if none is set up.
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

        # Click submit - only attempt this if something was actually
        # filled. An empty form's submit button is usually disabled by
        # the site's own validation, so clicking it just hangs for 30s
        # waiting for it to become clickable, when it never will.
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
                    "status": "success",
                    "session_id": session_id,
                    "platform_name": platform_name,
                    "filled_fields": filled,
                    "detail": f"✅ Submitted on {platform_name}",
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

        # Keep browser open for manual
        screenshot_path = SCREENSHOT_DIR / f"{session_id}_filled.png"
        try:
            await page.screenshot(path=str(screenshot_path), full_page=True)
        except Exception:
            pass

        _active_sessions[session_id] = {
            "playwright": p,
            "context": context,
            "page": page,
            "submit_button_idx": submit_idx,
            "platform_name": platform_name,
            "url": url,
        }

        return {
            "status": "awaiting_approval",
            "session_id": session_id,
            "platform_name": platform_name,
            "filled_fields": filled,
            "notes": "Fields filled. Click 'Confirm Submit' in dashboard or Submit manually.",
            "screenshot_path": str(screenshot_path) if screenshot_path else None,
        }

    except Exception as e:
        print(f"❌ Error: {e}")
        # ✅ KEEP BROWSER OPEN on error if possible
        if context and page:
            try:
                screenshot_path = SCREENSHOT_DIR / f"{session_id}_error.png"
                await page.screenshot(path=str(screenshot_path), full_page=True)

                _active_sessions[session_id] = {
                    "playwright": p,
                    "context": context,
                    "page": page,
                    "submit_button_idx": None,
                    "platform_name": platform_name,
                    "url": url,
                }

                return {
                    "status": "awaiting_approval",
                    "session_id": session_id,
                    "platform_name": platform_name,
                    "filled_fields": [],
                    "notes": f"⚠️ Error: {str(e)[:100]}. Browser open for manual.",
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
        # Check if page is still alive
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
                "status": "success",
                "detail": f"✅ Submitted on {session['platform_name']}",
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