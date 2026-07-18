# # # # # # # # # """
# # # # # # # # # Notion posting via the saved BROWSER session (sessions/notion_profile,
# # # # # # # # # created once by setup_notion_login.py) - not the API key. This matches
# # # # # # # # # how Contra works: a real logged-in session, not an invisible API call.

# # # # # # # # # Used by article_studio.py's submit step for Notion drafts. Does NOT
# # # # # # # # # auto-publish the page to the web - "Share -> Publish to web" stays a
# # # # # # # # # manual click, per earlier decision. This function only gets the content
# # # # # # # # # typed into a new page in your workspace and leaves the browser open for
# # # # # # # # # you to review.
# # # # # # # # # """
# # # # # # # # # import logging
# # # # # # # # # import re
# # # # # # # # # from pathlib import Path
# # # # # # # # # from playwright.sync_api import sync_playwright
# # # # # # # # # import config

# # # # # # # # # logger = logging.getLogger(__name__)

# # # # # # # # # PROFILE_DIR = Path(config.BASE_DIR) / "sessions" / "notion_profile"


# # # # # # # # # def _clean_title(raw_title: str) -> str:
# # # # # # # # #     title = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", raw_title)
# # # # # # # # #     title = re.sub(r"https?://\S+", "", title)
# # # # # # # # #     return title.replace("**", "").strip(" -")


# # # # # # # # # def post_to_notion_session(title: str, body: str) -> dict:
# # # # # # # # #     """
# # # # # # # # #     Opens the saved Notion session, creates a new page in the configured
# # # # # # # # #     database, types title + body live (letting Notion's own markdown
# # # # # # # # #     shortcuts convert ##, *, **bold** as it goes), and leaves the browser
# # # # # # # # #     open for manual review + Publish to web.
# # # # # # # # #     """
# # # # # # # # #     database_url = getattr(config, "NOTION_DATABASE_URL", "")
# # # # # # # # #     if not database_url:
# # # # # # # # #         return {"status": "failed", "detail": "NOTION_DATABASE_URL is not set in config.py/.env - add your Notion database URL there first."}

# # # # # # # # #     if not PROFILE_DIR.exists():
# # # # # # # # #         return {"status": "failed", "detail": "No saved Notion session. Run setup_notion_login.py once first."}

# # # # # # # # #     clean_title = _clean_title(title)

# # # # # # # # #     try:
# # # # # # # # #         with sync_playwright() as p:
# # # # # # # # #             context = p.chromium.launch_persistent_context(
# # # # # # # # #                 user_data_dir=str(PROFILE_DIR),
# # # # # # # # #                 headless=False,
# # # # # # # # #                 channel="chrome",
# # # # # # # # #                 viewport={"width": 1440, "height": 900},
# # # # # # # # #             )
# # # # # # # # #             page = context.new_page()
# # # # # # # # #             page.goto(database_url, wait_until="domcontentloaded", timeout=30000)
# # # # # # # # #             page.wait_for_timeout(2000)

# # # # # # # # #             if "login" in page.url.lower():
# # # # # # # # #                 context.close()
# # # # # # # # #                 return {"status": "failed", "detail": "Notion session expired. Re-run setup_notion_login.py."}

# # # # # # # # #             new_button = page.get_by_role("button", name=re.compile("New", re.IGNORECASE)).first
# # # # # # # # #             new_button.wait_for(state="visible", timeout=15000)
# # # # # # # # #             new_button.click()
# # # # # # # # #             page.wait_for_timeout(1500)

# # # # # # # # #             page.keyboard.type(clean_title, delay=15)
# # # # # # # # #             page.keyboard.press("Enter")
# # # # # # # # #             page.wait_for_timeout(500)

# # # # # # # # #             for line in body.split("\n"):
# # # # # # # # #                 if line.strip():
# # # # # # # # #                     page.keyboard.type(line, delay=8)
# # # # # # # # #                 page.keyboard.press("Enter")
# # # # # # # # #                 page.evaluate("""() => {
# # # # # # # # #                     const el = document.activeElement;
# # # # # # # # #                     if (el) el.scrollIntoView({block: 'center', behavior: 'instant'});
# # # # # # # # #                 }""")
# # # # # # # # #                 page.wait_for_timeout(150)

# # # # # # # # #             page.wait_for_timeout(2000)
# # # # # # # # #             # Deliberately NOT closing context/NOT clicking Publish - stays
# # # # # # # # #             # open so the human can review and click Share -> Publish to web.
# # # # # # # # #             logger.info(f"[NotionSessionPost] Typed article '{clean_title}' into workspace, awaiting manual publish.")
# # # # # # # # #             return {
# # # # # # # # #                 "status": "success",
# # # # # # # # #                 "detail": f"'{clean_title}' typed into your Notion workspace. Open the browser window, review, then click Share -> Publish to web yourself.",
# # # # # # # # #             }

# # # # # # # # #     except Exception as e:
# # # # # # # # #         logger.error(f"[NotionSessionPost] Failed: {e}")
# # # # # # # # #         return {"status": "failed", "detail": str(e)}




# # # # # # # # # src/notion_session_poster.py
# # # # # # # # """
# # # # # # # # Notion posting via saved BROWSER session (sessions/notion_profile)
# # # # # # # # """

# # # # # # # # import logging
# # # # # # # # import re
# # # # # # # # from pathlib import Path
# # # # # # # # from playwright.sync_api import sync_playwright
# # # # # # # # import config

# # # # # # # # logger = logging.getLogger(__name__)

# # # # # # # # PROFILE_DIR = Path(config.BASE_DIR) / "sessions" / "notion_profile"

# # # # # # # # # Use the database URL from config
# # # # # # # # NOTION_DATABASE_URL = getattr(config, "NOTION_DATABASE_URL", "")


# # # # # # # # def _clean_title(raw_title: str) -> str:
# # # # # # # #     """Clean title for Notion"""
# # # # # # # #     title = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", raw_title)
# # # # # # # #     title = re.sub(r"https?://\S+", "", title)
# # # # # # # #     return title.replace("**", "").strip(" -")[:70]


# # # # # # # # def post_to_notion_session(title: str, body: str) -> dict:
# # # # # # # #     """
# # # # # # # #     Posts to Notion using saved browser session.
# # # # # # # #     Creates new page in your database.
# # # # # # # #     """
# # # # # # # #     if not NOTION_DATABASE_URL:
# # # # # # # #         return {
# # # # # # # #             "status": "failed",
# # # # # # # #             "detail": "NOTION_DATABASE_URL not set in config. Add it to config.py"
# # # # # # # #         }
    
# # # # # # # #     if not PROFILE_DIR.exists():
# # # # # # # #         return {
# # # # # # # #             "status": "failed",
# # # # # # # #             "detail": "Notion session not found. Run 'python setup_notion_login.py' first."
# # # # # # # #         }

# # # # # # # #     clean_title = _clean_title(title)

# # # # # # # #     try:
# # # # # # # #         with sync_playwright() as p:
# # # # # # # #             context = p.chromium.launch_persistent_context(
# # # # # # # #                 user_data_dir=str(PROFILE_DIR),
# # # # # # # #                 headless=False,
# # # # # # # #                 channel="chrome",
# # # # # # # #                 viewport={"width": 1440, "height": 900},
# # # # # # # #             )
# # # # # # # #             page = context.new_page()
            
# # # # # # # #             logger.info(f"🌐 Opening Notion: {NOTION_DATABASE_URL}")
# # # # # # # #             page.goto(NOTION_DATABASE_URL, wait_until="domcontentloaded", timeout=30000)
# # # # # # # #             page.wait_for_timeout(2000)

# # # # # # # #             # Check if logged in
# # # # # # # #             if "login" in page.url.lower():
# # # # # # # #                 context.close()
# # # # # # # #                 return {
# # # # # # # #                     "status": "failed",
# # # # # # # #                     "detail": "Notion session expired. Run 'python setup_notion_login.py' again."
# # # # # # # #                 }

# # # # # # # #             # Click "New" button to create page
# # # # # # # #             logger.info("🆕 Creating new page...")
# # # # # # # #             new_button = page.get_by_role("button", name="New").first
# # # # # # # #             new_button.wait_for(state="visible", timeout=15000)
# # # # # # # #             new_button.click()
# # # # # # # #             page.wait_for_timeout(1500)

# # # # # # # #             # Type title
# # # # # # # #             logger.info(f"📝 Typing title: {clean_title}")
# # # # # # # #             page.keyboard.type(clean_title, delay=15)
# # # # # # # #             page.keyboard.press("Enter")
# # # # # # # #             page.wait_for_timeout(500)

# # # # # # # #             # Type body paragraph by paragraph
# # # # # # # #             logger.info("📝 Typing content...")
# # # # # # # #             for line in body.split("\n"):
# # # # # # # #                 if line.strip():
# # # # # # # #                     page.keyboard.type(line, delay=8)
# # # # # # # #                 page.keyboard.press("Enter")
# # # # # # # #                 page.wait_for_timeout(150)

# # # # # # # #             page.wait_for_timeout(2000)
            
# # # # # # # #             # Get page URL
# # # # # # # #             current_url = page.url
            
# # # # # # # #             logger.info(f"✅ Notion page '{clean_title}' created successfully!")
# # # # # # # #             context.close()
            
