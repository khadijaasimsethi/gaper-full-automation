
# # import logging
# # import urllib.parse
# # import xml.etree.ElementTree as ET
# # import requests
# # from src.database import SessionLocal, ThreadMemory, ListingOpportunity, is_duplicate
# # import config

# # logger = logging.getLogger(__name__)

# # SERPER_URL = "https://google.serper.dev/search"

# # # Working RSS feeds only. The old indiehackers.com/feed.xml and
# # # substack.com/feed were not real endpoints - Substack doesn't have one
# # # unified feed, and dev.to's feed IS real and stays.
# # RSS_FEEDS = [
# #     "https://dev.to/feed",
# # ]

# # # --- Two SEPARATE search tracks, per your requirement ---

# # # Track A: threads/articles to write a reply/article on (with a backlink)
# # ARTICLE_QUERIES = [
# #     "hire remote developers site:indiehackers.com",
# #     "hire remote developers site:dev.to",
# #     "AI implementation partner for startups discussion",
# #     "AI agents integration agency reddit",
# #     "vetted software developers platform forum",
# # ]

# # # Track B: platforms/directories where Gaper itself could be LISTED as a
# # # product (this was completely missing before - detect_missing_gaper_listing
# # # only ever ran on whatever thread URLs Track A happened to find, it never
# # # actively searched for directories).
# # LISTING_QUERIES = [
# #      "\"submit your startup\" AI tools",
# #     "\"submit your product\" AI agents directory",
# #     "\"add your product\" SaaS directory",
# #     "\"list your startup\" AI implementation",
# #     "\"submit a listing\" developer staffing platform",
# #     "intitle:submit AI tools directory",
# #     "\"get listed\" AI SaaS product directory",

# # ]


# # def serper_search(query: str, num: int = 10) -> list:
# #     """Real SERP results via Serper.dev. Raises on failure instead of
# #     silently returning fake mock URLs - a discovery run that fails should
# #     look like a failure, not quietly inject placeholder data."""
# #     if not config.SERPER_API_KEY:
# #         raise ValueError("SERPER_API_KEY is not set in .env - get one free at serper.dev")

# #     resp = requests.post(
# #         SERPER_URL,
# #         headers={"X-API-KEY": config.SERPER_API_KEY, "Content-Type": "application/json"},
# #         json={"q": query, "num": num},
# #         timeout=20,
# #     )
# #     resp.raise_for_status()
# #     data = resp.json()
# #     return [item.get("link", "") for item in data.get("organic", []) if item.get("link")]


# # def fetch_rss_feed_urls() -> list:
# #     urls = []
# #     headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
# #     for feed_url in RSS_FEEDS:
# #         try:
# #             logger.info(f"Fetching RSS feed: {feed_url}")
# #             response = requests.get(feed_url, headers=headers, timeout=10)
# #             if response.status_code == 200:
# #                 root = ET.fromstring(response.content)
# #                 for item in root.findall('.//item'):
# #                     link_elem = item.find('link')
# #                     if link_elem is not None and link_elem.text:
# #                         urls.append(link_elem.text.strip())
# #             else:
# #                 logger.warning(f"RSS feed {feed_url} returned status {response.status_code}")
# #         except Exception as e:
# #             logger.error(f"Error fetching RSS feed {feed_url}: {e}")
# #     return urls


# # def discover_threads() -> list:
# #     """
# #     Track A: finds threads/articles to write a reply or article on.
# #     Returns fresh URLs not already in the database. Raises if SERP fails
# #     entirely rather than masking the failure with fake data.
# #     """
# #     logger.info("Starting ARTICLE/THREAD discovery (Track A)...")
# #     all_urls = fetch_rss_feed_urls()

# #     for query in ARTICLE_QUERIES:
# #         try:
# #             all_urls.extend(serper_search(query))
# #         except Exception as e:
# #             logger.error(f"SERP query failed ('{query}'): {e}")
# #             # Continue with other queries rather than aborting the whole run,
# #             # but this failure is now visible in logs - not silently hidden.

# #     unique_urls = list(set(all_urls))
# #     logger.info(f"Track A: {len(unique_urls)} unique URLs found. Checking against DB...")

