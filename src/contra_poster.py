# # src/contra_poster.py
# """
# Contra Poster - Uses the same working logic as root/post_to_contra.py
# """

# import logging
# from pathlib import Path
# from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
# import config

# logger = logging.getLogger(__name__)

# PROFILE_DIR = Path(config.BASE_DIR) / "sessions" / "contra_profile"
# FEED_URL = getattr(config, "CONTRA_FEED_URL", "https://contra.com/community/for-you")


# def _first_visible(page, selector: str, timeout_ms: int = 0):
#     """Return first visible element matching selector."""
#     loc = page.locator(selector)
#     if timeout_ms:
#         try:
#             loc.first.wait_for(state="attached", timeout=timeout_ms)
#         except PWTimeout:
#             return None
#     try:
#         count = loc.count()
#     except Exception:
#         return None
#     for i in range(count):
#         el = loc.nth(i)
#         try:
#             if el.is_visible():
#                 return el
#         except Exception:
#             continue
#     return None


# def _open_composer_if_collapsed(page):
#     """Contra sometimes renders composer collapsed."""
#     triggers = [
#         'button:has-text("Share progress")',
#         'button:has-text("Share an update")',
#         'button:has-text("Share something")',
#         'text=/share progress, updates/i',
#         'text=/what.?s on your mind/i',
#     ]
#     for sel in triggers:
#         el = _first_visible(page, sel)
#         if el:
#             try:
#                 el.click(timeout=2000)
#                 page.wait_for_timeout(700)
#                 return True
#             except Exception:
#                 pass
#     return False


# def _find_post_box(page):
#     """Try multiple selectors, return first visible editable element."""
#     selectors = [
#         'textarea[placeholder*="Share progress" i]',
#         'textarea[placeholder*="update" i]',
#         'textarea[placeholder*="highlight" i]',
#         'div[contenteditable="true"][role="textbox"]',
#         'div[contenteditable="true"]',
#         '[role="textbox"]',
#         'textarea',
#     ]
#     for sel in selectors:
#         el = _first_visible(page, sel)
#         if el:
#             return el
#     return None


# def _find_post_button(page):
#     for sel in [
#         'button:has-text("Post"):not([disabled])',
#         'button:has-text("Share"):not([disabled])',
#         'button:has-text("Publish"):not([disabled])',
#         'button:has-text("Post")',
#         'button:has-text("Share")',
#     ]:
#         el = _first_visible(page, sel)
#         if el:
#             return el
#     return None


# def post_to_contra_feed(content: str, target_url: str = None) -> dict:
#     """
#     Post to Contra feed using saved session.
#     SAME LOGIC as root/post_to_contra.py
#     """
#     if not PROFILE_DIR.exists():
#         return {
#             "status": "failed",
#             "detail": "No saved Contra session. Run 'python setup_contra_login.py' first."
#         }

#     url = target_url or FEED_URL

#     try:
#         with sync_playwright() as p:
#             context = p.chromium.launch_persistent_context(
#                 user_data_dir=str(PROFILE_DIR),
#                 headless=False,
#                 viewport={"width": 1366, "height": 768},
#                 args=["--disable-blink-features=AutomationControlled"],
#             )
#             page = context.pages[0] if context.pages else context.new_page()

#             page.goto(url, wait_until="domcontentloaded", timeout=45000)

#             if "/login" in page.url or "signin" in page.url:
#                 context.close()
#                 return {
#                     "status": "failed",
#                     "detail": "Session expired. Re-run setup_contra_login.py."
#                 }

#             try:
#                 page.wait_for_load_state("networkidle", timeout=15000)
#             except PWTimeout:
#                 pass
#             page.wait_for_timeout(1500)

#             # Find post box (same as root script)
#             post_box = None
#             for attempt in range(1, 5):
#                 post_box = _find_post_box(page)
#                 if post_box:
#                     break
#                 _open_composer_if_collapsed(page)
#                 page.mouse.wheel(0, 150)
#                 page.wait_for_timeout(1500)

#             if not post_box:
#                 context.close()
#                 return {"status": "failed", "detail": "Could not find post box."}

#             # Type content (same as root script)
#             post_box.scroll_into_view_if_needed()
#             post_box.click()
#             page.wait_for_timeout(400)
#             page.keyboard.type(content, delay=20)
#             page.wait_for_timeout(800)

#             # Find and click Post button (same as root script)
#             post_button = None
#             for _ in range(15):
#                 post_button = _find_post_button(page)
#                 if post_button and post_button.is_enabled():
#                     break
#                 page.wait_for_timeout(300)

#             if post_button:
#                 try:
#                     post_button.click()
#                 except Exception:
#                     post_box.press("Control+Enter")
#             else:
#                 post_box.press("Control+Enter")

#             page.wait_for_timeout(4000)
#             context.close()
            
#             return {"status": "success", "detail": f"Posted to Contra: {url}"}

#     except Exception as e:
#         logger.error(f"Contra posting failed: {e}")
#         return {"status": "failed", "detail": str(e)}



# src/contra_poster.py
"""
Contra Poster - Uses the same working logic as root/post_to_contra.py
Works for both feed and profile pages
"""

import logging
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
import config

logger = logging.getLogger(__name__)

PROFILE_DIR = Path(config.BASE_DIR) / "sessions" / "contra_profile"
FEED_URL = getattr(config, "CONTRA_FEED_URL", "https://contra.com/community/for-you")


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
            page.wait_for_timeout(400)
            page.keyboard.type(content, delay=20)
            page.wait_for_timeout(800)

            # Find and click Post button
            post_button = None
            for _ in range(15):
                post_button = _find_post_button(page)
                if post_button and post_button.is_enabled():
                    break
                page.wait_for_timeout(300)

            if post_button:
                try:
                    post_button.click()
                except Exception:
                    post_box.press("Control+Enter")
            else:
                post_box.press("Control+Enter")

            page.wait_for_timeout(4000)
            context.close()
            
            return {"status": "success", "detail": f"Posted to Contra: {url}"}

    except Exception as e:
        logger.error(f"Contra posting failed: {e}")
        return {"status": "failed", "detail": str(e)}