# # # # # # # #             return {
# # # # # # # #                 "status": "success",
# # # # # # # #                 "detail": f"Notion page '{clean_title}' created",
# # # # # # # #                 "url": current_url
# # # # # # # #             }

# # # # # # # #     except Exception as e:
# # # # # # # #         logger.error(f"Notion posting failed: {e}")
# # # # # # # #         return {"status": "failed", "detail": str(e)}





# # # # # # # # src/notion_session_poster.py
# # # # # # # """
# # # # # # # Notion posting via saved BROWSER session - EXACT same logic as root script
# # # # # # # """

# # # # # # # import logging
# # # # # # # import re
# # # # # # # from pathlib import Path
# # # # # # # from playwright.sync_api import sync_playwright
# # # # # # # import config

# # # # # # # logger = logging.getLogger(__name__)

# # # # # # # PROFILE_DIR = Path(config.BASE_DIR) / "sessions" / "notion_profile"
# # # # # # # NOTION_DATABASE_URL = getattr(config, "NOTION_DATABASE_URL", "")


# # # # # # # def _clean_title(raw_title: str) -> str:
# # # # # # #     """Clean title - remove links, markdown, keep under 70 chars"""
# # # # # # #     # Remove markdown links [text](url)
# # # # # # #     title = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", raw_title)
# # # # # # #     # Remove bare URLs
# # # # # # #     title = re.sub(r"https?://\S+", "", title)
# # # # # # #     # Remove bold/italic markers
# # # # # # #     title = title.replace("**", "").replace("*", "")
# # # # # # #     # Remove extra spaces and dashes
# # # # # # #     title = title.strip(" -")
# # # # # # #     # Keep under 70 chars
# # # # # # #     if len(title) > 70:
# # # # # # #         title = title[:67] + "..."
# # # # # # #     return title


# # # # # # # def _clean_body(body: str) -> str:
# # # # # # #     """Ensure link is in body, not title"""
# # # # # # #     # Make sure gaper.io link is in body
# # # # # # #     if "gaper.io" not in body:
# # # # # # #         body += f"\n\nLearn more at https://gaper.io"
# # # # # # #     return body


# # # # # # # def post_to_notion_session(title: str, body: str) -> dict:
# # # # # # #     """
# # # # # # #     Posts to Notion using saved browser session.
# # # # # # #     EXACT same logic as post_to_notion_browser.py
# # # # # # #     """
# # # # # # #     if not NOTION_DATABASE_URL:
# # # # # # #         return {
# # # # # # #             "status": "failed",
# # # # # # #             "detail": "NOTION_DATABASE_URL not set in config. Add to config.py or .env"
# # # # # # #         }
    
# # # # # # #     if not PROFILE_DIR.exists():
# # # # # # #         return {
# # # # # # #             "status": "failed",
# # # # # # #             "detail": "Notion session not found. Run 'python setup_notion_login.py' first."
# # # # # # #         }

# # # # # # #     # Clean title and body
# # # # # # #     clean_title = _clean_title(title)
# # # # # # #     clean_body = _clean_body(body)

# # # # # # #     try:
# # # # # # #         with sync_playwright() as p:
# # # # # # #             context = p.chromium.launch_persistent_context(
# # # # # # #                 user_data_dir=str(PROFILE_DIR),
# # # # # # #                 headless=False,
# # # # # # #                 channel="chrome",
# # # # # # #                 viewport={"width": 1440, "height": 900},
# # # # # # #             )
# # # # # # #             page = context.new_page()
            
# # # # # # #             logger.info(f"🌐 Opening Notion: {NOTION_DATABASE_URL}")
# # # # # # #             page.goto(NOTION_DATABASE_URL, wait_until="domcontentloaded", timeout=30000)
# # # # # # #             page.wait_for_timeout(2000)

# # # # # # #             # Check if logged in
# # # # # # #             if "login" in page.url.lower():
# # # # # # #                 context.close()
# # # # # # #                 return {
# # # # # # #                     "status": "failed",
# # # # # # #                     "detail": "Notion session expired. Run 'python setup_notion_login.py' again."
# # # # # # #                 }

# # # # # # #             # Click "New" button
# # # # # # #             logger.info("🆕 Creating new page...")
# # # # # # #             new_button = page.get_by_role("button", name=re.compile("New", re.IGNORECASE)).first
# # # # # # #             new_button.wait_for(state="visible", timeout=15000)
# # # # # # #             new_button.click()
# # # # # # #             page.wait_for_timeout(1500)

# # # # # # #             # Type title (clean, no links)
# # # # # # #             logger.info(f"📝 Typing title: {clean_title}")
# # # # # # #             page.keyboard.type(clean_title, delay=15)
# # # # # # #             page.keyboard.press("Enter")
# # # # # # #             page.wait_for_timeout(500)

# # # # # # #             # Type body (with link)
# # # # # # #             logger.info("📝 Typing content...")
# # # # # # #             for line in clean_body.split("\n"):
# # # # # # #                 if line.strip():
# # # # # # #                     page.keyboard.type(line, delay=8)
# # # # # # #                 page.keyboard.press("Enter")
# # # # # # #                 # Keep cursor in view
# # # # # # #                 page.evaluate("""() => {
# # # # # # #                     const el = document.activeElement;
# # # # # # #                     if (el) el.scrollIntoView({block: 'center', behavior: 'instant'});
# # # # # # #                 }""")
# # # # # # #                 page.wait_for_timeout(150)

# # # # # # #             page.wait_for_timeout(2000)
            
# # # # # # #             # Get page URL
# # # # # # #             current_url = page.url
            
# # # # # # #             logger.info(f"✅ Notion page '{clean_title}' created successfully!")
            
# # # # # # #             # DON'T close browser - let user review and publish manually
# # # # # # #             # context.close()  # <- Commented out so browser stays open
            
# # # # # # #             return {
# # # # # # #                 "status": "success",
# # # # # # #                 "detail": f"Notion page '{clean_title}' created. Browser open for review.",
# # # # # # #                 "url": current_url
# # # # # # #             }

# # # # # # #     except Exception as e:
# # # # # # #         logger.error(f"Notion posting failed: {e}")
# # # # # # #         return {"status": "failed", "detail": str(e)}


# # # # # # # # """
# # # # # # # # Notion posting via the saved BROWSER session (sessions/notion_profile,
# # # # # # # # created once by setup_notion_login.py) - not the API key. This matches
# # # # # # # # how Contra works: a real logged-in session, not an invisible API call.

# # # # # # # # Used by article_studio.py's submit step for Notion drafts. Does NOT
# # # # # # # # auto-publish the page to the web - "Share -> Publish to web" stays a
# # # # # # # # manual click, per earlier decision. This function only gets the content
# # # # # # # # typed into a new page in your workspace and leaves the browser open for
# # # # # # # # you to review.
# # # # # # # # """
# # # # # # # # import logging
# # # # # # # # import re
# # # # # # # # from pathlib import Path
# # # # # # # # from playwright.sync_api import sync_playwright
# # # # # # # # import config

# # # # # # # # logger = logging.getLogger(__name__)

# # # # # # # # PROFILE_DIR = Path(config.BASE_DIR) / "sessions" / "notion_profile"


# # # # # # # # def _clean_title(raw_title: str) -> str:
# # # # # # # #     title = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", raw_title)
# # # # # # # #     title = re.sub(r"https?://\S+", "", title)
# # # # # # # #     return title.replace("**", "").strip(" -")


# # # # # # # # def post_to_notion_session(title: str, body: str) -> dict:
# # # # # # # #     """
# # # # # # # #     Opens the saved Notion session, creates a new page in the configured
# # # # # # # #     database, types title + body live (letting Notion's own markdown
# # # # # # # #     shortcuts convert ##, *, **bold** as it goes), and leaves the browser
# # # # # # # #     open for manual review + Publish to web.
# # # # # # # #     """
# # # # # # # #     database_url = getattr(config, "NOTION_DATABASE_URL", "")
# # # # # # # #     if not database_url:
# # # # # # # #         return {"status": "failed", "detail": "NOTION_DATABASE_URL is not set in config.py/.env - add your Notion database URL there first."}

# # # # # # # #     if not PROFILE_DIR.exists():
# # # # # # # #         return {"status": "failed", "detail": "No saved Notion session. Run setup_notion_login.py once first."}

# # # # # # # #     clean_title = _clean_title(title)

# # # # # # # #     try:
# # # # # # # #         with sync_playwright() as p:
# # # # # # # #             context = p.chromium.launch_persistent_context(
# # # # # # # #                 user_data_dir=str(PROFILE_DIR),
# # # # # # # #                 headless=False,
# # # # # # # #                 channel="chrome",
# # # # # # # #                 viewport={"width": 1440, "height": 900},
# # # # # # # #             )
# # # # # # # #             page = context.new_page()
# # # # # # # #             page.goto(database_url, wait_until="domcontentloaded", timeout=30000)
# # # # # # # #             page.wait_for_timeout(2000)

# # # # # # # #             if "login" in page.url.lower():
# # # # # # # #                 context.close()
# # # # # # # #                 return {"status": "failed", "detail": "Notion session expired. Re-run setup_notion_login.py."}

