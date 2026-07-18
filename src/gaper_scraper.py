# # import logging
# # import requests
# # from bs4 import BeautifulSoup
# # from src.database import SessionLocal, BrandProfile
# # import config

# # logger = logging.getLogger(__name__)

# # def scrape_gaper_brand() -> dict:
# #     """
# #     Scrapes Gaper.io website to fetch logo, description, and key metadata.
# #     Updates the local SQLite database.
# #     """
# #     url = config.PRIMARY_URL
# #     logger.info(f"Scraping brand details from {url}...")
    
# #     brand_data = {
# #         "description": "An AI-powered marketplace that connects businesses with vetted remote software developers and functions as an AI-native implementation partner.",
# #         "logo_url": "https://gaper.io/wp-content/uploads/2021/04/gaper-logo.svg", # Default known logo
# #         "usps": "\n".join(config.BRAND_USPS)
# #     }
    
# #     try:
# #         response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
# #         if response.status_code == 200:
# #             soup = BeautifulSoup(response.text, 'html.parser')
            
# #             # Extract meta description
# #             meta_desc = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
# #             if meta_desc and meta_desc.get('content'):
# #                 brand_data["description"] = meta_desc.get('content').strip()
                
# #             # Extract title
# #             title = soup.find('title')
# #             if title:
# #                 logger.info(f"Scraped Title: {title.text}")
                
# #             # Look for logo image
# #             logo_img = soup.find('img', class_=lambda c: c and 'logo' in c.lower()) or \
# #                        soup.find('img', src=lambda s: s and 'logo' in s.lower())
# #             if logo_img and logo_img.get('src'):
# #                 logo_src = logo_img.get('src')
# #                 if not logo_src.startswith('http'):
# #                     logo_src = f"{url.rstrip('/')}/{logo_src.lstrip('/')}"
# #                 brand_data["logo_url"] = logo_src
                
# #             # Look for key headings to extract USPs dynamically
# #             h2s = soup.find_all('h2')
# #             scraped_usps = []
# #             for h in h2s[:5]:
# #                 text = h.text.strip().replace('\n', ' ')
# #                 if text and len(text) > 15 and len(text) < 150:
# #                     scraped_usps.append(text)
# #             if scraped_usps:
# #                 brand_data["usps"] = "\n".join(scraped_usps)
                
# #             logger.info("Brand scraped successfully!")
# #         else:
# #             logger.warning(f"Could not scrape {url}: Status code {response.status_code}. Using defaults.")
# #     except Exception as e:
# #         logger.error(f"Error scraping brand {url}: {e}. Using defaults.")
        
# #     # Save to database
# #     db = SessionLocal()
# #     try:
# #         profile = db.query(BrandProfile).first()
# #         if profile:
# #             profile.description = brand_data["description"]
# #             profile.logo_url = brand_data["logo_url"]
# #             profile.usps = brand_data["usps"]
# #         else:
# #             profile = BrandProfile(
# #                 description=brand_data["description"],
# #                 logo_url=brand_data["logo_url"],
# #                 usps=brand_data["usps"]
# #             )
# #             db.add(profile)
# #         db.commit()
# #     finally:
# #         db.close()
        
# #     return brand_data

# # def get_brand_profile() -> dict:
# #     """
# #     Retrieves the brand profile from DB. Scrapes it if DB is empty.
# #     """
# #     db = SessionLocal()
# #     try:
# #         profile = db.query(BrandProfile).first()
# #         if not profile:
# #             return scrape_gaper_brand()
# #         return {
# #             "description": profile.description,
# #             "logo_url": profile.logo_url,
# #             "usps": profile.usps
# #         }
# #     finally:
# #         db.close()



# # src/gaper_scraper.py
# """
# Scrapes Gaper.io website for fresh content every time.
# This version scrapes the website ON DEMAND for dynamic content.
# """

# import logging
# import random
# import requests
# from bs4 import BeautifulSoup
# from src.database import SessionLocal, BrandProfile
# import config

# logger = logging.getLogger(__name__)

# # Sections to scrape for fresh content
# GAPER_SECTIONS = [
#     "https://gaper.io",
#     "https://gaper.io/about",
#     "https://gaper.io/services",
#     "https://gaper.io/blog",
#     "https://gaper.io/hire-developers",
# ]


# def scrape_gaper_brand() -> dict:
#     """
#     Scrapes Gaper.io website to fetch logo, description, and key metadata.
#     Updates the local SQLite database (for persistent brand profile).
#     """
#     url = config.PRIMARY_URL
#     logger.info(f"Scraping brand details from {url}...")
    
#     brand_data = {
#         "description": "An AI-powered marketplace that connects businesses with vetted remote software developers and functions as an AI-native implementation partner.",
#         "logo_url": "https://gaper.io/wp-content/uploads/2021/04/gaper-logo.svg",
#         "usps": "\n".join(config.BRAND_USPS)
#     }
    
#     try:
#         response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
#         if response.status_code == 200:
#             soup = BeautifulSoup(response.text, 'html.parser')
            