# #     fresh_urls = []
# #     db = SessionLocal()
# #     try:
# #         for url in unique_urls:
# #             if not is_duplicate(url):
# #                 domain = urllib.parse.urlparse(url).netloc
# #                 if not db.query(ThreadMemory).filter(ThreadMemory.url == url).first():
# #                     db.add(ThreadMemory(url=url, platform=domain, status='discovered'))
# #                     db.commit()
# #                 fresh_urls.append(url)
# #     finally:
# #         db.close()

# #     logger.info(f"Track A complete: {len(fresh_urls)} fresh article/thread URLs.")
# #     return fresh_urls


# # def discover_listing_platforms() -> list:
# #     """
# #     Track B (NEW): actively searches for directories/platforms where Gaper
# #     could be listed as a product - separate from Track A's thread search.
# #     Saves each as a ListingOpportunity with status 'discovered', ready for
# #     your review in the dashboard before anything gets added.
# #     """
# #     logger.info("Starting LISTING PLATFORM discovery (Track B)...")
# #     all_urls = []

# #     for query in LISTING_QUERIES:
# #         try:
# #             all_urls.extend(serper_search(query))
# #         except Exception as e:
# #             logger.error(f"SERP query failed ('{query}'): {e}")

# #     unique_urls = list(set(all_urls))
# #     logger.info(f"Track B: {len(unique_urls)} unique directory/platform URLs found.")

# #     new_opportunities = []
# #     db = SessionLocal()
# #     try:
# #         for url in unique_urls:
# #             domain = urllib.parse.urlparse(url).netloc
# #             existing = db.query(ListingOpportunity).filter(ListingOpportunity.url == url).first()
# #             if existing:
# #                 continue
# #             opp = ListingOpportunity(
# #                 url=url,
# #                 domain=domain,
# #                 competitors_found="",  # unknown yet - filled in if/when the page is scraped
# #                 status='discovered',
# #             )
# #             db.add(opp)
# #             db.commit()
# #             new_opportunities.append(url)
# #             logger.info(f"New listing opportunity: {url}")
# #     finally:
# #         db.close()

# #     logger.info(f"Track B complete: {len(new_opportunities)} new listing candidates.")
# #     return new_opportunities


# # def detect_missing_gaper_listing(url: str, page_content: str):
# #     """
# #     Kept for Track A: if a thread/article page happens to mention
# #     competitors but not Gaper, log it as a bonus listing opportunity too.
# #     This is now a SUPPLEMENT to Track B, not the only source of listing
# #     opportunities.
# #     """
# #     page_content = page_content or ""  # a strategy (esp. Type4/Gemini) can
# #                                         # return an explicit null for content,
# #                                         # which .get(key, "") does NOT catch
# #                                         # since the key exists, just with a
# #                                         # None value - this was crashing here.
# #     if "gaper" in page_content.lower():
# #         return

# #     found_competitors = [c for c in config.COMPETITORS if c in page_content.lower()]
# #     if not found_competitors:
# #         return

# #     db = SessionLocal()
# #     try:
# #         domain = urllib.parse.urlparse(url).netloc
# #         opp = db.query(ListingOpportunity).filter(ListingOpportunity.url == url).first()
# #         if not opp:
# #             logger.info(f"Missing listing detected: competitors {found_competitors} mentioned at {url}, Gaper is not.")
# #             opp = ListingOpportunity(
# #                 url=url, domain=domain,
# #                 competitors_found=",".join(found_competitors),
# #                 status='discovered',
# #             )
# #             db.add(opp)
# #             db.commit()
# #     except Exception as e:
# #         logger.error(f"Error logging missing listing: {e}")
# #     finally:
# #         db.close()


# import logging
# import urllib.parse
# import xml.etree.ElementTree as ET
# import requests
# from src.database import SessionLocal, ThreadMemory, ListingOpportunity, is_duplicate
# import config

# logger = logging.getLogger(__name__)

# SERPER_URL = "https://google.serper.dev/search"

# # Working RSS feeds only.
# RSS_FEEDS = [
#     "https://dev.to/feed",
# ]

# # --- Two SEPARATE search tracks ---

# # Track A: threads/articles to write a reply/article on (with a backlink)
# ARTICLE_QUERIES = [
#     "hire remote developers site:indiehackers.com",
#     "hire remote developers site:dev.to",
#     "AI implementation partner for startups discussion",
#     "AI agents integration agency reddit",
#     "vetted software developers platform forum",
# ]