# # # # # # # #             new_button = page.get_by_role("button", name=re.compile("New", re.IGNORECASE)).first
# # # # # # # #             new_button.wait_for(state="visible", timeout=15000)
# # # # # # # #             new_button.click()
# # # # # # # #             page.wait_for_timeout(1500)

# # # # # # # #             page.keyboard.type(clean_title, delay=15)
# # # # # # # #             page.keyboard.press("Enter")
# # # # # # # #             page.wait_for_timeout(500)

# # # # # # # #             for line in body.split("\n"):
# # # # # # # #                 if line.strip():
# # # # # # # #                     page.keyboard.type(line, delay=8)
# # # # # # # #                 page.keyboard.press("Enter")
# # # # # # # #                 page.evaluate("""() => {
# # # # # # # #                     const el = document.activeElement;
# # # # # # # #                     if (el) el.scrollIntoView({block: 'center', behavior: 'instant'});
# # # # # # # #                 }""")
# # # # # # # #                 page.wait_for_timeout(150)

# # # # # # # #             page.wait_for_timeout(2000)
# # # # # # # #             # Deliberately NOT closing context/NOT clicking Publish - stays
# # # # # # # #             # open so the human can review and click Share -> Publish to web.
# # # # # # # #             logger.info(f"[NotionSessionPost] Typed article '{clean_title}' into workspace, awaiting manual publish.")
# # # # # # # #             return {
# # # # # # # #                 "status": "success",
# # # # # # # #                 "detail": f"'{clean_title}' typed into your Notion workspace. Open the browser window, review, then click Share -> Publish to web yourself.",
# # # # # # # #             }

# # # # # # # #     except Exception as e:
# # # # # # # #         logger.error(f"[NotionSessionPost] Failed: {e}")
# # # # # # # #         return {"status": "failed", "detail": str(e)}




# # # # # # # # src/notion_session_poster.py
# # # # # # # """
# # # # # # # Notion posting via saved BROWSER session (sessions/notion_profile)
# # # # # # # """

# # # # # # # import logging
# # # # # # # import re
# # # # # # # from pathlib import Path
# # # # # # # from playwright.sync_api import sync_playwright
# # # # # # # import config

# # # # # # # logger = logging.getLogger(__name__)

# # # # # # # PROFILE_DIR = Path(config.BASE_DIR) / "sessions" / "notion_profile"

# # # # # # # # Use the database URL from config
# # # # # # # NOTION_DATABASE_URL = getattr(config, "NOTION_DATABASE_URL", "")


# # # # # # # def _clean_title(raw_title: str) -> str:
# # # # # # #     """Clean title for Notion"""
# # # # # # #     title = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", raw_title)
# # # # # # #     title = re.sub(r"https?://\S+", "", title)
# # # # # # #     return title.replace("**", "").strip(" -")[:70]


# # # # # # # def post_to_notion_session(title: str, body: str) -> dict:
# # # # # # #     """
# # # # # # #     Posts to Notion using saved browser session.
# # # # # # #     Creates new page in your database.
# # # # # # #     """
# # # # # # #     if not NOTION_DATABASE_URL:
# # # # # # #         return {
# # # # # # #             "status": "failed",
# # # # # # #             "detail": "NOTION_DATABASE_URL not set in config. Add it to config.py"
# # # # # # #         }
    
# # # # # # #     if not PROFILE_DIR.exists():
# # # # # # #         return {
# # # # # # #             "status": "failed",
# # # # # # #             "detail": "Notion session not found. Run 'python setup_notion_login.py' first."
# # # # # # #         }

# # # # # # #     clean_title = _clean_title(title)

# # # # # # #     try:
# # # # # # #         with sync_playwright() as p:
# # # # # # #             context = p.chromium.launch_persistent_context(
# # # # # # #                 user_data_dir=str(PROFILE_DIR),
# # # # # # #                 headless=False,
# # # # # # #                 channel="chrome",
# # # # # # #                 viewport={"width": 1440, "height": 900},
# # # # # # #             )
# # # # # # #             page = context.new_page()
            
# # # # # # #             logger.info(f"🌐 Opening Notion: {NOTION_DATABASE_URL}")
# # # # # # #             page.goto(NOTION_DATABASE_URL, wait_until="domcontentloaded", timeout=30000)
# # # # # # #             page.wait_for_timeout(2000)

# # # # # # #             # Check if logged in
# # # # # # #             if "login" in page.url.lower():
# # # # # # #                 context.close()
# # # # # # #                 return {
# # # # # # #                     "status": "failed",
# # # # # # #                     "detail": "Notion session expired. Run 'python setup_notion_login.py' again."
# # # # # # #                 }

# # # # # # #             # Click "New" button to create page
# # # # # # #             logger.info("🆕 Creating new page...")
# # # # # # #             new_button = page.get_by_role("button", name="New").first
# # # # # # #             new_button.wait_for(state="visible", timeout=15000)
# # # # # # #             new_button.click()
# # # # # # #             page.wait_for_timeout(1500)

# # # # # # #             # Type title
# # # # # # #             logger.info(f"📝 Typing title: {clean_title}")
# # # # # # #             page.keyboard.type(clean_title, delay=15)
# # # # # # #             page.keyboard.press("Enter")
# # # # # # #             page.wait_for_timeout(500)

# # # # # # #             # Type body paragraph by paragraph
# # # # # # #             logger.info("📝 Typing content...")
# # # # # # #             for line in body.split("\n"):
# # # # # # #                 if line.strip():
# # # # # # #                     page.keyboard.type(line, delay=8)
# # # # # # #                 page.keyboard.press("Enter")
# # # # # # #                 page.wait_for_timeout(150)

# # # # # # #             page.wait_for_timeout(2000)
            
# # # # # # #             # Get page URL
# # # # # # #             current_url = page.url
            
# # # # # # #             logger.info(f"✅ Notion page '{clean_title}' created successfully!")
# # # # # # #             context.close()
            
# # # # # # #             return {
# # # # # # #                 "status": "success",
# # # # # # #                 "detail": f"Notion page '{clean_title}' created",
# # # # # # #                 "url": current_url
# # # # # # #             }

# # # # # # #     except Exception as e:
# # # # # # #         logger.error(f"Notion posting failed: {e}")
# # # # # # #         return {"status": "failed", "detail": str(e)}





# # # # # # # src/notion_session_poster.py
# # # # # # """
# # # # # # Notion posting via saved BROWSER session - EXACT same logic as root script
# # # # # # """

# # # # # # import logging
# # # # # # import re
# # # # # # from pathlib import Path
# # # # # # from playwright.sync_api import sync_playwright
# # # # # # import config

# # # # # # logger = logging.getLogger(__name__)

# # # # # # PROFILE_DIR = Path(config.BASE_DIR) / "sessions" / "notion_profile"
# # # # # # NOTION_DATABASE_URL = getattr(config, "NOTION_DATABASE_URL", "")


# # # # # # def _clean_title(raw_title: str) -> str:
# # # # # #     """Clean title - remove links, markdown, keep under 70 chars"""
# # # # # #     # Remove markdown links [text](url)
# # # # # #     title = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", raw_title)
# # # # # #     # Remove bare URLs
# # # # # #     title = re.sub(r"https?://\S+", "", title)
# # # # # #     # Remove bold/italic markers
# # # # # #     title = title.replace("**", "").replace("*", "")
# # # # # #     # Remove extra spaces and dashes
# # # # # #     title = title.strip(" -")
# # # # # #     # Keep under 70 chars
# # # # # #     if len(title) > 70:
# # # # # #         title = title[:67] + "..."
# # # # # #     return title


# # # # # # def _clean_body(body: str) -> str:
# # # # # #     """Ensure link is in body, not title"""
# # # # # #     # Make sure gaper.io link is in body
# # # # # #     if "gaper.io" not in body:
# # # # # #         body += f"\n\nLearn more at https://gaper.io"
# # # # # #     return body


# # # # # # def post_to_notion_session(title: str, body: str) -> dict:
# # # # # #     """
# # # # # #     Posts to Notion using saved browser session.
# # # # # #     EXACT same logic as post_to_notion_browser.py
# # # # # #     """
# # # # # #     if not NOTION_DATABASE_URL:
# # # # # #         return {
# # # # # #             "status": "failed",
# # # # # #             "detail": "NOTION_DATABASE_URL not set in config. Add to config.py or .env"
# # # # # #         }
    
# # # # # #     if not PROFILE_DIR.exists():
# # # # # #         return {
# # # # # #             "status": "failed",
# # # # # #             "detail": "Notion session not found. Run 'python setup_notion_login.py' first."
# # # # # #         }

# # # # # #     # Clean title and body
# # # # # #     clean_title = _clean_title(title)
# # # # # #     clean_body = _clean_body(body)

# # # # # #     try:
# # # # # #         with sync_playwright() as p:
# # # # # #             context = p.chromium.launch_persistent_context(
# # # # # #                 user_data_dir=str(PROFILE_DIR),
# # # # # #                 headless=False,
# # # # # #                 channel="chrome",
# # # # # #                 viewport={"width": 1440, "height": 900},
# # # # # #             )
# # # # # #             page = context.new_page()
            
