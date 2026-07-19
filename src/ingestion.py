
from abc import ABC, abstractmethod
import logging
import requests
from bs4 import BeautifulSoup
import config

logger = logging.getLogger(__name__)

# gemini-2.5-flash was retired for new users (404). gemini-flash-latest is
# an alias Google keeps pointed at whatever the current stable flash model
# is, so this needs updating far less often than a pinned version string.
GEMINI_MODEL = "gemini-flash-latest"


class IngestionException(Exception):
    """Base exception for ingestion issues."""
    pass

class BlockedException(IngestionException):
    """Raised when blocked by Cloudflare, 403, or rate limits."""
    pass

class DomParseException(IngestionException):
    """Raised when layout changes or custom elements prevent parsing."""
    pass

class IngestionStrategy(ABC):
    @abstractmethod
    def fetch_thread_data(self, url: str) -> dict:
        pass

class Type1ApiRss(IngestionStrategy):
    def fetch_thread_data(self, url: str) -> dict:
        logger.info(f"[Type 1] Attempting API/RSS ingestion for {url}")

        if "dev.to" in url:
            try:
                parts = url.split("dev.to/")
                if len(parts) > 1:
                    slug = parts[1]
                    api_url = f"https://dev.to/api/articles/{slug}"
                    response = requests.get(api_url, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        return {
                            "title": data.get("title", ""),
                            "content": data.get("description", "") + "\n" + data.get("body_markdown", ""),
                            "comments_count": data.get("comments_count", 0),
                            "comments": [],
                            "guidelines": "Guidelines: Add value. Cite relevant resources."
                        }
            except Exception as e:
                logger.warning(f"[Type 1] Dev.to API parsing failed: {e}")

        raise DomParseException("No structured API endpoint mapped for this URL.")

class Type2StaticSoup(IngestionStrategy):
    def fetch_thread_data(self, url: str) -> dict:
        logger.info(f"[Type 2] Fetching static HTML for {url}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        }

        try:
            response = requests.get(url, headers=headers, timeout=15)

            if response.status_code in (403, 429) or "cloudflare" in response.text.lower():
                raise BlockedException(f"Blocked by Cloudflare/WAF. Status: {response.status_code}")

            if response.status_code != 200:
                raise IngestionException(f"HTTP error {response.status_code}")

            soup = BeautifulSoup(response.text, 'html.parser')

            title = soup.find('h1')
            title_text = title.text.strip() if title else "Untitled Thread"

            content_divs = soup.find_all(['p', 'article', 'main'])
            content_text = "\n".join([p.text.strip() for p in content_divs if p.text.strip()][:10])

            if len(content_text) < 50:
                raise DomParseException("Extracted content is too short, layout parser failed.")

            return {
                "title": title_text,
                "content": content_text,
                "comments_count": len(soup.find_all(class_=lambda c: c and 'comment' in c.lower())),
                "comments": [c.text.strip() for c in soup.find_all(class_=lambda c: c and 'comment-body' in c.lower())[:5]],
                "guidelines": "Follow community guidelines. Cite your sources."
            }

        except requests.RequestException as re:
            raise BlockedException(f"Request failed: {re}")

class Type3PlaywrightAuth(IngestionStrategy):
    def fetch_thread_data(self, url: str) -> dict:
        logger.info(f"[Type 3] Spinning up headless browser for {url}")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise IngestionException("Playwright is not installed. Please run 'pip install playwright' and 'playwright install'")

        from src.proxy_manager import ProxyManager
        proxy_mgr = ProxyManager()
        # Read-only scraping uses the cheap datacenter pool, not the
        # expensive per-GB residential one - that's reserved for
        # authenticated posting in the adapters (see proxy_manager.py).
        proxy_config = proxy_mgr.get_playwright_proxy("datacenter")
        if proxy_config:
            logger.info(f"[Type 3] Using datacenter proxy {proxy_config['server']}")

        try:
            with sync_playwright() as p:
                launch_kwargs = {"headless": True}
                if proxy_config:
                    launch_kwargs["proxy"] = proxy_config
                browser = p.chromium.launch(**launch_kwargs)
                page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

                try:
                    response = page.goto(url, wait_until="networkidle", timeout=30000)
                except Exception as nav_err:
                    # A bad/dead proxy fails here specifically - worth telling
                    # the waterfall this was a blocked/network issue (retryable
                    # via escalation) rather than a generic crash.
                    browser.close()
                    raise BlockedException(f"Navigation failed (possibly proxy issue): {nav_err}")

                if response.status == 403 or "cloudflare" in page.content().lower():
                    browser.close()
                    raise BlockedException("Cloudflare challenge page detected by Playwright.")

                title = page.title()
                content = page.locator("body").inner_text()

                browser.close()

                return {
                    "title": title,
                    "content": content[:1500],
                    "comments_count": 0,
                    "comments": [],
                    "guidelines": "Always write authentic, valuable answers."
                }
        except BlockedException:
            raise
        except Exception as e:
            if "Timeout" in str(e):
                raise BlockedException(f"Timeout browsing page: {e}")
            raise DomParseException(f"Playwright scraping failed: {e}")

class Type4LlmVision(IngestionStrategy):
    def fetch_thread_data(self, url: str) -> dict:
        logger.info(f"[Type 4] Falling back to LLM Vision strategy for {url}")

        try:
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            raw_html = response.text[:10000]
        except Exception:
            raw_html = "Could not fetch HTML. Scraping failure."

        import google.generativeai as genai
        if not config.GEMINI_API_KEY:
            raise IngestionException("Gemini API key is not set. Type 4 fallback aborted.")

        try:
            genai.configure(api_key=config.GEMINI_API_KEY)
            model = genai.GenerativeModel(GEMINI_MODEL)

            prompt = f"""
            Analyze the following raw HTML or page content from URL: {url}
            Extract the following details as JSON with fields "title", "content", "comments_count", "comments" (list of strings), and "guidelines" (rules for comments if found).

            HTML Content:
            {raw_html}
            """

            res = model.generate_content(prompt)
            import json
            import re

            text = res.text
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                return {
                    "title": data.get("title", "Untitled Thread"),
                    "content": data.get("content", ""),
                    "comments_count": data.get("comments_count", 0),
                    "comments": data.get("comments", []),
                    "guidelines": data.get("guidelines", "")
                }
            else:
                return {
                    "title": "LLM Extracted Page",
                    "content": text[:1000],
                    "comments_count": 0,
                    "comments": [],
                    "guidelines": ""
                }
        except Exception as e:
            raise IngestionException(f"LLM Ingestion Strategy failed: {e}")