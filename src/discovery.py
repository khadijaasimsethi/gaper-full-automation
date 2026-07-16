# # import logging
# # import urllib.parse
# # import xml.etree.ElementTree as ET
# # import requests
# # from bs4 import BeautifulSoup
# # from src.database import SessionLocal, ThreadMemory, ListingOpportunity, is_duplicate
# # import config

# # logger = logging.getLogger(__name__)

# # def fetch_rss_feed_urls() -> list:
# #     """
# #     Fetches articles from RSS feeds (IndieHackers, Dev.to, Substack, etc.)
# #     """
# #     feeds = [
# #         "https://dev.to/feed",
# #         "https://www.indiehackers.com/feed.xml",
# #         "https://substack.com/feed"
# #     ]
# #     urls = []
# #     headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
# #     for feed_url in feeds:
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
# #                 logger.warning(f"Failed to fetch RSS feed {feed_url}: {response.status_code}")
# #         except Exception as e:
# #             logger.error(f"Error fetching RSS feed {feed_url}: {e}")
            
# #     return urls

# # def fetch_serp_results(query: str) -> list:
# #     """
# #     Performs Google search to find relevant discussions, forum posts, or listing sites.
# #     Uses basic HTML scraping for Google search.
# #     If blocked by captcha, falls back to a high-quality set of mock/simulated URLs.
# #     """
# #     urls = []
# #     headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
# #     encoded_query = urllib.parse.quote_plus(query)
# #     search_url = f"https://www.google.com/search?q={encoded_query}&num=15"
    
# #     try:
# #         logger.info(f"Querying SERP: {query}")
# #         response = requests.get(search_url, headers=headers, timeout=10)
# #         if response.status_code == 200:
# #             soup = BeautifulSoup(response.text, 'html.parser')
# #             # Extract links from search result divs (Google's standard results are in a/h3 tags)
# #             for a in soup.find_all('a', href=True):
# #                 href = a['href']
# #                 if "/url?q=" in href:
# #                     # Clean up Google redirect URL
# #                     cleaned_url = href.split("/url?q=")[1].split("&sa=")[0]
# #                     cleaned_url = urllib.parse.unquote(cleaned_url)
# #                     if any(domain in cleaned_url for domain in ["indiehackers.com", "dev.to", "substack.com", "reddit.com", "quora.com", "peerlist.io"]):
# #                         urls.append(cleaned_url)
# #                 elif href.startswith("http") and not any(x in href for x in ["google.com", "youtube.com", "twitter.com"]):
# #                     if any(domain in href for domain in ["indiehackers.com", "dev.to", "substack.com", "reddit.com", "quora.com", "peerlist.io"]):
# #                         urls.append(href)
# #         else:
# #             logger.warning(f"SERP request rate limited (Status {response.status_code}). Triggering high-fidelity mock results.")
# #     except Exception as e:
# #         logger.error(f"Error scraping SERP: {e}. Triggering mock fallback.")
        
# #     # If scrapers returned no results (due to rate limits or captcha), trigger relevant mock links
# #     if not urls:
# #         logger.info("Using targeted mock URLs for testing.")
# #         # Generate mock urls representing potential backlink opportunities
# #         urls = [
# #             "https://www.indiehackers.com/post/best-platforms-to-hire-developers-for-startups-3f982d",
# #             "https://dev.to/recruitment/how-do-you-hire-remote-software-engineers-in-2026-4ka9",
# #             "https://substack.com/p/finding-tech-co-founders-and-early-employees",
# #             "https://peerlist.io/post/launching-a-new-ai-agent-project-looking-for-developers",
# #             "https://contra.com/opportunity/looking-for-fullstack-devs-with-ai-expertise"
# #         ]
        
# #     return urls

# # def detect_missing_gaper_listing(url: str, page_content: str):
# #     """
# #     Scrapes the target page to check if competitors are mentioned but Gaper is not.
# #     If so, registers this URL as a Listing Opportunity in SQLite.
# #     """
# #     if "gaper" in page_content.lower():
# #         # Gaper is already mentioned!
# #         return
        
# #     found_competitors = []
# #     for competitor in config.COMPETITORS:
# #         if competitor in page_content.lower():
# #             found_competitors.append(competitor)
            
# #     if found_competitors:
# #         db = SessionLocal()
# #         try:
# #             domain = urllib.parse.urlparse(url).netloc
# #             opp = db.query(ListingOpportunity).filter(ListingOpportunity.url == url).first()
# #             if not opp:
# #                 logger.info(f"🚨 Missing Listing Detected: competitors {found_competitors} mentioned at {url} but Gaper is not!")
# #                 opp = ListingOpportunity(
# #                     url=url,
# #                     domain=domain,
# #                     competitors_found=",".join(found_competitors),
# #                     status='discovered'
# #                 )
# #                 db.add(opp)
# #                 db.commit()
# #         except Exception as e:
# #             logger.error(f"Error logging missing listing: {e}")
# #         finally:
# #             db.close()

# # def discover_threads() -> list:
# #     """
# #     Combines search queries and RSS feeds to find potential targets.
# #     Applies smart filtering (duplicates and sets).
# #     """
# #     logger.info("Starting thread discovery pipeline...")
# #     all_urls = []
    
# #     # 1. Combine RSS feed sources
# #     rss_urls = fetch_rss_feed_urls()
# #     all_urls.extend(rss_urls)
    
# #     # 2. Combine SERP results for relevant queries
# #     queries = [
# #         "hire remote developers",
# #         "best platforms to hire remote engineers",
# #         "AI implementation partner for startups",
# #         "AI agents integration agency",
# #         "vetted software developers platform"
# #     ]
    