# # # # # #             logger.info(f"🌐 Opening Notion: {NOTION_DATABASE_URL}")
# # # # # #             page.goto(NOTION_DATABASE_URL, wait_until="domcontentloaded", timeout=30000)
# # # # # #             page.wait_for_timeout(2000)

# # # # # #             # Check if logged in
# # # # # #             if "login" in page.url.lower():
# # # # # #                 context.close()
# # # # # #                 return {
# # # # # #                     "status": "failed",
# # # # # #                     "detail": "Notion session expired. Run 'python setup_notion_login.py' again."
# # # # # #                 }

# # # # # #             # Click "New" button
# # # # # #             logger.info("🆕 Creating new page...")
# # # # # #             new_button = page.get_by_role("button", name=re.compile("New", re.IGNORECASE)).first
# # # # # #             new_button.wait_for(state="visible", timeout=15000)
# # # # # #             new_button.click()
# # # # # #             page.wait_for_timeout(1500)

# # # # # #             # Type title (clean, no links)
# # # # # #             logger.info(f"📝 Typing title: {clean_title}")
# # # # # #             page.keyboard.type(clean_title, delay=15)
# # # # # #             page.keyboard.press("Enter")
# # # # # #             page.wait_for_timeout(500)

# # # # # #             # Type body (with link)
# # # # # #             logger.info("📝 Typing content...")
# # # # # #             link_line_re = re.compile(r"^\[\[LINK:(.*?)\|(.*?)\]\]$")
# # # # # #             for line in clean_body.split("\n"):
# # # # # #                 m = link_line_re.match(line.strip())
# # # # # #                 if m:
# # # # # #                     # Special case: turn "[[LINK:anchor|url]]" into a real
# # # # # #                     # clickable Notion hyperlink instead of typing a raw URL.
# # # # # #                     anchor_text, link_url = m.group(1), m.group(2)
# # # # # #                     page.keyboard.type(anchor_text, delay=8)
# # # # # #                     page.keyboard.press("Shift+Home")
# # # # # #                     page.keyboard.press("Control+K")
# # # # # #                     page.wait_for_timeout(400)
# # # # # #                     page.keyboard.type(link_url, delay=10)
# # # # # #                     page.wait_for_timeout(300)
# # # # # #                     page.keyboard.press("Enter")
# # # # # #                     page.keyboard.press("End")
# # # # # #                 elif line.strip():
# # # # # #                     page.keyboard.type(line, delay=8)
# # # # # #                 page.keyboard.press("Enter")
# # # # # #                 # Keep cursor in view
# # # # # #                 page.evaluate("""() => {
# # # # # #                     const el = document.activeElement;
# # # # # #                     if (el) el.scrollIntoView({block: 'center', behavior: 'instant'});
# # # # # #                 }""")
# # # # # #                 page.wait_for_timeout(150)

# # # # # #             page.wait_for_timeout(2000)
            
# # # # # #             # Get page URL
# # # # # #             current_url = page.url
            
# # # # # #             logger.info(f"✅ Notion page '{clean_title}' created successfully!")
            
# # # # # #             # DON'T close browser - let user review and publish manually
# # # # # #             # context.close()  # <- Commented out so browser stays open
            
# # # # # #             return {
# # # # # #                 "status": "success",
# # # # # #                 "detail": f"Notion page '{clean_title}' created. Browser open for review.",
# # # # # #                 "url": current_url
# # # # # #             }

# # # # # #     except Exception as e:
# # # # # #         logger.error(f"Notion posting failed: {e}")
# # # # # #         return {"status": "failed", "detail": str(e)}



# # # # # # src/notion_session_poster.py
# # # # # """
# # # # # Notion posting via saved BROWSER session - EXACT same logic as root script
# # # # # """

# # # # # import logging
# # # # # import re
# # # # # from pathlib import Path
# # # # # from playwright.sync_api import sync_playwright
# # # # # import config

# # # # # logger = logging.getLogger(__name__)

# # # # # PROFILE_DIR = Path(config.BASE_DIR) / "sessions" / "notion_profile"
# # # # # NOTION_DATABASE_URL = getattr(config, "NOTION_DATABASE_URL", "")


# # # # # def _clean_title(raw_title: str) -> str:
# # # # #     """Clean title - remove links, markdown, keep under 70 chars"""
# # # # #     # Remove markdown links [text](url)
# # # # #     title = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", raw_title)
# # # # #     # Remove bare URLs
# # # # #     title = re.sub(r"https?://\S+", "", title)
# # # # #     # Remove bold/italic markers
# # # # #     title = title.replace("**", "").replace("*", "")
# # # # #     # Remove extra spaces and dashes
# # # # #     title = title.strip(" -")
# # # # #     # Keep under 70 chars
# # # # #     if len(title) > 70:
# # # # #         title = title[:67] + "..."
# # # # #     return title


# # # # # def _clean_body(body: str) -> str:
# # # # #     """Ensure link is in body, not title"""
# # # # #     # Make sure gaper.io link is in body
# # # # #     if "gaper.io" not in body:
# # # # #         body += f"\n\nLearn more at https://gaper.io"
# # # # #     return body


# # # # # def post_to_notion_session(title: str, body: str) -> dict:
# # # # #     """
# # # # #     Posts to Notion using saved browser session.
# # # # #     EXACT same logic as post_to_notion_browser.py
# # # # #     """
# # # # #     if not NOTION_DATABASE_URL:
# # # # #         return {
# # # # #             "status": "failed",
# # # # #             "detail": "NOTION_DATABASE_URL not set in config. Add to config.py or .env"
# # # # #         }
    
# # # # #     if not PROFILE_DIR.exists():
# # # # #         return {
# # # # #             "status": "failed",
# # # # #             "detail": "Notion session not found. Run 'python setup_notion_login.py' first."
# # # # #         }

# # # # #     # Clean title and body
# # # # #     clean_title = _clean_title(title)
# # # # #     clean_body = _clean_body(body)

# # # # #     try:
# # # # #         with sync_playwright() as p:
# # # # #             context = p.chromium.launch_persistent_context(
# # # # #                 user_data_dir=str(PROFILE_DIR),
# # # # #                 headless=False,
# # # # #                 channel="chrome",
# # # # #                 viewport={"width": 1440, "height": 900},
# # # # #             )
# # # # #             page = context.new_page()
            
# # # # #             logger.info(f"🌐 Opening Notion: {NOTION_DATABASE_URL}")
# # # # #             page.goto(NOTION_DATABASE_URL, wait_until="domcontentloaded", timeout=30000)
# # # # #             page.wait_for_timeout(3000)  # Wait for React to render

# # # # #             # Check if logged in
# # # # #             if "login" in page.url.lower():
# # # # #                 context.close()
# # # # #                 return {
# # # # #                     "status": "failed",
# # # # #                     "detail": "Notion session expired. Run 'python setup_notion_login.py' again."
# # # # #                 }

# # # # #             # ============================================
# # # # #             # Click "New" button - Multiple strategies
# # # # #             # ============================================
            
# # # # #             logger.info("🆕 Creating new page...")
            
# # # # #             # Strategy 1: Try role-based with scroll
# # # # #             try:
# # # # #                 new_button = page.get_by_role("button", name="New").first
# # # # #                 if new_button.count() > 0:
# # # # #                     new_button.scroll_into_view_if_needed()
# # # # #                     page.wait_for_timeout(500)
# # # # #                     new_button.click()
# # # # #                     logger.info("✅ Clicked 'New' button (Strategy 1)")
# # # # #                 else:
# # # # #                     raise Exception("Button not found")
# # # # #             except Exception:
# # # # #                 # Strategy 2: Try CSS selector
# # # # #                 try:
# # # # #                     new_button = page.locator('button:has-text("New")')
# # # # #                     new_button.scroll_into_view_if_needed()
# # # # #                     page.wait_for_timeout(500)
# # # # #                     new_button.click()
# # # # #                     logger.info("✅ Clicked 'New' button (Strategy 2)")
# # # # #                 except Exception:
# # # # #                     # Strategy 3: Keyboard shortcut
# # # # #                     logger.info("⌨️ Using Ctrl+N keyboard shortcut")
# # # # #                     page.keyboard.press("Control+N")
            
# # # # #             page.wait_for_timeout(2000)

# # # # #             # Type title (clean, no links)
# # # # #             logger.info(f"📝 Typing title: {clean_title}")
# # # # #             page.keyboard.type(clean_title, delay=15)
# # # # #             page.keyboard.press("Enter")
# # # # #             page.wait_for_timeout(500)

# # # # #             # Type body (with link)
# # # # #             logger.info("📝 Typing content...")
# # # # #             for line in clean_body.split("\n"):
# # # # #                 if line.strip():
# # # # #                     page.keyboard.type(line, delay=8)
# # # # #                 page.keyboard.press("Enter")
# # # # #                 # Keep cursor in view
# # # # #                 page.evaluate("""() => {
# # # # #                     const el = document.activeElement;
# # # # #                     if (el) el.scrollIntoView({block: 'center', behavior: 'instant'});
# # # # #                 }""")
# # # # #                 page.wait_for_timeout(150)

# # # # #             page.wait_for_timeout(2000)
            
# # # # #             # Get page URL
# # # # #             current_url = page.url
            
# # # # #             logger.info(f"✅ Notion page '{clean_title}' created successfully!")
            