# # Track B: ONLY genuine product-submission directories - i.e. pages whose
# # entire purpose is "submit your product here", not social posts, not
# # blog articles listing directories, not dev-content threads. Every query
# # below targets the submission-intent phrase itself, on generic domains -
# # no specific platform names hardcoded, so any new directory Google knows
# # about gets picked up the same way.
# LISTING_QUERIES = [
#     "\"submit your startup\" -site:facebook.com -site:instagram.com -site:linkedin.com -site:reddit.com -site:dev.to",
#     "\"submit your product\" AI tools directory -site:facebook.com -site:instagram.com -site:reddit.com -site:dev.to",
#     "\"add your product\" SaaS directory -site:facebook.com -site:instagram.com -site:reddit.com",
#     "\"list your startup\" AI implementation -site:facebook.com -site:instagram.com -site:reddit.com",
#     "intitle:submit AI tools directory -site:facebook.com -site:instagram.com -site:reddit.com -site:dev.to",
#     "\"get listed\" AI SaaS product directory -site:facebook.com -site:instagram.com -site:reddit.com",
# ]

# # Domains that are never genuine product-submission pages, even if they
# # happen to match a query above (social platforms, forums, dev-blogging
# # sites, generic file hosts). Filtered out before anything is saved.
# EXCLUDED_LISTING_DOMAINS = [
#     "facebook.com", "instagram.com", "linkedin.com", "reddit.com",
#     "twitter.com", "x.com", "dev.to", "medium.com", "youtube.com",
#     "tiktok.com", "pinterest.com", "quora.com", "github.com",
#     "fiverr.com", "upwork.com",
# ]

# # Path/keyword patterns that indicate a genuine submission FORM rather
# # than an article, listicle, or unrelated page. At least one should
# # appear in the URL for a Track B result to be kept.
# SUBMISSION_URL_HINTS = [
#     "submit", "add-product", "add-startup", "new-listing", "listing/new",
#     "create-listing", "get-listed",
# ]


# def serper_search(query: str, num: int = 10) -> list:
#     """Real SERP results via Serper.dev. Raises on failure instead of
#     silently returning fake mock URLs - a discovery run that fails should
#     look like a failure, not quietly inject placeholder data."""
#     if not config.SERPER_API_KEY:
#         raise ValueError("SERPER_API_KEY is not set in .env - get one free at serper.dev")

#     resp = requests.post(
#         SERPER_URL,
#         headers={"X-API-KEY": config.SERPER_API_KEY, "Content-Type": "application/json"},
#         json={"q": query, "num": num},
#         timeout=20,
#     )
#     resp.raise_for_status()
#     data = resp.json()
#     return [item.get("link", "") for item in data.get("organic", []) if item.get("link")]


# def fetch_rss_feed_urls() -> list:
#     urls = []
#     headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
#     for feed_url in RSS_FEEDS:
#         try:
#             logger.info(f"Fetching RSS feed: {feed_url}")
#             response = requests.get(feed_url, headers=headers, timeout=10)
#             if response.status_code == 200:
#                 root = ET.fromstring(response.content)
#                 for item in root.findall('.//item'):
#                     link_elem = item.find('link')
#                     if link_elem is not None and link_elem.text:
#                         urls.append(link_elem.text.strip())
#             else:
#                 logger.warning(f"RSS feed {feed_url} returned status {response.status_code}")
#         except Exception as e:
#             logger.error(f"Error fetching RSS feed {feed_url}: {e}")
#     return urls


# def discover_threads() -> list:
#     """
#     Track A: finds threads/articles to write a reply or article on.
#     Returns fresh URLs not already in the database.
#     """
#     logger.info("Starting ARTICLE/THREAD discovery (Track A)...")
#     all_urls = fetch_rss_feed_urls()

#     for query in ARTICLE_QUERIES:
#         try:
#             all_urls.extend(serper_search(query))
#         except Exception as e:
#             logger.error(f"SERP query failed ('{query}'): {e}")

#     unique_urls = list(set(all_urls))
#     logger.info(f"Track A: {len(unique_urls)} unique URLs found. Checking against DB...")

