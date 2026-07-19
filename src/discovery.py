import logging
import urllib.parse
import xml.etree.ElementTree as ET
import requests
from src.database import SessionLocal, ThreadMemory, ListingOpportunity, is_duplicate
import config

logger = logging.getLogger(__name__)

SERPER_URL = "https://google.serper.dev/search"

RSS_FEEDS = [
    "https://dev.to/feed",
]

ARTICLE_QUERIES = [
    "site:contra.com hire remote developers",
    "site:contra.com AI implementation discussion",
    "site:contra.com freelance developer hiring",
]

LISTING_QUERIES = [
    "\"submit your startup\" AI tools directory",
    "\"submit your product\" software directory",
    "\"add your product\" SaaS tools",
    "\"list your startup\" AI implementation",
    "\"submit a listing\" developer platform",
    "intitle:submit software directory",
    "\"get listed\" product directory",
    "AI developer tools directory submit",
    "best SaaS directories submit startup",
    "submit startup to directory 2024",
    "product hunt alternative submit",
    "g2 capterra alternative submit product",
    "startup directory list your tool",
    "AI agency directory submit listing",
    "site:producthunt.com/posts/new",
    "site:alternativeto.net/software/add/",
    "site:betalist.com/submit",
    "site:g2.com/products/new",
    "site:capterra.com/vendors/add",
    "site:sourceforge.net/software/add",
    "site:slant.co/add-product",
    "site:stackshare.io/tools/new",
    "\"submit your AI tool\" site:indiehackers.com OR site:reddit.com",
    "AI developer tools \"submit\" OR \"add listing\" OR \"get listed\"",
    "SaaS directory \"submit startup\" OR \"submit product\"",
    "startup directory \"add your product\" OR \"list your tool\"",
]


def serper_search(query: str, num: int = 10) -> list:
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
    logger.info("Starting ARTICLE/THREAD discovery (Track A)...")
    all_urls = fetch_rss_feed_urls()

    for query in ARTICLE_QUERIES:
        try:
            all_urls.extend(serper_search(query))
        except Exception as e:
            logger.error(f"SERP query failed ('{query}'): {e}")

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
    if not page_text or len(page_text) < 100:
        page_text = _fetch_page_text(url)

    text = f"{url} {page_text}".lower()
    score = 10

    high_value_terms = {
        "developer": 10, "software": 10, "ai": 12, "automation": 10,
        "remote work": 8, "staffing": 10, "engineer": 10, "saas": 8,
        "startup tools": 8, "agency": 6, "hire": 8, "hiring": 8,
        "freelance": 6, "talent": 6, "outsourcing": 6, "dev team": 8,
        "artificial intelligence": 10, "machine learning": 6,
        "web development": 6, "mobile development": 6,
        "full stack": 6, "backend": 4, "frontend": 4,
    }
    for term, points in high_value_terms.items():
        if term in text:
            score += points

    for competitor in config.COMPETITORS:
        if competitor in text:
            score += 8

    submission_terms = ["submit your product", "add your startup", "get listed",
                        "submit a listing", "list your product", "nominate"]
    for term in submission_terms:
        if term in text:
            score += 5

    return min(100, score)


def _fetch_page_text(url: str, timeout: int = 8) -> str:
    try:
        from bs4 import BeautifulSoup
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}, timeout=timeout)
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)[:5000]
    except Exception:
        return ""


def discover_listing_platforms() -> list:
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

            page_text = _fetch_page_text(url)
            score = _score_relevance_to_gaper(url, page_text)
            found_competitors = [c for c in config.COMPETITORS if c in page_text.lower()]

            opp = ListingOpportunity(
                url=url,
                domain=domain,
                competitors_found=",".join(found_competitors),
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
    page_content = page_content or ""
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
            score = _score_relevance_to_gaper(url, page_content) + (len(found_competitors) * 5)
            logger.info(f"Missing listing detected: competitors {found_competitors} mentioned at {url}. Score: {score}")
            opp = ListingOpportunity(
                url=url, domain=domain,
                competitors_found=",".join(found_competitors),
                relevance_score=min(100, score),
                status='discovered',
            )
            db.add(opp)
            db.commit()
    except Exception as e:
        logger.error(f"Error logging missing listing: {e}")
    finally:
        db.close()