# # # # #             # DON'T close browser - let user review and publish manually
# # # # #             # context.close()  # Commented out so browser stays open
            
# # # # #             return {
# # # # #                 "status": "success",
# # # # #                 "detail": f"Notion page '{clean_title}' created. Browser open for review.",
# # # # #                 "url": current_url
# # # # #             }

# # # # #     except Exception as e:
# # # # #         logger.error(f"Notion posting failed: {e}")
# # # # #         return {"status": "failed", "detail": str(e)}



# # # # # src/notion_session_poster.py
# # # # """
# # # # Notion posting via saved BROWSER session - FIXED typing issue
# # # # """

# # # # import logging
# # # # import re
# # # # import time
# # # # from pathlib import Path
# # # # from playwright.sync_api import sync_playwright, TimeoutError
# # # # import config

# # # # logger = logging.getLogger(__name__)

# # # # PROFILE_DIR = Path(config.BASE_DIR) / "sessions" / "notion_profile"
# # # # NOTION_DATABASE_URL = getattr(config, "NOTION_DATABASE_URL", "")


# # # # def _clean_title(raw_title: str) -> str:
# # # #     """Clean title - remove links, markdown, keep under 70 chars"""
# # # #     title = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", raw_title)
# # # #     title = re.sub(r"https?://\S+", "", title)
# # # #     title = title.replace("**", "").replace("*", "")
# # # #     title = title.strip(" -")
# # # #     if len(title) > 70:
# # # #         title = title[:67] + "..."
# # # #     return title


# # # # def _clean_body(body: str) -> str:
# # # #     """Clean body - preserve markdown formatting"""
# # # #     # Remove any weird characters
# # # #     body = body.replace("—", ", ").replace("–", ", ")
# # # #     return body


# # # # def post_to_notion_session(title: str, body: str) -> dict:
# # # #     """
# # # #     Posts to Notion using saved browser session.
# # # #     Types title + content into a new page.
# # # #     """
# # # #     if not NOTION_DATABASE_URL:
# # # #         return {
# # # #             "status": "failed",
# # # #             "detail": "NOTION_DATABASE_URL not set in config. Add to config.py or .env"
# # # #         }
    
# # # #     if not PROFILE_DIR.exists():
# # # #         return {
# # # #             "status": "failed",
# # # #             "detail": "Notion session not found. Run 'python setup_notion_login.py' first."
# # # #         }

# # # #     clean_title = _clean_title(title)
# # # #     clean_body = _clean_body(body)

# # # #     try:
# # # #         with sync_playwright() as p:
# # # #             context = p.chromium.launch_persistent_context(
# # # #                 user_data_dir=str(PROFILE_DIR),
# # # #                 headless=False,
# # # #                 channel="chrome",
# # # #                 viewport={"width": 1440, "height": 900},
# # # #             )
# # # #             page = context.new_page()
            
# # # #             logger.info(f"🌐 Opening Notion: {NOTION_DATABASE_URL}")
# # # #             page.goto(NOTION_DATABASE_URL, wait_until="domcontentloaded", timeout=30000)
            
# # # #             # Wait for page to fully load
# # # #             page.wait_for_timeout(3000)

# # # #             # Check if logged in
# # # #             if "login" in page.url.lower():
# # # #                 context.close()
# # # #                 return {
# # # #                     "status": "failed",
# # # #                     "detail": "Notion session expired. Run 'python setup_notion_login.py' again."
# # # #                 }

# # # #             # ============================================
# # # #             # Click "New" button - Multiple strategies
# # # #             # ============================================
            
# # # #             logger.info("🆕 Creating new page...")
            
# # # #             clicked = False
            
# # # #             # Strategy 1: Try by role
# # # #             try:
# # # #                 new_button = page.get_by_role("button", name="New").first
# # # #                 if new_button.count() > 0:
# # # #                     new_button.scroll_into_view_if_needed()
# # # #                     page.wait_for_timeout(500)
# # # #                     new_button.click()
# # # #                     logger.info("✅ Clicked 'New' button (Strategy 1)")
# # # #                     clicked = True
# # # #             except Exception:
# # # #                 pass
            
# # # #             # Strategy 2: Try CSS selector
# # # #             if not clicked:
# # # #                 try:
# # # #                     new_button = page.locator('button:has-text("New")')
# # # #                     if new_button.count() > 0:
# # # #                         new_button.scroll_into_view_if_needed()
# # # #                         page.wait_for_timeout(500)
# # # #                         new_button.click()
# # # #                         logger.info("✅ Clicked 'New' button (Strategy 2)")
# # # #                         clicked = True
# # # #                 except Exception:
# # # #                     pass
            
# # # #             # Strategy 3: Keyboard shortcut
# # # #             if not clicked:
# # # #                 logger.info("⌨️ Using Ctrl+N keyboard shortcut")
# # # #                 page.keyboard.press("Control+N")
# # # #                 clicked = True
            
# # # #             # Wait for editor to load
# # # #             page.wait_for_timeout(2000)

# # # #             # ============================================
# # # #             # Type title
# # # #             # ============================================
            
# # # #             logger.info(f"📝 Typing title: {clean_title}")
            
# # # #             # Click on the page to focus
# # # #             page.click('body')
# # # #             page.wait_for_timeout(500)
            
# # # #             # Type title
# # # #             page.keyboard.type(clean_title, delay=15)
# # # #             page.keyboard.press("Enter")
# # # #             page.wait_for_timeout(500)

# # # #             # ============================================
# # # #             # Type body - line by line with proper formatting
# # # #             # ============================================
            
# # # #             logger.info("📝 Typing content...")
            
# # # #             # Split body into lines
# # # #             lines = clean_body.split("\n")
            
# # # #             for line in lines:
# # # #                 if line.strip():
# # # #                     # Handle markdown headers
# # # #                     if line.startswith("##"):
# # # #                         # Type heading
# # # #                         page.keyboard.type(line, delay=8)
# # # #                     elif line.startswith("* "):
# # # #                         # Type bullet
# # # #                         page.keyboard.type(line, delay=8)
# # # #                     elif line.startswith("[[LINK:"):
# # # #                         # Handle link marker
# # # #                         match = re.match(r"\[\[LINK:(.*?)\|(.*?)\]\]", line.strip())
# # # #                         if match:
# # # #                             anchor_text, link_url = match.group(1), match.group(2)
# # # #                             # Type anchor text
# # # #                             page.keyboard.type(anchor_text, delay=8)
# # # #                             # Select text and add link
# # # #                             page.keyboard.press("Shift+Home")
# # # #                             page.wait_for_timeout(300)
# # # #                             page.keyboard.press("Control+K")
# # # #                             page.wait_for_timeout(500)
# # # #                             page.keyboard.type(link_url, delay=10)
# # # #                             page.wait_for_timeout(500)
# # # #                             page.keyboard.press("Enter")
# # # #                             page.wait_for_timeout(300)
# # # #                             page.keyboard.press("End")
# # # #                     else:
# # # #                         # Type regular text
# # # #                         page.keyboard.type(line, delay=8)
                
# # # #                 # Press Enter after each line
# # # #                 page.keyboard.press("Enter")
# # # #                 page.wait_for_timeout(150)

# # # #             page.wait_for_timeout(2000)
            
# # # #             # Get page URL
# # # #             current_url = page.url
            
# # # #             logger.info(f"✅ Notion page '{clean_title}' created successfully!")
            
# # # #             # Keep browser open for review
# # # #             # context.close()  # Commented out - user can close manually
            
# # # #             return {
# # # #                 "status": "success",
# # # #                 "detail": f"Notion page '{clean_title}' created. Browser open for review.",
# # # #                 "url": current_url
# # # #             }

# # # #     except Exception as e:
# # # #         logger.error(f"Notion posting failed: {e}")
# # # #         return {"status": "failed", "detail": str(e)}




# # # # src/notion_session_poster.py
# # # """
# # # Notion posting via saved BROWSER session - FULLY FIXED
# # # """

# # # import logging
# # # import re
# # # from pathlib import Path
# # # from playwright.sync_api import sync_playwright, TimeoutError
# # # import config

# # # logger = logging.getLogger(__name__)

# # # PROFILE_DIR = Path(config.BASE_DIR) / "sessions" / "notion_profile"
# # # NOTION_DATABASE_URL = getattr(config, "NOTION_DATABASE_URL", "")


# # # def _clean_title(raw_title: str) -> str:
# # #     """Clean title - remove links, markdown, keep under 70 chars"""
# # #     title = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", raw_title)
# # #     title = re.sub(r"https?://\S+", "", title)
# # #     title = title.replace("**", "").replace("*", "")
# # #     title = title.strip(" -")
# # #     if len(title) > 70:
# # #         title = title[:67] + "..."
# # #     return title


# # # def post_to_notion_session(title: str, body: str) -> dict:
# # #     """
# # #     Posts to Notion using saved browser session.
# # #     CORRECT technique for Notion posting.
# # #     """
    
# # #     # Validate config
# # #     if not NOTION_DATABASE_URL:
# # #         return {
# # #             "status": "failed",
# # #             "detail": "NOTION_DATABASE_URL not set. Add to config.py or .env"
# # #         }
    
