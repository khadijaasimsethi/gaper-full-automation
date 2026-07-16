# from abc import ABC, abstractmethod
# import logging
# import smtplib
# from email.mime.text import MIMEText
# from email.mime.multipart import MIMEMultipart
# import requests
# import config

# logger = logging.getLogger(__name__)

# class PlatformAdapter(ABC):
#     @abstractmethod
#     def authenticate(self) -> bool:
#         """Verifies if the necessary credentials exist."""
#         pass
        
#     @abstractmethod
#     def execute_post(self, target_url: str, content: str, is_ghost: bool = False) -> dict:
#         """
#         Executes the post or logs it.
#         Returns result dict: {"status": "success"/"failed", "detail": str}
#         """
#         pass

# class IndieHackersAdapter(PlatformAdapter):
#     def authenticate(self) -> bool:
#         creds = config.get_credentials()["indiehackers"]
#         return bool(creds["username"] and creds["password"])
        
#     def execute_post(self, target_url: str, content: str, is_ghost: bool = False) -> dict:
#         if not self.authenticate():
#             logger.warning("[IndieHackers] Credentials missing. Logging mock action.")
#             return {"status": "simulated_success", "detail": "Simulated post on IndieHackers (No credentials)"}
            
#         logger.info(f"[IndieHackers] Authenticating as {config.get_credentials()['indiehackers']['username']}...")
#         # Playwright auto-posting or API simulation can go here
#         logger.info(f"[IndieHackers] Success posting comment to thread {target_url}")
#         return {"status": "success", "detail": "Post successfully published via browser simulation."}

# class ContraAdapter(PlatformAdapter):
#     def authenticate(self) -> bool:
#         return bool(config.get_credentials()["contra"]["api_key"])
        
#     def execute_post(self, target_url: str, content: str, is_ghost: bool = False) -> dict:
#         if not self.authenticate():
#             logger.warning("[Contra] API Key missing. Logging mock action.")
#             return {"status": "simulated_success", "detail": "Simulated Contra opportunity pitch."}
            
#         logger.info("[Contra] Directing pitch draft via API call...")
#         # Perform API post to Contra opportunities endpoint
#         return {"status": "success", "detail": "Project brief submitted to Contra."}

# class NotionAdapter(PlatformAdapter):
#     def authenticate(self) -> bool:
#         creds = config.get_credentials()["notion"]
#         return bool(creds["api_key"] and creds["database_id"])
        
#     def execute_post(self, target_url: str, content: str, is_ghost: bool = False) -> dict:
#         if not self.authenticate():
#             logger.warning("[Notion] Credentials missing. Logging to local markdown backup instead.")
#             return {"status": "simulated_success", "detail": "Saved opportunity detail locally."}
            
#         creds = config.get_credentials()["notion"]
#         headers = {
#             "Authorization": f"Bearer {creds['api_key']}",
#             "Content-Type": "application/json",
#             "Notion-Version": "2022-06-28"
#         }
        
#         # Structure Notion payload
#         payload = {
#             "parent": {"database_id": creds["database_id"]},
#             "properties": {
#                 "Title": {"title": [{"text": {"content": f"Backlink Opportunity - {target_url[:50]}"}}]},
#                 "URL": {"url": target_url},
#                 "Type": {"select": {"name": "Ghost" if is_ghost else "Citation"}},
#                 "Status": {"status": {"name": "Discovered"}}
#             }
#         }
        
#         try:
#             res = requests.post("https://api.notion.com/v1/pages", headers=headers, json=payload, timeout=10)
#             if res.status_code == 200:
#                 logger.info("[Notion] Successfully logged opportunity row to Notion Database!")
#                 return {"status": "success", "detail": "Opportunity logged in Notion."}
#             else:
#                 logger.error(f"[Notion] Error logging row: Status {res.status_code} - {res.text}")
#                 return {"status": "failed", "detail": f"Notion API error: {res.text}"}
#         except Exception as e:
#             return {"status": "failed", "detail": str(e)}

