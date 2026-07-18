"""
Run ONCE manually: python setup_peerlist_login.py

Opens a real browser using a residential/datacenter proxy (from
config.PROXY_LIST, if configured) to avoid Cloudflare flagging the
connection, and auto-solves the Turnstile challenge via 2Captcha if it
appears (searching all iframes, not just the top-level page). You still
log in manually (email/password + any email code). Session is saved to
sessions/peerlist_profile/ and reused forever after by PeerlistAdapter.
"""

from pathlib import Path
from playwright.sync_api import sync_playwright
import config
from src.captcha_solver import CaptchaSolver

PROFILE_DIR = Path(config.BASE_DIR) / "sessions" / "peerlist_profile"
PROFILE_DIR.mkdir(parents=True, exist_ok=True)

CHROME_FLAGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
]


def _get_proxy():
    """Pull the first proxy from config.PROXY_LIST, formatted for Playwright."""
    proxies = getattr(config, "PROXY_LIST", [])
    if not proxies:
        return None
    p = proxies[0]
    proxy_config = {"server": f"http://{p['ip']}:{p['port']}"}
    if p.get("username"):
        proxy_config["username"] = p["username"]
        proxy_config["password"] = p["password"]
    return proxy_config


def _try_solve_turnstile(page):
    """
    Uses our own CaptchaSolver (2Captcha REST API directly). Searches ALL
    frames (not just the top-level page) because Cloudflare's Turnstile
    widget is almost always nested inside an iframe, which naive
    top-level-only detection misses entirely.
    """
    solver = CaptchaSolver()
    if not solver.api_key:
        print("⚠️ No CAPTCHA_API_KEY set - skipping auto-solve.")
        return False

    site_key = None

    # Check the main page first
    try:
        el = page.locator("[data-sitekey]").first
        if el.count() > 0:
            site_key = el.get_attribute("data-sitekey")
    except Exception:
        pass

    # Then check every iframe on the page - Turnstile is almost always here
    if not site_key:
        for frame in page.frames:
            try:
                el = frame.locator("[data-sitekey]").first
                if el.count() > 0:
                    candidate = el.get_attribute("data-sitekey")
                    if candidate:
                        site_key = candidate
                        print(f"🔍 Found sitekey inside iframe: {frame.url[:60]}")
                        break
            except Exception:
                continue

    if not site_key:
        print("⚠️ Could not find any Turnstile sitekey on the page or in its iframes.")
        return False

    print(f"🔑 Found Turnstile site key: {site_key[:20]}... Solving via 2Captcha (may take 30-90s)...")
    try:
        token = solver.solve_turnstile(site_key, page.url)
        print("✅ Got token from 2Captcha. Injecting...")
        page.evaluate(f"""
            () => {{
                const input = document.querySelector('[name="cf-turnstile-response"]');
                if (input) {{
                    input.value = '{token}';
                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }}
                if (window.turnstileCallback) window.turnstileCallback('{token}');
            }}
        """)
        page.wait_for_timeout(2000)
        print("🔄 Refreshing to let Cloudflare validate the injected token...")
        page.reload(wait_until="domcontentloaded", timeout=30000)
        return True
    except Exception as e:
        print(f"⚠️ 2Captcha solve failed: {e}")
        return False


def main():
    proxy_config = _get_proxy()
    if proxy_config:
        print(f"🌐 Using proxy: {proxy_config['server']}")
    else:
        print("⚠️ No proxy configured - continuing without one.")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            args=CHROME_FLAGS,
            ignore_default_args=["--enable-automation"],
            proxy=proxy_config,
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            timezone_id="America/New_York",
        )
        page = context.pages[0] if context.pages else context.new_page()

        # Extra stealth - hide the most common automation fingerprints
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
            window.chrome = { runtime: {} };
        """)

        try:
            print("Opening Peerlist login...")
            try:
                page.goto("https://peerlist.io/login",
                          wait_until="domcontentloaded", timeout=60000)
            except Exception as e:
                print(f"⚠️ page.goto issue: {e}")
                print("Browser is still open - check it manually.")

            print("⏳ Waiting up to 15s for Cloudflare to clear on its own...")
            cleared = False
            for _ in range(15):
                page.wait_for_timeout(1000)
                try:
                    content_lower = page.content().lower()
                    title_lower = page.title().lower()
                except Exception:
                    continue
                if "verifying" not in content_lower and "just a moment" not in title_lower:
                    cleared = True
                    break

            if cleared:
                print("✅ Cloudflare check cleared automatically.")
            else:
                print("Still on Cloudflare check - trying 2Captcha auto-solve...")
                solved = _try_solve_turnstile(page)
                if not solved:
                    print("⚠️ Auto-solve didn't work.")
                    print("👉 Try clicking/interacting with the checkbox in the browser window manually,")
                    print("   or just wait/refresh - it sometimes clears with a human-like interaction.")

            print("\n>>> Log in manually in the browser window now (if not already past Cloudflare).")
            print(">>> Complete email/password + any email code.")
            input(">>> When you see your Peerlist feed, press Enter here to save session...\n")

            if "login" in page.url.lower():
                page.goto("https://peerlist.io/scroll",
                          wait_until="domcontentloaded", timeout=60000)
                if "login" in page.url.lower():
                    print("FAILED: still on login page. Session NOT saved.")
                    return

            print(f"OK: logged in. Landed on: {page.url}")
            print(f"OK: session saved at: {PROFILE_DIR}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            input("Press Enter to close browser (check window manually first if needed)...")
        finally:
            context.close()


if __name__ == "__main__":
    main()