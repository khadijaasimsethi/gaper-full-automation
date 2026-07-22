
"""
Powers the Articles tab: generate a draft (Gemini + RAG case studies),
let the human edit/improve/discard it, then submit - which posts live
using the SAME saved login sessions Contra/Notion already use.

Does not touch adapters.py's ContraAdapter/NotionAdapter classes.
"""
import logging
import google.generativeai as genai
from src.database import (
    create_article_draft, get_article_draft, update_article_draft,
    delete_article_draft, retrieve_relevant_case_studies, PostedBacklink, SessionLocal,
    get_cached_guidelines, set_cached_guidelines
)
from src.gaper_scraper import get_brand_profile
from src.adapters import get_adapter
from src.notion_session_poster import post_to_notion_session
from src.contra_poster import post_to_contra_feed
from src.devto_poster import post_to_devto
from src.waterfall import ingest_thread
from src.ingestion import IngestionException
import urllib.parse
import config

logger = logging.getLogger(__name__)
GEMINI_MODEL = "gemini-flash-latest"


CONTRA_DEFAULT_GUIDELINES = (
    "Be genuinely helpful and on-topic. Light self-promotion is fine if it "
    "directly answers the thread, but no repeated posting of the same link, "
    "no unrelated pitches, no spammy phrasing."
)

DEVTO_GUIDELINES = (
    "Write genuinely useful, technical or experience-based content for developers first. "
    "No pure advertising or listicle-style spam. It's fine to mention your own product/company "
    "if it's naturally relevant to the point being made, but the post must stand on its own "
    "value even if that mention were removed. No plagiarized or purely AI-sounding filler content. "
    "No excessive tags (max 4), no clickbait titles. Never use em dashes (—) or en dashes (–)."
)
def _get_or_cache_guidelines(domain: str, fallback: str) -> str:
    cached = get_cached_guidelines(domain)
    if cached:
        return cached
    set_cached_guidelines(domain, fallback)
    return fallback


def _check_relevance(topic: str, content_context: str) -> dict:
    """
    Lightweight AI relevance gate (Phase 4's missing 'Relevant?' check).
    Returns a warning instead of hard-blocking - the human still approves
    everything in the Articles tab, this just flags likely-irrelevant
    drafts so they're easy to spot before submitting.
    """
    try:
        model = _gemini()
        prompt = f"""
Topic: {topic}
Context: {content_context[:800]}

Is this genuinely relevant to Gaper (an AI-native developer staffing / implementation platform)?
Answer with ONLY one word: RELEVANT or IRRELEVANT.
"""
        res = model.generate_content(prompt)
        verdict = (res.text or "").strip().upper()
        return {"relevant": "IRRELEVANT" not in verdict}
    except Exception:
        return {"relevant": True}  # fail open - don't block on a relevance-check error


def _gemini():
    genai.configure(api_key=config.GEMINI_API_KEY)

    return genai.GenerativeModel(GEMINI_MODEL, generation_config={"temperature": 1.1, "top_p": 0.95})


def _case_study_block(query_text: str) -> str:
    cases = retrieve_relevant_case_studies(query_text)
    return "\n".join(f"- {c}" for c in cases) if cases else "No specific case study matched - use general USPs only, do not invent stats."


