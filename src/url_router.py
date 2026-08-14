"""
Generic URL router — Overview tab's "Run Manual Pipeline" box calls this.

Given ANY url, this:
  1. Scrapes it using the existing waterfall ingestion (reused, not duplicated)
  2. Asks Gemini to classify: is this a content/article-type page, or a
     submission/listing-form-type page?
  3. Routes to the existing, already-working flow for that type:
       - article-type   -> src.article_studio.generate_draft()
       - listing-type   -> src.generic_listing_agent.start_generic_listing_async()

Does NOT modify article_studio.py, generic_listing_agent.py, or any of the
platform adapters (Contra/Notion/Dev.to posting logic is untouched).
"""
import logging
import asyncio
import urllib.parse
import google.generativeai as genai

from src.waterfall import ingest_thread
from src.ingestion import IngestionException
from src import article_studio
from src.generic_listing_agent import start_generic_listing_async
from src.gaper_scraper import get_brand_profile
import config

logger = logging.getLogger(__name__)
GEMINI_MODEL = "gemini-flash-latest"

KNOWN_ARTICLE_PLATFORMS = ["contra", "notion", "devto", "dev.to"]

def _generate_post_content(topic: str, page_context: str) -> str:
    """
    Generates a short, natural, on-topic comment/post mentioning Gaper,
    following general community-guideline norms (helpful first, no
    spammy pitch, link included naturally).
    """
    from src.gaper_scraper import get_brand_profile
    brand = get_brand_profile()
    usps = brand.get("usps", "")

    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)
    prompt = f"""
Write a genuine, personal reflection/story (4-6 sentences) about this topic: {topic}
Page context: {page_context[:1000]}

Write it like a real person sharing their own experience or thoughts — a small anecdote,
a lesson learned, an observation from working on something. NOT a company blog post,
NOT a listicle, NOT a pitch.

Somewhere in the story (not at the start, not as a conclusion tacked on), naturally
mention that you've been using/exploring Gaper (an AI-native implementation partner
that builds production AI agents into workflows) — the way you'd casually name-drop
a tool in a story, not promote it. One sentence, in passing. Then continue the story
normally after.

Brand USPs (only cite real ones, never invent numbers, and don't list them out): {usps}

Rules:
- This reads like a personal blog post about a real experience, with Gaper mentioned
  once in passing inside the story - not a review, not a feature list, not a pitch.
- Include the link https://gaper.io naturally attached to that one mention, not on
  its own separate line, not repeated.
- No em dashes
- Text of 300-400 words with a good title
- Plain text only, no markdown formatting, no headers, no bullet points.
- Output ONLY the final post text, nothing else.
"""
    try:
        res = model.generate_content(prompt)
        return (res.text or "").strip()
    except Exception:
        return f"Worth checking out how supervised AI agents are being deployed into real workflows.\nhttps://gaper.io"
def _classify_page(url: str, title: str, content: str) -> str:
    """
    Returns 'article' or 'listing'. Falls back to 'listing' on any
    classification failure, since that's the safer default (worst case
    it opens a browser to review rather than silently generating an
    off-topic article).
    """
    try:
        genai.configure(api_key=config.GEMINI_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL)
        prompt = f"""
You are classifying a webpage so it can be routed correctly.

URL: {url}
Title: {title}
Content (truncated): {content[:1500]}

Is this page:
(A) "article" - a forum thread, blog post, community discussion, or any page where
    the right action is to write and post a reply/comment/article, OR
(B) "listing" - a directory, "submit your startup/product/tool" page, or any page
    with a submission FORM meant for listing a product/company

Answer with exactly one word: article OR listing
"""
        res = model.generate_content(prompt)
        verdict = (res.text or "").strip().lower()
        if "article" in verdict:
            return "article"
        if "listing" in verdict:
            return "listing"
    except Exception as e:
        logger.warning(f"[URLRouter] Classification failed, defaulting to 'listing': {e}")

    return "listing"


