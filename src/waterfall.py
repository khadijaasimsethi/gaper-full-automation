import logging
import urllib.parse
from src.database import get_platform_config, set_platform_config
from src.discovery import detect_missing_gaper_listing
from src.ingestion import (
    Type1ApiRss,
    Type2StaticSoup,
    Type3PlaywrightAuth,
    Type4LlmVision,
    BlockedException,
    DomParseException,
    IngestionException
)
import config

logger = logging.getLogger(__name__)

STRATEGIES = {
    "Type1ApiRss": Type1ApiRss(),
    "Type2StaticSoup": Type2StaticSoup(),
    "Type3PlaywrightAuth": Type3PlaywrightAuth(),
    "Type4LlmVision": Type4LlmVision()
}


def ingest_thread(url: str) -> dict:
    """
    Implements the Waterfall Ingestion Escalation (Block 4).
    """
    domain = urllib.parse.urlparse(url).netloc
    cached_strategy_name = get_platform_config(domain)

    if cached_strategy_name and cached_strategy_name in STRATEGIES:
        logger.info(f"Using cached strategy '{cached_strategy_name}' for domain '{domain}'")
        try:
            strategy = STRATEGIES[cached_strategy_name]
            data = strategy.fetch_thread_data(url)
            # data.get("content", "") does NOT protect against an explicit
            # None value (only a missing key) - a strategy (esp. Type4/
            # Gemini) can return {"content": None}, which crashed
            # detect_missing_gaper_listing's .lower() call downstream.
            detect_missing_gaper_listing(url, data.get("content") or "")
            return data
        except IngestionException as e:
            logger.warning(f"Cached strategy '{cached_strategy_name}' failed for {url}: {e}. Falling back to waterfall escalation...")

    last_error = None
    successful_strategy = None
    parsed_data = None

    escalation_list = []
    if "dev.to" in url or "feed" in url:
        escalation_list.append("Type1ApiRss")
    escalation_list.extend(config.ESCALATION_ORDER)

    seen = set()
    escalation_order = [x for x in escalation_list if not (x in seen or seen.add(x))]

    for strategy_name in escalation_order:
        if strategy_name not in STRATEGIES:
            continue

        logger.info(f"Escalating: Trying strategy '{strategy_name}' for URL: {url}")
        try:
            strategy = STRATEGIES[strategy_name]
            parsed_data = strategy.fetch_thread_data(url)
            successful_strategy = strategy_name
            break
        except (BlockedException, DomParseException) as exc:
            logger.warning(f"Strategy '{strategy_name}' failed with recoverable exception: {exc}")
            last_error = exc
        except Exception as e:
            logger.error(f"Strategy '{strategy_name}' failed with unexpected error: {e}")
            last_error = e

    if successful_strategy and parsed_data:
        logger.info(f"Ingestion success! Caching strategy '{successful_strategy}' for domain '{domain}'")
        set_platform_config(domain, successful_strategy)
        detect_missing_gaper_listing(url, parsed_data.get("content") or "")
        return parsed_data

    raise IngestionException(f"All ingestion strategies failed for {url}. Last error: {last_error}")