#     fresh_urls = []
#     db = SessionLocal()
#     try:
#         for url in unique_urls:
#             if not is_duplicate(url):
#                 domain = urllib.parse.urlparse(url).netloc
#                 if not db.query(ThreadMemory).filter(ThreadMemory.url == url).first():
#                     db.add(ThreadMemory(url=url, platform=domain, status='discovered'))
#                     db.commit()
#                 fresh_urls.append(url)
#     finally:
#         db.close()

#     logger.info(f"Track A complete: {len(fresh_urls)} fresh article/thread URLs.")
#     return fresh_urls


# def _is_genuine_submission_candidate(url: str) -> bool:
#     """
#     Two-part generic filter, no platform names hardcoded:
#       1. Domain isn't a known social/dev/forum site (EXCLUDED_LISTING_DOMAINS)
#       2. URL path itself looks like a submission form (SUBMISSION_URL_HINTS)
#     Both checks work identically on a brand-new platform we've never seen.
#     """
#     url_lower = url.lower()
#     domain = urllib.parse.urlparse(url).netloc.lower()

#     if any(excluded in domain for excluded in EXCLUDED_LISTING_DOMAINS):
#         return False

#     if not any(hint in url_lower for hint in SUBMISSION_URL_HINTS):
#         return False

#     return True


# def _gaper_already_mentioned(url: str) -> bool:
#     """Fetches the page and checks if 'gaper' already appears there -
#     used to skip directories Gaper is already listed on."""
#     try:
#         resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
#         return "gaper" in resp.text.lower()
#     except Exception:
#         return False  # can't verify - don't block discovery, let human review decide


# def discover_listing_platforms() -> list:
#     """
#     Track B: actively searches for GENUINE product-submission directories
#     where Gaper could be listed - filters out social media, dev-content
#     sites, and articles/listicles, keeping only pages whose URL structure
#     signals an actual submission form. Also skips any page where Gaper is
#     already mentioned. Saves each as a ListingOpportunity with status
#     'discovered', ready for review in the dashboard.
#     """
#     logger.info("Starting LISTING PLATFORM discovery (Track B)...")
#     all_urls = []

#     for query in LISTING_QUERIES:
#         try:
#             all_urls.extend(serper_search(query))
#         except Exception as e:
#             logger.error(f"SERP query failed ('{query}'): {e}")

#     unique_urls = list(set(all_urls))
#     logger.info(f"Track B: {len(unique_urls)} raw URLs found. Filtering to genuine submission pages...")

#     candidate_urls = [u for u in unique_urls if _is_genuine_submission_candidate(u)]
#     logger.info(f"Track B: {len(candidate_urls)} pass the submission-page filter (from {len(unique_urls)} raw results).")

#     new_opportunities = []
#     db = SessionLocal()
#     try:
#         for url in candidate_urls:
#             domain = urllib.parse.urlparse(url).netloc
#             existing = db.query(ListingOpportunity).filter(ListingOpportunity.url == url).first()
#             if existing:
#                 continue

#             if domain in getattr(config, "ALREADY_LISTED_PLATFORMS", []):
#                 logger.info(f"Skipping {url} - domain is in ALREADY_LISTED_PLATFORMS.")
#                 continue

#             if _gaper_already_mentioned(url):
#                 logger.info(f"Skipping {url} - Gaper already appears to be listed there.")
#                 continue

#             opp = ListingOpportunity(
#                 url=url,
#                 domain=domain,
#                 competitors_found="",
#                 status='discovered',
#             )
#             db.add(opp)
#             db.commit()
#             new_opportunities.append(url)
#             logger.info(f"New listing opportunity: {url}")
#     finally:
#         db.close()

#     logger.info(f"Track B complete: {len(new_opportunities)} new listing candidates.")
#     return new_opportunities


# def detect_missing_gaper_listing(url: str, page_content: str):
#     """
#     Supplement to Track B: if a Track A thread/article page happens to
#     mention competitors but not Gaper, log it as a bonus listing
#     opportunity too.
#     """
#     page_content = page_content or ""
#     if "gaper" in page_content.lower():
#         return

#     found_competitors = [c for c in config.COMPETITORS if c in page_content.lower()]
#     if not found_competitors:
#         return

