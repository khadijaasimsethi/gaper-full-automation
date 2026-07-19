



"""
Run this from your project root:

    python post_to_contra.py
"""

import logging
from pathlib import Path

import google.generativeai as genai
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
import config


# ============================================
# CONFIG
# ============================================

PROFILE_DIR = Path(config.BASE_DIR) / "sessions" / "contra_profile"
FEED_URL = "https://contra.com/community/for-you"
GEMINI_MODEL = "gemini-flash-latest"

logger = logging.getLogger(__name__)

print("🚀 Script started!")
print(f"📂 Profile dir: {PROFILE_DIR}")
print(f"🌐 Feed URL: {FEED_URL}")
print(f"📁 Profile exists: {PROFILE_DIR.exists()}")


# ============================================
# GENERATE CONTENT
# ============================================

def generate_post_content() -> str:
    print("🤖 Generating content with Gemini...")
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)

    usps = config.BRAND_USPS if hasattr(config, "BRAND_USPS") else \
        "AI-native implementation partner for remote developer teams"
    if isinstance(usps, list):
        usps = "\n".join(f"- {u}" for u in usps)

    prompt = f"""
You are writing a short standalone community update post for Gaper (gaper.io),
to be posted in Contra's community feed under "Share progress, updates, or highlights".

Brand USPs:
{usps}
Link: {config.PRIMARY_URL}

Rules:
- 2 sentences only, like a real "progress update / highlight" post, NOT a sales pitch.
- Casual, first-person, builder-to-builder tone.
- No markdown formatting (no **, no #, no bullet lists) - plain text only.
- Include {config.PRIMARY_URL} naturally, once.
- Output ONLY the final post text, nothing else.
"""

    try:
        response = model.generate_content(prompt)
        content = (response.text or "").strip()
        if not content:
            content = (f"Working on Gaper ({config.PRIMARY_URL}) — an AI-native implementation "
                       f"partner helping teams deploy supervised AI workflows with vetted remote "
                       f"developers within 24 hours. Focused on production-ready automation.")
        print("✅ Content generated!")
        return content
    except Exception as e:
        logger.error(f"Gemini generation failed: {e}")
        return (f"Working on Gaper ({config.PRIMARY_URL}) — helping teams build supervised AI "
                f"workflows with vetted remote developers within 24 hours.")


# ============================================
# HELPERS
# ============================================

def _first_visible(page, selector: str, timeout_ms: int = 0):
    """
    Return the first *visible* element matching selector, or None.
    Iterates all matches instead of blindly taking .first (which is the #1
    reason the composer isn't found — the first match is often a hidden
    search/comment box).
    """
    loc = page.locator(selector)
    if timeout_ms:
        try:
            loc.first.wait_for(state="attached", timeout=timeout_ms)
        except PWTimeout:
            return None
    try:
        count = loc.count()
    except Exception:
        return None
    for i in range(count):
        el = loc.nth(i)
        try:
            if el.is_visible():
                return el
        except Exception:
            continue
    return None


def _open_composer_if_collapsed(page):
    """Contra sometimes renders composer collapsed as a 'Share…' trigger."""
    triggers = [
        'button:has-text("Share progress")',
        'button:has-text("Share an update")',
        'button:has-text("Share something")',
        'text=/share progress, updates/i',
        'text=/what.?s on your mind/i',
    ]
    for sel in triggers:
        el = _first_visible(page, sel)
        if el:
            try:
                print(f"👆 Clicking collapsed composer trigger: {sel}")
                el.click(timeout=2000)
                page.wait_for_timeout(700)
                return True
            except Exception:
                pass
    return False


def _find_post_box(page):
    """Try multiple selectors, return first visible editable element."""
    selectors = [
        'textarea[placeholder*="Share progress" i]',
        'textarea[placeholder*="update" i]',
        'textarea[placeholder*="highlight" i]',
        'div[contenteditable="true"][role="textbox"]',
        'div[contenteditable="true"]',
        '[role="textbox"]',
        'textarea',
    ]
    for sel in selectors:
        el = _first_visible(page, sel)
        if el:
            print(f"✅ Found post box with: {sel}")
            return el
    return None


