"""
Universal auto-poster.

Give it ANY url:
  1. Opens it with the domain's saved session (cookies/profile).
  2. If a login wall shows up, waits for a one-time manual login, saves session.
  3. Finds the "write / new post" editor (clicking a trigger link if needed).
  4. Generates an article with Gemini where the Gaper backlink is EMBEDDED in
     natural anchor words (never a bare URL), then fills + publishes it.

Entry points:
  post_article(url)                 -> sync, does everything
  await post_article_async(url)
  run(url)                          -> parse first (llm_parser) then act
"""

import asyncio
import json
import logging
import re
import uuid
from pathlib import Path

import google.generativeai as genai

import config
from src import session_manager as sm

logger = logging.getLogger(__name__)
GEMINI_MODEL = "gemini-flash-latest"

SCREENSHOT_DIR = Path(config.BASE_DIR) / "output" / "post_screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

BRAND_URL = "https://gaper.io"
BRAND_NAME = "Gaper"

ANCHOR_TEXTS = [
    "hire vetted remote developers",
    "AI implementation partner",
    "on-demand AI engineers",
    "remote developer staffing",
    "build with senior AI engineers",
]

# Links that usually lead from a homepage to the real editor.
WRITE_TRIGGERS = [
    'a:has-text("New post")', 'button:has-text("New post")',
    'a:has-text("Write")', 'button:has-text("Write")',
    'a:has-text("Create post")', 'button:has-text("Create post")',
    'a:has-text("New paste")', 'a:has-text("New entry")',
    'a:has-text("Start writing")', 'a:has-text("Compose")',
    'a:has-text("Submit article")', 'a:has-text("Submit a post")',
    'a:has-text("Guest post")', 'a:has-text("Add article")',
    'a[href*="new" i]', 'a[href*="write" i]', 'a[href*="submit" i]',
]

PUBLISH_TRIGGERS = [
    'button:has-text("Publish")', 'button:has-text("Post")',
    'button:has-text("Submit")', 'button:has-text("Save")',
    'button:has-text("Create")', 'button:has-text("Go")',
    'input[type="submit"]', 'button[type="submit"]',
    'a:has-text("Publish")',
]

TITLE_HINTS = ("title", "subject", "headline", "heading", "name", "url")


# ----------------------------------------------------------------------------
# Article generation (backlink embedded in anchor words)
# ----------------------------------------------------------------------------
def generate_article(topic_hint: str = "", platform: str = "", supports_html: bool = False) -> dict:
    """
    Returns {"title": str, "body": str, "anchor": str}.
    body contains the backlink as [anchor](url) markdown, or <a href> when the
    target editor accepts HTML. Never a naked URL.
    """
    import random

    anchor = random.choice(ANCHOR_TEXTS)
    link_format = (
        f'<a href="{BRAND_URL}">{anchor}</a>' if supports_html else f"[{anchor}]({BRAND_URL})"
    )

    prompt = f"""
Write a genuinely useful 500-650 word article for {platform or 'a public blog'}.

Topic focus: {topic_hint or 'how companies actually ship AI features - hiring, scoping, and avoiding the common failure modes'}

HARD RULES:
- Plain, practical, non-promotional tone. No fluff, no "in today's fast-paced world".
- Structure: a short intro, 3-4 subheadings, a 2-sentence conclusion.
- Mention {BRAND_NAME} exactly ONCE, in the middle of a sentence, as helpful
  context - not a sales pitch.
- The link MUST appear exactly once, embedded in the anchor words, written
  literally as: {link_format}
- NEVER print the raw URL {BRAND_URL} on its own anywhere else.
- Output format: {"HTML fragment" if supports_html else "Markdown"}.

Return ONLY valid JSON:
{{"title": "<catchy 6-10 word title>", "body": "<the full article>"}}
"""

    try:
        genai.configure(api_key=config.GEMINI_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL)
        raw = (model.generate_content(prompt).text or "").strip()

        if raw.startswith("```json"):
            raw = raw[7:]
        elif raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            data = json.loads(match.group()) if match else {}

        title = (data.get("title") or "").strip()
        body = (data.get("body") or "").strip()
        if not body:
            raise ValueError("empty body from Gemini")

        # Guarantee the backlink survived the model.
        if BRAND_URL not in body:
            body += f"\n\nFurther reading: {link_format}."

        return {"title": title or "Shipping AI features without burning a quarter",
                "body": body, "anchor": anchor}

    except Exception as e:  # noqa: BLE001
        logger.warning(f"Article generation failed, using fallback: {e}")
        return _fallback_article(link_format, anchor)


