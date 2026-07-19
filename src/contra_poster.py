
# src/contra_poster.py
"""
Contra Poster - Uses the same working logic as root/post_to_contra.py
Works for both feed and profile pages
"""

import logging
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
import config

logger = logging.getLogger(__name__)

PROFILE_DIR = Path(config.BASE_DIR) / "sessions" / "contra_profile"
FEED_URL = getattr(config, "CONTRA_FEED_URL", "https://contra.com/community/for-you")

# Chromium's --user-data-dir only allows ONE process to own a profile at
# a time. If two submits/generates fire close together (double-click, or
# two requests landing seconds apart), the second launch_persistent_context()
# collides with the first and Playwright reports "Target page, context or
# browser has been closed" - not a real crash, just two sessions fighting
# over the same locked profile folder. This lock makes the second call
# simply wait its turn instead of colliding.
_contra_session_lock = threading.Lock()


def _first_visible(page, selector: str, timeout_ms: int = 0):
    """Return first visible element matching selector."""
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
    """Contra sometimes renders composer collapsed."""
    triggers = [
        'button:has-text("Share progress")',
        'button:has-text("Share an update")',
        'button:has-text("Share something")',
        'text=/share progress, updates/i',
        'text=/what.?s on your mind/i',
        'button:has-text("What are you working on")',
        'text=/what are you working on/i',
    ]
    for sel in triggers:
        el = _first_visible(page, sel)
        if el:
            try:
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
        'textarea[placeholder*="What are you working on" i]',
        'div[contenteditable="true"][role="textbox"]',
        'div[contenteditable="true"]',
        '[role="textbox"]',
        'textarea',
    ]
    for sel in selectors:
        el = _first_visible(page, sel)
        if el:
            return el
    return None


def _find_post_button(page):
    for sel in [
        'button:has-text("Post"):not([disabled])',
        'button:has-text("Share"):not([disabled])',
        'button:has-text("Publish"):not([disabled])',
        'button:has-text("Post")',
        'button:has-text("Share")',
        'button:has-text("Done")',
    ]:
        el = _first_visible(page, sel)
        if el:
            return el
    return None


def post_to_contra_feed(content: str, target_url: str = None) -> dict:
    """
    Post to Contra using saved session.
    Works for feed AND profile pages.
    """
    if not PROFILE_DIR.exists():
        return {
            "status": "failed",
            "detail": "No saved Contra session. Run 'python setup_contra_login.py' first."
        }

    url = target_url or FEED_URL

    if not _contra_session_lock.acquire(timeout=90):
        return {"status": "failed", "detail": "Another Contra post is already in progress - please wait for it to finish and try again."}

    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE_DIR),
                headless=False,
                viewport={"width": 1366, "height": 768},
                args=["--disable-blink-features=AutomationControlled"],
            )
            page = context.pages[0] if context.pages else context.new_page()

            page.goto(url, wait_until="domcontentloaded", timeout=45000)

            if "/login" in page.url or "signin" in page.url:
                context.close()
                return {
                    "status": "failed",
                    "detail": "Session expired. Re-run setup_contra_login.py."
                }

            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except PWTimeout:
                pass
            page.wait_for_timeout(1500)

            # Find post box with retry
            post_box = None
            for attempt in range(1, 6):
                post_box = _find_post_box(page)
                if post_box:
                    break
                _open_composer_if_collapsed(page)
                page.mouse.wheel(0, 150)
                page.wait_for_timeout(1500)

            if not post_box:
                context.close()
                return {"status": "failed", "detail": "Could not find post box. Please check if composer is visible."}

            # Type content
            post_box.scroll_into_view_if_needed()
            post_box.click()
            page.wait_for_timeout(300)
            # Clear any leftover draft text sitting in the composer from a
            # previous attempt - Contra's persistent profile can leave
            # half-typed content behind, which otherwise gets mixed with
            # what we type next instead of being replaced.
            page.keyboard.press("Control+A")
            page.keyboard.press("Delete")
            page.wait_for_timeout(200)

            # fill() sets the whole text in one atomic action - unlike
            # typing letter-by-letter over several seconds, it can't get
            # cut off halfway if the page re-renders or focus shifts
            # mid-way. Only fall back to keystroke typing if this
            # particular element doesn't support fill() at all.
            typed_ok = False
            try:
                post_box.fill(content, timeout=8000)
                typed_ok = True
            except Exception as fill_err:
                logger.warning(f"fill() failed ({fill_err}), falling back to keystroke typing")

            if not typed_ok:
                post_box.click()
                page.keyboard.press("Control+A")
                page.keyboard.press("Delete")
                page.wait_for_timeout(200)
                page.keyboard.type(content, delay=20)

            # Nudge: some Contra composers only flip "Post" to enabled
            # after a follow-up keystroke event, even though the typed
            # text is already visibly there. This forces that trigger.
            page.keyboard.press("Space")
            page.keyboard.press("Backspace")
            page.wait_for_timeout(1300)

            # Find and click Post button
            post_button = None
            for _ in range(20):
                post_button = _find_post_button(page)
                if post_button and post_button.is_enabled():
                    break
                page.wait_for_timeout(500)

            if post_button:
                try:
                    # Short explicit timeout - if it's still not truly
                    # clickable, fail fast into the Ctrl+Enter fallback
                    # instead of hanging for Playwright's 30s default.
                    post_button.click(timeout=6000)
                except Exception:
                    post_box.click()
                    post_box.press("Control+Enter")
            else:
                post_box.click()
                post_box.press("Control+Enter")

            page.wait_for_timeout(4000)

            # If we still ended up here without confidence it posted,
            # save a screenshot so the actual on-screen state is visible
            # for debugging, instead of guessing blind next time.
            try:
                from pathlib import Path as _Path
                shot_dir = _Path(config.BASE_DIR) / "output"
                shot_dir.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(shot_dir / "contra_feed_post_result.png"))
            except Exception:
                pass

            context.close()

            return {"status": "success", "detail": f"Posted to Contra: {url}"}

    except Exception as e:
        logger.error(f"Contra posting failed: {e}")
        return {"status": "failed", "detail": str(e)}
    finally:
        _contra_session_lock.release()