def _find_post_button(page):
    for sel in [
        'button:has-text("Post"):not([disabled])',
        'button:has-text("Share"):not([disabled])',
        'button:has-text("Publish"):not([disabled])',
        'button:has-text("Post")',
        'button:has-text("Share")',
    ]:
        el = _first_visible(page, sel)
        if el:
            return el
    return None


# ============================================
# POST TO CONTRA
# ============================================

def post_to_contra(content: str) -> dict:
    print("📤 Starting post_to_contra...")

    if not PROFILE_DIR.exists():
        print("❌ Profile directory not found!")
        return {"status": "failed",
                "detail": "No saved Contra session. Run 'python setup_contra_login.py' first."}

    try:
        print("🔄 Launching Playwright...")
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE_DIR),
                headless=False,
                viewport={"width": 1366, "height": 768},
                args=["--disable-blink-features=AutomationControlled"],
            )
            page = context.pages[0] if context.pages else context.new_page()

            print(f"🌐 Opening Contra feed: {FEED_URL}")
            page.goto(FEED_URL, wait_until="domcontentloaded", timeout=45000)

            # Session check
            if "/login" in page.url or "signin" in page.url:
                context.close()
                return {"status": "failed",
                        "detail": "Session expired. Re-run setup_contra_login.py."}

            # Wait for React hydration properly (not a blind sleep)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except PWTimeout:
                pass
            page.wait_for_timeout(1500)

            # Save page for debugging
            try:
                with open("contra_page.html", "w", encoding="utf-8") as f:
                    f.write(page.content())
                print("✅ Page source saved to contra_page.html")
            except Exception:
                pass

            # Try to locate composer, retrying + expanding if needed
            print("🔍 Searching for post box...")
            post_box = None
            for attempt in range(1, 5):
                post_box = _find_post_box(page)
                if post_box:
                    break
                print(f"  Attempt {attempt}: not found, trying to expand composer…")
                _open_composer_if_collapsed(page)
                page.mouse.wheel(0, 150)
                page.wait_for_timeout(1500)

            if not post_box:
                try:
                    page.screenshot(path="contra_no_composer.png", full_page=True)
                    print("📸 Screenshot: contra_no_composer.png")
                except Exception:
                    pass
                context.close()
                return {"status": "failed", "detail": "Could not find post box."}

            # Type into it — use keyboard.type so contenteditable React
            # composers get real input events.
            print("📝 Typing content...")
            post_box.scroll_into_view_if_needed()
            post_box.click()
            page.wait_for_timeout(400)
            page.keyboard.type(content, delay=20)
            page.wait_for_timeout(800)

            # Find Post button, wait until enabled
            print("🔍 Finding Post button...")
            post_button = None
            for _ in range(15):
                post_button = _find_post_button(page)
                if post_button and post_button.is_enabled():
                    break
                page.wait_for_timeout(300)

            if post_button:
                try:
                    post_button.click()
                    print("✅ Post button clicked")
                except Exception as e:
                    print(f"⚠️ Click failed ({e}), using Ctrl+Enter…")
                    post_box.press("Control+Enter")
            else:
                print("⚠️ Post button not found, using Ctrl+Enter…")
                post_box.press("Control+Enter")

            page.wait_for_timeout(4000)
            context.close()
            return {"status": "success", "detail": "Posted to Contra feed."}

    except Exception as e:
        logger.error(f"Posting failed: {e}")
        return {"status": "failed", "detail": f"Error: {e}"}


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🚀 CONTRA STATUS POST")
    print("=" * 60)

    content = generate_post_content()
    print(f"\n📝 Generated content:\n{content}\n")

    result = post_to_contra(content)

    print(f"\n📋 Result: {result}")

    if result["status"] == "success":
        print("\n✅ Post successful! Check Contra: https://contra.com/community/for-you")
    else:
        print(f"\n❌ Failed: {result.get('detail')}")

    print("\n" + "=" * 60)