# # #     if not PROFILE_DIR.exists():
# # #         return {
# # #             "status": "failed",
# # #             "detail": "Notion session not found. Run 'python setup_notion_login.py' first."
# # #         }

# # #     clean_title = _clean_title(title)
    
# # #     # Extract heading and body content
# # #     lines = body.split("\n")
# # #     heading = lines[0].strip() if lines else clean_title
# # #     body_content = "\n".join(lines[1:]).strip() if len(lines) > 1 else body

# # #     try:
# # #         with sync_playwright() as p:
# # #             # Launch browser with saved session
# # #             context = p.chromium.launch_persistent_context(
# # #                 user_data_dir=str(PROFILE_DIR),
# # #                 headless=False,
# # #                 channel="chrome",
# # #                 viewport={"width": 1440, "height": 900},
# # #                 args=[
# # #                     '--disable-blink-features=AutomationControlled',
# # #                     '--no-sandbox',
# # #                 ]
# # #             )
            
# # #             page = context.pages[0] if context.pages else context.new_page()
            
# # #             # Step 1: Open Notion database
# # #             logger.info(f"🌐 Opening Notion: {NOTION_DATABASE_URL}")
# # #             page.goto(NOTION_DATABASE_URL, wait_until="domcontentloaded", timeout=30000)
            
# # #             # Wait for React to fully load
# # #             page.wait_for_timeout(3000)
            
# # #             # Check if logged in
# # #             current_url = page.url.lower()
# # #             if "login" in current_url:
# # #                 context.close()
# # #                 return {
# # #                     "status": "failed",
# # #                     "detail": "Notion session expired. Run 'python setup_notion_login.py' again."
# # #                 }
            
# # #             # Step 2: Click "New" button
# # #             logger.info("🆕 Finding and clicking 'New' button...")
            
# # #             clicked = False
            
# # #             # Try different strategies
# # #             strategies = [
# # #                 lambda: page.locator('button:has-text("New")').first,
# # #                 lambda: page.get_by_role("button", name="New").first,
# # #                 lambda: page.locator('[data-testid="new-page-button"]').first,
# # #                 lambda: page.locator('div[role="button"]:has-text("New")').first,
# # #             ]
            
# # #             for strategy in strategies:
# # #                 try:
# # #                     button = strategy()
# # #                     if button.count() > 0 and button.is_visible():
# # #                         button.scroll_into_view_if_needed()
# # #                         page.wait_for_timeout(500)
# # #                         button.click()
# # #                         logger.info("✅ 'New' button clicked")
# # #                         clicked = True
# # #                         break
# # #                 except Exception:
# # #                     continue
            
# # #             # If all strategies fail, use keyboard shortcut
# # #             if not clicked:
# # #                 logger.info("⌨️ Using Ctrl+N keyboard shortcut")
# # #                 page.keyboard.press("Control+N")
            
# # #             # Wait for new page to open
# # #             page.wait_for_timeout(3000)
            
# # #             # Step 3: Type title
# # #             logger.info(f"📝 Typing title: {clean_title}")
            
# # #             # Click on the page to focus
# # #             try:
# # #                 page.click('div[contenteditable="true"]')
# # #             except:
# # #                 page.click('body')
            
# # #             page.wait_for_timeout(500)
            
# # #             # Type title and press Enter
# # #             page.keyboard.type(clean_title, delay=20)
# # #             page.keyboard.press("Enter")
# # #             page.wait_for_timeout(1000)
            
# # #             # Step 4: Type body content
# # #             logger.info("📝 Typing content...")
            
# # #             # Process each line
# # #             for line in body_content.split("\n"):
# # #                 line = line.strip()
# # #                 if not line:
# # #                     page.keyboard.press("Enter")
# # #                     page.wait_for_timeout(100)
# # #                     continue
                
# # #                 # Handle markdown
# # #                 if line.startswith("## "):
# # #                     # Heading
# # #                     page.keyboard.type(line, delay=10)
# # #                 elif line.startswith("* "):
# # #                     # Bullet point
# # #                     page.keyboard.type(line, delay=10)
# # #                 elif line.startswith("[[LINK:"):
# # #                     # Link marker - convert to clickable link
# # #                     match = re.match(r"\[\[LINK:(.*?)\|(.*?)\]\]", line)
# # #                     if match:
# # #                         anchor_text, link_url = match.group(1), match.group(2)
# # #                         page.keyboard.type(anchor_text, delay=8)
# # #                         page.wait_for_timeout(300)
# # #                         page.keyboard.press("Shift+Home")
# # #                         page.wait_for_timeout(300)
# # #                         page.keyboard.press("Control+K")
# # #                         page.wait_for_timeout(500)
# # #                         page.keyboard.type(link_url, delay=10)
# # #                         page.wait_for_timeout(500)
# # #                         page.keyboard.press("Enter")
# # #                         page.wait_for_timeout(300)
# # #                         page.keyboard.press("End")
# # #                 else:
# # #                     # Regular text
# # #                     page.keyboard.type(line, delay=10)
                
# # #                 page.keyboard.press("Enter")
# # #                 page.wait_for_timeout(150)
            
# # #             page.wait_for_timeout(2000)
            
# # #             # Get page URL
# # #             current_url = page.url
            
# # #             logger.info(f"✅ Notion page '{clean_title}' created successfully!")
            
# # #             # Keep browser open for review
# # #             # context.close() - COMMENTED OUT so user can review
            
# # #             return {
# # #                 "status": "success",
# # #                 "detail": f"Notion page '{clean_title}' created. Browser open for review.",
# # #                 "url": current_url
# # #             }

# # #     except Exception as e:
# # #         logger.error(f"Notion posting failed: {e}")
# # #         return {"status": "failed", "detail": str(e)}




# # """
# # Notion posting via saved BROWSER session.

# # Fixes over the previous version:
# # 1. Typing was silently cutting off mid-line on some blocks (React's
# #    editor couldn't keep up with fast raw type()). Every line is now
# #    typed, then VERIFIED against the page's visible text, and retried
# #    (slower, in smaller chunks) if it didn't fully land - same pattern
# #    used to fix the Contra half-typed bug.
# # 2. The "make link clickable" step (select text -> Ctrl+K -> type URL)
# #    had no confirmation that Notion's link popup actually opened before
# #    typing the URL into it, so the URL was sometimes typed into the
# #    editor as plain text instead of the popup. Now it explicitly waits
# #    for the link popup input to appear; if it doesn't, it falls back to
# #    just appending the URL as plain visible text instead of silently
# #    failing.
# # """

# # import logging
# # import re
# # from pathlib import Path
# # from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
# # import config

# # logger = logging.getLogger(__name__)

# # PROFILE_DIR = Path(config.BASE_DIR) / "sessions" / "notion_profile"
# # NOTION_DATABASE_URL = getattr(config, "NOTION_DATABASE_URL", "")


# # def _clean_title(raw_title: str) -> str:
# #     title = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", raw_title)
# #     title = re.sub(r"https?://\S+", "", title)
# #     title = title.replace("**", "").replace("*", "")
# #     title = title.strip(" -")
# #     if len(title) > 70:
# #         title = title[:67] + "..."
# #     return title


# # def _type_line_reliably(page, text: str, max_attempts: int = 3) -> bool:
# #     """
# #     Types one line/block of text and verifies it actually landed in the
# #     page before moving on. Fixes the 'half-typed then moves to next line
# #     anyway' bug - fast type() can outrun Notion's own React editor, so we
# #     check the page's visible text contains what we just typed, and retry
# #     slower/in smaller chunks if it's missing or truncated.
# #     """
# #     if not text.strip():
# #         return True  # nothing to verify for a blank line

# #     for attempt in range(1, max_attempts + 1):
# #         if attempt == 1:
# #             page.keyboard.type(text, delay=15)
# #         else:
# #             logger.info(f"  Retry #{attempt} for line, typing slower in chunks...")
# #             for i in range(0, len(text), 25):
# #                 chunk = text[i:i + 25]
# #                 page.keyboard.type(chunk, delay=30)
# #                 page.wait_for_timeout(100)

# #         page.wait_for_timeout(400)

# #         try:
# #             body_text = page.locator("body").inner_text()
# #         except Exception:
# #             body_text = ""

# #         # Check the last ~40 non-space chars of what we typed are visible
# #         # somewhere on the page - good enough signal it landed, without
# #         # needing an exact full-line selector (Notion blocks don't expose
# #         # one reliably).
# #         check_fragment = text.strip()[-40:] if len(text.strip()) > 40 else text.strip()
# #         if check_fragment and check_fragment in body_text:
# #             return True

# #         logger.warning(f"  Line may not have fully landed (attempt {attempt}/{max_attempts}): '{text[:50]}...'")

# #     logger.warning(f"  Proceeding anyway after {max_attempts} attempts - could not verify: '{text[:50]}...'")
# #     return False


# # def _make_link_clickable(page, anchor_text: str, url: str) -> bool:
# #     """
# #     Types anchor_text, selects it, opens Notion's link popup (Ctrl+K),
# #     and ONLY types the URL if the popup actually appeared. If it didn't
# #     open (timing/layout change), falls back to leaving the anchor text
# #     plain and appending the raw URL next to it, so the link is at least
# #     visibly present even if not hyperlinked.
# #     """
# #     page.keyboard.type(anchor_text, delay=10)
# #     page.wait_for_timeout(300)
# #     page.keyboard.press("Shift+Home")
# #     page.wait_for_timeout(300)
# #     page.keyboard.press("Control+K")

