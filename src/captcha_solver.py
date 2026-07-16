"""
2Captcha integration. One account balance covers recaptcha v2/v3,
hCaptcha, Turnstile, and image captchas - matches the shared account
Alisha described (PR@gaper.io login, $10 test top-up).
"""

import logging
import time
import requests
import config

logger = logging.getLogger(__name__)

TWOCAPTCHA_IN_URL = "https://2captcha.com/in.php"
TWOCAPTCHA_RES_URL = "https://2captcha.com/res.php"


class CaptchaSolver:
    def __init__(self):
        self.api_key = config.CAPTCHA_API_KEY
        if not self.api_key:
            logger.warning("CAPTCHA_API_KEY not set - captcha solving will be skipped.")

    def get_balance(self) -> float:
        """Check remaining 2Captcha balance so we can warn when it's low."""
        if not self.api_key:
            return 0.0
        try:
            resp = requests.get(TWOCAPTCHA_RES_URL, params={
                "key": self.api_key, "action": "getbalance", "json": 1
            }, timeout=10)
            data = resp.json()
            balance = float(data.get("request", 0))
            if balance < 2.0:
                logger.warning(f"⚠️ 2Captcha balance is low: ${balance:.2f}. Top up soon.")
            return balance
        except Exception as e:
            logger.error(f"Could not check 2Captcha balance: {e}")
            return 0.0

    def detect_captcha_type(self, page) -> str:
        """Looks at the page for known captcha widgets."""
        try:
            if page.locator("iframe[src*='recaptcha']").count() > 0:
                return "recaptcha_v2"
            if page.locator("iframe[src*='hcaptcha']").count() > 0:
                return "hcaptcha"
            if page.locator("iframe[src*='turnstile'], .cf-turnstile").count() > 0:
                return "turnstile"
        except Exception as e:
            logger.warning(f"Captcha detection failed: {e}")
        return None

    def get_site_key(self, page, captcha_type: str) -> str:
        """Extracts the site key from the page's captcha widget element."""
        try:
            selector_map = {
                "recaptcha_v2": "[data-sitekey]",
                "hcaptcha": "[data-sitekey]",
                "turnstile": "[data-sitekey]",
            }
            el = page.locator(selector_map.get(captcha_type, "[data-sitekey]")).first
            return el.get_attribute("data-sitekey")
        except Exception as e:
            logger.warning(f"Could not extract site key: {e}")
            return None

    def _poll_result(self, request_id: str, timeout: int = 120) -> str:
        elapsed = 0
        while elapsed < timeout:
            time.sleep(5)
            elapsed += 5
            resp = requests.get(TWOCAPTCHA_RES_URL, params={
                "key": self.api_key, "action": "get", "id": request_id, "json": 1
            }, timeout=10)
            data = resp.json()
            if data.get("status") == 1:
                return data.get("request")
            if data.get("request") != "CAPCHA_NOT_READY":
                raise Exception(f"2Captcha error: {data.get('request')}")
        raise Exception("2Captcha solve timed out.")

    def solve_recaptcha_v2(self, site_key: str, page_url: str) -> str:
        self.get_balance()
        resp = requests.post(TWOCAPTCHA_IN_URL, data={
            "key": self.api_key, "method": "userrecaptcha",
            "googlekey": site_key, "pageurl": page_url, "json": 1
        }, timeout=15)
        data = resp.json()
        if data.get("status") != 1:
            raise Exception(f"2Captcha submit failed: {data.get('request')}")
        return self._poll_result(data["request"])

    def solve_hcaptcha(self, site_key: str, page_url: str) -> str:
        self.get_balance()
        resp = requests.post(TWOCAPTCHA_IN_URL, data={
            "key": self.api_key, "method": "hcaptcha",
            "sitekey": site_key, "pageurl": page_url, "json": 1
        }, timeout=15)
        data = resp.json()
        if data.get("status") != 1:
            raise Exception(f"2Captcha submit failed: {data.get('request')}")
        return self._poll_result(data["request"])

    def solve_turnstile(self, site_key: str, page_url: str) -> str:
        self.get_balance()
        resp = requests.post(TWOCAPTCHA_IN_URL, data={
            "key": self.api_key, "method": "turnstile",
            "sitekey": site_key, "pageurl": page_url, "json": 1
        }, timeout=15)
        data = resp.json()
        if data.get("status") != 1:
            raise Exception(f"2Captcha submit failed: {data.get('request')}")
        return self._poll_result(data["request"])