# #     for q in queries:
# #         serp_urls = fetch_serp_results(q)
# #         all_urls.extend(serp_urls)
        
# #     # Deduplicate URL list
# #     unique_urls = list(set(all_urls))
# #     logger.info(f"Discovered {len(unique_urls)} unique URLs. Filtering database duplicates...")
    
# #     fresh_urls = []
# #     db = SessionLocal()
# #     try:
# #         for url in unique_urls:
# #             # Check db duplicate
# #             if not is_duplicate(url):
# #                 # Save as new thread memory
# #                 thread = db.query(ThreadMemory).filter(ThreadMemory.url == url).first()
# #                 if not thread:
# #                     domain = urllib.parse.urlparse(url).netloc
# #                     # Add to DB
# #                     new_thread = ThreadMemory(
# #                         url=url,
# #                         platform=domain,
# #                         status='discovered'
# #                     )
# #                     db.add(new_thread)
# #                     db.commit()
# #                 fresh_urls.append(url)
# #     except Exception as e:
# #         logger.error(f"Error during duplicate filtering: {e}")
# #     finally:
# #         db.close()
        
# #     logger.info(f"Discovery complete. Found {len(fresh_urls)} fresh URLs to ingest.")
# #     return fresh_urls




# import logging
# import urllib.parse
# import xml.etree.ElementTree as ET
# import requests
# from src.database import SessionLocal, ThreadMemory, ListingOpportunity, is_duplicate
# import config

# logger = logging.getLogger(__name__)

# SERPER_URL = "https://google.serper.dev/search"

# # Working RSS feeds only. The old indiehackers.com/feed.xml and
# # substack.com/feed were not real endpoints - Substack doesn't have one
# # unified feed, and dev.to's feed IS real and stays.
# RSS_FEEDS = [
#     "https://dev.to/feed",
# ]

# # --- Two SEPARATE search tracks, per your requirement ---

# # Track A: threads/articles to write a reply/article on (with a backlink)
# ARTICLE_QUERIES = [
#     "hire remote developers site:indiehackers.com",
#     "hire remote developers site:dev.to",
#     "AI implementation partner for startups discussion",
#     "AI agents integration agency reddit",
#     "vetted software developers platform forum",
# ]

# # Track B: platforms/directories where Gaper itself could be LISTED as a
# # product (this was completely missing before - detect_missing_gaper_listing
# # only ever ran on whatever thread URLs Track A happened to find, it never
# # actively searched for directories).
# LISTING_QUERIES = [
#     "AI agent platforms directory submit listing",
#     "best AI implementation partners list 2026",
#     "staff augmentation companies directory",
#     "site:producthunt.com AI staffing OR AI agents",
#     "site:saashub.com AI implementation partner",
#     "site:alternativeto.net AI developer staffing",
#     "top remote developer hiring platforms comparison",
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
#     Returns fresh URLs not already in the database. Raises if SERP fails
#     entirely rather than masking the failure with fake data.
#     """
#     logger.info("Starting ARTICLE/THREAD discovery (Track A)...")
#     all_urls = fetch_rss_feed_urls()

#     for query in ARTICLE_QUERIES:
#         try:
#             all_urls.extend(serper_search(query))
#         except Exception as e:
#             logger.error(f"SERP query failed ('{query}'): {e}")
#             # Continue with other queries rather than aborting the whole run,
#             # but this failure is now visible in logs - not silently hidden.

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


# def discover_listing_platforms() -> list:
#     """
#     Track B (NEW): actively searches for directories/platforms where Gaper
#     could be listed as a product - separate from Track A's thread search.
#     Saves each as a ListingOpportunity with status 'discovered', ready for
#     your review in the dashboard before anything gets added.
#     """
#     logger.info("Starting LISTING PLATFORM discovery (Track B)...")
#     all_urls = []

#     for query in LISTING_QUERIES:
#         try:
#             all_urls.extend(serper_search(query))
#         except Exception as e:
#             logger.error(f"SERP query failed ('{query}'): {e}")

#     unique_urls = list(set(all_urls))
#     logger.info(f"Track B: {len(unique_urls)} unique directory/platform URLs found.")

#     new_opportunities = []
#     db = SessionLocal()
#     try:
#         for url in unique_urls:
#             domain = urllib.parse.urlparse(url).netloc
#             existing = db.query(ListingOpportunity).filter(ListingOpportunity.url == url).first()
#             if existing:
#                 continue
#             opp = ListingOpportunity(
#                 url=url,
#                 domain=domain,
#                 competitors_found="",  # unknown yet - filled in if/when the page is scraped
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
#     Kept for Track A: if a thread/article page happens to mention
#     competitors but not Gaper, log it as a bonus listing opportunity too.
#     This is now a SUPPLEMENT to Track B, not the only source of listing
#     opportunities.
#     """
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

# Track A: threads/articles to write a reply/article on (with a backlink)
ARTICLE_QUERIES = [
    "hire remote developers site:indiehackers.com",
    "hire remote developers site:dev.to",
    "AI implementation partner for startups discussion",
    "AI agents integration agency reddit",
    "vetted software developers platform forum",
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
            opp = ListingOpportunity(
                url=url,
                domain=domain,
                competitors_found="",  # unknown yet - filled in if/when the page is scraped
                status='discovered',
            )
            db.add(opp)
            db.commit()
            new_opportunities.append(url)
            logger.info(f"New listing opportunity: {url}")
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
                status='discovered',
            )
            db.add(opp)
            db.commit()
    except Exception as e:
        logger.error(f"Error logging missing listing: {e}")
    finally:
        db.close()