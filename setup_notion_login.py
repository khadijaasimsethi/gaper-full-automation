"""
Run this ONCE manually:
    python setup_notion_login.py

Opens a visible automated browser. Log in to Notion (your workspace) in
THIS window, then come back here and press Enter. Session gets saved to
sessions/notion_profile for reuse by post_to_notion_browser.py.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import config

PROFILE_DIR = Path(config.BASE_DIR) / "sessions" / "notion_profile"
PROFILE_DIR.mkdir(parents=True, exist_ok=True)


def main():
    print(f"Session will be saved to: {PROFILE_DIR}")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            channel="chrome",
            viewport={"width": 1440, "height": 900},
        )
        page = context.new_page()
        page.goto("https://www.notion.so/login", wait_until="domcontentloaded", timeout=30000)

        print("\n>>> Log in to Notion in the automated browser window.")
        print(">>> Once you see your workspace, come back here and press Enter.\n")
        input("Press Enter once you're fully logged in... ")

        print("✅ Session saved.")
        context.close()


if __name__ == "__main__":
    main()