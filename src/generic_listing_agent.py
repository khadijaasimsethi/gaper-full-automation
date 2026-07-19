import logging
import json
import uuid
import time
import traceback
from pathlib import Path
from playwright.sync_api import sync_playwright
import google.generativeai as genai
from src.gaper_scraper import get_brand_profile
import config

logger = logging.getLogger(__name__)
GEMINI_MODEL = "gemini-flash-latest"

SESSION_DIR = Path(config.BASE_DIR) / "sessions"
SESSION_DIR.mkdir(exist_ok=True)
SCREENSHOT_DIR = Path(config.BASE_DIR) / "output" / "listing_screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

_active_sessions = {}


def _build_brand_data() -> dict:
    brand = get_brand_profile()
    usps = brand.get("usps", "") or ""
    tagline = usps.split("\n")[0] if usps else "AI-native implementation partner for remote developer teams."
    description = brand.get("description", "") or (
        "Gaper is an AI-native implementation partner and hiring platform that matches "
        "companies with pre-vetted remote software developers within 24 hours. We deploy "
        "AI agents, copilots, and custom automation alongside top engineering talent."
    )
    return {
        "product_name": "Gaper",
        "product_url": "https://gaper.io",
        "tagline": tagline[:200],
        "description": description[:800],
        "short_description": "AI-powered hiring platform matching companies with vetted remote developers within 24 hours.",
        "category_tags": "AI agents, developer staffing, remote work, automation, SaaS, hiring platform",
        "contact_email": "pr@gaper.io",
        "website": "https://gaper.io",
        "company_name": "Gaper",
        "industry": "Software Development & AI",
        "founded": "2021",
        "team_size": "50-200",
        "pricing": "Flexible monthly contracts, no long-term lock-in",
        "location": "Remote / Global",
        "social_linkedin": "https://linkedin.com/company/gaper-io",
        "social_twitter": "https://twitter.com/gaper_io",
        "logo_url": brand.get("logo_url", "https://gaper.io/favicon.ico"),
    }


def _get_browser_context(platform_name: str):
    p = sync_playwright().start()
    profile_dir = SESSION_DIR / f"generic_{platform_name.replace('.', '_')}_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    # FIX: channel="chrome" (real installed Chrome) with fallback to bundled
    # Chromium, and removed the stealth flags (--disable-blink-features=
    # AutomationControlled, ignore_default_args=["--enable-automation"]) -
    # these were the likely cause of "Target page, context or browser has
    # been closed" errors happening 800ms-1500ms after every launch.
    try:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            channel="chrome",
            viewport={"width": 1166, "height": 738},
            args=["--no-first-run", "--no-default-browser-check"],
        )
    except Exception as e:
        logger.warning(f"channel='chrome' launch failed ({e}), falling back to bundled Chromium.")
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={"width": 1166, "height": 738},
            args=["--no-first-run", "--no-default-browser-check"],
        )
    page = context.new_page()
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    """)
    return p, context, page


def _debug_page(page, label=""):
    """Print exactly what's on the page right now."""
    try:
        url = page.url
        title = page.title()
        body_text = page.locator("body").inner_text()[:600]
        input_count = page.eval_on_selector_all(
            "input:not([type='hidden']), textarea, select",
            "(els) => els.length",
        )
        ce_count = page.eval_on_selector_all(
            "[contenteditable='true'], [role='textbox'], .ql-editor, .ProseMirror",
            "(els) => els.length",
        )
        print(f"\n  [DEBUG {label}]")
        print(f"    URL: {url}")
        print(f"    Title: {title}")
        print(f"    Inputs/textareas/selects: {input_count}")
        print(f"    Contenteditable editors: {ce_count}")
        print(f"    Body text preview: {body_text[:300]}")
    except Exception as e:
        print(f"  [DEBUG] Error reading page: {e}")