def _fallback_article(link_format: str, anchor: str) -> dict:
    body = f"""Most AI projects do not fail on the model. They fail on scoping and staffing.

## Start with one painful workflow
Pick a single workflow that costs your team real hours every week. Ship a narrow
version of it end to end before you generalise anything.

## Staff for iteration, not for demos
A demo takes a weekend; production takes evaluation harnesses, logging, and
someone on call. Teams that {anchor} early tend to get past the prototype wall,
which is the gap {BRAND_NAME} was built to close ({link_format}).

## Measure before you optimise
Log inputs, outputs, and human corrections from day one. Without that, model
swaps are guesswork.

## Conclusion
Narrow scope, real telemetry, and engineers who have shipped this before beat a
bigger model almost every time. Start small and keep the feedback loop tight.
"""
    return {"title": "Why AI projects stall after the prototype", "body": body, "anchor": anchor}


# ----------------------------------------------------------------------------
# Editor discovery
# ----------------------------------------------------------------------------
async def _click_write_trigger(page) -> bool:
    for sel in WRITE_TRIGGERS:
        try:
            el = page.locator(sel).first
            if await el.count() > 0 and await el.is_visible():
                await el.click(timeout=4000)
                await page.wait_for_timeout(2500)
                print(f"  ↪️  Clicked '{sel}' to reach the editor.")
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


async def _search_frame_for_body(frame):
    """Search ONE frame (main page or an iframe) for the biggest editable field."""
    best, best_area, is_ce = None, 0, False
    try:
        candidates = await frame.locator(
            "textarea, div[contenteditable='true'], [role='textbox'], body[contenteditable='true']"
        ).all()
    except Exception:  # noqa: BLE001
        return None, 0, False

    for el in candidates:
        try:
            if not await el.is_visible():
                continue
            box = await el.bounding_box()
            if not box:
                continue
            area = box["width"] * box["height"]
            if area > best_area:
                best_area, best = area, el
                is_ce = (await el.evaluate("el => el.tagName.toLowerCase()")) != "textarea"
        except Exception:  # noqa: BLE001
            continue
    return best, best_area, is_ce


async def _find_body_field(page):
    """
    Biggest visible textarea / contenteditable = the article body.
    Searches the MAIN page first, then every iframe on it - rich editors
    like Blogger, WordPress (classic), and TinyMCE-based editors put the
    actual writable area inside an <iframe>, which a plain page.locator()
    call never sees.
    """
    best, best_area, is_ce = await _search_frame_for_body(page)

    for frame in page.frames:
        if frame == page.main_frame:
            continue
        try:
            f_best, f_area, f_is_ce = await _search_frame_for_body(frame)
        except Exception:  # noqa: BLE001
            continue
        if f_best is not None and f_area > best_area:
            best, best_area, is_ce = f_best, f_area, f_is_ce

    return best, is_ce


async def _find_title_field(page, body_field):
    """A short text input that looks like a title/subject field."""
    try:
        inputs = await page.locator(
            "input[type='text'], input[type='search'], input:not([type])"
        ).all()
    except Exception:  # noqa: BLE001
        return None

    fallback = None
    for el in inputs:
        try:
            if not await el.is_visible():
                continue
            meta = " ".join(
                str(x or "").lower()
                for x in [
                    await el.get_attribute("name"),
                    await el.get_attribute("id"),
                    await el.get_attribute("placeholder"),
                    await el.get_attribute("aria-label"),
                ]
            )
            if any(h in meta for h in TITLE_HINTS):
                return el
            if fallback is None:
                fallback = el
        except Exception:  # noqa: BLE001
            continue
    return fallback


async def _fill(el, text: str, contenteditable: bool = False):
    await el.click()
    if contenteditable:
        await el.evaluate(
            "(node, value) => { node.focus(); node.innerText = value; "
            "node.dispatchEvent(new Event('input', { bubbles: true })); }",
            text,
        )
    else:
        await el.fill(text)


async def _publish(page) -> bool:
    for sel in PUBLISH_TRIGGERS:
        try:
            el = page.locator(sel).first
            if await el.count() > 0 and await el.is_visible() and await el.is_enabled():
                await el.click(timeout=8000)
                await page.wait_for_timeout(5000)
                print(f"  ✅ Clicked publish via '{sel}'")
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


