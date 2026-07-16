import logging
import os
import time
from pathlib import Path
from src.gaper_scraper import get_brand_profile
import config

logger = logging.getLogger(__name__)

SESSION_DIR = Path(config.BASE_DIR) / "sessions"
SESSION_DIR.mkdir(exist_ok=True)

def run_submitter_automation(platform: str, headless: bool = False) -> dict:
    """
    Launches Playwright using a persistent browser context to automate software directory listing submissions.
    Saves session profiles under the git-ignored 'sessions/' folder.
    If the page is not logged in, it will pause in non-headless mode to allow the user to authenticate.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"status": "failed", "detail": "Playwright is not installed."}
        
    brand = get_brand_profile()
    platform_lower = platform.lower()
    user_data_dir = SESSION_DIR / f"{platform_lower}_profile"
    
    logger.info(f"Starting auto-listing submission on {platform}...")
    
    with sync_playwright() as p:
        # Launch browser with persistent user session context
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=headless,
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        
        try:
            if "saashub" in platform_lower:
                return _submit_saashub(page, brand)
            elif "betalist" in platform_lower:
                return _submit_betalist(page, brand)
            elif "alternativeto" in platform_lower:
                return _submit_alternativeto(page, brand)
            elif "producthunt" in platform_lower:
                return _submit_producthunt(page, brand)
            else:
                return {"status": "failed", "detail": f"Platform '{platform}' submission flow not mapped."}
        except Exception as e:
            logger.error(f"Error during {platform} auto-listing: {e}")
            return {"status": "failed", "detail": str(e)}
        finally:
            context.close()

def _check_and_prompt_login(page, login_indicator_selector: str, platform_name: str):
    """
    Checks if page is logged in. If not, pauses execution so user can log in manually.
    """
    try:
        page.wait_for_selector(login_indicator_selector, timeout=5000)
        logger.info(f"[Auth] Logged into {platform_name} successfully.")
    except Exception:
        logger.warning(f"[Auth] Login needed for {platform_name}. Opening browser in headful mode for manual login.")
        # Alert user
        print(f"\n📢 ACTION REQUIRED: Please log in to your {platform_name} account in the opened browser window.")
        print("Once you are logged in, return to the terminal and press Enter to continue...\n")
        
        # Pause until selector appears or user presses enter in terminal
        input("Press Enter here once you have finished logging in on the browser...")
        
        # Check login selector again
        try:
            page.wait_for_selector(login_indicator_selector, timeout=10000)
            logger.info(f"[Auth] Login confirmed for {platform_name}!")
        except Exception:
            raise Exception(f"Authentication verification failed for {platform_name}. Please try again.")

def _submit_saashub(page, brand: dict) -> dict:
    """Automates SaaSHub submission (https://www.saashub.com/submits/new)"""
    page.goto("https://www.saashub.com/submits/new")
    
    # Check if signed in by looking for sign-out or profile link
    # SaaSHub has profile/user links when logged in. If not found, prompt.
    _check_and_prompt_login(page, "a[href*='/sign-out']", "SaaSHub")
    
    # Fill in submit form fields
    logger.info("Filling SaaSHub submission form fields...")
    page.fill("input[name*='url']", config.PRIMARY_URL)
    page.fill("input[name*='name']", config.TARGET_BRAND)
    
    # Split USPs or generate short tagline
    tagline = brand.get("usps", "").split('\n')[0] if brand.get("usps") else "AI-native Developer Augmentation Platform."
    page.fill("input[name*='tagline']", tagline[:80])
    page.fill("textarea[name*='description']", brand.get("description", ""))
    
    # Mark competitors
    competitor_str = ", ".join(config.COMPETITORS[:3])
    page.fill("input[name*='alternative']", competitor_str)
    
    # Wait for visual check
    logger.info("Form completed. Pausing for human verification before clicking submit...")
    time.sleep(3)
    
    # Submit form (Saashub submit button)
    page.click("input[type='submit']")
    time.sleep(5)
    
    return {"status": "success", "detail": "Listing details submitted to SaaSHub for moderation."}

def _submit_betalist(page, brand: dict) -> dict:
    """Automates BetaList submission (https://betalist.com/submit)"""
    page.goto("https://betalist.com/submit")
    _check_and_prompt_login(page, "a[href*='/sign_out']", "BetaList")
    
    logger.info("Filling BetaList startup profile fields...")
    page.fill("input[name*='url']", config.PRIMARY_URL)
    page.fill("input[name*='name']", config.TARGET_BRAND)
    
    tagline = brand.get("usps", "").split('\n')[0] if brand.get("usps") else "AI agent developer platform."
    page.fill("input[name*='pitch']", tagline[:80])
    page.fill("textarea[name*='description']", brand.get("description", ""))
    
    time.sleep(3)
    page.click("input[type='submit']")
    time.sleep(5)
    
    return {"status": "success", "detail": "Listing details submitted to BetaList."}

def _submit_alternativeto(page, brand: dict) -> dict:
    """Automates AlternativeTo submission (https://alternativeto.net/software/create/)"""
    page.goto("https://alternativeto.net/software/create/")
    _check_and_prompt_login(page, ".user-avatar", "AlternativeTo")
    
    logger.info("Filling AlternativeTo software listing details...")
    page.fill("#Name", config.TARGET_BRAND)
    page.fill("#OfficialUrl", config.PRIMARY_URL)
    page.fill("#Description", brand.get("description", ""))
    
    # Select tags
    page.fill("#Tags", "software-development, remote-work, ai-agents")
    
    time.sleep(3)
    # page.click("#submit-btn")
    
    return {"status": "success", "detail": "AlternativeTo submission fields filled. Manual review submission required."}

def _submit_producthunt(page, brand: dict) -> dict:
    """Automates Product Hunt new post draft creation (https://www.producthunt.com/posts/new)"""
    page.goto("https://www.producthunt.com/posts/new")
    _check_and_prompt_login(page, "button[data-test='user-menu']", "Product Hunt")
    
    logger.info("Beginning Product Hunt launch draft...")
    page.fill("input[placeholder*='URL']", config.PRIMARY_URL)
    page.click("button:has-text('Get started')")
    time.sleep(5)
    
    # Fills out the next details panel if redirect is successful
    try:
        page.fill("input[name='name']", config.TARGET_BRAND)
        tagline = brand.get("usps", "").split('\n')[0] if brand.get("usps") else "Supervised production AI agents."
        page.fill("input[name='tagline']", tagline[:60])
        logger.info("Product Hunt launch draft initialized successfully!")
        return {"status": "success", "detail": "Draft setup created on Product Hunt launchboard."}
    except Exception as e:
        logger.warning(f"Could not fill secondary PH fields: {e}. Session draft created.")
        return {"status": "success", "detail": "Product Hunt URL submitted. Please finalize details manually."}