def generate_draft(platform: str, topic: str = None, target_url: str = None) -> dict:
    """
    platform: 'contra' or 'notion'.
    topic: what the post/article should be about. If None/empty, Gemini
    picks a relevant topic itself (based on Gaper's USPs/case studies).
    target_url: required for contra reply mode, ignored for notion.
    """
    if not config.GEMINI_API_KEY:
        return {"status": "failed", "detail": "GEMINI_API_KEY not set in .env."}

    if platform not in ("contra", "notion","devto"):
        return {"status": "failed", "detail": f"Unknown platform '{platform}'."}


    brand = get_brand_profile()
    usps = brand.get("usps", "")
    model = _gemini()

    if not topic or not topic.strip():
        try:
            topic_prompt = f"""
Suggest ONE specific, non-generic topic (under 12 words) for a Gaper (gaper.io) {platform} post.
Brand USPs: {usps}
Output ONLY the topic phrase, nothing else.
"""
            topic_res = model.generate_content(topic_prompt)
            topic = (topic_res.text or "").strip().strip('"') or "hiring remote developers fast"
        except Exception:
            topic = "hiring remote developers fast"

    case_block = _case_study_block(topic)

    try:
        if platform == "notion":
            prompt = f"""
Write a full blog article (200-400 words) about: {topic}
This is for Gaper (gaper.io), to be published as a public Notion blog page.

Brand USPs:
{usps}
Relevant case studies/facts you MAY cite naturally if they genuinely fit (never invent numbers not listed):
{case_block}
Link to include naturally once, INSIDE THE BODY ONLY: {config.PRIMARY_URL}

Rules:
- Line 1: ONLY the plain title text. No links, no markdown, no brackets, under 70 characters.
- Then a blank line, then the body.
- Use "## " for headings, "* " for bullets, "**text**" for bold.
- Genuinely useful, factual tone, not a sales pitch.
- Output ONLY the title + article, nothing else.
"""
            res = model.generate_content(prompt)
            text = (res.text or "").strip()
            lines = [l for l in text.split("\n") if l.strip()]
            title = lines[0].strip() if lines else topic[:70]
            body = "\n".join(lines[1:]).strip() if len(lines) > 1 else text
            draft_id = create_article_draft(platform="notion", topic=topic, content=body, title=title)
            return {"status": "success", "draft_id": draft_id, "title": title, "content": body}
        elif platform == "devto":
            prompt = f"""
Write a blog article (350-500 words) about: {topic}
This is for Gaper (gaper.io), to be published on Dev.to (a developer community site).

Dev.to's community guidelines (follow these strictly - Dev.to moderators actively remove content that violates them):
{DEVTO_GUIDELINES}

Brand USPs (mention Gaper only if it's naturally relevant to the point, not forced):
{usps}
Relevant case studies/facts you MAY cite naturally if they genuinely fit (never invent numbers not listed):
{case_block}
If you mention Gaper, link to it naturally once, as a bare clickable URL written exactly like this (no markdown, no brackets): {config.PRIMARY_URL}

Rules:
- Line 1: ONLY the plain title text. No links, no markdown, no brackets, under 70 characters.
- Then a blank line, then the body, written for a developer audience (technical, specific, no fluff).
- Use "## " for headings, "* " for bullets, "**text**" for bold, and fenced code blocks (```) if genuinely relevant.
- NEVER use em dashes (—) or en dashes (–). Use a comma, period, or "and" instead.
- Output ONLY the title + article, nothing else.
"""
            res = model.generate_content(prompt)
            text = (res.text or "").strip()
            lines = [l for l in text.split("\n") if l.strip()]
            title = lines[0].strip() if lines else topic[:70]
            body = "\n".join(lines[1:]).strip() if len(lines) > 1 else text
            draft_id = create_article_draft(platform="devto", topic=topic, content=body, title=title)
            return {"status": "success", "draft_id": draft_id, "title": title, "content": body}

        elif not target_url:  
            prompt = f"""
Write a short standalone community update post (2 sentences) for Gaper (gaper.io),
to be posted in Contra's community feed under "Share progress, updates, or highlights".
Topic: {topic}

Brand USPs:
{usps}
Relevant case studies/facts you MAY cite naturally if they genuinely fit (never invent numbers not listed):
{case_block}
Link to include naturally once: {config.PRIMARY_URL}

Rules:
- Casual, first-person, builder-to-builder tone, like a real progress update - NOT a sales pitch.
- No markdown formatting (no **, no #, no bullet lists) - plain text only.
- NEVER use em dashes (—) or en dashes (–). Use a comma, period, or "and" instead.
- Output ONLY the final post text, nothing else.

"""
            res = model.generate_content(prompt)
            content = (res.text or "").strip()
            draft_id = create_article_draft(platform="contra", topic=topic, content=content, target_url=None)
            return {"status": "success", "draft_id": draft_id, "content": content}

        else:  
           
            domain = urllib.parse.urlparse(target_url).netloc
            thread_content = ""
            thread_title = topic
            try:
                thread_data = ingest_thread(target_url)
                thread_content = thread_data.get("content") or ""
                thread_title = thread_data.get("title") or topic
            except IngestionException as e:
                logger.warning(f"[ArticleStudio] Could not read thread content for {target_url}: {e}. Falling back to topic-only.")

            guidelines = _get_or_cache_guidelines(domain, CONTRA_DEFAULT_GUIDELINES)
            is_ghost = "no link" in guidelines.lower() or "no promotional" in guidelines.lower()

            relevance = _check_relevance(topic, thread_content)

            prompt = f"""
Write a short community comment (2-4 sentences) replying to this REAL thread:
Thread title: {thread_title}
Thread content: {thread_content[:1500] if thread_content else "(could not be read - reply generally to the topic below)"}
Topic to focus on: {topic}

This community's norms: {guidelines}

This is for Gaper (gaper.io).
Brand USPs:
{usps}
Relevant case studies/facts you MAY cite naturally if they genuinely fit (never invent numbers not listed):
{case_block}
{"Do NOT include any link or mention Gaper by name - this community forbids promotional links." if is_ghost else f"Link to include naturally once, as a bare clickable URL written exactly like this (no markdown, no brackets): {config.PRIMARY_URL}"}

Rules:
- React specifically to what the thread actually says - don't write a generic pitch.
- Casual, builder-to-builder tone, add real value first.
- No markdown formatting (no **, no #, no bullet lists, no [text](url) style links) - the link must appear as a plain bare URL so it auto-detects as clickable.
- NEVER use em dashes (—) or en dashes (–). Use a comma, period, or "and" instead.
- Output ONLY the final comment text, nothing else.
"""
            res = model.generate_content(prompt)
            content = (res.text or "").strip()
            draft_id = create_article_draft(platform="contra", topic=topic, content=content, target_url=target_url, is_ghost=is_ghost)
            result = {"status": "success", "draft_id": draft_id, "content": content}
            if not relevance["relevant"]:
                result["relevance_warning"] = "This topic/thread may not be strongly relevant to Gaper - review before submitting."
            return result

    except Exception as e:
        logger.error(f"[ArticleStudio] Generation failed: {e}")
        return {"status": "failed", "detail": str(e)}


