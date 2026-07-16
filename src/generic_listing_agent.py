
# """
# GENERIC LISTING AGENT - Works on ANY platform
# No hardcode, no platform-specific code
# """

# import logging
# import json
# import uuid
# import time
# from pathlib import Path
# from playwright.sync_api import sync_playwright
# import google.generativeai as genai
# from src.gaper_scraper import get_brand_profile
# import config

# logger = logging.getLogger(__name__)
# GEMINI_MODEL = "gemini-flash-latest"

# SESSION_DIR = Path(config.BASE_DIR) / "sessions"
# SESSION_DIR.mkdir(exist_ok=True)
# SCREENSHOT_DIR = Path(config.BASE_DIR) / "output" / "listing_screenshots"
# SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

# _active_sessions = {}

# # ============================================
# # STEP 1: GAPER DATA
# # ============================================

# def _build_brand_data() -> dict:
#     brand = get_brand_profile()
#     usps = brand.get("usps", "") or ""
#     tagline = usps.split("\n")[0] if usps else "AI-native implementation partner for remote developer teams."
#     return {
#         "product_url": config.PRIMARY_URL,
#         "product_name": config.TARGET_BRAND,
#         "tagline": tagline[:80],
#         "description": brand.get("description", "") or "",
#         "category_tags": "AI agents, developer staffing, remote work, automation",
#         "contact_email": getattr(config, "CONTACT_EMAIL", "pr@gaper.io"),
#     }

# # ============================================
# # STEP 2: BROWSER CONTEXT (Stealth)
# # ============================================

# def _get_browser_context(platform_name: str):
#     p = sync_playwright().start()
#     profile_dir = SESSION_DIR / f"generic_{platform_name.replace('.', '_')}_profile"
#     profile_dir.mkdir(parents=True, exist_ok=True)
#     context = p.chromium.launch_persistent_context(
#         user_data_dir=str(profile_dir),
#         headless=False,
#         viewport={"width": 1920, "height": 1080},
#         args=['--start-maximized'],
#         user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
#     )
#     page = context.new_page()
#     page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
#     return p, context, page

# # ============================================
# # STEP 3: DETECT FORM ELEMENTS (Generic)
# # ============================================

# def _tag_and_extract_elements(page) -> list:
#     """Detect ALL form elements on ANY page - no hardcode!"""
#     elements = page.eval_on_selector_all(
#         "input:not([type='hidden']):not([type='submit']), textarea, select, button",
#         """
#         (els) => els.map((el, idx) => {
#             el.setAttribute('data-gaper-idx', idx);
#             let labelText = '';
#             if (el.labels && el.labels.length) {
#                 labelText = el.labels[0].innerText;
#             } else if (el.id) {
#                 const lbl = document.querySelector(`label[for="${el.id}"]`);
#                 if (lbl) labelText = lbl.innerText;
#             }
#             const rect = el.getBoundingClientRect();
#             return {
#                 gaper_idx: idx,
#                 tag: el.tagName.toLowerCase(),
#                 type: el.type || null,
#                 name: el.name || null,
#                 id: el.id || null,
#                 placeholder: el.placeholder || null,
#                 aria_label: el.getAttribute('aria-label'),
#                 label_text: labelText,
#                 button_text: (el.tagName.toLowerCase() === 'button') ? (el.innerText || '').slice(0, 60) : null,
#                 visible: rect.width > 0 && rect.height > 0
#             };
#         })
#         """
#     )
#     return [e for e in elements if e.get("visible")]

# # ============================================
# # STEP 4: GEMINI MAPPING (Generic)
# # ============================================

# def _ask_gemini_to_map_fields(elements: list, brand_data: dict) -> dict:
#     """Gemini maps fields - works for ANY platform!"""
#     genai.configure(api_key=config.GEMINI_API_KEY)
#     model = genai.GenerativeModel(GEMINI_MODEL)

#     prompt = f"""
# You are an AI assistant that fills out product/startup directory submission forms.

# BRAND DATA TO FILL:
# {json.dumps(brand_data, indent=2)}

# FORM ELEMENTS FOUND (each has a unique gaper_idx):
# {json.dumps(elements, indent=2)}

# YOUR TASK:
# 1. Match each brand_data field to the correct form element
# 2. Identify the submit button

