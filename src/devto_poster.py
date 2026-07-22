"""
Dev.to (forem) posting via their public REST API. Get your API key from
https://dev.to/settings/extensions -> "DEV API Keys" section, then add to
.env: DEVTO_API_KEY=your_key_here

Much simpler than Contra/Notion - no browser, no session, just a signed
POST request. Publishes immediately (published: true) since Dev.to has
no separate "manual publish" step like Notion does.
"""
import logging
import requests
import config

logger = logging.getLogger(__name__)

DEVTO_API_URL = "https://dev.to/api/articles"


def post_to_devto(title: str, body_markdown: str, tags: list = None) -> dict:
    api_key = getattr(config, "DEVTO_API_KEY", "")
    if not api_key:
        return {"status": "failed", "detail": "DEVTO_API_KEY not set in .env. Get one at https://dev.to/settings/extensions"}

    headers = {"api-key": api_key, "Content-Type": "application/json"}
    payload = {
        "article": {
            "title": title[:128],  # Dev.to's title length limit
            "body_markdown": body_markdown,
            "published": True,
            "tags": tags or ["ai", "hiring", "startup"],
        }
    }

    try:
        res = requests.post(DEVTO_API_URL, headers=headers, json=payload, timeout=15)
        if res.status_code == 201:
            data = res.json()
            article_url = data.get("url", "")
            article_id = data.get("id", "")
            logger.info(f"[Devto] Published: {article_url}")
            return {"status": "success", "detail": f"Published on Dev.to: {article_url}", "posted_url": article_url, "article_id": article_id}
        else:
            logger.error(f"[Devto] API error {res.status_code}: {res.text}")
            return {"status": "failed", "detail": f"Dev.to API error ({res.status_code}): {res.text}"}
    except Exception as e:
        logger.error(f"[Devto] Failed: {e}")
        return {"status": "failed", "detail": str(e)}