def regenerate_draft(draft_id: int, feedback: str) -> dict:
    draft = get_article_draft(draft_id)
    if not draft:
        return {"status": "failed", "detail": "Draft not found."}

    model = _gemini()
    prompt = f"""
You are revising a draft for Gaper (gaper.io).

Original topic: {draft.topic}
Previous draft:
{(draft.title + chr(10) if draft.title else "")}{draft.content}

User feedback: "{feedback}"

Revise to address the feedback. Keep the same format as before (title+body for a Notion article, plain short comment for Contra). Output ONLY the revised content, nothing else.
"""
    try:
        res = model.generate_content(prompt)
        text = (res.text or "").strip()

        if draft.platform == ("notion","devto"):
            lines = [l for l in text.split("\n") if l.strip()]
            new_title = lines[0].strip() if lines else draft.title
            new_body = "\n".join(lines[1:]).strip() if len(lines) > 1 else text
            update_article_draft(draft_id, content=new_body, title=new_title)
            return {"status": "success", "title": new_title, "content": new_body}
        else:
            update_article_draft(draft_id, content=text)
            return {"status": "success", "content": text}
    except Exception as e:
        logger.error(f"[ArticleStudio] Regeneration failed: {e}")
        return {"status": "failed", "detail": str(e)}


def submit_draft(draft_id: int) -> dict:
    """Actually posts the draft live, using the same saved sessions the adapters/scripts already use."""
    draft = get_article_draft(draft_id)
    if not draft:
        return {"status": "failed", "detail": "Draft not found."}

    if draft.platform == "contra":
        if draft.target_url:
           
            
            from src.contra_poster import post_reply_to_contra
            result = post_reply_to_contra(draft.target_url, draft.content)
            if result["status"] == "success":
                db = SessionLocal()
                try:
                    db.add(PostedBacklink(
                        platform="contra", target_url=draft.target_url,
                        content=draft.content, status="live", is_ghost=draft.is_ghost,
                    ))
                    db.commit()
                finally:
                    db.close()
            if result["status"] == "success" and draft.is_ghost:
                db = SessionLocal()
                try:
                    latest = (db.query(PostedBacklink)
                              .filter(PostedBacklink.platform == "contra", PostedBacklink.target_url == draft.target_url)
                              .order_by(PostedBacklink.created_at.desc()).first())
                    if latest:
                        latest.is_ghost = True
                        db.commit()
                finally:
                    db.close()
        else:
            # Standalone feed post - the robust, tested composer-detection path
            result = post_to_contra_feed(draft.content)
            if result["status"] == "success":
                db = SessionLocal()
                try:
                    db.add(PostedBacklink(
                        platform="contra", target_url="https://contra.com/community/for-you",
                        content=draft.content, status="live", is_ghost=draft.is_ghost,
                    ))
                    db.commit()
                finally:
                    db.close()
        update_article_draft(draft_id, status="posted" if result["status"] == "success" else "failed", detail=result.get("detail"))
        return result

    elif draft.platform == "notion":
        result = post_to_notion_session(draft.title or draft.topic, draft.content)
        if result["status"] == "success":
       
            update_article_draft(draft_id, status="awaiting_confirm", detail=result.get("detail"))
        else:
            update_article_draft(draft_id, status="failed", detail=result.get("detail"))
        return result
    elif draft.platform == "devto":
        
        result = post_to_devto(draft.title or draft.topic, draft.content, tags=["ai", "hiring", "startup"])
        if result["status"] == "success":
            update_article_draft(draft_id, status="posted", detail=result.get("detail"))
            db = SessionLocal()
            try:
                db.add(PostedBacklink(
                    platform="devto", target_url=result.get("posted_url", "https://dev.to"),
                    content=f"{draft.title}\n\n{draft.content}", status="live",
                    note="Published via Dev.to API.",
                ))
                db.commit()
            finally:
                db.close()
        else:
            update_article_draft(draft_id, status="failed", detail=result.get("detail"))
        return result
    return {"status": "failed", "detail": f"Unknown platform '{draft.platform}'."}


def confirm_notion_publish(draft_id: int) -> dict:
    """
    Call this ONLY after the human has actually clicked Share -> Publish
    to web in the Notion browser window. Marks the draft posted and logs
    it to PostedBacklink so it shows up in the New Backlinks tab.
    """
    draft = get_article_draft(draft_id)
    if not draft:
        return {"status": "failed", "detail": "Draft not found."}
    if draft.platform != "notion":
        return {"status": "failed", "detail": "This is only for Notion drafts."}
    if draft.status != "awaiting_confirm":
        return {"status": "failed", "detail": f"Draft isn't awaiting confirmation (status: {draft.status})."}

    update_article_draft(draft_id, status="posted", detail="Confirmed published by user.")
    db = SessionLocal()
    try:
        db.add(PostedBacklink(
            platform="notion", target_url=getattr(config, "NOTION_DATABASE_URL", ""),
            content=f"{draft.title}\n\n{draft.content}", status="live",
            note="Typed via browser session, published manually by user.",
        ))
        db.commit()
    finally:
        db.close()
    return {"status": "success", "detail": "Marked as published and logged to New Backlinks."}


def discard_draft(draft_id: int) -> bool:
    return delete_article_draft(draft_id)