def _tag_and_extract_elements(page) -> list:
    """Detect ALL fillable elements."""

    standard_js = """
    (els) => els.map((el, idx) => {
        el.setAttribute('data-gaper-idx', idx);
        let labelText = '';
        if (el.labels && el.labels.length) {
            labelText = el.labels[0].innerText;
        } else if (el.id) {
            const lbl = document.querySelector('label[for="' + el.id + '"]');
            if (lbl) labelText = lbl.innerText;
        }
        if (!labelText) {
            let walk = el;
            for (let i = 0; i < 8 && walk.parentElement; i++) {
                walk = walk.parentElement;
                const lbl = walk.querySelector('label');
                if (lbl && !lbl.contains(el)) { labelText = lbl.innerText; break; }
                const h = walk.querySelector('h1,h2,h3,h4,h5,h6,span.form-label,div.form-label,p.form-label');
                if (h && !h.contains(el) && h.innerText && h.innerText.length < 100 && h.innerText.length > 1) {
                    labelText = h.innerText; break;
                }
            }
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
            label_text: labelText.trim().slice(0, 120),
            button_text: el.tagName.toLowerCase() === 'button' ? (el.innerText || '').slice(0, 80) : null,
            visible: rect.width > 0 && rect.height > 0
        };
    })
    """
    standard = page.eval_on_selector_all(
        "input:not([type='hidden']):not([type='submit']):not([type='file']), textarea, select, button",
        standard_js,
    )
    standard = [e for e in standard if e.get("visible")]

    max_idx = max((e["gaper_idx"] for e in standard), default=-1)
    ce_js = """
    (els, startIdx) => els.map((el, i) => {
        const idx = startIdx + i;
        el.setAttribute('data-gaper-idx', idx);
        let labelText = '';
        let walk = el;
        for (let j = 0; j < 8 && walk.parentElement; j++) {
            walk = walk.parentElement;
            const lbl = walk.querySelector('label');
            if (lbl && !lbl.contains(el)) { labelText = lbl.innerText; break; }
            const h = walk.querySelector('h1,h2,h3,h4,h5,h6,span,div,p');
            if (h && !h.contains(el) && h.innerText && h.innerText.length < 100 && h.innerText.length > 1) {
                labelText = h.innerText; break;
            }
        }
        const rect = el.getBoundingClientRect();
        return {
            gaper_idx: idx,
            tag: 'contenteditable',
            type: 'contenteditable',
            name: null,
            id: el.id || null,
            placeholder: el.getAttribute('data-placeholder') || el.getAttribute('aria-placeholder') || null,
            aria_label: el.getAttribute('aria-label'),
            label_text: labelText.trim().slice(0, 120),
            button_text: null,
            visible: rect.width > 10 && rect.height > 10
        };
    })
    """
    contenteditable = page.eval_on_selector_all(
        "[contenteditable='true'], [role='textbox'], .ql-editor, .trix-content, .ProseMirror, .tiptap",
        ce_js,
        max_idx + 1,
    )
    contenteditable = [e for e in contenteditable if e.get("visible")]

    all_elements = standard + contenteditable

    print(f"\n  [DETECT] Found {len(standard)} standard + {len(contenteditable)} editors = {len(all_elements)} total")
    for e in all_elements:
        tag = e.get('tag', '?')
        lbl = e.get('label_text', '')[:50]
        ph = e.get('placeholder', '') or ''
        nm = e.get('name', '') or ''
        print(f"    idx={e['gaper_idx']:3d}  tag={tag:15s}  label={lbl:50s}  placeholder={ph[:30]:30s}  name={nm[:20]}")
    return all_elements