#             meta_desc = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
#             if meta_desc and meta_desc.get('content'):
#                 brand_data["description"] = meta_desc.get('content').strip()
                
#             title = soup.find('title')
#             if title:
#                 logger.info(f"Scraped Title: {title.text}")
                
#             logo_img = soup.find('img', class_=lambda c: c and 'logo' in c.lower()) or \
#                        soup.find('img', src=lambda s: s and 'logo' in s.lower())
#             if logo_img and logo_img.get('src'):
#                 logo_src = logo_img.get('src')
#                 if not logo_src.startswith('http'):
#                     logo_src = f"{url.rstrip('/')}/{logo_src.lstrip('/')}"
#                 brand_data["logo_url"] = logo_src
                
#             h2s = soup.find_all('h2')
#             scraped_usps = []
#             for h in h2s[:5]:
#                 text = h.text.strip().replace('\n', ' ')
#                 if text and len(text) > 15 and len(text) < 150:
#                     scraped_usps.append(text)
#             if scraped_usps:
#                 brand_data["usps"] = "\n".join(scraped_usps)
                
#             logger.info("Brand scraped successfully!")
#         else:
#             logger.warning(f"Could not scrape {url}: Status code {response.status_code}. Using defaults.")
#     except Exception as e:
#         logger.error(f"Error scraping brand {url}: {e}. Using defaults.")
        
#     # Save to database
#     db = SessionLocal()
#     try:
#         profile = db.query(BrandProfile).first()
#         if profile:
#             profile.description = brand_data["description"]
#             profile.logo_url = brand_data["logo_url"]
#             profile.usps = brand_data["usps"]
#         else:
#             profile = BrandProfile(
#                 description=brand_data["description"],
#                 logo_url=brand_data["logo_url"],
#                 usps=brand_data["usps"]
#             )
#             db.add(profile)
#         db.commit()
#     finally:
#         db.close()
        
#     return brand_data


# def scrape_fresh_content() -> dict:
#     """
#     SCRAPES FRESH CONTENT from Gaper website.
#     Called every time to get different content.
#     Returns dict with random selections.
#     """
#     results = {
#         "headlines": [],
#         "descriptions": [],
#         "services": [],
#         "testimonials": [],
#         "features": [],
#     }
    
#     headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
#     for url in GAPER_SECTIONS:
#         try:
#             response = requests.get(url, headers=headers, timeout=10)
#             if response.status_code != 200:
#                 continue
                
#             soup = BeautifulSoup(response.text, 'html.parser')
            
#             # Get all headings (H1, H2, H3)
#             for tag in soup.find_all(['h1', 'h2', 'h3']):
#                 text = tag.text.strip()
#                 if text and len(text) > 10 and len(text) < 200:
#                     results["headlines"].append(text)
            
#             # Get all paragraphs
#             for p in soup.find_all('p'):
#                 text = p.text.strip()
#                 if text and len(text) > 20 and len(text) < 500:
#                     results["descriptions"].append(text)
            
#             # Find service/feature sections
#             for section in soup.find_all(['section', 'div'], class_=lambda c: c and any(x in c.lower() for x in ['service', 'feature', 'offer', 'benefit'])):
#                 text = section.text.strip()
#                 if text and len(text) > 30:
#                     results["services"].append(text[:300])
            
#             # Find testimonials
#             for block in soup.find_all(['blockquote', 'div'], class_=lambda c: c and 'testimonial' in c.lower()):
#                 text = block.text.strip()
#                 if text and len(text) > 20:
#                     results["testimonials"].append(text)
                    
#         except Exception as e:
#             logger.error(f"Failed to scrape {url}: {e}")
    
#     # If no data scraped, use defaults
#     if not results["descriptions"]:
#         results["descriptions"] = config.BRAND_USPS
    
#     return results


# def get_fresh_content_for_post() -> dict:
#     """
#     Gets fresh, UNIQUE content for each post.
#     Scrapes website and picks random items.
#     Called every time a new post is generated.
#     """
#     # Scrape fresh content
#     scraped = scrape_fresh_content()
    
#     # Randomly select items
#     headlines = scraped["headlines"] if scraped["headlines"] else ["AI-native implementation partner"]
#     descriptions = scraped["descriptions"] if scraped["descriptions"] else config.BRAND_USPS
#     services = scraped["services"] if scraped["services"] else ["AI agent deployment", "Developer staffing"]
#     testimonials = scraped["testimonials"] if scraped["testimonials"] else []
    
#     return {
#         "headline": random.choice(headlines) if headlines else "AI-native implementation partner",
#         "description": random.choice(descriptions) if descriptions else config.BRAND_USPS[0],
#         "service": random.choice(services) if services else "AI agent deployment",
#         "testimonial": random.choice(testimonials) if testimonials else None,
#         "all_headlines": headlines[:5],  # For Gemini prompt
#         "all_descriptions": descriptions[:5],
#         "all_services": services[:3],
#     }


