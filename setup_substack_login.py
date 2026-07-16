from pathlib import Path
from playwright.sync_api import sync_playwright
import config

def main():
    profile_dir = Path(config.BASE_DIR) / "sessions" / "substack_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={"width": 1366, "height": 768},
        )
        page = context.new_page()
        page.goto("https://substack.com", wait_until="domcontentloaded", timeout=30000)

        print("\n📧 Browser opened. Please:")
        print("1. Click Sign In, enter your email")
        print("2. Check your email inbox for the code or magic link")
        print("3. Complete login in the browser")
        input("\nPress Enter here ONLY after you're fully logged in...\n")

        print("✅ Session saved to sessions/substack_profile/")
        context.close()

if __name__ == "__main__":
    main()