# class SubstackAdapter(PlatformAdapter):
#     def authenticate(self) -> bool:
#         creds = config.get_credentials()["substack"]
#         return bool(creds["email"] and creds["password"])
        
#     def execute_post(self, target_url: str, content: str, is_ghost: bool = False) -> dict:
#         if not self.authenticate():
#             logger.warning("[Substack] Credentials missing. Logging mock action.")
#             return {"status": "simulated_success", "detail": "Drafted Substack comment."}
            
#         logger.info("[Substack] Writing newsletter comment via authenticated session...")
#         return {"status": "success", "detail": "Comment posted under active subscriber profile."}

# class PinterestAdapter(PlatformAdapter):
#     def authenticate(self) -> bool:
#         return bool(config.get_credentials()["pinterest"]["access_token"])
        
#     def execute_post(self, target_url: str, content: str, is_ghost: bool = False) -> dict:
#         if not self.authenticate():
#             logger.warning("[Pinterest] Token missing. Logging mock action.")
#             return {"status": "simulated_success", "detail": "Simulated Pin generation linked to Gaper."}
            
#         logger.info("[Pinterest] Generating pin using official board credentials...")
#         return {"status": "success", "detail": "Visual Pin backlink generated."}

# class PeerlistAdapter(PlatformAdapter):
#     def authenticate(self) -> bool:
#         return bool(config.get_credentials()["peerlist"]["api_key"])
        
#     def execute_post(self, target_url: str, content: str, is_ghost: bool = False) -> dict:
#         if not self.authenticate():
#             logger.warning("[Peerlist] API key missing. Logging mock action.")
#             return {"status": "simulated_success", "detail": "Simulated Peerlist launch post."}
            
#         logger.info("[Peerlist] Publishing to feed database...")
#         return {"status": "success", "detail": "Launch details posted on Peerlist profile."}

# class OutreachAdapter(PlatformAdapter):
#     """
#     Outreach Adapter used to send listing pitch emails to webmasters
#     when Gaper is found missing from a directories/articles competitor list.
#     """
#     def authenticate(self) -> bool:
#         creds = config.get_credentials()["outreach"]
#         return bool(creds["sender"] and creds["password"])
        
#     def execute_post(self, target_url: str, content: str, is_ghost: bool = False) -> dict:
#         """Sends listing outreach pitch to target webmaster."""
#         if not self.authenticate():
#             logger.warning("[Outreach] SMTP email credentials missing. Saving pitch to SQLite for manual outreach.")
#             return {"status": "simulated_success", "detail": "Saved outreach pitch locally for manual copy-paste."}
            
#         creds = config.get_credentials()["outreach"]
#         msg = MIMEMultipart()
#         msg['From'] = creds["sender"]
#         msg['To'] = "webmaster@" + target_url.split('/')[2] # Fallback domain target
#         msg['Subject'] = "Suggestion for addition: Gaper.io Developer Platform"
        
#         msg.attach(MIMEText(content, 'plain'))
        
#         try:
#             server = smtplib.SMTP(creds["smtp_server"], creds["smtp_port"])
#             server.starttls()
#             server.login(creds["sender"], creds["password"])
#             server.sendmail(creds["sender"], msg['To'], msg.as_string())
#             server.close()
#             logger.info(f"[Outreach] Webmaster pitch email sent successfully to {msg['To']}!")
#             return {"status": "success", "detail": f"Outreach email dispatched to {msg['To']}"}
#         except Exception as e:
#             logger.error(f"[Outreach] Failed to dispatch email: {e}")
#             return {"status": "failed", "detail": f"SMTP Error: {e}"}

