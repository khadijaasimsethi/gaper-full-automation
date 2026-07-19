

"""
Run this from your project root:
    python post_to_notion_browser.py

1. Generates a full article about Gaper using Gemini.
2. Opens your saved Notion session, goes to your database, creates a
   new page, and TYPES the title + article body into it live (using
   Notion's own markdown-shortcut typing, so ## becomes a heading,
   * becomes a bullet, **bold** becomes bold, automatically).
3. Stops there. It does NOT click Share / Publish to web - that stays
   a manual step for you to review and do yourself.

Before running: paste your Notion database URL below (open the
database in your browser, copy the URL from the address bar).
"""
from pathlib import Path
import re
import google.generativeai as genai
from playwright.sync_api import sync_playwright
import config

PROFILE_DIR = Path(config.BASE_DIR) / "sessions" / "notion_profile"
GEMINI_MODEL = "gemini-flash-latest"

# ---- CHANGE THIS to your actual Notion database URL ----
NOTION_DATABASE_URL = "https://app.notion.com/p/PASTE_YOUR_DATABASE_URL_HERE"


def generate_article() -> dict:
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)

    usps = "\n".join(f"- {u}" for u in config.BRAND_USPS)
    prompt = f"""
Write a full blog article (500-700 words) about Gaper (gaper.io) for publishing
on a public Notion blog page.

Brand USPs:
{usps}
Link to include naturally once, INSIDE THE BODY ONLY (never in the title): {config.PRIMARY_URL}

Rules:
- Line 1: ONLY the plain title text. No links, no markdown, no brackets, no bold, under 70 characters.
- Then a blank line, then the body.
- Use "## " for section headings, "* " for bullet points, "**text**" for bold - Notion converts these live as you type.
- Genuinely useful, not a sales pitch. Third-person or neutral tone, factual.
- Output ONLY the title + article, nothing else (no preamble, no explanation).
"""
    res = model.generate_content(prompt)
    text = (res.text or "").strip()
    lines = [l for l in text.split("\n") if l.strip()]
    raw_title = lines[0].strip()
    # Safety net: strip any markdown link/bold syntax that slipped into the title anyway
    title = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", raw_title)  # [text](url) -> text
    title = re.sub(r"https?://\S+", "", title)  # bare URLs
    title = title.replace("**", "").strip(" -")
    body = "\n".join(lines[1:]).strip()
    return {"title": title, "body": body}


def type_into_notion(title: str, body: str):
    if not PROFILE_DIR.exists():
        print("❌ No saved Notion session. Run setup_notion_login.py first.")
        return

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            channel="chrome",
            viewport={"width": 1440, "height": 900},
        )
        page = context.new_page()
        page.goto(NOTION_DATABASE_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        # Click "New" to create a new database row/page
        new_button = page.get_by_role("button", name=re.compile("New", re.IGNORECASE)).first
        new_button.wait_for(state="visible", timeout=15000)
        new_button.click()
        page.wait_for_timeout(1500)

        # Title field - Notion focuses the title automatically on a new page
        page.keyboard.type(title, delay=15)
        page.keyboard.press("Enter")
        page.wait_for_timeout(500)

        # Type the body, line by line, letting Notion's live markdown
        # shortcuts (## , * , **bold**) convert as we go.
        for line in body.split("\n"):
            if line.strip():
                page.keyboard.type(line, delay=8)
            page.keyboard.press("Enter")
            # Keep the cursor's block in view as content grows past the viewport
            page.evaluate("""() => {
                const el = document.activeElement;
                if (el) el.scrollIntoView({block: 'center', behavior: 'instant'});
            }""")
            page.wait_for_timeout(150)

        print("✅ Content typed into Notion. Review the page, then click")
        print("   Share -> Publish to web yourself when you're happy with it.")
        print("   (This script does NOT auto-publish - that stays a manual click by design.)")
        print("   (Leaving the browser open - close it manually when done.)")
        page.wait_for_timeout(3000)
        # NOTE: not closing context on purpose, so you can review/edit before publishing.


if __name__ == "__main__":
    print("Generating article with Gemini...")
    article = generate_article()
    print(f"\nTitle: {article['title']}\n")

    print("Opening Notion and typing content...")
    type_into_notion(article["title"], article["body"])