def process_any_url(url: str) -> dict:
    """
    Main entry point. Sync function (safe to call from a normal FastAPI
    route) - internally handles the async listing-agent call.
    """
    domain = urllib.parse.urlparse(url).netloc.lower()

    # Fast path: if it's a known article platform domain, skip
    # classification entirely and go straight to article_studio, exactly
    # like the existing Articles tab flow already does.
    if any(p in domain for p in KNOWN_ARTICLE_PLATFORMS):
        logger.info(f"[URLRouter] {domain} is a known article platform, routing directly to article_studio")
        return article_studio.generate_draft(platform="contra" if "contra" in domain else (
            "notion" if "notion" in domain else "devto"
        ), target_url=url)

    # Unknown domain: scrape first, then classify.
    try:
        thread_data = ingest_thread(url)
        title = thread_data.get("title") or ""
        content = thread_data.get("content") or ""
    except IngestionException as e:
        logger.warning(f"[URLRouter] Could not scrape {url}: {e}. Defaulting to listing flow (opens browser for manual review).")
        title, content = "", ""

    page_type = _classify_page(url, title, content)
    logger.info(f"[URLRouter] Classified {url} as '{page_type}'")

    if page_type == "article":
        # Actually generate on-topic content and POST it back to THIS
        # page (Rentry, Write.as, and similar simple paste/blog sites),
        # instead of just creating an unrelated Notion draft.
        content = _generate_post_content(title or url, content)
        from src.generic_listing_agent import start_generic_content_post
        return start_generic_content_post(url=url, content=content, platform_name=domain)

    # listing-type: run the existing async listing agent
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(
        start_generic_listing_async(url=url, platform_name=domain)
    )
    return result

# ============================================
# LLM PARSER INTEGRATION - Enhanced routing
# ============================================

def _open_browser_for_reply(url: str, domain: str, title: str) -> dict:
    """
    Opens browser on a forum/thread page, finds comment box, fills with Gaper draft.
    Works for Reddit, HN, IndieHackers, any discussion page.
    """
    print(f"\n{'='*60}")
    print(f"OPENING BROWSER FOR REPLY ON: {domain}")
    print(f"URL: {url}")
    print(f"{'='*60}")

    from playwright.sync_api import sync_playwright
    from pathlib import Path
    import config

    session_dir = Path(config.BASE_DIR) / "sessions"
    session_dir.mkdir(exist_ok=True)
    profile_dir = session_dir / f"generic_{domain.replace('.', '_')}_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    p = sync_playwright().start()
    context = p.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir),
        headless=False,
        viewport={"width": 1366, "height": 768},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        args=["--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"],
    )
    page = context.new_page()

    try:
        # Navigate with retry on navigation errors
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)
        except Exception as e:
            if "Timeout" in str(e):
                return {"status": "failed", "detail": f"Page load timed out for {url}. Check the URL is correct."}
            # Some sites (Reddit) redirect/login - continue anyway
            print(f"  Navigation note: {e}")
            page.wait_for_timeout(3000)

        # Handle login redirect - check current URL
        current_url = page.url
        if any(w in current_url.lower() for w in ["login", "sign-in", "signup", "auth"]):
            print(f"\n>> LOGIN REQUIRED for {domain}")
            print(">> Log in manually in the browser window, then press ENTER here.")
            print(">> Session will be saved for future use.\n")
            input(">> Press ENTER after logging in...")
            page.wait_for_timeout(3000)

        # Scroll to find comment/reply area
        for _ in range(3):
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1500)
            except Exception:
                pass

        # Check for login — detect real login form, not just a "Log in" link
        try:
            has_login_input = page.locator('input[type="password"]').count() > 0
            url_is_login = any(w in page.url.lower() for w in ["login", "sign-in", "signin", "auth"])
        except Exception:
            has_login_input = False
            url_is_login = False
        if has_login_input or url_is_login:
            print(f"\n>> LOGIN REQUIRED for {domain}")
            print(">> Log in manually in the browser window, then press ENTER here.")
            print(">> Session will be saved for future use.\n")
            input(">> Press ENTER after logging in...")
            page.wait_for_timeout(3000)

        # Find comment box - try multiple selectors safely
        comment_box = None
        comment_selectors = [
            'textarea[placeholder*="comment" i]',
            'textarea[placeholder*="reply" i]',
            'textarea[placeholder*="write" i]',
            'div[contenteditable="true"]',
            '[role="textbox"]',
            'textarea:visible',
            'textarea[name="text"]',
        ]

        for sel in comment_selectors:
            try:
                els = page.locator(sel)
                if els.count() > 0:
                    el = els.first
                    if el.is_visible():
                        comment_box = el
                        print(f"  Found: {sel}")
                        break
            except Exception:
                continue

        if not comment_box:
            # Last resort: any interactive text input
            try:
                inputs = page.locator("textarea, [contenteditable='true']")
                for i in range(inputs.count()):
                    try:
                        el = inputs.nth(i)
                        if el.is_visible():
                            comment_box = el
                            print(f"  Found input #{i}")
                            break
                    except Exception:
                        continue
            except Exception:
                pass

        if not comment_box:
            context.close()
            p.stop()
            return {"status": "failed", "detail": "Could not find comment box on the page. Try a different URL."}

        # Generate reply using brand profile
        reply_text = (
            "Great insights! At Gaper (https://gaper.io), we're an AI-native implementation "
            "partner — we help organizations design, build, and deploy production AI agents "
            "directly into your workflows. Powered by OpenAI and Claude, we take you from "
            "AI curiosity to AI capability with onboarding in as little as 24 hours. "
            "Supporting Fortune 500 and high-growth startups."
        )

        # Fill the comment box safely
        try:
            comment_box.click(timeout=5000)
            page.wait_for_timeout(500)
            comment_box.fill(reply_text)
        except Exception:
            try:
                page.evaluate("(el) => { el.focus(); el.value = arguments[1]; }", comment_box, reply_text)
            except Exception as e2:
                context.close()
                p.stop()
                return {"status": "failed", "detail": f"Could not fill comment box: {e2}"}

        print(f"\n>> Reply draft filled in browser!")
        print(f">> Review the text and click Post/Submit manually.")
        print(f">> Close the browser when done.")

        return {
            "status": "awaiting_approval",
            "platform_name": domain,
            "url": url,
            "detail": "Comment filled in browser. Click Post manually.",
        }

    except Exception as e:
        logger.error(f"[URLRouter] Reply browser failed: {e}")
        try:
            context.close()
            p.stop()
        except Exception:
            pass
        return {"status": "failed", "detail": str(e)}