# # Factory Pattern mapping source names to Adapter instances
# ADAPTER_MAP = {
#     "indiehackers": IndieHackersAdapter(),
#     "contra": ContraAdapter(),
#     "notion": NotionAdapter(),
#     "substack": SubstackAdapter(),
#     "pinterest": PinterestAdapter(),
#     "peerlist": PeerlistAdapter(),
#     "outreach": OutreachAdapter()
# }

# def get_adapter(platform_source: str) -> PlatformAdapter:
#     """
#     Factory Pattern for Platform Adapters (Block 6).
#     Returns the appropriate adapter based on the platform string.
#     """
#     source_lower = platform_source.lower()
#     for key, adapter in ADAPTER_MAP.items():
#         if key in source_lower:
#             return adapter
            
#     # Default fallback adapter
#     return IndieHackersAdapter()





from abc import ABC, abstractmethod
import logging
import os
import config

logger = logging.getLogger(__name__)

class PlatformAdapter(ABC):
    @abstractmethod
    def authenticate(self) -> bool:
        """Verifies if the necessary credentials exist."""
        pass

    @abstractmethod
    def execute_post(self, target_url: str, content: str, is_ghost: bool = False) -> dict:
        """
        Executes the post for real.
        Returns result dict: {"status": "success"/"failed"/"not_implemented", "detail": str}
        """
        pass


class IndieHackersAdapter(PlatformAdapter):
    """
    Real implementation using Playwright. Login and posting happen in ONE
    continuous browser session, not saved-then-reloaded across two
    separate browser launches - Indie Hackers uses Firebase Authentication,
    which stores the session in IndexedDB, and Playwright's session-saving
    only captures cookies + localStorage, not IndexedDB. A second, freshly
    launched browser loading a saved session file would look logged-out to
    Firebase even though login worked moments earlier.
    """

    LOGIN_URL = "https://www.indiehackers.com/login"

    def authenticate(self) -> bool:
        creds = config.get_credentials()["indiehackers"]
        return bool(creds["username"] and creds["password"])

    def execute_post(self, target_url: str, content: str, is_ghost: bool = False) -> dict:
        if not self.authenticate():
            logger.warning("[IndieHackers] Credentials missing (INDIEHACKERS_USERNAME/PASSWORD in .env).")
            return {"status": "failed", "detail": "No credentials configured - nothing was posted."}

        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        except ImportError:
            return {"status": "failed", "detail": "Playwright not installed. Run: pip install playwright && playwright install chromium"}

        creds = config.get_credentials()["indiehackers"]
        email = creds["username"]
        password = creds["password"]

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
                    viewport={"width": 1366, "height": 768},
                )
                page = context.new_page()

                page.goto(self.LOGIN_URL, wait_until="domcontentloaded", timeout=30000)

                email_field = page.get_by_placeholder("Enter your email address")
                password_field = page.get_by_placeholder("Enter your password")
                submit_button = page.get_by_role("button", name="SIGN IN")
                email_field.wait_for(state="visible", timeout=15000)
                email_field.fill(email)
                password_field.fill(password)
                submit_button.click()

                try:
                    page.wait_for_url(lambda u: "/login" not in u, timeout=10000)
                except PWTimeout:
                    pass

                # Verify login actually stuck by testing against the real target
                page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                if "/login" in page.url or "/sign-in" in page.url:
                    shot_path = os.path.join(config.BASE_DIR, "output", "indiehackers_login_failed.png")
                    os.makedirs(os.path.dirname(shot_path), exist_ok=True)
                    page.screenshot(path=shot_path)
                    browser.close()
                    return {"status": "failed", "detail": f"Login did not stick, bounced back to sign-in. Screenshot: {shot_path}"}

                # Best-effort: find a comment box on the thread page.
                # NOTE: Indie Hackers' page layout can change - if this
                # selector stops matching, this is the line to update.
                comment_box = page.locator(
                    'textarea[placeholder*="comment" i], div[contenteditable="true"]'
                ).first
                comment_box.wait_for(state="visible", timeout=15000)
                comment_box.click()
                comment_box.type(content, delay=5)

                submit_comment = page.get_by_role("button", name="Post").or_(
                    page.get_by_role("button", name="Comment")
                ).or_(page.locator('button[type="submit"]'))
                submit_comment.first.click()

                page.wait_for_timeout(2000)
                browser.close()
                return {"status": "success", "detail": f"Comment posted to {target_url}"}

        except Exception as e:
            logger.error(f"[IndieHackers] Posting failed: {e}")
            return {"status": "failed", "detail": f"Automation error: {e}"}