# MAPPING RULES:
# - "product_name" → field asking for: name, product, startup, company, title
# - "product_url" → field asking for: url, website, link, domain
# - "tagline" → field asking for: tagline, short description, pitch, one-liner
# - "description" → field asking for: description, about, overview, details (usually textarea)
# - "category_tags" → field asking for: category, tags, industry, keywords
# - "contact_email" → field asking for: email, contact

# SUBMIT BUTTON: Look for button with text: Submit, Save, List, Publish, Launch, Add, Create, Next, Continue, Register, Sign Up

# Return ONLY JSON:
# {{
#   "field_mappings": [
#     {{"gaper_idx": 3, "brand_data_key": "product_name"}},
#     {{"gaper_idx": 5, "brand_data_key": "product_url"}}
#   ],
#   "submit_button_idx": 12,
#   "notes": "any warnings"
# }}

# If you cannot find a field, skip it. If you cannot find submit button, set to null.
# """

#     response = model.generate_content(prompt)
#     raw = response.text.strip()
#     if raw.startswith("```json"):
#         raw = raw[7:]
#     elif raw.startswith("```"):
#         raw = raw[3:]
#     if raw.endswith("```"):
#         raw = raw[:-3]
#     return json.loads(raw.strip())

# # ============================================
# # STEP 5: SMART WAIT FOR PAGE LOAD (Generic)
# # ============================================

# def _wait_for_form(page, timeout=30000):
#     """Wait for ANY form to load - no hardcode!"""
#     try:
#         page.wait_for_function(
#             """
#             () => {
#                 const inputs = document.querySelectorAll('input:not([type="hidden"]), textarea, select');
#                 return inputs.length > 0;
#             }
#             """,
#             timeout=timeout
#         )
#         return True
#     except Exception:
#         return False

# # ============================================
# # STEP 5b: VALIDATE THIS IS ACTUALLY A SUBMISSION PAGE (Generic)
# # ============================================

# def _looks_like_submission_page(page) -> bool:
#     """
#     Generic sanity check - NOT tied to any specific platform name.
#     Discovery (SERP) can occasionally return a blog article, a "best
#     tools" listicle, or an existing product's own listing page instead
#     of an actual submission form. Rather than hardcoding which domains
#     are "real" platforms, we just check the page itself:
#       - does it already have a form with a couple of real input fields?
#       - OR does the visible text contain submission-intent phrases
#         like "submit your product", "get listed", "add your startup"?
#     This works identically for a platform we've never seen before.
#     """
#     try:
#         input_count = page.locator(
#             "input:not([type='hidden']):not([type='submit']), textarea"
#         ).count()
#     except Exception:
#         input_count = 0

#     try:
#         page_text_sample = page.locator("body").inner_text()[:3000].lower()
#     except Exception:
#         page_text_sample = ""

#     submission_keywords = [
#         "submit your", "add your", "list your", "get listed",
#         "create listing", "new submission", "submit a listing",
#         "submit product", "add product", "add a product",
#         "list your startup", "submit startup",
#     ]
#     has_keyword = any(kw in page_text_sample for kw in submission_keywords)

#     return input_count >= 2 or has_keyword

# # ============================================
# # STEP 6: MAIN FUNCTION (Generic)
# # ============================================

# def start_generic_listing(url: str, platform_name: str = None) -> dict:
#     """Generic listing - works on ANY platform!"""
#     platform_name = platform_name or url.split("/")[2]
#     session_id = str(uuid.uuid4())[:8]

#     p, context, page = _get_browser_context(platform_name)

#     try:
#         print(f"\n🌐 Opening {url}...")
#         page.goto(url, wait_until="domcontentloaded", timeout=30000)

#         # ✅ Validate this is actually a submission-type page before wasting
#         # time/tokens filling it. Generic check - no platform names
#         # hardcoded here, just structural + keyword signals on whatever
#         # page we landed on.
#         page.wait_for_timeout(1500)
#         if not _looks_like_submission_page(page):
#             print(f"⚠️ {url} doesn't look like a submission page (no form, no submission keywords). Skipping.")
#             context.close()
#             p.stop()
#             return {
#                 "status": "not_a_form",
#                 "detail": "Page doesn't appear to be a product submission page. Skipped automatically.",
#                 "url": url,
#                 "platform_name": platform_name,
#             }