def _fill_element(page, idx: int, tag: str, value: str) -> bool:
    """Fill element. Tries multiple strategies with verification."""
    selector = f'[data-gaper-idx="{idx}"]'
    value_str = str(value)

    if tag == "contenteditable":
        try:
            el = page.locator(selector).first
            el.scroll_into_view_if_needed()
            page.wait_for_timeout(500)
            el.click()
            page.wait_for_timeout(300)
            page.keyboard.press("Control+a")
            page.wait_for_timeout(100)
            page.keyboard.press("Backspace")
            page.wait_for_timeout(100)
            el.type(value_str, delay=8)
            page.wait_for_timeout(300)
            el.evaluate("""(el) => {
                el.dispatchEvent(new Event('input', {bubbles:true}));
                el.dispatchEvent(new Event('change', {bubbles:true}));
            }""")
            text = el.inner_text()
            if len(text.strip()) > 5:
                print(f"    [FILL-CE] OK ({len(text)} chars)")
                return True
        except Exception as e:
            print(f"    [FILL-CE] type() failed: {e}")

        try:
            el = page.locator(selector).first
            el.evaluate("""(el, val) => {
                el.innerHTML = '<p>' + val.replace(/\\n/g, '</p><p>') + '</p>';
                el.dispatchEvent(new Event('input', {bubbles:true}));
                el.dispatchEvent(new Event('change', {bubbles:true}));
            }""", value_str)
            page.wait_for_timeout(300)
            text = page.locator(selector).first.inner_text()
            if len(text.strip()) > 5:
                print(f"    [FILL-CE] innerHTML OK ({len(text)} chars)")
                return True
        except Exception as e:
            print(f"    [FILL-CE] innerHTML failed: {e}")
        return False

    if tag == "select":
        try:
            page.locator(selector).first.select_option(label=value_str)
            print(f"    [FILL-SELECT] OK")
            return True
        except Exception as e:
            print(f"    [FILL-SELECT] failed: {e}")
        return False

    el = page.locator(selector).first
    try:
        el.scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        el.click()
        page.wait_for_timeout(200)
        el.fill(value_str)
        page.wait_for_timeout(300)
        try:
            actual = el.input_value()
            if actual.strip():
                print(f"    [FILL] Strategy 1 (fill) OK: '{actual[:60]}'")
                return True
        except Exception:
            pass
    except Exception as e:
        print(f"    [FILL] Strategy 1 (fill) error: {e}")

    try:
        el = page.locator(selector).first
        el.click()
        page.wait_for_timeout(100)
        page.keyboard.press("Control+a")
        page.wait_for_timeout(50)
        page.keyboard.press("Backspace")
        page.wait_for_timeout(50)
        page.keyboard.type(value_str, delay=5)
        page.wait_for_timeout(300)
        try:
            actual = el.input_value()
            if actual.strip():
                print(f"    [FILL] Strategy 2 (keyboard) OK: '{actual[:60]}'")
                return True
        except Exception:
            pass
    except Exception as e:
        print(f"    [FILL] Strategy 2 error: {e}")

    try:
        el = page.locator(selector).first
        el.evaluate("""(el, val) => {
            const proto = el.tagName === 'TEXTAREA'
                ? window.HTMLTextAreaElement.prototype
                : window.HTMLInputElement.prototype;
            const desc = Object.getOwnPropertyDescriptor(proto, 'value');
            if (desc && desc.set) {
                desc.set.call(el, val);
            } else {
                el.value = val;
            }
            el.dispatchEvent(new Event('input', {bubbles: true}));
            el.dispatchEvent(new Event('change', {bubbles: true}));
        }""", value_str)
        page.wait_for_timeout(300)
        try:
            actual = el.input_value()
            if actual.strip():
                print(f"    [FILL] Strategy 3 (native setter) OK: '{actual[:60]}'")
                return True
        except Exception:
            pass
    except Exception as e:
        print(f"    [FILL] Strategy 3 error: {e}")

    try:
        el = page.locator(selector).first
        el.evaluate("""(el, val) => {
            el.value = val;
            el.setAttribute('value', val);
            el.dispatchEvent(new Event('focus', {bubbles:true}));
            el.dispatchEvent(new Event('input', {bubbles:true}));
            el.dispatchEvent(new Event('change', {bubbles:true}));
            el.dispatchEvent(new Event('blur', {bubbles:true}));
        }""", value_str)
        page.wait_for_timeout(200)
        try:
            actual = el.input_value()
            if actual.strip():
                print(f"    [FILL] Strategy 4 (brute) OK: '{actual[:60]}'")
                return True
        except Exception:
            pass
    except Exception as e:
        print(f"    [FILL] Strategy 4 error: {e}")

    print(f"    [FILL] ALL strategies FAILED for idx={idx}")
    return False


