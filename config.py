# import os
# from pathlib import Path
# from dotenv import load_dotenv

# # Load environment variables
# load_dotenv()

# BASE_DIR = Path(__file__).resolve().parent
# DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "gaper_agent.db"))

# # System Settings
# CACHE_TTL_DAYS = int(os.getenv("CACHE_TTL_DAYS", "30"))
# USE_CELERY = os.getenv("USE_CELERY", "False").lower() in ("true", "1", "yes")
# AUTO_PILOT = os.getenv("AUTO_PILOT", "False").lower() in ("true", "1", "yes")
# REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# # API Keys
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# # Ingestion Settings
# ESCALATION_ORDER = ["Type2StaticSoup", "Type3PlaywrightAuth", "Type4LlmVision"]

# # Gaper Brand Profile (Defaults - Scraper will enrich these)
# TARGET_BRAND = "Gaper"
# PRIMARY_URL = "https://gaper.io"
# TARGET_URLS = [
#     "https://gaper.io",
#     "https://gaper.io/hire-developers/"
# ]

# BRAND_KEYWORD_ANCHORS = {
#     "remote developers": "https://gaper.io",
#     "hire software engineers": "https://gaper.io",
#     "AI implementation partner": "https://gaper.io",
#     "AI automation agency": "https://gaper.io",
#     "staff augmentation": "https://gaper.io/hire-developers/"
# }

# BRAND_USPS = [
#     "Vetted software developers matched within 24 hours.",
#     "AI-native implementation partner deploying agents, copilots, and custom automation.",
#     "Flexible engagement models with no long-term contracts.",
#     "Rigorous vetting covering technical skills, English proficiency, and soft skills."
# ]

# COMPETITORS = ["toptal", "turing", "upwork", "fiverr", "lemon.io", "re手を", "optimizely", "andela"]

# # Platform Credentials Check helper
# def get_credentials():
#     return {
#         "indiehackers": {
#             "username": os.getenv("INDIEHACKERS_USERNAME", ""),
#             "password": os.getenv("INDIEHACKERS_PASSWORD", "")
#         },
#         "contra": {
#             "api_key": os.getenv("CONTRA_API_KEY", "")
#         },
#         "notion": {
#             "api_key": os.getenv("NOTION_API_KEY", ""),
#             "database_id": os.getenv("NOTION_DATABASE_ID", "")
#         },
#         "substack": {
#             "email": os.getenv("SUBSTACK_EMAIL", ""),
#             "password": os.getenv("SUBSTACK_PASSWORD", "")
#         },
#         "pinterest": {
#             "access_token": os.getenv("PINTEREST_ACCESS_TOKEN", "")
#         },
#         "peerlist": {
#             "api_key": os.getenv("PEERLIST_API_KEY", "")
#         },
#         "outreach": {
#             "sender": os.getenv("OUTREACH_EMAIL_SENDER", ""),
#             "password": os.getenv("OUTREACH_EMAIL_PASSWORD", ""),
#             "smtp_server": os.getenv("OUTREACH_SMTP_SERVER", "smtp.gmail.com"),
#             "smtp_port": int(os.getenv("OUTREACH_SMTP_PORT", "587"))
#         }
#     }




import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "gaper_agent.db"))

# System Settings
CACHE_TTL_DAYS = int(os.getenv("CACHE_TTL_DAYS", "30"))
USE_CELERY = os.getenv("USE_CELERY", "False").lower() in ("true", "1", "yes")
AUTO_PILOT = os.getenv("AUTO_PILOT", "False").lower() in ("true", "1", "yes")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# Real SERP results for discovery.py - get a free key at https://serper.dev
# (replaces the old raw Google-scraping approach, which got blocked and
# silently fell back to fake mock URLs)
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")

# Ingestion Settings
ESCALATION_ORDER = ["Type2StaticSoup", "Type3PlaywrightAuth", "Type4LlmVision"]