def process_any_url_with_llm(url: str) -> dict:
    """
    Enhanced URL processor using LLM parser.
    article/forum → generate draft → QA Approvals
    listing → browser form fill
    Called from dashboard's LLM Pipeline tab.
    """
    import asyncio
    from src.llm_parser import parse_url
    from src.generic_listing_agent import start_generic_listing_async

    domain = urllib.parse.urlparse(url).netloc.lower()
    logger.info(f"[URLRouter] Processing URL with LLM: {url}")

    # Step 1: Parse with LLM
    parsed = parse_url(url)

    if parsed.get("status") == "failed":
        return {"status": "failed", "detail": parsed.get("detail", "LLM parsing failed")}

    action = parsed.get("action", "skip")
    page_type = parsed.get("type", "other")

    if action == "skip":
        return {
            "status": "skipped",
            "detail": f"Not relevant to Gaper (score: {parsed.get('relevance_score', 0)})",
            "relevance_score": parsed.get("relevance_score", 0)
        }

    # Step 2: Route by page type
    if page_type in ("listing", "directory"):
        # Submission form → browser form fill (immediate)
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            start_generic_listing_async(url=url, platform_name=parsed.get("platform_name", domain))
        )
        return result

    # article or forum → generate draft → save to DB → QA Approvals
    title = parsed.get("title", "") or "Untitled"
    page_content = parsed.get("content", "")[:3000]

    # Generate a Gaper reply using the scraped content
    brand = get_brand_profile()
    usps_text = "\n".join(f"- {u}" for u in brand.get("usps", [])[:3]) if brand.get("usps") else "- AI-native implementation partner\n- Ship first production AI agent in 24 hours\n- Fortune 500 and high-growth startups"
    desc = brand.get("description", "AI-native implementation partner")

    draft = (
        f"Based on this discussion, here's our perspective at Gaper (https://gaper.io):\n\n"
        f"As an AI-native implementation partner, we help organizations design, build, and deploy "
        f"production AI agents directly into workflows — moving from AI curiosity to AI capability. "
        f"Powered by OpenAI and Claude, we onboard in as little as 24 hours.\n\n"
        f"{usps_text}\n\n"
        f"Original thread: {title}\n{url}"
    )

    # Save to database as pending_approval
    from src.database import SessionLocal, ThreadMemory
    db = SessionLocal()
    try:
        existing = db.query(ThreadMemory).filter(ThreadMemory.url == url).first()
        if existing:
            existing.generated_reply = draft
            existing.status = "pending_approval"
            existing.platform = "url_pipeline"
            db.commit()
            thread_id = existing.id
        else:
            thread = ThreadMemory(
                url=url,
                platform="url_pipeline",
                status="pending_approval",
                scraped_content=page_content,
                generated_reply=draft,
                is_ghost=False,
            )
            db.add(thread)
            db.commit()
            thread_id = thread.id
    finally:
        db.close()

    return {
        "status": "success",
        "detail": f"Draft generated for QA Approval (#{thread_id})",
        "thread_id": thread_id,
        "platform_name": domain,
        "title": title,
    }