def _ask_gemini_to_map_fields(elements: list, brand_data: dict) -> dict:
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)

    prompt = f"""You are an AI assistant that fills out product/startup directory submission forms.

BRAND DATA (use these exact keys as brand_data_key):
{json.dumps(brand_data, indent=2)}

FORM ELEMENTS DETECTED ON PAGE (each has a unique gaper_idx):
{json.dumps(elements, indent=2)}

Elements with tag "contenteditable" are rich text editors — use them for LONG description/bio fields.

YOUR TASK: Map EVERY brand_data field that has a matching form element.

MATCHING RULES:
- "product_name" -> name, product, startup, company, title
- "product_url" -> url, website, link, domain, homepage
- "tagline" -> tagline, short description, pitch, headline, subtitle
- "description" -> description, about, overview, details, bio, describe (use contenteditable editor if available!)
- "short_description" -> brief, summary, elevator pitch
- "category_tags" -> category, tags, industry, keywords, sector
- "contact_email" -> email, contact
- "website" -> website, homepage, url
- "company_name" -> company, organization, business
- "industry" -> industry, sector, field
- "founded" -> founded, year, started
- "team_size" -> team, employees, people, how many
- "pricing" -> pricing, plan, cost
- "location" -> location, country, region, based, city
- "social_linkedin" -> linkedin
- "social_twitter" -> twitter, x.com

SUBMIT BUTTON: find button with text like Submit, Save, List, Publish, Launch, Add, Next, Continue, Post, Send.
If no submit button found, set submit_button_idx to null.

SKIP these: file uploads, hidden fields, buttons that are not submit.

Return ONLY this JSON:
{{
  "field_mappings": [
    {{"gaper_idx": 3, "brand_data_key": "product_name"}},
    {{"gaper_idx": 5, "brand_data_key": "product_url"}}
  ],
  "submit_button_idx": 12,
  "checkboxes_to_check": [15, 16],
  "notes": "any warnings"
}}
"""

    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()
        if raw.startswith("```json"):
            raw = raw[7:]
        elif raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        result = json.loads(raw.strip())

        print(f"\n  [GEMINI] Mapping result:")
        for m in result.get("field_mappings", []):
            print(f"    idx={m.get('gaper_idx')} -> key={m.get('brand_data_key')}")
        if result.get("submit_button_idx") is not None:
            print(f"    submit_button_idx={result.get('submit_button_idx')}")
        if result.get("checkboxes_to_check"):
            print(f"    checkboxes={result.get('checkboxes_to_check')}")
        if result.get("notes"):
            print(f"    notes={result.get('notes')}")
        return result

    except Exception as e:
        print(f"\n  [GEMINI] ERROR: {e}")
        traceback.print_exc()
        return {"field_mappings": [], "submit_button_idx": None, "checkboxes_to_check": [], "notes": str(e)}


def _wait_for_page_stable(page, timeout=10000):
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except Exception:
        pass
    page.wait_for_timeout(800)