#         # 🔄 Handle login if needed
#         if "login" in page.url.lower() or "signin" in page.url.lower() or "signup" in page.url.lower():
#             print("\n🔐 Login/Signup page detected!")
#             print("👉 Please login/signup manually in the browser window.")
#             input("Press Enter AFTER you have logged in...\n")
#             page.goto(url, wait_until="domcontentloaded", timeout=30000)

#         # ⏳ Wait for form to load
#         print("⏳ Waiting for form to load...")
#         page.wait_for_timeout(3000)

#         # Scroll to load dynamic content
#         page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
#         page.wait_for_timeout(2000)
#         page.evaluate("window.scrollTo(0, 0)")
#         page.wait_for_timeout(2000)

#         # 🔍 Detect form elements
#         elements = _tag_and_extract_elements(page)
#         print(f"🔍 Found {len(elements)} form elements")

#         if not elements:
#             print("⚠️ No form elements found! Retrying...")
#             page.wait_for_timeout(5000)
#             elements = _tag_and_extract_elements(page)
#             print(f"🔍 Retry: Found {len(elements)} form elements")

#         if not elements:
#             print("❌ Still no form elements. Please fill manually.")
#             input("Press Enter after manual fill...")
#             screenshot_path = SCREENSHOT_DIR / f"{session_id}_manual.png"
#             page.screenshot(path=str(screenshot_path), full_page=True)
#             return {
#                 "status": "manual",
#                 "session_id": session_id,
#                 "screenshot_path": str(screenshot_path),
#                 "notes": "Manual fill required"
#             }

#         # 🤖 Gemini mapping
#         brand_data = _build_brand_data()
#         print("🤖 Asking Gemini to map fields...")

#         mapping = _ask_gemini_to_map_fields(elements, brand_data)
#         print(f"📋 Gemini mapping: {len(mapping.get('field_mappings', []))} fields mapped")

#         # 📝 Fill fields
#         filled = []
#         for fm in mapping.get("field_mappings", []):
#             idx = fm.get("gaper_idx")
#             key = fm.get("brand_data_key")
#             value = brand_data.get(key)
#             if value is None:
#                 continue
#             selector = f'[data-gaper-idx="{idx}"]'
#             try:
#                 el = page.locator(selector)
#                 tag = el.evaluate("el => el.tagName.toLowerCase()")
#                 if tag in ("input", "textarea"):
#                     el.fill(str(value))
#                     filled.append(key)
#                     print(f"  ✅ {key}: {str(value)[:30]}...")
#                 elif tag == "select":
#                     el.select_option(label=str(value))
#                     filled.append(key)
#                     print(f"  ✅ {key}: {str(value)[:30]}...")
#             except Exception as e:
#                 print(f"  ⚠️ Could not fill {key}: {e}")

#         # 📸 Screenshot
#         screenshot_path = SCREENSHOT_DIR / f"{session_id}_filled.png"
#         page.screenshot(path=str(screenshot_path), full_page=True)
#         print(f"\n📸 Screenshot: {screenshot_path}")

#         # 💾 Save session
#         _active_sessions[session_id] = {
#             "playwright": p,
#             "context": context,
#             "page": page,
#             "submit_button_idx": mapping.get("submit_button_idx"),
#             "platform_name": platform_name,
#             "url": url,
#         }

#         print(f"\n✅ Form filled! Session: {session_id}")
#         print(f"📝 Fields filled: {', '.join(filled) if filled else 'None'}")
#         print("👉 Approve via dashboard or confirm_generic_listing()")

#         return {
#             "status": "awaiting_approval",
#             "session_id": session_id,
#             "platform_name": platform_name,
#             "filled_fields": filled,
#             "notes": mapping.get("notes", ""),
#             "screenshot_path": str(screenshot_path),
#         }

#     except Exception as e:
#         logger.error(f"Failed: {e}")
#         context.close()
#         p.stop()
#         return {"status": "failed", "detail": str(e)}

# # ============================================
# # STEP 7: CONFIRM / CANCEL
# # ============================================

# def confirm_generic_listing(session_id: str) -> dict:
#     session = _active_sessions.get(session_id)
#     if not session:
#         return {"status": "failed", "detail": "Session not found"}