# def get_brand_profile() -> dict:
#     """
#     Retrieves the brand profile from DB. Scrapes it if DB is empty.
#     """
#     db = SessionLocal()
#     try:
#         profile = db.query(BrandProfile).first()
#         if not profile:
#             return scrape_gaper_brand()
#         return {
#             "description": profile.description,
#             "logo_url": profile.logo_url,
#             "usps": profile.usps
#         }
#     finally:
#         db.close()


# def get_clickable_link() -> str:
#     """Returns clickable link for Contra post"""
#     return "https://gaper.io"





# src/gaper_scraper.py
"""
Scrapes Gaper.io website for fresh content every time.
This version scrapes the website ON DEMAND for dynamic content.
"""

import logging
import random
import requests
from bs4 import BeautifulSoup
from src.database import SessionLocal, BrandProfile
import config

logger = logging.getLogger(__name__)

# Sections to scrape for fresh content
GAPER_SECTIONS = [
    "https://gaper.io",
    "https://gaper.io/about",
    "https://gaper.io/services",
    "https://gaper.io/blog",
    "https://gaper.io/hire-developers",
]


def scrape_gaper_brand() -> dict:
    """
    Scrapes Gaper.io website to fetch logo, description, and key metadata.
    Updates the local SQLite database (for persistent brand profile).
    """
    url = config.PRIMARY_URL
    logger.info(f"Scraping brand details from {url}...")
    
    brand_data = {
        "description": "An AI-powered marketplace that connects businesses with vetted remote software developers and functions as an AI-native implementation partner.",
        "logo_url": "https://gaper.io/wp-content/uploads/2021/04/gaper-logo.svg",
        "usps": "\n".join(config.BRAND_USPS)
    }
    
    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            meta_desc = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
            if meta_desc and meta_desc.get('content'):
                brand_data["description"] = meta_desc.get('content').strip()
                
            title = soup.find('title')
            if title:
                logger.info(f"Scraped Title: {title.text}")
                
            logo_img = soup.find('img', class_=lambda c: c and 'logo' in c.lower()) or \
                       soup.find('img', src=lambda s: s and 'logo' in s.lower())
            if logo_img and logo_img.get('src'):
                logo_src = logo_img.get('src')
                if not logo_src.startswith('http'):
                    logo_src = f"{url.rstrip('/')}/{logo_src.lstrip('/')}"
                brand_data["logo_url"] = logo_src
                
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


def scrape_fresh_content() -> dict:
    """
    SCRAPES FRESH CONTENT from Gaper website.
    Called every time to get different content.
    Returns dict with random selections.
    """
    results = {
        "headlines": [],
        "descriptions": [],
        "services": [],
        "testimonials": [],
        "features": [],
    }
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    for url in GAPER_SECTIONS:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                continue
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Get all headings (H1, H2, H3)
            for tag in soup.find_all(['h1', 'h2', 'h3']):
                text = tag.text.strip()
                if text and len(text) > 10 and len(text) < 200:
                    results["headlines"].append(text)
            
            # Get all paragraphs
            for p in soup.find_all('p'):
                text = p.text.strip()
                if text and len(text) > 20 and len(text) < 500:
                    results["descriptions"].append(text)
            
            # Find service/feature sections
            for section in soup.find_all(['section', 'div'], class_=lambda c: c and any(x in c.lower() for x in ['service', 'feature', 'offer', 'benefit'])):
                text = section.text.strip()
                if text and len(text) > 30:
                    results["services"].append(text[:300])
            
            # Find testimonials
            for block in soup.find_all(['blockquote', 'div'], class_=lambda c: c and 'testimonial' in c.lower()):
                text = block.text.strip()
                if text and len(text) > 20:
                    results["testimonials"].append(text)
                    
        except Exception as e:
            logger.error(f"Failed to scrape {url}: {e}")
    
    # If no data scraped, use defaults
    if not results["descriptions"]:
        results["descriptions"] = config.BRAND_USPS
    
    return results


def get_fresh_content_for_post() -> dict:
    """
    Gets fresh, UNIQUE content for each post.
    Scrapes website and picks random items.
    Called every time a new post is generated.
    """
    # Scrape fresh content
    scraped = scrape_fresh_content()
    
    # Randomly select items
    headlines = scraped["headlines"] if scraped["headlines"] else ["AI-native implementation partner"]
    descriptions = scraped["descriptions"] if scraped["descriptions"] else config.BRAND_USPS
    services = scraped["services"] if scraped["services"] else ["AI agent deployment", "Developer staffing"]
    testimonials = scraped["testimonials"] if scraped["testimonials"] else []
    
    return {
        "headline": random.choice(headlines) if headlines else "AI-native implementation partner",
        "description": random.choice(descriptions) if descriptions else config.BRAND_USPS[0],
        "service": random.choice(services) if services else "AI agent deployment",
        "testimonial": random.choice(testimonials) if testimonials else None,
        "all_headlines": headlines[:5],
        "all_descriptions": descriptions[:5],
        "all_services": services[:3],
    }


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


def get_clickable_link() -> str:
    """Returns clickable link for Contra post"""
    return "https://gaper.io"