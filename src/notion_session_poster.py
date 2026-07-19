
"""
Notion posting via saved BROWSER session.

Uses the persistent profile at:
sessions/notion_profile/

Important:
- Run setup_notion_login.py once first.
- This script does NOT auto-publish.
- It creates/opens the Notion page, types the article, brings the window forward,
  and keeps the browser alive while your Python app is still running.
"""

import logging
import re
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

import config

logger = logging.getLogger(__name__)

PROFILE_DIR = Path(config.BASE_DIR) / "sessions" / "notion_profile"
NOTION_DATABASE_URL = getattr(config, "NOTION_DATABASE_URL", "")

_CHROME_FLAGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--start-maximized",
]

# Keep these global so the Playwright browser does not close immediately
# after post_to_notion_session() returns.
_PLAYWRIGHT = None
_NOTION_CONTEXT = None
_NOTION_PAGE = None


def _clean_title(raw_title: str) -> str:
    title = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", raw_title or "")
    title = re.sub(r"https?://\S+", "", title)
    title = title.replace("**", "").replace("*", "")
    title = title.strip(" -\n\t")

    if len(title) > 70:
        title = title[:67] + "..."

    return title or "Untitled Gaper Article"


def _body_text(page) -> str:
    try:
        return page.locator("body").inner_text(timeout=3000)
    except Exception:
        return ""


def _visible_contains(page, text: str) -> bool:
    text = (text or "").strip()
    if not text:
        return True

    fragment = text[-60:] if len(text) > 60 else text
    return fragment in _body_text(page)


def _get_browser_page():
    """
    Reuses the same persistent Notion browser if it is already open.
    This is important because returning from the function should not instantly
    close the browser before you can click Share/Publish.
    """
    global _PLAYWRIGHT, _NOTION_CONTEXT, _NOTION_PAGE

    if _NOTION_CONTEXT is not None:
        try:
            pages = _NOTION_CONTEXT.pages
            if pages:
                _NOTION_PAGE = pages[-1]
                return _NOTION_CONTEXT, _NOTION_PAGE
        except Exception:
            _NOTION_CONTEXT = None
            _NOTION_PAGE = None

    _PLAYWRIGHT = sync_playwright().start()

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    launch_kwargs = dict(
        user_data_dir=str(PROFILE_DIR),
        headless=False,
        viewport=None,
        args=_CHROME_FLAGS,
    )

    try:
        _NOTION_CONTEXT = _PLAYWRIGHT.chromium.launch_persistent_context(
            channel="chrome",
            **launch_kwargs,
        )
    except Exception as e:
        logger.warning(f"Could not launch Chrome channel, falling back to Chromium: {e}")
        _NOTION_CONTEXT = _PLAYWRIGHT.chromium.launch_persistent_context(
            **launch_kwargs,
        )

    _NOTION_PAGE = (
        _NOTION_CONTEXT.pages[0]
        if _NOTION_CONTEXT.pages
        else _NOTION_CONTEXT.new_page()
    )

    return _NOTION_CONTEXT, _NOTION_PAGE


def close_notion_browser():
    """
    Optional cleanup helper.
    Call this only if you intentionally want to close the automation browser.
    """
    global _PLAYWRIGHT, _NOTION_CONTEXT, _NOTION_PAGE

    try:
        if _NOTION_CONTEXT:
            _NOTION_CONTEXT.close()
    except Exception:
        pass

    try:
        if _PLAYWRIGHT:
            _PLAYWRIGHT.stop()
    except Exception:
        pass

    _PLAYWRIGHT = None
    _NOTION_CONTEXT = None
    _NOTION_PAGE = None


def _click_visible_from_locator(locator, reverse: bool = False) -> bool:
    try:
        count = locator.count()
    except Exception:
        return False

    indexes = range(count - 1, -1, -1) if reverse else range(count)

    for i in indexes:
        try:
            item = locator.nth(i)
            if item.is_visible():
                item.scroll_into_view_if_needed(timeout=2000)
                item.click(timeout=5000)
                return True
        except Exception:
            continue

    return False