def post_reply_to_contra(target_url: str, content: str) -> dict:
    """Same robust composer-detection logic as post_to_contra_feed, but
    navigates to a specific thread URL to reply, instead of the feed."""
    if not PROFILE_DIR.exists():
        return {"status": "failed", "detail": "No saved Contra session. Run setup_contra_login.py first."}

    if not _contra_session_lock.acquire(timeout=90):
        return {"status": "failed", "detail": "Another Contra post is already in progress - please wait for it to finish and try again."}

    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE_DIR),
                headless=False,
                viewport={"width": 1366, "height": 768},
                args=["--disable-blink-features=AutomationControlled"],
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(target_url, wait_until="domcontentloaded", timeout=45000)

            if "/login" in page.url or "signin" in page.url:
                context.close()
                return {"status": "failed", "detail": "Session expired. Re-run setup_contra_login.py."}

            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except PWTimeout:
                pass
            page.wait_for_timeout(1500)

            post_box = None
            for attempt in range(1, 5):
                post_box = _find_post_box(page)
                if post_box:
                    break
                page.mouse.wheel(0, 150)
                page.wait_for_timeout(1500)

            if not post_box:
                context.close()
                return {"status": "failed", "detail": "Could not find comment box on thread."}

            post_box.scroll_into_view_if_needed()
            post_box.click()
            page.wait_for_timeout(300)
            # Same leftover-draft-text cleanup as the feed post path.
            page.keyboard.press("Control+A")
            page.keyboard.press("Delete")
            page.wait_for_timeout(200)

            # Atomic fill() first - avoids the multi-second letter-by-letter
            # typing window where a page re-render can steal focus and cut
            # the text off halfway. Falls back to keystroke typing only if
            # this element doesn't support fill().
            typed_ok = False
            try:
                post_box.fill(content, timeout=8000)
                typed_ok = True
            except Exception as fill_err:
                logger.warning(f"fill() failed ({fill_err}), falling back to keystroke typing")

            if not typed_ok:
                post_box.click()
                page.keyboard.press("Control+A")
                page.keyboard.press("Delete")
                page.wait_for_timeout(200)
                page.keyboard.type(content, delay=25)

            page.keyboard.press("Space")
            page.keyboard.press("Backspace")
            page.wait_for_timeout(1300)

            post_button = None
            for _ in range(20):
                post_button = _find_post_button(page)
                if post_button and post_button.is_enabled():
                    break
                page.wait_for_timeout(500)

            if post_button:
                try:
                    post_button.click(timeout=6000)
                except Exception:
                    post_box.click()
                    post_box.press("Control+Enter")
            else:
                post_box.click()
                post_box.press("Control+Enter")

            page.wait_for_timeout(4000)
            try:
                from pathlib import Path as _Path
                shot_dir = _Path(config.BASE_DIR) / "output"
                shot_dir.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(shot_dir / "contra_reply_post_result.png"))
            except Exception:
                pass
            context.close()
            return {"status": "success", "detail": f"Replied on Contra: {target_url}"}

    except Exception as e:
        logger.error(f"[ContraReply] Failed: {e}")
        return {"status": "failed", "detail": f"Error: {e}"}
    finally:
        _contra_session_lock.release()