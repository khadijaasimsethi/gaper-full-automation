
"""
Session manager - one persistent browser profile per domain + cookie backup.

Flow:
  1. get_context(domain) -> reuses sessions/<domain>_profile (cookies survive)
  2. ensure_logged_in(...) -> if the site shows a login wall, opens the browser
     visibly, waits for you to log in once, then saves cookies to
     sessions/cookies/<domain>.json
  3. Next runs load that profile/cookies and go straight to posting.
"""

import asyncio
import json
import os
import random
from pathlib import Path

from playwright.async_api import async_playwright

import config

IS_HEADLESS = os.environ.get("PLAYWRIGHT_HEADLESS", "false").lower() == "true"

SESSION_DIR = Path(config.BASE_DIR) / "sessions"
COOKIE_DIR = SESSION_DIR / "cookies"
SESSION_DIR.mkdir(parents=True, exist_ok=True)
COOKIE_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
window.chrome = { runtime: {}, loadTimes: function () {}, csi: function () {}, app: {} };
"""

LOGIN_URL_HINTS = ("login", "log-in", "signin", "sign-in", "sign_in", "signup", "sign-up", "/auth")
LOGIN_TEXT_HINTS = ("sign in", "log in", "login", "create an account", "sign up")


def domain_of(url: str) -> str:
    try:
        return url.split("/")[2]
    except Exception:  # noqa: BLE001
        return "unknown"


def _slug(domain: str) -> str:
    return domain.replace(".", "_").replace(":", "_")


def profile_dir(domain: str) -> Path:
    return SESSION_DIR / f"generic_{_slug(domain)}_profile"


def cookie_file(domain: str) -> Path:
    return COOKIE_DIR / f"{_slug(domain)}.json"


def has_saved_session(domain: str) -> bool:
    """True if we already have a profile or cookie jar for this domain."""
    return profile_dir(domain).exists() or cookie_file(domain).exists()


def list_saved_sessions() -> list:
    """All domains with a saved session."""
    out = set()
    for d in SESSION_DIR.iterdir():
        if d.is_dir() and d.name.startswith("generic_"):
            out.add(d.name.replace("generic_", "").replace("_profile", "").replace("_", "."))
    for f in COOKIE_DIR.glob("*.json"):
        out.add(f.stem.replace("_", "."))
    return sorted(out)


def clear_session(domain: str) -> None:
    """Forget a domain's login (use when a session goes stale)."""
    import shutil

    p = profile_dir(domain)
    if p.exists():
        shutil.rmtree(p, ignore_errors=True)
    c = cookie_file(domain)
    if c.exists():
        c.unlink()


def _get_proxy():
    if not getattr(config, "PROXY_LIST", None):
        return None
    proxy = random.choice(config.PROXY_LIST)
    return {
        "server": f"http://{proxy['ip']}:{proxy['port']}",
        "username": proxy.get("username"),
        "password": proxy.get("password"),
    }


async def get_context(domain: str, force_visible: bool = False):
    """
    Start Playwright with a persistent profile for this domain.
    Returns (playwright, context, page). Caller must close both.
    """
    p = await async_playwright().start()
    pdir = profile_dir(domain)
    pdir.mkdir(parents=True, exist_ok=True)

    proxy = _get_proxy()
    if proxy:
        print(f"🌐 Using proxy: {proxy['server']}")

    context = await p.chromium.launch_persistent_context(
        user_data_dir=str(pdir),
        headless=False if force_visible else IS_HEADLESS,
        viewport={"width": 1366, "height": 900},
        user_agent=USER_AGENT,
        proxy=proxy,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
        ],
        ignore_default_args=["--enable-automation"],
    )
    await context.add_init_script(STEALTH_JS)

    # Replay cookie backup (covers a wiped/copied profile dir).
    cf = cookie_file(domain)
    if cf.exists():
        try:
            cookies = json.loads(cf.read_text())
            if cookies:
                await context.add_cookies(cookies)
                print(f"🍪 Restored {len(cookies)} saved cookies for {domain}")
        except Exception as e:  # noqa: BLE001
            print(f"⚠️ Could not restore cookies for {domain}: {e}")

    page = context.pages[0] if context.pages else await context.new_page()
    return p, context, page


async def save_cookies(context, domain: str) -> int:
    """Persist cookies so the login survives even if the profile is lost."""
    try:
        cookies = await context.cookies()
        cookie_file(domain).write_text(json.dumps(cookies, indent=2))
        print(f"💾 Saved {len(cookies)} cookies for {domain}")
        return len(cookies)
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ Could not save cookies for {domain}: {e}")
        return 0


async def looks_logged_out(page) -> bool:
    """Heuristic login-wall detection: URL hints, or a login form on the page."""
    url = (page.url or "").lower()
    if any(h in url for h in LOGIN_URL_HINTS):
        return True
    try:
        if await page.locator("input[type='password']").count() > 0:
            return True
    except Exception:  # noqa: BLE001
        pass
    try:
        body = (await page.locator("body").inner_text()).lower()[:4000]
    except Exception:  # noqa: BLE001
        return False
    # Only treat as logged out if there is NO content editor available.
    try:
        editors = await page.locator("textarea, div[contenteditable='true']").count()
    except Exception:  # noqa: BLE001
        editors = 0
    if editors == 0 and any(h in body for h in LOGIN_TEXT_HINTS):
        return True
    return False


async def ensure_logged_in(context, page, url: str, domain: str, interactive: bool = True) -> bool:
    """
    If the page is a login wall, wait for a manual login once, then save the
    session. Returns True when we believe we're logged in (or none needed).
    """
    if not await looks_logged_out(page):
        return True

    if not interactive:
        print(f"🔐 {domain} needs a login and interactive mode is off - skipping.")
        return False

    print("\n" + "=" * 56)
    print(f"🔐 LOGIN REQUIRED for {domain}")
    print("=" * 56)
    print("1. Log in inside the browser window that just opened")
    print("2. Finish any email/OTP verification")
    print("3. Come back HERE and press ENTER - the session gets saved,")
    print("   so this is a ONE-TIME step for this domain.")
    print("=" * 56)

    await asyncio.get_event_loop().run_in_executor(
        None, input, "\n👉 Press ENTER after you have COMPLETED login...\n"
    )

    # Login may have finished in a popup/new tab (e.g. Sign in with Google).
    try:
        if len(context.pages) > 1:
            page = context.pages[-1]
            print(f"↪️  Continuing on the newest of {len(context.pages)} tabs.")
    except Exception:  # noqa: BLE001
        pass

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(3000)
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ Could not reload target after login: {e}")

    await save_cookies(context, domain)

    still_out = await looks_logged_out(page)
    if still_out:
        print("⚠️ Still looks logged out - session saved anyway, retry the run.")
        return False

    print("✅ Logged in and session saved.")
    return True