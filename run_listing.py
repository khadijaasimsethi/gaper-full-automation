"""
End-to-end: find new listing platforms -> auto-login/fill -> human
review -> type yes to submit (or no to skip).
"""

import sys
from src.database import init_db, SessionLocal, ListingOpportunity
from src.discovery import discover_listing_platforms
from src.generic_listing_agent import start_generic_listing, confirm_generic_listing, cancel_generic_listing

def main():
    init_db()
    print("🔎 Searching for new platforms where Gaper isn't listed yet...")
    new_urls = discover_listing_platforms()
    print(f"Found {len(new_urls)} new platform candidates.\n")

    if not new_urls:
        print("No new platforms found this run.")
        return

    for url in new_urls:
        print(f"\n=== {url} ===")
        proceed = input("Attempt auto-fill for this platform? (y/N): ").strip().lower()
        if proceed != "y":
            continue

        result = start_generic_listing(url)
        print(result)

        if result.get("status") != "awaiting_approval":
            continue

        print(f"\nScreenshot: {result['screenshot_path']}")
        print("Open the screenshot and check the browser window to verify the fields.")
        decision = input("Type 'yes' to submit, anything else to cancel: ").strip().lower()

        if decision == "yes":
            final = confirm_generic_listing(result["session_id"])
            print(final)
        else:
            cancel_generic_listing(result["session_id"])
            print("Cancelled - nothing submitted.")

if __name__ == "__main__":
    main()