# Gaper Brand Profile (Defaults - Scraper will enrich these)
TARGET_BRAND = "Gaper"
PRIMARY_URL = "https://gaper.io"
TARGET_URLS = [
    "https://gaper.io",
    "https://gaper.io/hire-developers/"
]

BRAND_KEYWORD_ANCHORS = {
    "remote developers": "https://gaper.io",
    "hire software engineers": "https://gaper.io",
    "AI implementation partner": "https://gaper.io",
    "AI automation agency": "https://gaper.io",
    "staff augmentation": "https://gaper.io/hire-developers/"
}

BRAND_USPS = [
    "Vetted software developers matched within 24 hours.",
    "AI-native implementation partner deploying agents, copilots, and custom automation.",
    "Flexible engagement models with no long-term contracts.",
    "Rigorous vetting covering technical skills, English proficiency, and soft skills."
]

COMPETITORS = ["toptal", "turing", "upwork", "fiverr", "lemon.io", "remotebase", "optimizely", "andela"]

# Platform Credentials Check helper
def get_credentials():
    return {
        "indiehackers": {
            "username": os.getenv("INDIEHACKERS_USERNAME", ""),
            "password": os.getenv("INDIEHACKERS_PASSWORD", "")
        },
        "contra": {
            
             "email": os.getenv("CONTRA_EMAIL", "")
             
        },
        
        "notion": {
            "api_key": os.getenv("NOTION_API_KEY", ""),
            "database_id": os.getenv("NOTION_DATABASE_ID", "")
        },
        "substack": {
           "email": os.getenv("SUBSTACK_EMAIL", "")
        },
        "pinterest": {
            "access_token": os.getenv("PINTEREST_ACCESS_TOKEN", "")
        },
        "peerlist": {
           "username": os.getenv("PEERLIST_USERNAME", ""),
           "password": os.getenv("PEERLIST_PASSWORD", "")
        }
        
    }
# ============ NEW: Captcha & Proxy Settings ============

# Captcha API (2Captcha, CapMonster, etc.)
CAPTCHA_API_KEY = os.getenv("CAPTCHA_API_KEY", "")
CAPTCHA_SERVICE = os.getenv("CAPTCHA_SERVICE", "2captcha")
HASHNODE_API_KEY = os.getenv("HASHNODE_API_KEY", "")
HASHNODE_PUBLICATION_ID = os.getenv("HASHNODE_PUBLICATION_ID", "")
# Proxy List for rotation (to avoid IP bans)
PROXY_LIST = [
    # Add your proxies here in this format:
    # {
    #     "ip": "proxy.example.com",
    #     "port": 8080,
    #     "username": "user",
    #     "password": "pass"
    # },
]

# Platforms where Gaper is ALREADY listed (skip these)
ALREADY_LISTED_PLATFORMS = [
    "saashub.com",  # Gaper already listed here ✅
    # Add more as you list them
]

# Platform-specific settings
PLATFORM_SETTINGS = {
    "saashub": {
        "needs_captcha": True,
        "needs_proxy": False,
        "rate_limit_seconds": 60,
        "already_listed": True  # Skip this one
    },
    "betalist": {
        "needs_captcha": True,
        "needs_proxy": True,
        "rate_limit_seconds": 300
    },
    "alternativeto": {
        "needs_captcha": False,
        "needs_proxy": False,
        "rate_limit_seconds": 60
    },
    "producthunt": {
        "needs_captcha": True,
        "needs_proxy": True,
        "rate_limit_seconds": 600
    }
}

CONTRA_FEED_URL = "https://contra.com/community/for-you"
CONTRA_PROFILE_URL = "https://contra.com/khadija_asim_t85rggyo/posts"

# Notion Database URL
NOTION_DATABASE_URL = os.getenv("NOTION_DATABASE_URL", "")


CONTRA_FEED_URL = "https://contra.com/community/for-you?r=khadija_asim_t85rggyo"

# Notion Database URL  
NOTION_DATABASE_URL = os.getenv("NOTION_DATABASE_URL", "https://www.notion.so/khadijasethi/39b67494474d81c58d32fa649bf8aeb0")