# ----------------------------------------------------------------------------
# Main flow
# ----------------------------------------------------------------------------
async def post_article_async(
    url: str,
    article: dict = None,
    topic_hint: str = "",
    interactive_login: bool = True,
) -> dict:
    domain = sm.domain_of(url)
    session_id = str(uuid.uuid4())[:8]
    known = sm.has_saved_session(domain)
    print(f"\n🌐 {url}\n   session for {domain}: {'reused ✅' if known else 'new'}")

    p = context = page = None
    try:
        # If we have no session yet, show the window so a login can be done.
        p, context, page = await sm.get_context(domain, force_visible=not known)

        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(2500)

        logged_in = await sm.ensure_logged_in(
            context, page, url, domain, interactive=interactive_login
        )
        if not logged_in:
            shot = await _shot(page, session_id, "login_required")
            return {
                "status": "needs_login",
                "url": url,
                "platform_name": domain,
                "detail": f"Login required for {domain}. Log in once, then re-run.",
                "screenshot_path": shot,
            }
        if context.pages:
            page = context.pages[-1]
        await sm.save_cookies(context, domain)

        # Reach the editor if this is a homepage.
        body_field, is_ce = await _find_body_field(page)
        if body_field is None:
            if await _click_write_trigger(page):
                body_field, is_ce = await _find_body_field(page)

        if body_field is None:
            shot = await _shot(page, session_id, "no_editor")
            return {
                "status": "failed",
                "url": url,
                "platform_name": domain,
                "detail": "No content editor found on this page.",
                "screenshot_path": shot,
            }

        # Content: HTML anchors only make sense in a rich-text editor.
        if article is None:
            article = generate_article(
                topic_hint=topic_hint, platform=domain, supports_html=is_ce
            )

        title_field = await _find_title_field(page, body_field)
        if title_field is not None and article.get("title"):
            try:
                await _fill(title_field, article["title"])
                print(f"  ✅ Title: {article['title'][:60]}")
            except Exception as e:  # noqa: BLE001
                print(f"  ⚠️ Title fill failed: {e}")

        await _fill(body_field, article["body"], contenteditable=is_ce)
        print(f"  ✅ Body filled ({len(article['body'])} chars), backlink anchor: '{article['anchor']}'")
        await page.wait_for_timeout(800)

        published = await _publish(page)
        landed = page.url
        shot = await _shot(page, session_id, "posted" if published else "filled")

        return {
            "status": "success" if published else "awaiting_manual",
            "url": url,
            "platform_name": domain,
            "posted_url": landed,
            "title": article.get("title"),
            "anchor_text": article.get("anchor"),
            "backlink": BRAND_URL,
            "detail": (
                f"✅ Published on {domain} with embedded backlink"
                if published
                else "Content filled but no publish button found - finish manually."
            ),
            "screenshot_path": shot,
        }

    except Exception as e:  # noqa: BLE001
        logger.error(f"post_article failed: {e}")
        shot = await _shot(page, session_id, "error") if page else None
        return {"status": "failed", "url": url, "platform_name": domain,
                "detail": str(e), "screenshot_path": shot}
    finally:
        try:
            if context:
                await context.close()
            if p:
                await p.stop()
        except Exception:  # noqa: BLE001
            pass


async def _shot(page, session_id: str, label: str):
    try:
        path = SCREENSHOT_DIR / f"{session_id}_{label}.png"
        await page.screenshot(path=str(path), full_page=True)
        return str(path)
    except Exception:  # noqa: BLE001
        return None


def _run_sync(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # Already inside a loop (e.g. a web server) - use a private one.
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def post_article(url: str, article: dict = None, topic_hint: str = "",
                 interactive_login: bool = True) -> dict:
    """Sync wrapper."""
    return _run_sync(post_article_async(url, article, topic_hint, interactive_login))


def run(url: str, topic_hint: str = "") -> dict:
    """
    Full pipeline: classify with llm_parser, then post when the page is postable.
    """
    from src.llm_parser import parse_url

    parsed = parse_url(url)
    action = parsed.get("action", "skip")
    print(f"📊 action={action} type={parsed.get('type')} score={parsed.get('relevance_score')}")

    if action in ("post", "reply") or parsed.get("requires_login"):
        result = post_article(
            url,
            topic_hint=topic_hint or parsed.get("title", ""),
        )
        result["parsed"] = parsed
        return result

    return {"status": "skipped", "url": url, "detail": f"action={action}", "parsed": parsed}


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("usage: python -m src.universal_poster <url> [topic hint]")
        raise SystemExit(1)
    print(json.dumps(run(sys.argv[1], " ".join(sys.argv[2:])), indent=2, default=str))