def _click_new_button(page) -> bool:
    """
    Clicks Notion's New button. Uses several selectors because Notion changes
    this UI often.
    """
    logger.info("Finding Notion New button...")

    candidates = [
        page.get_by_role("button", name=re.compile(r"^New\b", re.I)),
        page.locator('button:has-text("New")'),
        page.locator('div[role="button"]:has-text("New")'),
        page.locator('[data-testid="new-page-button"]'),
    ]

    for locator in candidates:
        if _click_visible_from_locator(locator, reverse=True):
            logger.info("Clicked Notion New button.")
            return True

    logger.warning("Could not find visible New button. Trying Ctrl+N fallback.")
    try:
        page.keyboard.press("Control+N")
        return True
    except Exception:
        return False


def _open_as_full_page_if_possible(page) -> bool:
    """
    If Notion opens the new entry as a side peek / center peek, open it as a
    full page so the Share button is visible at the top-right.
    """
    selectors = [
        '[aria-label*="Open as full page" i]',
        '[aria-label*="Open as page" i]',
        '[aria-label*="Open in full page" i]',
        'button:has-text("Open as page")',
        'div[role="button"]:has-text("Open as page")',
    ]

    for selector in selectors:
        try:
            locator = page.locator(selector)
            if _click_visible_from_locator(locator, reverse=False):
                logger.info("Opened Notion entry as full page.")
                page.wait_for_timeout(2500)
                return True
        except Exception:
            continue

    return False


def _wait_for_editor(page) -> bool:
    try:
        page.wait_for_selector('div[contenteditable="true"]', state="visible", timeout=15000)
        return True
    except PWTimeout:
        return False


def _focus_title(page):
    """
    Finds the Notion page title field.
    """
    title_selectors = [
        'div[contenteditable="true"][data-placeholder="Untitled"]',
        'div[contenteditable="true"][aria-label*="Untitled" i]',
        '[contenteditable="true"][placeholder="Untitled"]',
    ]

    for selector in title_selectors:
        try:
            locator = page.locator(selector).first
            locator.wait_for(state="visible", timeout=2500)
            locator.click(timeout=3000)
            return locator
        except Exception:
            continue

    # Fallback: first visible contenteditable is usually the title on a new page.
    editables = page.locator('div[contenteditable="true"]')
    try:
        count = min(editables.count(), 20)
    except Exception:
        count = 0

    for i in range(count):
        try:
            item = editables.nth(i)
            if item.is_visible():
                item.click(timeout=3000)
                return item
        except Exception:
            continue

    return None


def _insert_text(page, text: str):
    """
    More reliable than keyboard.type for long text. It inserts text through the
    browser input system, avoiding half-typed lines.
    """
    if not text:
        return

    for i in range(0, len(text), 120):
        chunk = text[i:i + 120]
        try:
            page.keyboard.insert_text(chunk)
        except Exception:
            page.keyboard.type(chunk, delay=25)
        page.wait_for_timeout(50)


def _type_plain_line(page, line: str) -> bool:
    line = line.rstrip()
    if not line:
        return True

    _insert_text(page, line)
    page.wait_for_timeout(300)

    ok = _visible_contains(page, line)
    if not ok:
        logger.warning(f"Line could not be visually verified: {line[:80]}")

    return ok


