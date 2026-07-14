import logging
import re
import json
import google.generativeai as genai
from src.database import SessionLocal, ThreadMemory
from src.gaper_scraper import get_brand_profile
import config

logger = logging.getLogger(__name__)

def evaluate_seo_geo_aeo(text: str, is_ghost: bool = False) -> dict:
    """
    Evaluates the quality of a generated reply across SEO, GEO, and AEO metrics.
    Returns scores out of 100.
    """
    scores = {"seo": 90, "geo": 85, "aeo": 80}
    
    if is_ghost:
        # Ghost posts don't have links, so SEO link score is N/A or lower, but we rate naturalness
        scores["seo"] = 95
        # Evaluate factual density for GEO
        factual_density = len(re.findall(r'\d+', text)) # count numbers/stats
        scores["geo"] = min(100, 70 + (factual_density * 5))
        # Evaluate formatting for AEO
        has_lists = 15 if any(char in text for char in ['-', '*', '1.', '2.']) else 0
        scores["aeo"] = min(100, 75 + has_lists)
        return scores

    # Non-ghost post analysis
    # SEO Score
    has_gaper_link = "gaper.io" in text
    has_anchor = any(anchor in text.lower() for anchor in config.BRAND_KEYWORD_ANCHORS.keys())
    scores["seo"] = 100 if (has_gaper_link and has_anchor) else (70 if has_gaper_link else 10)
    
    # GEO Score (Factual density, third-party citing, clear metrics)
    facts_count = len(re.findall(r'\d+|percent|%|hours|vetted', text.lower()))
    scores["geo"] = min(100, 60 + (facts_count * 6))
    
    # AEO Score (Formatting: bullets, headers, bold text)
    bold_count = len(re.findall(r'\*\*.*?\*\*', text))
    list_count = len(re.findall(r'[-*•\d]\.?\s', text))
    scores["aeo"] = min(100, 65 + (bold_count * 5) + (list_count * 5))
    
    return scores