# #     # Wait for Notion's link popup input to actually appear before typing
# #     # into it - this is the missing check that caused URLs to sometimes
# #     # get typed into the editor as plain text instead.
# #     popup_selectors = [
# #         'input[placeholder*="Paste link" i]',
# #         'input[placeholder*="Search or paste" i]',
# #         '[data-testid="link-input"]',
# #         'div[role="dialog"] input[type="text"]',
# #     ]
# #     popup_input = None
# #     for sel in popup_selectors:
# #         try:
# #             el = page.locator(sel).first
# #             el.wait_for(state="visible", timeout=2500)
# #             popup_input = el
# #             break
# #         except PWTimeout:
# #             continue
# #         except Exception:
# #             continue

# #     if popup_input:
# #         popup_input.fill(url)
# #         page.wait_for_timeout(400)
# #         page.keyboard.press("Enter")
# #         page.wait_for_timeout(400)
# #         page.keyboard.press("End")
# #         logger.info("  Link popup confirmed and URL applied.")
# #         return True

# #     # Fallback: popup never appeared - back out of whatever Ctrl+K did
# #     # (Escape is safe whether or not anything opened) and just make the
# #     # link visible as plain text instead of silently losing it.
# #     logger.warning("  Link popup did not appear - falling back to plain visible URL text.")
# #     page.keyboard.press("Escape")
# #     page.wait_for_timeout(200)
# #     page.keyboard.press("End")
# #     page.keyboard.type(f" ({url})", delay=10)
# #     page.wait_for_timeout(300)
# #     return False


# # def post_to_notion_session(title: str, body: str) -> dict:
# #     """
# #     Posts to Notion using the saved browser session (sessions/notion_profile,
# #     created once via setup_notion_login.py). Types the title + body into a
# #     new database entry, verifying each line lands and confirming the
# #     backlink actually becomes clickable. Leaves the browser open for your
# #     own review/Publish click - never auto-publishes.
# #     """
# #     if not NOTION_DATABASE_URL:
# #         return {
# #             "status": "failed",
# #             "detail": "NOTION_DATABASE_URL not set. Add to config.py or .env"
# #         }

# #     if not PROFILE_DIR.exists():
# #         return {
# #             "status": "failed",
# #             "detail": "Notion session not found. Run 'python setup_notion_login.py' first."
# #         }

# #     clean_title = _clean_title(title)
# #     lines = body.split("\n")
# #     heading = lines[0].strip() if lines else clean_title
# #     body_content = "\n".join(lines[1:]).strip() if len(lines) > 1 else body

# #     try:
# #         with sync_playwright() as p:
# #             context = p.chromium.launch_persistent_context(
# #                 user_data_dir=str(PROFILE_DIR),
# #                 headless=False,
# #                 channel="chrome",
# #                 viewport={"width": 1440, "height": 900},
# #                 args=[
# #                     '--disable-blink-features=AutomationControlled',
# #                     '--no-sandbox',
# #                 ]
# #             )

# #             page = context.pages[0] if context.pages else context.new_page()

# #             logger.info(f"Opening Notion: {NOTION_DATABASE_URL}")
# #             page.goto(NOTION_DATABASE_URL, wait_until="domcontentloaded", timeout=30000)
# #             page.wait_for_timeout(3000)

# #             current_url = page.url.lower()
# #             if "login" in current_url:
# #                 context.close()
# #                 return {
# #                     "status": "failed",
# #                     "detail": "Notion session expired. Run 'python setup_notion_login.py' again."
# #                 }

# #             logger.info("Finding and clicking 'New' button...")
# #             clicked = False
# #             strategies = [
# #                 lambda: page.locator('button:has-text("New")').first,
# #                 lambda: page.get_by_role("button", name="New").first,
# #                 lambda: page.locator('[data-testid="new-page-button"]').first,
# #                 lambda: page.locator('div[role="button"]:has-text("New")').first,
# #             ]
# #             for strategy in strategies:
# #                 try:
# #                     button = strategy()
# #                     if button.count() > 0 and button.is_visible():
# #                         button.scroll_into_view_if_needed()
# #                         page.wait_for_timeout(500)
# #                         button.click()
# #                         logger.info("'New' button clicked.")
# #                         clicked = True
# #                         break
# #                 except Exception:
# #                     continue

# #             if not clicked:
# #                 logger.info("Falling back to Ctrl+N keyboard shortcut.")
# #                 page.keyboard.press("Control+N")

# #             page.wait_for_timeout(3000)

# #             # ---- Title ----
# #             logger.info(f"Typing title: {clean_title}")
# #             try:
# #                 page.click('div[contenteditable="true"]')
# #             except Exception:
# #                 page.click('body')
# #             page.wait_for_timeout(500)

# #             title_ok = _type_line_reliably(page, clean_title)
# #             page.keyboard.press("Enter")
# #             page.wait_for_timeout(800)

# #             # ---- Body ----
# #             logger.info("Typing content...")
# #             link_made_clickable = True
# #             for line in body_content.split("\n"):
# #                 stripped = line.strip()

# #                 if not stripped:
# #                     page.keyboard.press("Enter")
# #                     page.wait_for_timeout(100)
# #                     continue

# #                 if stripped.startswith("[[LINK:"):
# #                     match = re.match(r"\[\[LINK:(.*?)\|(.*?)\]\]", stripped)
# #                     if match:
# #                         anchor_text, link_url = match.group(1), match.group(2)
# #                         link_made_clickable = _make_link_clickable(page, anchor_text, link_url)
# #                     else:
# #                         _type_line_reliably(page, stripped)
# #                 else:
# #                     _type_line_reliably(page, stripped)

# #                 page.keyboard.press("Enter")
# #                 # keep the cursor's block in view as content grows past the viewport
# #                 try:
# #                     page.evaluate("""() => {
# #                         const el = document.activeElement;
# #                         if (el) el.scrollIntoView({block: 'center', behavior: 'instant'});
# #                     }""")
# #                 except Exception:
# #                     pass
# #                 page.wait_for_timeout(150)

# #             page.wait_for_timeout(1500)
# #             current_url = page.url

# #             logger.info(f"Notion page '{clean_title}' created.")

# #             detail = f"Notion page '{clean_title}' created. Browser open for review."
# #             if not link_made_clickable:
# #                 detail += " NOTE: the backlink could not be confirmed as clickable - check it manually before publishing."
# #             if not title_ok:
# #                 detail += " NOTE: title may not have fully landed - please verify it in the browser."

# #             return {
# #                 "status": "success",
# #                 "detail": detail,
# #                 "url": current_url,
# #                 "link_confirmed": link_made_clickable,
# #             }

# #     except Exception as e:
# #         logger.error(f"Notion posting failed: {e}")
# #         return {"status": "failed", "detail": str(e)}



# """
# Notion posting via saved BROWSER session.

# Fixes in this version:
# 1. Half-typed lines: every line is typed then VERIFIED against the
#    page's visible text, retried slower/in chunks if it didn't land.
# 2. Link not clickable: waits for Notion's actual link popup to appear
#    before typing the URL into it; falls back to visible plain text if
#    the popup never shows, instead of silently failing.
# 3. Markdown not converting (## heading, * bullet): Notion only converts
#    these into real blocks if the marker ('##' or '*') and the space
#    after it are each registered as their own keystroke, with a short
#    pause for Notion's editor to react. Typing the whole line in one fast
#    burst was skipping that conversion - markers now get typed and paused
#    separately before the rest of the line.
# 4. "Wrong browser / not the real workspace": this script deliberately
#    uses its OWN separate Chrome process (a persistent automation profile
#    at sessions/notion_profile), not your everyday Chrome - that's by
#    design, so automation never touches your regular browsing session.
#    IMPORTANT: it is still logged into your real Notion ACCOUNT and real
#    WORKSPACE (same account you logged into during setup_notion_login.py)
#    - the page it creates is a genuine page in your genuine workspace.
#    The Share/Publish button is at the top-right of THAT automated
#    window, not in your regular Chrome. The window is brought to the
#    front and maximized at the end of this script specifically so it's
#    easy to find and use.
# """

# import logging
# import re
# from pathlib import Path
# from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
# import config

# logger = logging.getLogger(__name__)

# PROFILE_DIR = Path(config.BASE_DIR) / "sessions" / "notion_profile"
# NOTION_DATABASE_URL = getattr(config, "NOTION_DATABASE_URL", "")


# def _clean_title(raw_title: str) -> str:
#     title = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", raw_title)
#     title = re.sub(r"https?://\S+", "", title)
#     title = title.replace("**", "").replace("*", "")
#     title = title.strip(" -")
#     if len(title) > 70:
#         title = title[:67] + "..."
#     return title


# def _type_line_reliably(page, text: str, max_attempts: int = 3) -> bool:
#     """
#     Types text and verifies it actually landed in the page before moving
#     on, retrying slower/in smaller chunks if it didn't fully land.
#     """
#     if not text.strip():
#         return True

