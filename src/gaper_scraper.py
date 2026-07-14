import logging
import requests
from bs4 import BeautifulSoup
from src.database import SessionLocal, BrandProfile
import config

logger = logging.getLogger(__name__)

def scrape_gaper_brand() -> dict:
    """
    Scrapes Gaper.io website to fetch logo, description, and key metadata.
    Updates the local SQLite database.
    """
    url = config.PRIMARY_URL
    logger.info(f"Scraping brand details from {url}...")
    
    brand_data = {
        "description": "An AI-powered marketplace that connects businesses with vetted remote software developers and functions as an AI-native implementation partner.",
        "logo_url": "https://gaper.io/wp-content/uploads/2021/04/gaper-logo.svg", # Default known logo
        "usps": "\n".join(config.BRAND_USPS)
    }
    
    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
            if meta_desc and meta_desc.get('content'):
                brand_data["description"] = meta_desc.get('content').strip()
                
            # Extract title
            title = soup.find('title')
            if title:
                logger.info(f"Scraped Title: {title.text}")
                
            # Look for logo image
            logo_img = soup.find('img', class_=lambda c: c and 'logo' in c.lower()) or \
                       soup.find('img', src=lambda s: s and 'logo' in s.lower())
            if logo_img and logo_img.get('src'):
                logo_src = logo_img.get('src')
                if not logo_src.startswith('http'):
                    logo_src = f"{url.rstrip('/')}/{logo_src.lstrip('/')}"
                brand_data["logo_url"] = logo_src
                
            # Look for key headings to extract USPs dynamically
            h2s = soup.find_all('h2')
            scraped_usps = []
            for h in h2s[:5]:
                text = h.text.strip().replace('\n', ' ')
                if text and len(text) > 15 and len(text) < 150:
                    scraped_usps.append(text)
            if scraped_usps:
                brand_data["usps"] = "\n".join(scraped_usps)
                
            logger.info("Brand scraped successfully!")
        else:
            logger.warning(f"Could not scrape {url}: Status code {response.status_code}. Using defaults.")
    except Exception as e:
        logger.error(f"Error scraping brand {url}: {e}. Using defaults.")
        
    # Save to database
    db = SessionLocal()
    try:
        profile = db.query(BrandProfile).first()
        if profile:
            profile.description = brand_data["description"]
            profile.logo_url = brand_data["logo_url"]
            profile.usps = brand_data["usps"]
        else:
            profile = BrandProfile(
                description=brand_data["description"],
                logo_url=brand_data["logo_url"],
                usps=brand_data["usps"]
            )
            db.add(profile)
        db.commit()
    finally:
        db.close()
        
    return brand_data

def get_brand_profile() -> dict:
    """
    Retrieves the brand profile from DB. Scrapes it if DB is empty.
    """
    db = SessionLocal()
    try:
        profile = db.query(BrandProfile).first()
        if not profile:
            return scrape_gaper_brand()
        return {
            "description": profile.description,
            "logo_url": profile.logo_url,
            "usps": profile.usps
        }
    finally:
        db.close()
