"""
Proxy rotation. Per Alisha's plan: datacenter proxies for read-only
scraping (cheap), residential reserved only for authenticated posting
(expensive, billed per-GB).
"""

import logging
import random
import config

logger = logging.getLogger(__name__)


class ProxyManager:
    def __init__(self):
        self.proxies = getattr(config, "PROXY_LIST", [])

    def has_proxies(self) -> bool:
        return bool(self.proxies)

    def get_playwright_proxy(self, proxy_type: str = "datacenter") -> dict:
        """
        Returns a Playwright-compatible proxy dict, or None if no proxies
        configured. proxy_type is currently informational (filter your
        PROXY_LIST by type key in config.py if you have both kinds).
        """
        if not self.proxies:
            logger.info("No proxies configured in config.PROXY_LIST - running without proxy.")
            return None

        candidates = [p for p in self.proxies if p.get("type", "datacenter") == proxy_type]
        if not candidates:
            candidates = self.proxies

        proxy = random.choice(candidates)
        server = f"http://{proxy['ip']}:{proxy['port']}"
        result = {"server": server}
        if proxy.get("username"):
            result["username"] = proxy["username"]
            result["password"] = proxy["password"]
        return result