def post_generic_url_draft(thread_id: int) -> dict:
    """
    Opens browser, navigates to the thread's URL, finds comment/editor,
    fills with the approved draft. Called when user clicks Approve.
    """
    from src.database import SessionLocal, ThreadMemory

    db = SessionLocal()
    try:
        thread = db.query(ThreadMemory).filter(ThreadMemory.id == thread_id).first()
        if not thread:
            return {"status": "failed", "detail": "Thread not found"}
        url = thread.url
        draft_text = thread.generated_reply or ""
        domain = urllib.parse.urlparse(url).netloc.lower()
    finally:
        db.close()

    if not draft_text:
        return {"status": "failed", "detail": "No draft text to post"}

    # Open browser
    from playwright.sync_api import sync_playwright
    from pathlib import Path
    import config

    print(f"\n{'='*60}")
    print(f"POSTING DRAFT #{thread_id} ON: {domain}")
    print(f"URL: {url}")
    print(f"{'='*60}")

    session_dir = Path(config.BASE_DIR) / "sessions"
    session_dir.mkdir(exist_ok=True)
    profile_dir = session_dir / f"generic_{domain.replace('.', '_')}_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    p = sync_playwright().start()
    context = p.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir),
        headless=False,
        viewport={"width": 1366, "height": 768},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        args=["--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"],
    )
    page = context.new_page()

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        # Login check — only if it's a REAL login barrier, not just a "Log in" link
        try:
            has_login_input = page.locator('input[type="password"]').count() > 0
            url_is_login = any(w in page.url.lower() for w in ["login", "sign-in", "signin", "auth"])
        except Exception:
            has_login_input = False
            url_is_login = False
        if has_login_input or url_is_login:
            print(f"\n>> LOGIN REQUIRED for {domain}")
            print(">> Log in manually, then press ENTER.\n")
            input(">> Press ENTER after logging in...")
            page.wait_for_timeout(3000)

        # Find text input
        comment_box = None
        selectors = [
            'textarea:visible', 'textarea[name="text"]',
            'div[contenteditable="true"]', '[role="textbox"]',
        ]
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if el.count() > 0 and el.is_visible():
                    comment_box = el
                    print(f"  Found: {sel}")
                    break
            except Exception:
                continue

        if not comment_box:
            context.close()
            p.stop()
            return {"status": "failed", "detail": "Could not find comment box"}

        comment_box.click()
        page.wait_for_timeout(500)
        comment_box.fill(draft_text)
        page.wait_for_timeout(500)

        # Actually find and click a submit/post/reply button - filling
        # the box alone does NOT post anything.
        submit_selectors = [
            'button:has-text("Post")', 'button:has-text("Publish")',
            'button:has-text("Comment")', 'button:has-text("Reply")',
            'button:has-text("Submit")', 'button:has-text("Save")',
            'button[type="submit"]', 'input[type="submit"]',
        ]
        clicked_submit = False
        for sel in submit_selectors:
            try:
                btn = page.locator(sel).first
                if await_count := btn.count():
                    if btn.is_visible():
                        btn.click(timeout=5000)
                        page.wait_for_timeout(3000)
                        clicked_submit = True
                        print(f"  ✅ Clicked submit button: {sel}")
                        break
            except Exception:
                continue

        db = SessionLocal()
        try:
            t = db.query(ThreadMemory).filter(ThreadMemory.id == thread_id).first()
            if t:
                t.status = "posted" if clicked_submit else "awaiting_manual"
                db.commit()
        finally:
            db.close()

        if clicked_submit:
            print(f">> ✅ Actually posted! Verify on the live page.")
            return {"status": "success", "detail": "Posted live - browser will confirm on page.", "posted_url": page.url}
        else:
            print(f">> ⚠️ Could not find a Submit/Post button. Draft is filled - please click it manually.")
            return {"status": "awaiting_manual", "detail": "Draft filled but no Submit button found automatically - please click Post/Submit manually in the open browser."}
        

    except Exception as e:
        logger.error(f"[URLRouter] Posting failed: {e}")
        try:
            context.close()
            p.stop()
        except Exception:
            pass
        return {"status": "failed", "detail": str(e)}


def list_sessions() -> list:
    """Return all domains with saved browser sessions."""
    from src.generic_listing_agent import list_saved_sessions
    return list_saved_sessions()