class ContraAdapter(PlatformAdapter):
    """
    Contra uses email + emailed verification code (no fixed password), so
    login can't be automated here - run setup_contra_login.py once
    manually first. This adapter only reuses that saved session; if the
    session has expired, it fails clearly and tells you to re-run setup
    instead of getting stuck waiting for a code that never arrives.
    """

    def authenticate(self) -> bool:
        creds = config.get_credentials()["contra"]
        return bool(creds["email"])

    def _get_profile_dir(self):
        from pathlib import Path
        profile_dir = Path(config.BASE_DIR) / "sessions" / "contra_profile"
        return profile_dir

    def execute_post(self, target_url: str, content: str, is_ghost: bool = False) -> dict:
        if not self.authenticate():
            logger.warning("[Contra] CONTRA_EMAIL missing in .env.")
            return {"status": "failed", "detail": "No email configured - nothing was posted."}

        profile_dir = self._get_profile_dir()
        if not profile_dir.exists():
            return {
                "status": "failed",
                "detail": "No saved Contra session found. Run 'python setup_contra_login.py' once first to log in manually."
            }

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return {"status": "failed", "detail": "Playwright not installed."}

        try:
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    headless=False,
                    viewport={"width": 1366, "height": 768},
                )
                page = context.new_page()
                page.goto(target_url, wait_until="domcontentloaded", timeout=30000)

                # Session expired - can't auto re-login with an emailed
                # code, so fail clearly instead of hanging. Checks multiple
                # patterns since Contra's own "login" flow actually runs
                # through their "Sign up" button, not a dedicated /login URL.
                current_url = page.url.lower()
                if "login" in current_url or "sign-up" in current_url or "signup" in current_url or "sign-in" in current_url:
                    context.close()
                    return {
                        "status": "failed",
                        "detail": "Contra session expired. Run 'python setup_contra_login.py' again to log in manually."
                    }

                # NOTE: Contra's comment/reply box selector - update this
                # line if Contra changes their page layout.
                comment_box = page.locator(
                    'textarea[placeholder*="comment" i], div[contenteditable="true"]'
                ).first
                comment_box.wait_for(state="visible", timeout=15000)
                comment_box.click()
                comment_box.type(content, delay=5)

                submit_btn = page.get_by_role("button", name="Post").or_(
                    page.get_by_role("button", name="Reply")
                ).or_(page.locator('button[type="submit"]'))
                submit_btn.first.click()
                page.wait_for_timeout(2000)

                context.close()
                return {"status": "success", "detail": f"Posted to Contra: {target_url}"}

        except Exception as e:
            logger.error(f"[Contra] Posting failed: {e}")
            return {"status": "failed", "detail": f"Automation error: {e}"}