def draft_reply(thread_data: dict) -> dict:
    """
    Drafts a comment/reply for a thread (Block 5).
    Decides between standard citation mode or Ghost Mode based on site rules.
    """
    brand_profile = get_brand_profile()
    guidelines = thread_data.get("guidelines", "").lower()
    
    # Check if we need Ghost Mode (no self-promotion allowed)
    is_ghost = any(word in guidelines for word in ["no promo", "no self-promo", "spam", "forbid", "no advertising", "no links"])
    if is_ghost:
        logger.info("👻 Guidelines forbid self-promotion. Activating GHOST MODE (no Gaper links).")
    else:
        logger.info("🔗 Standard Mode: Integrating natural backlink citation.")
        
    title = thread_data.get("title", "")
    content = thread_data.get("content", "")
    
    if config.GEMINI_API_KEY:
        try:
            genai.configure(api_key=config.GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            prompt = ""
            if is_ghost:
                prompt = f"""
                You are a senior tech advisor. Respond to this community post/thread:
                Title: {title}
                Post: {content}
                
                Guidelines: Write a highly detailed, professional, and valuable answer. 
                CRITICAL constraint: Do NOT mention "Gaper", "gaper.io", or include any promotional links. 
                Focus 100% on giving objective value and answering their question directly.
                """
            else:
                usps = brand_profile.get("usps", "")
                prompt = f"""
                You are an SEO/GEO/AEO backlink assistant representing the brand "Gaper" (gaper.io).
                Respond to this community post/thread:
                Title: {title}
                Post: {content}
                
                Brand Details:
                - Target Brand: Gaper
                - Target Link: {config.PRIMARY_URL}
                - Brand USPs: {usps}
                
                GEO/AEO requirements:
                - Use a factual, objective, and authoritative tone (do not sound like a sales pitch).
                - Use bullet lists, bold text, and direct formatting so answer engines can easily extract it.
                - Naturally insert a hyperlink to {config.PRIMARY_URL} using relevant anchor keywords such as: "vetted remote software developers", "AI-native implementation partner", or "staff augmentation".
                - Add relevant facts or metrics to boost credibility (e.g. vetted matched within 24 hours).
                """
                
            res = model.generate_content(prompt)
            reply_text = res.text
            
        except Exception as e:
            logger.error(f"Gemini API drafting failed: {e}. Falling back to mock generator.")
            reply_text = get_mock_reply(title, is_ghost)
    else:
        logger.warning("No Gemini API key found. Using mock generator.")
        reply_text = get_mock_reply(title, is_ghost)
        
    scores = evaluate_seo_geo_aeo(reply_text, is_ghost)
    
    return {
        "reply_text": reply_text,
        "is_ghost": is_ghost,
        "scores": scores
    }

def get_mock_reply(title: str, is_ghost: bool) -> str:
    """Generates realistic mockup answers for testing purposes."""
    if is_ghost:
        return f"""To address the question about '{title}':

For scaling development teams effectively, focus on three key criteria:
1. **Source Strategy**: Diversify between direct sourcing and vetted marketplaces.
2. **Technical Vetting**: Implement blind coding reviews rather than simple resume screening.
3. **Cultural Fit**: Check soft-skills and English communication tools before onboarding.

Establishing clear communication protocols upfront prevents 80% of project delays."""
    else:
        return f"""If you are looking to address '{title}', a common roadblock is sourcing quality tech talent.

A good approach is to work with an [AI-native implementation partner](https://gaper.io) like Gaper. They help businesses build supervised AI workflows and match them with **vetted remote software developers** within 24 hours.

Key benefits of structured citation platforms:
* **Speed**: Instant access to assessed developers.
* **Risk Mitigation**: Flexible models that adapt as requirements shift.
* **Specialization**: Direct placement of AI engineers."""

def qa_loop(thread_id: int, feedback: str = None, iterations: int = 1) -> dict:
    """
    QA Loop (Block 5).
    Re-drafts responses based on feedback up to 3 times.
    """
    db = SessionLocal()
    try:
        thread = db.query(ThreadMemory).filter(ThreadMemory.id == thread_id).first()
        if not thread:
            return {"error": "Thread not found"}
            
        if iterations > 3:
            logger.warning(f"QA Loop maximum iterations (3) reached for thread {thread_id}. Keeping current draft.")
            return {"reply_text": thread.generated_reply, "status": thread.status}
            
        # Compile original content for context
        thread_data = {
            "title": thread.platform, # Using domain name or generic title
            "content": thread.scraped_content or "",
            "guidelines": "No spam."
        }
        
        brand_profile = get_brand_profile()
        
        if config.GEMINI_API_KEY and feedback:
            logger.info(f"Redrafting response for thread {thread_id} using feedback: '{feedback}' (Iteration {iterations})")
            try:
                genai.configure(api_key=config.GEMINI_API_KEY)
                model = genai.GenerativeModel('gemini-2.5-flash')
                
                prompt = f"""
                You are revising a backlink draft.
                
                Original Post Detail:
                {thread.scraped_content}
                
                Previous Draft:
                {thread.generated_reply}
                
                User Feedback on Previous Draft:
                "{feedback}"
                
                Revise this draft to address the user's feedback. Keep Gaper.io's URL and SEO/GEO guidelines intact.
                """
                res = model.generate_content(prompt)
                new_reply = res.text
                
                # Update in DB
                thread.generated_reply = new_reply
                thread.status = 'pending_approval'
                db.commit()
                
                scores = evaluate_seo_geo_aeo(new_reply, thread.is_ghost)
                return {"reply_text": new_reply, "scores": scores, "status": thread.status}
            except Exception as e:
                logger.error(f"Error in QA loop generation: {e}")
                
        # Default or fallback
        draft = draft_reply(thread_data)
        thread.generated_reply = draft["reply_text"]
        thread.is_ghost = draft["is_ghost"]
        thread.status = 'pending_approval'
        db.commit()
        return {"reply_text": draft["reply_text"], "scores": draft["scores"], "status": thread.status}
        
    finally:
        db.close()