#     page = session["page"]
#     submit_idx = session["submit_button_idx"]

#     try:
#         if submit_idx is not None:
#             page.locator(f'[data-gaper-idx="{submit_idx}"]').click()
#             page.wait_for_timeout(4000)
#             result = {"status": "success", "detail": f"Submitted on {session['platform_name']}"}
#         else:
#             result = {"status": "failed", "detail": "No submit button found - submit manually"}
#     except Exception as e:
#         result = {"status": "failed", "detail": str(e)}
#     finally:
#         session["context"].close()
#         session["playwright"].stop()
#         del _active_sessions[session_id]

#     return result

# def cancel_generic_listing(session_id: str) -> dict:
#     session = _active_sessions.pop(session_id, None)
#     if session:
#         session["context"].close()
#         session["playwright"].stop()
#         return {"status": "cancelled"}
#     return {"status": "not_found"}



"""
GENERIC LISTING AGENT - Works on ANY platform
No hardcode, no platform-specific code
"""

import logging
import json
import uuid
import time
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

# ============================================
# STEP 1: GAPER DATA
# ============================================

def _build_brand_data() -> dict:
    brand = get_brand_profile()
    usps = brand.get("usps", "") or ""
    tagline = usps.split("\n")[0] if usps else "AI-native implementation partner for remote developer teams."
    return {
        "product_url": config.PRIMARY_URL,
        "product_name": config.TARGET_BRAND,
        "tagline": tagline[:80],
        "description": brand.get("description", "") or "",
        "category_tags": "AI agents, developer staffing, remote work, automation",
        "contact_email": getattr(config, "CONTACT_EMAIL", "pr@gaper.io"),
    }

# ============================================
# STEP 2: BROWSER CONTEXT (Stealth)
# ============================================

def _get_browser_context(platform_name: str):
    p = sync_playwright().start()
    profile_dir = SESSION_DIR / f"generic_{platform_name.replace('.', '_')}_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    context = p.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir),
        headless=False,
        viewport={"width": 1920, "height": 1080},
        args=['--start-maximized'],
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )
    page = context.new_page()
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
    return p, context, page

# ============================================
# STEP 3: DETECT FORM ELEMENTS (Generic)
# ============================================

def _tag_and_extract_elements(page) -> list:
    """Detect ALL form elements on ANY page - no hardcode!"""
    elements = page.eval_on_selector_all(
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
                label_text: labelText,
                button_text: (el.tagName.toLowerCase() === 'button') ? (el.innerText || '').slice(0, 60) : null,
                visible: rect.width > 0 && rect.height > 0
            };
        })
        """
    )
    return [e for e in elements if e.get("visible")]

# ============================================
# STEP 4: GEMINI MAPPING (Generic)
# ============================================

def _ask_gemini_to_map_fields(elements: list, brand_data: dict) -> dict:
    """Gemini maps fields - works for ANY platform!"""
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)

    prompt = f"""
You are an AI assistant that fills out product/startup directory submission forms.

BRAND DATA TO FILL:
{json.dumps(brand_data, indent=2)}

FORM ELEMENTS FOUND (each has a unique gaper_idx):
{json.dumps(elements, indent=2)}

YOUR TASK:
1. Match each brand_data field to the correct form element
2. Identify the submit button

MAPPING RULES:
- "product_name" -> field asking for: name, product, startup, company, title
- "product_url" -> field asking for: url, website, link, domain
- "tagline" -> field asking for: tagline, short description, pitch, one-liner
- "description" -> field asking for: description, about, overview, details (usually textarea)
- "category_tags" -> field asking for: category, tags, industry, keywords
- "contact_email" -> field asking for: email, contact

SUBMIT BUTTON: Look for button with text: Submit, Save, List, Publish, Launch, Add, Create, Next, Continue, Register, Sign Up

Return ONLY JSON:
{{
  "field_mappings": [
    {{"gaper_idx": 3, "brand_data_key": "product_name"}},
    {{"gaper_idx": 5, "brand_data_key": "product_url"}}
  ],
  "submit_button_idx": 12,
  "notes": "any warnings"
}}