#     for attempt in range(1, max_attempts + 1):
#         if attempt == 1:
#             page.keyboard.type(text, delay=15)
#         else:
#             logger.info(f"  Retry #{attempt} for line, typing slower in chunks...")
#             for i in range(0, len(text), 25):
#                 chunk = text[i:i + 25]
#                 page.keyboard.type(chunk, delay=30)
#                 page.wait_for_timeout(100)

#         page.wait_for_timeout(400)

#         try:
#             body_text = page.locator("body").inner_text()
#         except Exception:
#             body_text = ""

#         check_fragment = text.strip()[-40:] if len(text.strip()) > 40 else text.strip()
#         if check_fragment and check_fragment in body_text:
#             return True

#         logger.warning(f"  Line may not have fully landed (attempt {attempt}/{max_attempts}): '{text[:50]}...'")

#     logger.warning(f"  Proceeding anyway after {max_attempts} attempts - could not verify: '{text[:50]}...'")
#     return False


# def _type_markdown_line(page, line: str):
#     """
#     Types a line so Notion's markdown shortcuts actually trigger.
#     '## ' and '* ' only convert into a real heading/bullet if the marker
#     and the space after it land as distinct keystrokes with the editor
#     given a moment to react - so those get typed separately with short
#     pauses, then the rest of the line is typed and verified normally.
#     """
#     if line.startswith("## "):
#         page.keyboard.type("##", delay=15)
#         page.wait_for_timeout(150)
#         page.keyboard.type(" ", delay=15)
#         page.wait_for_timeout(250)  # let Notion convert the block to a heading
#         rest = line[3:]
#         if rest:
#             _type_line_reliably(page, rest)
#     elif line.startswith("* "):
#         page.keyboard.type("*", delay=15)
#         page.wait_for_timeout(150)
#         page.keyboard.type(" ", delay=15)
#         page.wait_for_timeout(250)  # let Notion convert the block to a bullet
#         rest = line[2:]
#         if rest:
#             _type_line_reliably(page, rest)
#     else:
#         _type_line_reliably(page, line)


# def _make_link_clickable(page, anchor_text: str, url: str) -> bool:
#     """
#     Types anchor_text, selects it, opens Notion's link popup (Ctrl+K),
#     and ONLY types the URL if the popup actually appeared. Falls back to
#     visible plain text if the popup never shows.
#     """
#     page.keyboard.type(anchor_text, delay=10)
#     page.wait_for_timeout(300)
#     page.keyboard.press("Shift+Home")
#     page.wait_for_timeout(300)
#     page.keyboard.press("Control+K")

#     popup_selectors = [
#         'input[placeholder*="Paste link" i]',
#         'input[placeholder*="Search or paste" i]',
#         '[data-testid="link-input"]',
#         'div[role="dialog"] input[type="text"]',
#     ]
#     popup_input = None
#     for sel in popup_selectors:
#         try:
#             el = page.locator(sel).first
#             el.wait_for(state="visible", timeout=2500)
#             popup_input = el
#             break
#         except PWTimeout:
#             continue
#         except Exception:
#             continue

#     if popup_input:
#         popup_input.fill(url)
#         page.wait_for_timeout(400)
#         page.keyboard.press("Enter")
#         page.wait_for_timeout(400)
#         page.keyboard.press("End")
#         logger.info("  Link popup confirmed and URL applied.")
#         return True

#     logger.warning("  Link popup did not appear - falling back to plain visible URL text.")
#     page.keyboard.press("Escape")
#     page.wait_for_timeout(200)
#     page.keyboard.press("End")
#     page.keyboard.type(f" ({url})", delay=10)
#     page.wait_for_timeout(300)
#     return False


# def post_to_notion_session(title: str, body: str) -> dict:
#     """
#     Posts to Notion using the saved browser session (sessions/notion_profile,
#     created once via setup_notion_login.py). Types the title + body into a
#     new database entry, verifying each line lands and confirming the
#     backlink actually becomes clickable. Leaves the browser open, brought
#     to the front, for your own review/Publish click - never auto-publishes.
#     """
#     if not NOTION_DATABASE_URL:
#         return {
#             "status": "failed",
#             "detail": "NOTION_DATABASE_URL not set. Add to config.py or .env"
#         }

#     if not PROFILE_DIR.exists():
#         return {
#             "status": "failed",
#             "detail": "Notion session not found. Run 'python setup_notion_login.py' first."
#         }

#     clean_title = _clean_title(title)
#     lines = body.split("\n")
#     body_content = "\n".join(lines[1:]).strip() if len(lines) > 1 else body

#     try:
#         with sync_playwright() as p:
#             context = p.chromium.launch_persistent_context(
#                 user_data_dir=str(PROFILE_DIR),
#                 headless=False,
#                 channel="chrome",
#                 viewport=None,  # None + --start-maximized lets Chrome use the FULL actual screen size, instead of being locked to a small fixed viewport
#                 args=[
#                     '--disable-blink-features=AutomationControlled',
#                     '--no-sandbox',
#                     '--start-maximized',
#                 ]
#             )

#             page = context.pages[0] if context.pages else context.new_page()
#             page.wait_for_timeout(500)
#             page.bring_to_front()

#             logger.info(f"Opening Notion: {NOTION_DATABASE_URL}")
#             page.goto(NOTION_DATABASE_URL, wait_until="domcontentloaded", timeout=30000)
#             page.wait_for_timeout(3000)

#             current_url = page.url.lower()
#             if "login" in current_url:
#                 context.close()
#                 return {
#                     "status": "failed",
#                     "detail": "Notion session expired. Run 'python setup_notion_login.py' again."
#                 }

#             logger.info("Finding and clicking 'New' button...")
#             clicked = False
#             strategies = [
#                 lambda: page.locator('button:has-text("New")').first,
#                 lambda: page.get_by_role("button", name="New").first,
#                 lambda: page.locator('[data-testid="new-page-button"]').first,
#                 lambda: page.locator('div[role="button"]:has-text("New")').first,
#             ]
#             for strategy in strategies:
#                 try:
#                     button = strategy()
#                     if button.count() > 0 and button.is_visible():
#                         button.scroll_into_view_if_needed()
#                         page.wait_for_timeout(500)
#                         button.click()
#                         logger.info("'New' button clicked.")
#                         clicked = True
#                         break
#                 except Exception:
#                     continue

#             if not clicked:
#                 logger.info("Falling back to Ctrl+N keyboard shortcut.")
#                 page.keyboard.press("Control+N")

#             page.wait_for_timeout(3000)

#             # ---- Title ----
#             logger.info(f"Typing title: {clean_title}")
#             try:
#                 page.click('div[contenteditable="true"]')
#             except Exception:
#                 page.click('body')
#             page.wait_for_timeout(500)

#             title_ok = _type_line_reliably(page, clean_title)
#             page.keyboard.press("Enter")
#             page.wait_for_timeout(800)

#             # ---- Body ----
#             logger.info("Typing content...")
#             link_made_clickable = True
#             for line in body_content.split("\n"):
#                 stripped = line.strip()

#                 if not stripped:
#                     page.keyboard.press("Enter")
#                     page.wait_for_timeout(100)
#                     continue

#                 if stripped.startswith("[[LINK:"):
#                     match = re.match(r"\[\[LINK:(.*?)\|(.*?)\]\]", stripped)
#                     if match:
#                         anchor_text, link_url = match.group(1), match.group(2)
#                         link_made_clickable = _make_link_clickable(page, anchor_text, link_url)
#                     else:
#                         _type_line_reliably(page, stripped)
#                 else:
#                     _type_markdown_line(page, stripped)

#                 page.keyboard.press("Enter")
#                 try:
#                     page.evaluate("""() => {
#                         const el = document.activeElement;
#                         if (el) el.scrollIntoView({block: 'center', behavior: 'instant'});
#                     }""")
#                 except Exception:
#                     pass
#                 page.wait_for_timeout(150)

#             page.wait_for_timeout(1500)
#             current_url = page.url

#             # Bring window to front one more time and scroll to top so the
#             # Share/Publish button (top-right of the page) is immediately
#             # visible - this IS the real workspace, just this dedicated
#             # automation window rather than your everyday Chrome.
#             try:
#                 page.evaluate("window.scrollTo(0, 0)")
#                 page.bring_to_front()
#             except Exception:
#                 pass

#             logger.info(f"Notion page '{clean_title}' created.")
#             print("\n" + "=" * 60)
#             print("Content typed into your REAL Notion workspace.")
#             print("This automated browser window is now in front -")
#             print("look at the TOP-RIGHT of the page for 'Share' -> 'Publish to web'.")
#             print("This is the same Notion account/workspace as your normal")
#             print("Chrome, just running in its own dedicated browser window.")
#             print("=" * 60 + "\n")

#             detail = f"Notion page '{clean_title}' created. Browser open (brought to front) for review."
#             if not link_made_clickable:
#                 detail += " NOTE: the backlink could not be confirmed as clickable - check it manually before publishing."
#             if not title_ok:
#                 detail += " NOTE: title may not have fully landed - please verify it in the browser."

#             return {
#                 "status": "success",
#                 "detail": detail,
#                 "url": current_url,
#                 "link_confirmed": link_made_clickable,
#             }

#     except Exception as e:
#         logger.error(f"Notion posting failed: {e}")
#         return {"status": "failed", "detail": str(e)}




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
