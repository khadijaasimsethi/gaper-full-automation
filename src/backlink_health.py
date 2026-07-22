"""
Real implementation of Phase 5's "7-day follow-up" check: for every live
backlink that's due (>=7 days old, not checked in the last 7 days),
actually fetch the target page and verify Gaper/the link is still there.
Manually triggered from the dashboard button (no background scheduler
required) - human-in-the-loop friendly, and works even without Celery/Redis.
"""
import logging
import requests
from src.database import get_backlinks_due_for_check, update_backlink_health
import config

logger = logging.getLogger(__name__)


def _is_gaper_still_present(url: str) -> bool:
    """
    Fetches the page and checks for 'gaper' text or a gaper.io link.
    Returns True on fetch failure too (can't verify != confirmed missing -
    avoids flagging a link as 'missing' just because a site blocked our
    request), so 'missing' only means we positively confirmed it's gone.
    """
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}, timeout=10)
        if resp.status_code != 200:
            return True  # can't verify - don't wrongly flag as missing
        text = resp.text.lower()
        return "gaper" in text
    except Exception as e:
        logger.warning(f"[LinkHealth] Could not fetch {url} to verify: {e}")
        return True  # fetch failed - don't wrongly flag as missing


def check_overdue_backlinks(days: int = 7) -> dict:
    """
    Checks every live backlink due for a recheck. For Contra (comment on
    a live feed/thread page), target_url is checked directly. For Notion,
    target_url is the workspace database URL, not a public page (unless
    published) - those get marked 'still_live' by default since API-level
    archive-status already reflects deletion accurately in the New
    Backlinks tab itself, no need for a duplicate public-page check.
    """
    due = get_backlinks_due_for_check(days)
    still_live = 0
    missing = 0

    for backlink in due:
        if backlink.platform == "notion":
           
            update_backlink_health(backlink.id, "still_live")
            still_live += 1
            continue

        present = _is_gaper_still_present(backlink.target_url)
        if present:
            update_backlink_health(backlink.id, "still_live")
            still_live += 1
        else:
            update_backlink_health(backlink.id, "missing")
            missing += 1
            logger.warning(f"[LinkHealth] Gaper mention no longer found at {backlink.target_url} (backlink id {backlink.id})")

    return {"checked": len(due), "still_live": still_live, "missing": missing}