If you cannot find a field, skip it. If you cannot find submit button, set to null.
"""

    response = model.generate_content(prompt)
    raw = response.text.strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    elif raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    return json.loads(raw.strip())

# ============================================
# STEP 5: SMART WAIT FOR PAGE LOAD (Generic)
# ============================================

def _wait_for_form(page, timeout=30000):
    """Wait for ANY form to load - no hardcode!"""
    try:
        page.wait_for_function(
            """
            () => {
                const inputs = document.querySelectorAll('input:not([type="hidden"]), textarea, select');
                return inputs.length > 0;
            }
            """,
            timeout=timeout
        )
        return True
    except Exception:
        return False

def _wait_for_page_stable(page, timeout=15000):
    """
    Waits for the page to stop moving/loading before we touch it. This is
    the main fix for the 'screenshot caught mid-scroll / mid-transition'
    problem - networkidle means no network requests for 500ms, i.e. any
    redirect, lazy-loaded content, or animation has settled.
    """
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except Exception:
        # Some sites never go fully idle (polling, analytics beacons) -
        # that's fine, we just fall through with a fixed pause instead.
        pass
    page.wait_for_timeout(1000)

# ============================================
# STEP 5b: VALIDATE THIS IS ACTUALLY A SUBMISSION PAGE (Generic)
# ============================================

def _looks_like_submission_page(page) -> bool:
    """
    Generic sanity check - NOT tied to any specific platform name.
    Discovery (SERP) can occasionally return a blog article, a "best
    tools" listicle, or an existing product's own listing page instead
    of an actual submission form. Rather than hardcoding which domains
    are "real" platforms, we just check the page itself:
      - does it already have a form with a couple of real input fields?
      - OR does the visible text contain submission-intent phrases
        like "submit your product", "get listed", "add your startup"?
    This works identically for a platform we've never seen before.
    """
    try:
        input_count = page.locator(
            "input:not([type='hidden']):not([type='submit']), textarea"
        ).count()
    except Exception:
        input_count = 0

    try:
        page_text_sample = page.locator("body").inner_text()[:3000].lower()
    except Exception:
        page_text_sample = ""

    submission_keywords = [
        "submit your", "add your", "list your", "get listed",
        "create listing", "new submission", "submit a listing",
        "submit product", "add product", "add a product",
        "list your startup", "submit startup",
    ]
    has_keyword = any(kw in page_text_sample for kw in submission_keywords)

    return input_count >= 2 or has_keyword

# ============================================
# STEP 6: MAIN FUNCTION (Generic)
# ============================================

def start_generic_listing(url: str, platform_name: str = None) -> dict:
    """Generic listing - works on ANY platform!"""
    platform_name = platform_name or url.split("/")[2]
    session_id = str(uuid.uuid4())[:8]

    p, context, page = _get_browser_context(platform_name)

    try:
        print(f"\n🌐 Opening {url}...")
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        _wait_for_page_stable(page)

        # Validate this is actually a submission-type page before wasting
        # time/tokens filling it. Generic check - no platform names
        # hardcoded here, just structural + keyword signals on whatever
        # page we landed on.
        if not _looks_like_submission_page(page):
            print(f"⚠️ {url} doesn't look like a submission page (no form, no submission keywords). Skipping.")
            context.close()
            p.stop()
            return {
                "status": "not_a_form",
                "detail": "Page doesn't appear to be a product submission page. Skipped automatically.",
                "url": url,
                "platform_name": platform_name,
            }

        # Handle login if needed
        if "login" in page.url.lower() or "signin" in page.url.lower() or "signup" in page.url.lower():
            print("\n🔐 Login/Signup page detected!")
            print("👉 Please login/signup manually in the browser window.")
            input("Press Enter AFTER you have logged in...\n")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            _wait_for_page_stable(page)

        # Wait for form to fully settle (fixes the "moving screen" screenshot bug)
        print("⏳ Waiting for form to load and settle...")
        _wait_for_form(page, timeout=15000)
        _wait_for_page_stable(page)

        # Scroll to trigger any lazy-loaded fields, then back to top and settle again
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1500)
        page.evaluate("window.scrollTo(0, 0)")
        _wait_for_page_stable(page, timeout=8000)

        # Detect form elements
        elements = _tag_and_extract_elements(page)
        print(f"🔍 Found {len(elements)} form elements")

        if not elements:
            print("⚠️ No form elements found! Retrying once...")
            page.wait_for_timeout(4000)
            elements = _tag_and_extract_elements(page)
            print(f"🔍 Retry: Found {len(elements)} form elements")

        if not elements:
            print("❌ No form elements found after retry. Not screenshotting a blank/unrelated page.")
            context.close()
            p.stop()
            return {
                "status": "failed",
                "detail": "No fillable form elements found on this page. May be a multi-step flow, JS-rendered form, or wrong URL.",
                "url": url,
                "platform_name": platform_name,
            }

        # Gemini mapping
        brand_data = _build_brand_data()
        print("🤖 Asking Gemini to map fields...")
        mapping = _ask_gemini_to_map_fields(elements, brand_data)
        print(f"📋 Gemini mapping: {len(mapping.get('field_mappings', []))} fields mapped")

        # Fill fields
        filled = []
        for fm in mapping.get("field_mappings", []):
            idx = fm.get("gaper_idx")
            key = fm.get("brand_data_key")
            value = brand_data.get(key)
            if value is None:
                continue
            selector = f'[data-gaper-idx="{idx}"]'
            try:
                el = page.locator(selector)
                tag = el.evaluate("el => el.tagName.toLowerCase()")
                if tag in ("input", "textarea"):
                    el.fill(str(value))
                    filled.append(key)
                    print(f"  ✅ {key}: {str(value)[:30]}...")
                elif tag == "select":
                    el.select_option(label=str(value))
                    filled.append(key)
                    print(f"  ✅ {key}: {str(value)[:30]}...")
            except Exception as e:
                print(f"  ⚠️ Could not fill {key}: {e}")

        # KEY FIX: refuse to report success / take a "final" screenshot if
        # literally nothing got filled. A blank or randomly-scrolled
        # screenshot with zero filled fields was the exact bug reported -
        # this makes that case an explicit failure instead of a silent one.
        if not filled:
            print("❌ Zero fields were successfully filled. Aborting - not a valid auto-fill result.")
            fail_screenshot = SCREENSHOT_DIR / f"{session_id}_FAILED_no_fields_filled.png"
            page.screenshot(path=str(fail_screenshot), full_page=True)
            context.close()
            p.stop()
            return {
                "status": "failed",
                "detail": "Form elements were detected but none could be filled - Gemini's field mapping likely didn't match this page's layout.",
                "debug_screenshot": str(fail_screenshot),
                "url": url,
                "platform_name": platform_name,
            }

        # Only now, after confirming real fields were filled, let the page
        # settle one more time and take the screenshot that goes to review.
        _wait_for_page_stable(page, timeout=8000)
        screenshot_path = SCREENSHOT_DIR / f"{session_id}_filled.png"
        page.screenshot(path=str(screenshot_path), full_page=True)
        print(f"\n📸 Screenshot: {screenshot_path}")

        # Save session
        _active_sessions[session_id] = {
            "playwright": p,
            "context": context,
            "page": page,
            "submit_button_idx": mapping.get("submit_button_idx"),
            "platform_name": platform_name,
            "url": url,
        }

        print(f"\n✅ Form filled! Session: {session_id}")
        print(f"📝 Fields filled: {', '.join(filled)}")
        print("👉 Approve via dashboard or confirm_generic_listing()")

        return {
            "status": "awaiting_approval",
            "session_id": session_id,
            "platform_name": platform_name,
            "filled_fields": filled,
            "notes": mapping.get("notes", ""),
            "screenshot_path": str(screenshot_path),
        }

    except Exception as e:
        logger.error(f"Failed: {e}")
        try:
            context.close()
            p.stop()
        except Exception:
            pass
        return {"status": "failed", "detail": str(e)}

# ============================================
# STEP 7: CONFIRM / CANCEL
# ============================================

def confirm_generic_listing(session_id: str) -> dict:
    session = _active_sessions.get(session_id)
    if not session:
        return {"status": "failed", "detail": "Session not found"}

    page = session["page"]
    submit_idx = session["submit_button_idx"]

    try:
        if submit_idx is not None:
            page.locator(f'[data-gaper-idx="{submit_idx}"]').click()
            page.wait_for_timeout(4000)
            result = {"status": "success", "detail": f"Submitted on {session['platform_name']}"}
        else:
            result = {"status": "failed", "detail": "No submit button found - submit manually"}
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