def start_generic_listing(url: str, platform_name: str = None) -> dict:
    """Opens browser, auto-fills ALL fields, keeps browser open for manual submit."""
    platform_name = platform_name or url.split("/")[2]
    session_id = str(uuid.uuid4())[:8]

    p, context, page = _get_browser_context(platform_name)

    try:
        print(f"\n{'='*60}")
        print(f"STARTING GENERIC LISTING: {platform_name}")
        print(f"URL: {url}")
        print(f"{'='*60}")

        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        _wait_for_page_stable(page)

        _debug_page(page, "after page load")

        current_url = page.url.lower()
        page_text = ""
        try:
            page_text = page.locator("body").inner_text()[:3000].lower()
        except Exception:
            pass

        is_login = any(w in current_url for w in [
            "login", "signin", "signup", "sign-in", "sign-up", "auth",
        ])
        is_verification = any(w in page_text for w in [
            "verify", "verification", "check your email", "confirm your email",
            "we sent", "click the link", "activation", "confirm your account",
            "email sent", "check your inbox", "enter the code", "enter code",
        ])

        if is_login or is_verification:
            print("\n" + "=" * 60)
            if is_verification:
                print("EMAIL VERIFICATION REQUIRED!")
                print("")
                print("DO NOT CLICK THE LINK IN YOUR EMAIL!")
                print("")
                print("1. Open your email (pr@gaper.io)")
                print("2. Find the verification email")
                print("3. RIGHT-CLICK the verification link")
                print("4. Click 'Copy Link Address'")
                print("5. PASTE it in THIS browser address bar")
                print("6. Press Enter")
            else:
                print("LOGIN REQUIRED!")
                print("Please login manually in this browser window.")
            print("")
            print("Waiting up to 3 minutes...")
            print("=" * 60 + "\n")
            try:
                initial_url = page.url
                page.wait_for_url(lambda u: u != initial_url, timeout=180000)
                print("\n>> Page changed after verification/login!")
                print(">> Waiting 8 seconds for page to fully load...")
                page.wait_for_timeout(8000)
                _wait_for_page_stable(page)
            except Exception:
                try:
                    context.close()
                    p.stop()
                except Exception:
                    pass
                return {"status": "failed", "detail": "Verification/login timed out after 3 minutes."}

        print("\n>> Waiting for form elements to appear...")
        _debug_page(page, "before form wait")

        found_form = False
        for wait_attempt in range(6):
            _wait_for_page_stable(page, timeout=8000)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1500)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(1500)

            input_count = page.eval_on_selector_all(
                "input:not([type='hidden']), textarea, select, [contenteditable='true'], [role='textbox'], .ql-editor, .ProseMirror",
                "(els) => els.length",
            )
            print(f"  Wait attempt {wait_attempt + 1}/6: found {input_count} fillable elements on page")

            if input_count > 0:
                found_form = True
                break
            print(f"  No form elements yet. Waiting 5s...")
            page.wait_for_timeout(5000)

        _debug_page(page, "after form wait")

        if not found_form:
            screenshot_path = SCREENSHOT_DIR / f"{session_id}_no_form.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
            _active_sessions[session_id] = {
                "playwright": p, "context": context, "page": page,
                "submit_button_idx": None, "platform_name": platform_name, "url": url,
            }
            print(f"\n>> NO FORM FOUND after 6 attempts (30+ seconds)")
            print(f">> Screenshot saved: {screenshot_path}")
            print(f">> Browser is open — navigate to the submission form, then fill manually.")
            return {
                "status": "awaiting_approval",
                "session_id": session_id,
                "platform_name": platform_name,
                "filled_fields": [],
                "notes": "No form found. Navigate to submission form in browser, fill manually.",
                "screenshot_path": str(screenshot_path),
            }

        print("\n>> Detecting form elements...")
        elements = _tag_and_extract_elements(page)

        if not elements:
            screenshot_path = SCREENSHOT_DIR / f"{session_id}_no_elements.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
            _active_sessions[session_id] = {
                "playwright": p, "context": context, "page": page,
                "submit_button_idx": None, "platform_name": platform_name, "url": url,
            }
            print(f"\n>> Detected 0 elements after _tag_and_extract_elements")
            print(f">> Screenshot saved: {screenshot_path}")
            print(f">> Browser is open — fill manually.")
            return {
                "status": "awaiting_approval",
                "session_id": session_id,
                "platform_name": platform_name,
                "filled_fields": [],
                "notes": "No elements detected. Fill manually in browser.",
                "screenshot_path": str(screenshot_path),
            }

        brand_data = _build_brand_data()
        print(f"\n>> Calling Gemini to map {len(elements)} elements to brand data...")
        mapping = _ask_gemini_to_map_fields(elements, brand_data)
        field_mappings = mapping.get("field_mappings", [])

        if not field_mappings:
            print(f"\n>> Gemini returned 0 field mappings!")
            print(f">> Gemini notes: {mapping.get('notes', 'none')}")
            screenshot_path = SCREENSHOT_DIR / f"{session_id}_no_mapping.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
            _active_sessions[session_id] = {
                "playwright": p, "context": context, "page": page,
                "submit_button_idx": None, "platform_name": platform_name, "url": url,
            }
            print(f">> Browser is open — fill manually.")
            return {
                "status": "awaiting_approval",
                "session_id": session_id,
                "platform_name": platform_name,
                "filled_fields": [],
                "notes": "Gemini returned no mappings. Fill manually in browser.",
                "screenshot_path": str(screenshot_path),
            }

        print(f"\n>> Gemini mapped {len(field_mappings)} fields. Starting fill...\n")

        filled = []
        failed = []
        for fm in field_mappings:
            idx = fm.get("gaper_idx")
            key = fm.get("brand_data_key")
            value = brand_data.get(key)
            if value is None:
                print(f"  SKIP '{key}': no brand data for this key")
                continue

            el_info = next((e for e in elements if e.get("gaper_idx") == idx), None)
            if not el_info:
                print(f"  SKIP '{key}': element idx={idx} not found in detected list")
                continue

            tag = el_info.get("tag", "input")
            print(f"  >> Filling '{key}' (idx={idx}, tag={tag})")
            print(f"     value: {str(value)[:80]}")

            if _fill_element(page, idx, tag, str(value)):
                filled.append(key)
                print(f"     >>> SUCCESS <<<\n")
            else:
                failed.append(key)
                print(f"     >>> FAILED <<<\n")

        checkboxes = mapping.get("checkboxes_to_check", [])
        for cb_idx in checkboxes:
            try:
                cb = page.locator(f'[data-gaper-idx="{cb_idx}"]')
                if not cb.is_checked():
                    cb.check()
                    print(f"  Checked checkbox idx={cb_idx}")
            except Exception as e:
                print(f"  Could not check checkbox idx={cb_idx}: {e}")

        _wait_for_page_stable(page, timeout=8000)
        screenshot_path = SCREENSHOT_DIR / f"{session_id}_filled.png"
        page.screenshot(path=str(screenshot_path), full_page=True)

        _active_sessions[session_id] = {
            "playwright": p, "context": context, "page": page,
            "submit_button_idx": mapping.get("submit_button_idx"),
            "platform_name": platform_name,
            "url": url,
        }

        print(f"\n{'='*60}")
        print(f"FILL SUMMARY — {platform_name}")
        print(f"{'='*60}")
        print(f"  Filled OK:  {len(filled)} — {', '.join(filled)}")
        if failed:
            print(f"  FAILED:     {len(failed)} — {', '.join(failed)}")
        print(f"  Checkboxes: {len(checkboxes)}")
        print(f"\n>> Browser is open. Review and click Submit.")
        print(f"{'='*60}\n")

        return {
            "status": "awaiting_approval",
            "session_id": session_id,
            "platform_name": platform_name,
            "filled_fields": filled,
            "failed_fields": failed,
            "notes": "Review form in browser. Click Submit when ready.",
            "screenshot_path": str(screenshot_path),
        }

    except Exception as e:
        logger.error(f"Failed: {e}")
        traceback.print_exc()
        try:
            screenshot_path = SCREENSHOT_DIR / f"{session_id}_error.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
            _active_sessions[session_id] = {
                "playwright": p, "context": context, "page": page,
                "submit_button_idx": None, "platform_name": platform_name, "url": url,
            }
            return {
                "status": "awaiting_approval",
                "session_id": session_id,
                "platform_name": platform_name,
                "filled_fields": [],
                "notes": f"Error: {e}. Browser kept open.",
                "screenshot_path": str(screenshot_path),
            }
        except Exception:
            try:
                context.close()
                p.stop()
            except Exception:
                pass
            return {"status": "failed", "detail": str(e)}


def confirm_generic_listing(session_id: str) -> dict:
    session = _active_sessions.get(session_id)
    if not session:
        return {"status": "failed", "detail": "Session not found"}
    page = session["page"]
    try:
        _wait_for_page_stable(page, timeout=10000)
        result = {
            "status": "success",
            "detail": f"Submitted on {session['platform_name']}",
            "posted_url": page.url,
        }
    except Exception as e:
        result = {"status": "failed", "detail": str(e)}
    finally:
        session["context"].close()
        session["playwright"].stop()
        del _active_sessions[session_id]
    return result


def cancel_generic_listing(session_id: str) -> dict:
    session = _active_sessions.pop(session_id, None)
    if session:
        session["context"].close()
        session["playwright"].stop()
        return {"status": "cancelled"}
    return {"status": "not_found"}