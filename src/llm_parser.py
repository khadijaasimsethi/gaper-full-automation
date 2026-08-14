# src/llm_parser.py
"""
Universal LLM Parser - Scrapes ANY URL and determines action
"""

import logging
import json
import re
from playwright.sync_api import sync_playwright
import google.generativeai as genai
import config

logger = logging.getLogger(__name__)
GEMINI_MODEL = "gemini-flash-latest"


def parse_url(url: str) -> dict:
    """Parse ANY URL using Gemini - SAFE version"""
    print(f"\n🔍 LLM Parsing URL: {url}")
    
    try:
        page_data = _scrape_page(url)
        if not page_data or page_data.get("error"):
            return {
                "status": "failed",
                "detail": page_data.get("error", "Could not scrape page"),
                "action": "skip",
                "relevance_score": 0,
                "type": "other",
                "title": "",
                "suggested_reply": "",
            }
        
        analysis = _analyze_with_gemini(page_data, url)
        
        return {
            "status": "success",
            "url": url,
            "type": analysis.get("type", "other"),
            "title": analysis.get("title", page_data.get("title", "")),
            "content": page_data.get("content", "")[:5000],
            "action": _determine_action(analysis),
            "platform_name": analysis.get("platform_name", "unknown"),
            "requires_login": analysis.get("requires_login", False),
            "suggested_reply": analysis.get("suggested_reply", ""),
            "relevance_score": analysis.get("relevance_score", 50),
            "form_fields": analysis.get("form_fields", []),
        }
        
    except Exception as e:
        logger.error(f"parse_url failed: {e}")
        return {
            "status": "failed",
            "detail": str(e),
            "action": "skip",
            "relevance_score": 0,
        }
def _scrape_page(url: str) -> dict:
    """Scrape page content using Playwright"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = context.new_page()
            
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(3000)
                
                # Check for login
                if "login" in page.url or "sign-in" in page.url:
                    browser.close()
                    return {"requires_login": True}
                
                # Get page info
                title = page.title()
                content = page.locator("body").inner_text()
                
                browser.close()
                
                return {
                    "title": title,
                    "content": content[:15000],  # Limit for Gemini
                    "url": url,
                    "requires_login": False
                }
                
            except Exception as e:
                browser.close()
                return {"error": str(e)}
                
    except Exception as e:
        return {"error": str(e)}

def _analyze_with_gemini(page_data: dict, url: str) -> dict:
    """Analyze page with Gemini - SAFE version with error handling"""
    
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)
    
    prompt = f"""
You are analyzing a webpage for Gaper (an AI implementation partner).

URL: {url}
Page Title: {page_data.get('title', '')}
Page Content (first 5000 chars):
{page_data.get('content', '')[:5000]}

CRITICAL: "listing" means a SUBMISSION FORM page where you can LIST a product/startup.
This is NOT a forum post, NOT a blog post, NOT a discussion thread, NOT an article.
IndieHackers posts, Reddit threads, HN threads, blog posts are NEVER "listing".

ANALYZE AND RETURN JSON:
1. "type": "article" or "listing" or "forum" or "directory" or "other"
   - "article" = blog post, article page, any content page
   - "forum" = discussion thread, forum post, Reddit thread, HN thread, IndieHackers post, comment section
   - "listing" = ONLY submit/registration forms (NOT forum threads or articles)
   - "directory" = a list/catalog of products (NOT a single thread)
   - "other" = anything else
2. "title": Main title
3. "platform_name": What platform is this? (e.g., "reddit", "indiehackers", "dev.to", etc.)
4. "requires_login": true/false
5. "form_fields": If listing/directory, list fields found
6. "suggested_action": "reply" or "list" or "skip"
   - "reply" = forum threads, Reddit, HN, IndieHackers posts, blog posts with comments
   - "list" = ONLY if this is a product submission form
   - "skip" = irrelevant page
7. "suggested_reply": If replying, write helpful 2-3 sentence Gaper comment
   Include "https://gaper.io" naturally
8. "relevance_score": 0-100 (AI agents, remote developer hiring = high)

CRITICAL RULE: IndieHackers posts, Reddit threads, HackerNews threads, blog posts = "reply", NEVER "list".
"list" is ONLY for pages that say "Submit your product" or "Add your startup".

Return ONLY valid JSON. No markdown, no explanation.
"""
    
    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()
        
        # ✅ If empty, return defaults
        if not raw:
            logger.warning("Gemini returned empty response")
            return _default_analysis(page_data)
        
        # Clean JSON
        if raw.startswith("```json"):
            raw = raw[7:]
        elif raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        
        raw = raw.strip()
        
        # ✅ Try to parse JSON
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}. Raw: {raw[:200]}")
            # Try to extract JSON from the text if possible
            import re
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                except:
                    return _default_analysis(page_data)
            else:
                return _default_analysis(page_data)
        
        # ✅ Ensure all keys exist
        return {
            "type": result.get("type", "other"),
            "title": result.get("title", page_data.get("title", "Untitled")),
            "platform_name": result.get("platform_name", "unknown"),
            "requires_login": result.get("requires_login", False),
            "form_fields": result.get("form_fields", []),
            "suggested_action": result.get("suggested_action", "skip"),
            "suggested_reply": result.get("suggested_reply", ""),
            "relevance_score": result.get("relevance_score", 50),
        }
        
    except Exception as e:
        logger.error(f"Gemini analysis failed: {e}")
        return _default_analysis(page_data)


def _default_analysis(page_data: dict) -> dict:
    """Return default analysis when Gemini fails"""
    return {
        "type": "other",
        "title": page_data.get("title", "Untitled"),
        "platform_name": "unknown",
        "requires_login": False,
        "form_fields": [],
        "suggested_action": "skip",
        "suggested_reply": "",
        "relevance_score": 30,
    }
def _determine_action(analysis: dict) -> str:
    """Determine action based on analysis"""
    score = analysis.get("relevance_score", 0)
    
    if score < 10:
        return "skip"
    
    page_type = analysis.get("type", "other")
    suggested = analysis.get("suggested_action", "skip")
    
    # Override based on type
    if page_type in ["listing", "directory"]:
        return "list"
    
    if page_type in ["article", "forum"]:
        return "reply"
    
    return suggested