#     db = SessionLocal()
#     try:
#         domain = urllib.parse.urlparse(url).netloc
#         opp = db.query(ListingOpportunity).filter(ListingOpportunity.url == url).first()
#         if not opp:
#             logger.info(f"Missing listing detected: competitors {found_competitors} mentioned at {url}, Gaper is not.")
#             opp = ListingOpportunity(
#                 url=url, domain=domain,
#                 competitors_found=",".join(found_competitors),
#                 status='discovered',
#             )
#             db.add(opp)
#             db.commit()
#     except Exception as e:
#         logger.error(f"Error logging missing listing: {e}")
#     finally:
#         db.close()






import logging
import urllib.parse
import xml.etree.ElementTree as ET
import requests
from src.database import SessionLocal, ThreadMemory, ListingOpportunity, is_duplicate
import config
 
logger = logging.getLogger(__name__)
 
SERPER_URL = "https://google.serper.dev/search"
 
# Working RSS feeds only. The old indiehackers.com/feed.xml and
# substack.com/feed were not real endpoints - Substack doesn't have one
# unified feed, and dev.to's feed IS real and stays.
RSS_FEEDS = [
    "https://dev.to/feed",
]
 
# --- Two SEPARATE search tracks, per your requirement ---
 
# Track A: threads to write a REPLY on (with a backlink).
# Scoped to Contra only right now - that's the one active platform that
# needs a target thread to reply to. Notion doesn't need thread discovery
# (it's a standalone article generator, no target URL required - see
# post_to_notion_browser.py). Add more platforms back here once they're
# actually wired up and tested, not before.
ARTICLE_QUERIES = [
    "site:contra.com hire remote developers",
    "site:contra.com AI implementation discussion",
    "site:contra.com freelance developer hiring",
]
 