def _type_markdown_line(page, line: str) -> bool:
    """
    Notion markdown shortcuts require actual key events for the marker + space.
    After Notion converts the block, the rest of the text is inserted reliably.
    """
    stripped = line.strip()

    heading_match = re.match(r"^(#{1,3})\s+(.+)$", stripped)
    if heading_match:
        marker = heading_match.group(1)
        rest = heading_match.group(2).replace("**", "")

        page.keyboard.type(marker, delay=20)
        page.wait_for_timeout(150)
        page.keyboard.type(" ", delay=20)
        page.wait_for_timeout(350)

        return _type_plain_line(page, rest)

    bullet_match = re.match(r"^[-*]\s+(.+)$", stripped)
    if bullet_match:
        rest = bullet_match.group(1).replace("**", "")

        page.keyboard.type("*", delay=20)
        page.wait_for_timeout(150)
        page.keyboard.type(" ", delay=20)
        page.wait_for_timeout(350)

        return _type_plain_line(page, rest)

    # Avoid raw **bold** showing in Notion if Gemini outputs it.
    stripped = stripped.replace("**", "")
    return _type_plain_line(page, stripped)


def _find_link_popup_input(page):
    selectors = [
        'input[placeholder*="Paste link" i]',
        'input[placeholder*="Search or paste" i]',
        'input[placeholder*="Link" i]',
        '[data-testid="link-input"]',
        'div[role="dialog"] input[type="text"]',
        'div[role="dialog"] input',
    ]

    for selector in selectors:
        try:
            locator = page.locator(selector).first
            locator.wait_for(state="visible", timeout=3000)
            return locator
        except Exception:
            continue

    return None


def _make_link_clickable(page, anchor_text: str, url: str) -> bool:
    """
    Types anchor text, selects it, opens Notion's link popup, waits for the real
    popup input, then applies the URL.
    """
    anchor_text = anchor_text.strip() or url
    url = url.strip()

    _insert_text(page, anchor_text)
    page.wait_for_timeout(400)

    # Select just the anchor text typed on this line.
    page.keyboard.press("Shift+Home")
    page.wait_for_timeout(250)

    page.keyboard.press("Control+K")
    page.wait_for_timeout(500)

    popup_input = _find_link_popup_input(page)

    if not popup_input:
        logger.warning("Notion link popup did not appear. Falling back to plain URL text.")
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
        page.keyboard.press("End")
        _insert_text(page, f" ({url})")
        return False

    try:
        popup_input.click(timeout=3000)
        popup_input.fill(url)
        page.wait_for_timeout(300)
        page.keyboard.press("Enter")
        page.wait_for_timeout(800)
        page.keyboard.press("End")

        logger.info("Backlink URL applied through Notion link popup.")
        return True
    except Exception as e:
        logger.warning(f"Could not apply Notion link: {e}")
        try:
            page.keyboard.press("Escape")
            page.keyboard.press("End")
            _insert_text(page, f" ({url})")
        except Exception:
            pass
        return False


def _share_button_visible(page) -> bool:
    selectors = [
        'button:has-text("Share")',
        'div[role="button"]:has-text("Share")',
        '[aria-label*="Share" i]',
        'button:has-text("Publish")',
        'div[role="button"]:has-text("Publish")',
    ]

    for selector in selectors:
        try:
            locator = page.locator(selector)
            count = min(locator.count(), 10)
            for i in range(count):
                if locator.nth(i).is_visible():
                    return True
        except Exception:
            continue

    return False