class NotionAdapter(PlatformAdapter):
    def authenticate(self) -> bool:
        creds = config.get_credentials()["notion"]
        return bool(creds["api_key"] and creds["database_id"])

    def execute_post(self, target_url: str, content: str, is_ghost: bool = False) -> dict:
        if not self.authenticate():
            logger.warning("[Notion] Credentials missing.")
            return {"status": "failed", "detail": "No credentials configured - nothing was posted."}

        import requests
        creds = config.get_credentials()["notion"]
        headers = {
            "Authorization": f"Bearer {creds['api_key']}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
        payload = {
            "parent": {"database_id": creds["database_id"]},
            "properties": {
                "Title": {"title": [{"text": {"content": f"Backlink Opportunity - {target_url[:50]}"}}]},
                "URL": {"url": target_url},
                "Type": {"select": {"name": "Ghost" if is_ghost else "Citation"}},
                "Status": {"status": {"name": "Discovered"}}
            }
        }
        try:
            res = requests.post("https://api.notion.com/v1/pages", headers=headers, json=payload, timeout=10)
            if res.status_code == 200:
                logger.info("[Notion] Successfully logged opportunity row to Notion Database!")
                return {"status": "success", "detail": "Opportunity logged in Notion."}
            else:
                logger.error(f"[Notion] Error logging row: Status {res.status_code} - {res.text}")
                return {"status": "failed", "detail": f"Notion API error: {res.text}"}
        except Exception as e:
            return {"status": "failed", "detail": str(e)}


class SubstackAdapter(PlatformAdapter):
    """
    Same pattern as Contra: email + emailed verification code/magic link,
    no fixed password. Run setup_substack_login.py once manually first.
    This adapter only reuses that saved session.
    """

    def authenticate(self) -> bool:
        creds = config.get_credentials()["substack"]
        return bool(creds["email"])

    def _get_profile_dir(self):
        from pathlib import Path
        return Path(config.BASE_DIR) / "sessions" / "substack_profile"

    def execute_post(self, target_url: str, content: str, is_ghost: bool = False) -> dict:
        if not self.authenticate():
            logger.warning("[Substack] SUBSTACK_EMAIL missing in .env.")
            return {"status": "failed", "detail": "No email configured - nothing was posted."}

        profile_dir = self._get_profile_dir()
        if not profile_dir.exists():
            return {
                "status": "failed",
                "detail": "No saved Substack session found. Run 'python setup_substack_login.py' once first."
            }

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return {"status": "failed", "detail": "Playwright not installed."}

        try:
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    headless=False,
                    viewport={"width": 1366, "height": 768},
                )
                page = context.new_page()
                page.goto(target_url, wait_until="domcontentloaded", timeout=30000)

                if "sign-in" in page.url.lower() or "login" in page.url.lower():
                    context.close()
                    return {
                        "status": "failed",
                        "detail": "Substack session expired. Run 'python setup_substack_login.py' again."
                    }

                comment_box = page.locator(
                    'textarea[placeholder*="comment" i], div[contenteditable="true"]'
                ).first
                comment_box.wait_for(state="visible", timeout=15000)
                comment_box.click()
                comment_box.type(content, delay=5)

                submit_btn = page.get_by_role("button", name="Post").or_(
                    page.get_by_role("button", name="Comment")
                ).or_(page.locator('button[type="submit"]'))
                submit_btn.first.click()
                page.wait_for_timeout(2000)

                context.close()
                return {"status": "success", "detail": f"Posted to Substack: {target_url}"}

        except Exception as e:
            logger.error(f"[Substack] Posting failed: {e}")
            return {"status": "failed", "detail": f"Automation error: {e}"}


class PinterestAdapter(PlatformAdapter):
    def authenticate(self) -> bool:
        return bool(config.get_credentials()["pinterest"]["access_token"])

    def execute_post(self, target_url: str, content: str, is_ghost: bool = False) -> dict:
        logger.warning("[Pinterest] Adapter not yet implemented - nothing was posted.")
        return {"status": "not_implemented", "detail": "Pinterest posting isn't built yet. Nothing was sent."}