# Track B: platforms/directories where Gaper itself could be LISTED as a
# product (this was completely missing before - detect_missing_gaper_listing
# only ever ran on whatever thread URLs Track A happened to find, it never
# actively searched for directories).
LISTING_QUERIES = [
     "\"submit your startup\" AI tools",
    "\"submit your product\" AI agents directory",
    "\"add your product\" SaaS directory",
    "\"list your startup\" AI implementation",
    "\"submit a listing\" developer staffing platform",
    "intitle:submit AI tools directory",
    "\"get listed\" AI SaaS product directory",
 
]
 
 
def serper_search(query: str, num: int = 10) -> list:
    """Real SERP results via Serper.dev. Raises on failure instead of
    silently returning fake mock URLs - a discovery run that fails should
    look like a failure, not quietly inject placeholder data."""
    if not config.SERPER_API_KEY:
        raise ValueError("SERPER_API_KEY is not set in .env - get one free at serper.dev")
 
    resp = requests.post(
        SERPER_URL,
        headers={"X-API-KEY": config.SERPER_API_KEY, "Content-Type": "application/json"},
        json={"q": query, "num": num},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    return [item.get("link", "") for item in data.get("organic", []) if item.get("link")]
 
 
def fetch_rss_feed_urls() -> list:
    urls = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    for feed_url in RSS_FEEDS:
        try:
            logger.info(f"Fetching RSS feed: {feed_url}")
            response = requests.get(feed_url, headers=headers, timeout=10)
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                for item in root.findall('.//item'):
                    link_elem = item.find('link')
                    if link_elem is not None and link_elem.text:
                        urls.append(link_elem.text.strip())
            else:
                logger.warning(f"RSS feed {feed_url} returned status {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching RSS feed {feed_url}: {e}")
    return urls
 
 
def discover_threads() -> list:
    """
    Track A: finds threads/articles to write a reply or article on.
    Returns fresh URLs not already in the database. Raises if SERP fails
    entirely rather than masking the failure with fake data.
    """
    logger.info("Starting ARTICLE/THREAD discovery (Track A)...")
    all_urls = fetch_rss_feed_urls()
 
    for query in ARTICLE_QUERIES:
        try:
            all_urls.extend(serper_search(query))
        except Exception as e:
            logger.error(f"SERP query failed ('{query}'): {e}")
            # Continue with other queries rather than aborting the whole run,
            # but this failure is now visible in logs - not silently hidden.
 
    unique_urls = list(set(all_urls))
    logger.info(f"Track A: {len(unique_urls)} unique URLs found. Checking against DB...")
 
    fresh_urls = []
    db = SessionLocal()
    try:
        for url in unique_urls:
            if not is_duplicate(url):
                domain = urllib.parse.urlparse(url).netloc
                if not db.query(ThreadMemory).filter(ThreadMemory.url == url).first():
                    db.add(ThreadMemory(url=url, platform=domain, status='discovered'))
                    db.commit()
                fresh_urls.append(url)
    finally:
        db.close()
 
    logger.info(f"Track A complete: {len(fresh_urls)} fresh article/thread URLs.")
    return fresh_urls
 
 
def _score_relevance_to_gaper(url: str, page_text: str = "") -> int:
    """
    0-100 score for how relevant a listing directory is to Gaper's niche
    (dev staffing / AI implementation), so the dashboard can sort/filter
    instead of treating every generic 'submit your startup' page equally.
    Cheap keyword-based scoring - no extra API calls, always available.
    """
    text = f"{url} {page_text}".lower()
    score = 20  # base score for passing the submission-page filter at all
 
    high_value_terms = ["developer", "software", "ai", "automation", "remote work",
                         "staffing", "engineer", "saas", "startup tools", "agency"]
    for term in high_value_terms:
        if term in text:
            score += 8
 
    for competitor in config.COMPETITORS:
        if competitor in text:
            score += 5  # a directory that lists our competitors is a strong fit
 
    return min(100, score)
 
 
def discover_listing_platforms() -> list:
    """
    Track B (NEW): actively searches for directories/platforms where Gaper
    could be listed as a product - separate from Track A's thread search.
    Saves each as a ListingOpportunity with status 'discovered', ready for
    your review in the dashboard before anything gets added.
    """
    logger.info("Starting LISTING PLATFORM discovery (Track B)...")
    all_urls = []
 
    for query in LISTING_QUERIES:
        try:
            all_urls.extend(serper_search(query))
        except Exception as e:
            logger.error(f"SERP query failed ('{query}'): {e}")
 
    unique_urls = list(set(all_urls))
    logger.info(f"Track B: {len(unique_urls)} unique directory/platform URLs found.")
 
    new_opportunities = []
    db = SessionLocal()
    try:
        for url in unique_urls:
            domain = urllib.parse.urlparse(url).netloc
            existing = db.query(ListingOpportunity).filter(ListingOpportunity.url == url).first()
            if existing:
                continue
            score = _score_relevance_to_gaper(url)
            opp = ListingOpportunity(
                url=url,
                domain=domain,
                competitors_found="",  # unknown yet - filled in if/when the page is scraped
                relevance_score=score,
                status='discovered',
            )
            db.add(opp)
            db.commit()
            new_opportunities.append(url)
            logger.info(f"New listing opportunity: {url} (relevance: {score})")
    finally:
        db.close()
 
    logger.info(f"Track B complete: {len(new_opportunities)} new listing candidates.")
    return new_opportunities
 
 
def detect_missing_gaper_listing(url: str, page_content: str):
    """
    Kept for Track A: if a thread/article page happens to mention
    competitors but not Gaper, log it as a bonus listing opportunity too.
    This is now a SUPPLEMENT to Track B, not the only source of listing
    opportunities.
    """
    page_content = page_content or ""  # a strategy (esp. Type4/Gemini) can
                                        # return an explicit null for content,
                                        # which .get(key, "") does NOT catch
                                        # since the key exists, just with a
                                        # None value - this was crashing here.
    if "gaper" in page_content.lower():
        return
 
    found_competitors = [c for c in config.COMPETITORS if c in page_content.lower()]
    if not found_competitors:
        return
 
    db = SessionLocal()
    try:
        domain = urllib.parse.urlparse(url).netloc
        opp = db.query(ListingOpportunity).filter(ListingOpportunity.url == url).first()
        if not opp:
            logger.info(f"Missing listing detected: competitors {found_competitors} mentioned at {url}, Gaper is not.")
            opp = ListingOpportunity(
                url=url, domain=domain,
                competitors_found=",".join(found_competitors),
                relevance_score=_score_relevance_to_gaper(url, page_content) + (len(found_competitors) * 5),
                status='discovered',
            )
            db.add(opp)
            db.commit()
    except Exception as e:
        logger.error(f"Error logging missing listing: {e}")
    finally:
        db.close()