def post_to_notion_session(title: str, body: str) -> dict:
    """
    Creates a Notion page from the saved browser session.

    Important behavior:
    - Does not publish automatically.
    - Keeps browser open while your Python app process is alive.
    - Does not drop the first body line.
    """
    if not NOTION_DATABASE_URL:
        return {
            "status": "failed",
            "detail": "NOTION_DATABASE_URL not set. Add it to config.py or .env.",
        }

    if not PROFILE_DIR.exists():
        return {
            "status": "failed",
            "detail": "Notion session not found. Run 'python setup_notion_login.py' first.",
        }

    clean_title = _clean_title(title)

    # CRITICAL FIX:
    # Your Article Studio already passes body WITHOUT the title.
    # Old code used lines[1:], which deleted the first paragraph.
    body_content = (body or "").strip()

    try:
        context, page = _get_browser_page()

        page.bring_to_front()
        page.wait_for_timeout(500)

        logger.info(f"Opening Notion database: {NOTION_DATABASE_URL}")
        page.goto(NOTION_DATABASE_URL, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(5000)

        if "login" in page.url.lower():
            return {
                "status": "failed",
                "detail": "Notion session expired. Run 'python setup_notion_login.py' again.",
            }

        old_url = page.url

        if not _click_new_button(page):
            return {
                "status": "failed",
                "detail": "Could not find or click Notion New button.",
            }

        try:
            page.wait_for_url(lambda url: url != old_url, timeout=12000)
        except Exception:
            pass

        page.wait_for_timeout(4000)

        # If Notion opened a side/center peek, convert it to a real full page.
        _open_as_full_page_if_possible(page)
        page.wait_for_timeout(2000)

        if not _wait_for_editor(page):
            return {
                "status": "failed",
                "detail": "Notion editor did not load. Check whether the database URL is correct.",
            }

        logger.info(f"Typing title: {clean_title}")
        title_locator = _focus_title(page)

        if not title_locator:
            return {
                "status": "failed",
                "detail": "Could not focus the Notion title field.",
            }

        try:
            title_locator.fill("")
            title_locator.fill(clean_title)
        except Exception:
            page.keyboard.press("Control+A")
            _insert_text(page, clean_title)

        page.wait_for_timeout(500)

        title_ok = _visible_contains(page, clean_title)
        if not title_ok:
            logger.warning("Title could not be visually verified.")

        page.keyboard.press("Enter")
        page.wait_for_timeout(900)

        logger.info("Typing Notion article body...")

        link_confirmed = True
        all_lines_ok = True

        for raw_line in body_content.splitlines():
            line = raw_line.strip()

            if not line:
                page.keyboard.press("Enter")
                page.wait_for_timeout(150)
                continue

            link_match = re.match(r"^\[\[LINK:(.*?)\|(.*?)\]\]$", line)

            if link_match:
                anchor_text = link_match.group(1).strip()
                link_url = link_match.group(2).strip()
                link_confirmed = _make_link_clickable(page, anchor_text, link_url)
            else:
                ok = _type_markdown_line(page, line)
                all_lines_ok = all_lines_ok and ok

            page.keyboard.press("Enter")
            page.wait_for_timeout(180)

            try:
                page.evaluate(
                    """() => {
                        const el = document.activeElement;
                        if (el && el.scrollIntoView) {
                            el.scrollIntoView({ block: "center", behavior: "instant" });
                        }
                    }"""
                )
            except Exception:
                pass

        page.wait_for_timeout(1500)

        # Make sure top bar is visible.
        try:
            _open_as_full_page_if_possible(page)
            page.evaluate("window.scrollTo(0, 0)")
            page.keyboard.press("Home")
            page.bring_to_front()
        except Exception:
            pass

        page.wait_for_timeout(1000)

        current_url = page.url
        share_visible = _share_button_visible(page)

        print("\n" + "=" * 70)
        print("Notion draft created in your REAL Notion workspace.")
        print("The automated browser window should now be in front.")
        print("Look at the TOP-RIGHT of that Playwright/Chrome window for Share.")
        print("Then click: Share -> Publish to web.")
        print("=" * 70 + "\n")

        detail = (
            f"Notion page '{clean_title}' created. "
            "Browser kept open for review and manual Publish."
        )

        if not share_visible:
            detail += " NOTE: Share button was not detected. If the page opened as a peek, click 'Open as page' in Notion."

        if not link_confirmed:
            detail += " NOTE: backlink popup was not confirmed, check the link manually."

        if not all_lines_ok:
            detail += " NOTE: one or more lines could not be visually verified."

        if not title_ok:
            detail += " NOTE: title could not be visually verified."

        return {
            "status": "success",
            "detail": detail,
            "url": current_url,
            "link_confirmed": link_confirmed,
            "share_visible": share_visible,
        }

    except Exception as e:
        logger.exception(f"Notion posting failed: {e}")
        return {"status": "failed", "detail": str(e)}