class PeerlistAdapter(PlatformAdapter):
    """
    Session-persistent: uses a saved browser profile (like
    generic_listing_agent.py's approach), so login only happens once
    manually. Every subsequent call reuses the same profile folder and
    stays logged in automatically.
    """

    LOGIN_URL = "https://peerlist.io/login"

    def authenticate(self) -> bool:
        creds = config.get_credentials()["peerlist"]
        return bool(creds["username"] and creds["password"])

    def _get_profile_dir(self):
        from pathlib import Path
        profile_dir = Path(config.BASE_DIR) / "sessions" / "peerlist_profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        return profile_dir

    def execute_post(self, target_url: str, content: str, is_ghost: bool = False) -> dict:
        if not self.authenticate():
            logger.warning("[Peerlist] Credentials missing (PEERLIST_USERNAME/PASSWORD in .env).")
            return {"status": "failed", "detail": "No credentials configured - nothing was posted."}

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return {"status": "failed", "detail": "Playwright not installed."}

        creds = config.get_credentials()["peerlist"]
        profile_dir = self._get_profile_dir()

        try:
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    headless=False,
                    viewport={"width": 1366, "height": 768},
                )
                page = context.new_page()
                page.goto(target_url, wait_until="domcontentloaded", timeout=30000)

                # If the persisted session expired, we'll land on login - log in
                # once here; next time the saved profile keeps us logged in.
                if "login" in page.url.lower():
                    logger.info("[Peerlist] Session expired or first run - logging in...")
                    page.goto(self.LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
                    page.fill("input[type='email'], input[name='email']", creds["username"])
                    page.fill("input[type='password'], input[name='password']", creds["password"])
                    page.click("button[type='submit']")
                    page.wait_for_timeout(4000)
                    page.goto(target_url, wait_until="domcontentloaded", timeout=30000)

                # NOTE: Peerlist's comment/post box selector - update this
                # line if Peerlist changes their page layout.
                comment_box = page.locator(
                    'textarea[placeholder*="comment" i], div[contenteditable="true"]'
                ).first
                comment_box.wait_for(state="visible", timeout=15000)
                comment_box.click()
                comment_box.type(content, delay=5)

                submit_btn = page.get_by_role("button", name="Post").or_(
                    page.get_by_role("button", name="Comment")
                ).or_(page.locator('button[type="submit"]'))
                submit_btn.first.click()
                page.wait_for_timeout(2000)

                context.close()
                return {"status": "success", "detail": f"Posted to Peerlist: {target_url}"}

        except Exception as e:
            logger.error(f"[Peerlist] Posting failed: {e}")
            return {"status": "failed", "detail": f"Automation error: {e}"}
class HashnodeAdapter(PlatformAdapter):
    """API-based, like Notion - publishes an article via Hashnode's GraphQL API."""

    API_URL = "https://gql.hashnode.com"

    def authenticate(self) -> bool:
        return bool(getattr(config, "HASHNODE_API_KEY", "") and getattr(config, "HASHNODE_PUBLICATION_ID", ""))

    def execute_post(self, target_url: str, content: str, is_ghost: bool = False) -> dict:
        if not self.authenticate():
            logger.warning("[Hashnode] Credentials missing (HASHNODE_API_KEY/HASHNODE_PUBLICATION_ID in .env).")
            return {"status": "failed", "detail": "No credentials configured - nothing was posted."}

        import requests
        headers = {
            "Authorization": config.HASHNODE_API_KEY,
            "Content-Type": "application/json",
        }
        title = f"Thoughts on: {target_url.split('/')[-1][:60]}"
        query = """
        mutation PublishPost($input: PublishPostInput!) {
          publishPost(input: $input) {
            post { id url }
          }
        }
        """
        variables = {
            "input": {
                "title": title,
                "contentMarkdown": content,
                "publicationId": config.HASHNODE_PUBLICATION_ID,
                "tags": []
            }
        }
        try:
            res = requests.post(self.API_URL, headers=headers, json={"query": query, "variables": variables}, timeout=15)
            data = res.json()
            if "errors" in data:
                logger.error(f"[Hashnode] API error: {data['errors']}")
                return {"status": "failed", "detail": f"Hashnode API error: {data['errors']}"}
            post_url = data.get("data", {}).get("publishPost", {}).get("post", {}).get("url", "")
            logger.info(f"[Hashnode] Published successfully: {post_url}")
            return {"status": "success", "detail": f"Published on Hashnode: {post_url}"}
        except Exception as e:
            return {"status": "failed", "detail": str(e)}
class ContraAdapter(PlatformAdapter):
    """
    Contra - session-persistent (manual login once via setup script).
    Posts comments on community posts.
    """

    def authenticate(self) -> bool:
        creds = config.get_credentials()["contra"]
        return bool(creds["email"])

    def _get_profile_dir(self):
        from pathlib import Path
        profile_dir = Path(config.BASE_DIR) / "sessions" / "contra_profile"
        return profile_dir

    def execute_post(self, target_url: str, content: str, is_ghost: bool = False) -> dict:
        if not self.authenticate():
            logger.warning("[Contra] CONTRA_EMAIL missing in .env.")
            return {"status": "failed", "detail": "No email configured."}

        profile_dir = self._get_profile_dir()
        if not profile_dir.exists():
            return {
                "status": "failed",
                "detail": "No saved session. Run 'python setup_contra_login.py' first."
            }

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return {"status": "failed", "detail": "Playwright not installed."}

        try:
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    headless=False,
                    viewport={"width": 1366, "height": 768},
                )
                page = context.new_page()
                page.goto(target_url, wait_until="domcontentloaded", timeout=30000)

                # Check login
                current_url = page.url.lower()
                if "login" in current_url or "sign-up" in current_url or "signup" in current_url:
                    context.close()
                    return {
                        "status": "failed",
                        "detail": "Session expired. Run 'python setup_contra_login.py' again."
                    }

                # Wait and scroll
                page.wait_for_timeout(3000)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2000)
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(2000)

                # Find comment box
                selectors = [
                    'textarea[placeholder*="comment" i]',
                    'textarea[placeholder*="write" i]',
                    'div[contenteditable="true"]',
                    '[role="textbox"]',
                    'textarea',
                ]

                comment_box = None
                for selector in selectors:
                    try:
                        el = page.locator(selector).first
                        if el.count() > 0 and el.is_visible():
                            comment_box = el
                            print(f"✅ Found comment box with: {selector}")
                            break
                    except:
                        continue

                if not comment_box:
                    try:
                        comment_box = page.locator("textarea").first
                        if comment_box.count() == 0:
                            raise Exception("No textarea")
                    except:
                        context.close()
                        return {"status": "failed", "detail": "Could not find comment box."}

                # Post comment
                comment_box.wait_for(state="visible", timeout=15000)
                comment_box.click()
                comment_box.type(content, delay=5)

                submit_btn = page.get_by_role("button", name="Post").or_(
                    page.get_by_role("button", name="Reply")
                ).or_(
                    page.locator('button[type="submit"]')
                ).first

                if submit_btn.count() > 0 and submit_btn.is_visible():
                    submit_btn.click()
                else:
                    comment_box.press("Control+Enter")

                page.wait_for_timeout(3000)
                context.close()

                return {"status": "success", "detail": f"Posted to Contra: {target_url}"}

        except Exception as e:
            logger.error(f"[Contra] Failed: {e}")
            return {"status": "failed", "detail": f"Error: {e}"}
# Factory Pattern mapping source names to Adapter instances.
ADAPTER_MAP = {
    "indiehackers": IndieHackersAdapter(),
    "contra": ContraAdapter(),
    "notion": NotionAdapter(),
    "hashnode": HashnodeAdapter(),
    "substack": SubstackAdapter(),
    "pinterest": PinterestAdapter(),
    "peerlist": PeerlistAdapter(),
}

def get_adapter(platform_source: str) -> PlatformAdapter:
    source_lower = platform_source.lower()
    for key, adapter in ADAPTER_MAP.items():
        if key in source_lower:
            return adapter
    return IndieHackersAdapter()

