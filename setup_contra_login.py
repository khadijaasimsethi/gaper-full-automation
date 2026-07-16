"""
Run this ONCE to manually log into Contra. It opens a browser, you enter
your email and the verification code Contra emails you, and the session
gets saved to sessions/contra_profile/. After this, ContraAdapter reuses
that saved session automatically - no more manual login needed.
"""

from pathlib import Path
from playwright.sync_api import sync_playwright
import config

def main():
    profile_dir = Path(config.BASE_DIR) / "sessions" / "contra_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={"width": 1366, "height": 768},
        )
        page = context.new_page()
        page.goto("https://contra.com", wait_until="domcontentloaded", timeout=30000)

        print("\n📧 Browser opened. Please:")
        print("1. Enter your email and request the verification code")
        print("2. Check your email inbox for the code")
        print("3. Enter the code in the browser to complete login")
        input("\nPress Enter here ONLY after you're fully logged in...\n")

        print("✅ Session saved to sessions/contra_profile/")
        print("You won't need to log in manually again - ContraAdapter will reuse this session.")
        context.close()

if __name__ == "__main__":
    main()