def post_new_article_on_site(url: str, topic: str = None) -> dict:
    """
    For simple writing tools (write.as, retry.co, Hashnode's new-post page,
    etc.) where the whole page IS the editor - no thread to reply to, no
    comment box to hunt for. This opens the given URL, writes an AI
    article directly into the editor, publishes it, and returns the live
    published URL as the backlink.
    """
    from playwright.sync_api import sync_playwright
    from pathlib import Path
    import config

    domain = urllib.parse.urlparse(url).netloc.lower()
    print(f"\n{'='*60}")
    print(f"WRITING NEW ARTICLE ON: {domain}")
    print(f"URL: {url}")
    print(f"{'='*60}")

    # Generate the article content first (before opening the browser)
    brand = get_brand_profile()
    content = _generate_post_content(topic or f"AI agents and production workflows", brand.get("description", ""))

    session_dir = Path(config.BASE_DIR) / "sessions"
    session_dir.mkdir(exist_ok=True)
    profile_dir = session_dir / f"generic_{domain.replace('.', '_')}_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    p = sync_playwright().start()
    context = p.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir),
        headless=False,
        viewport={"width": 1366, "height": 768},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        args=["--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"],
    )
    page = context.new_page()

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        # Login check - only if it's a REAL login barrier
        try:
            has_login_input = page.locator('input[type="password"]').count() > 0
            url_is_login = any(w in page.url.lower() for w in ["login", "sign-in", "signin", "auth"])
        except Exception:
            has_login_input = False
            url_is_login = False
        if has_login_input or url_is_login:
            print(f"\n>> LOGIN REQUIRED for {domain}")
            print(">> Log in manually in the browser window, then press ENTER here.\n")
            input(">> Press ENTER after logging in...")
            page.wait_for_timeout(3000)

        # Find the editor - simple writing tools usually have ONE obvious
        # editable area: a textarea, a contenteditable div, or the body
        # itself is directly editable. Try broad selectors in order.
        editor_selectors = [
            'textarea',
            'div[contenteditable="true"]',
            '[role="textbox"]',
            'article[contenteditable]',
            '.editor', '#editor',
        ]
        editor = None
        found_selector = None
        for sel in editor_selectors:
            try:
                el = page.locator(sel).first
                if el.count() > 0 and el.is_visible():
                    editor = el
                    found_selector = sel
                    break
            except Exception:
                continue

        if not editor:
            context.close()
            p.stop()
            return {"status": "failed", "detail": "Could not find an editor on this page - it may need manual setup first (e.g. clicking 'New Post')."}

        print(f"  Found editor: {found_selector}")

        editor.click()
        page.wait_for_timeout(300)

        # Fill atomically - avoids partial/interrupted typing on longer articles
        typed_ok = False
        try:
            editor.fill(content, timeout=10000)
            typed_ok = True
        except Exception as fill_err:
            print(f"  fill() failed ({fill_err}), falling back to keystroke typing")

        if not typed_ok:
            try:
                editor.click()
                page.keyboard.type(content, delay=10)
            except Exception as e2:
                context.close()
                p.stop()
                return {"status": "failed", "detail": f"Could not write into editor: {e2}"}

        page.wait_for_timeout(1000)

        # Find and click a publish button
        publish_selectors = [
            'button:has-text("Publish")', 'button:has-text("Post")',
            'button:has-text("Save")', 'button:has-text("Submit")',
            'button[type="submit"]',
        ]
        published = False
        for sel in publish_selectors:
            try:
                btn = page.locator(sel).first
                if btn.count() > 0 and btn.is_visible():
                    try:
                        btn.click(timeout=6000)
                        page.wait_for_timeout(3000)
                        published = True
                        print(f"  ✅ Clicked publish button: {sel}")
                        break
                    except Exception:
                        continue
            except Exception:
                continue

        landed_url = page.url

        if published:
            # Save as a real backlink immediately - the published URL IS the backlink
            from src.database import SessionLocal, PostedBacklink
            db = SessionLocal()
            try:
                db.add(PostedBacklink(
                    platform=domain, target_url=landed_url,
                    content=content, status="live",
                    note="Published as a new standalone article via generic writer flow.",
                ))
                db.commit()
            finally:
                db.close()

            print(f">> ✅ Published! Live URL: {landed_url}")
            context.close()
            p.stop()
            return {"status": "success", "detail": f"Published new article on {domain}", "posted_url": landed_url}
        else:
            print(f">> ⚠️ Could not find a Publish button. Content is typed - please click Publish manually, then copy the URL.")
            return {"status": "awaiting_manual", "detail": "Article written but no Publish button found automatically - please click Publish manually in the open browser, then note the URL for your tracker."}

    except Exception as e:
        logger.error(f"[URLRouter] New article posting failed: {e}")
        try:
            context.close()
            p.stop()
        except Exception:
            pass
        return {"status": "failed", "detail": str(e)}

