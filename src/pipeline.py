import logging
import queue
import threading
import time
import datetime
from src.database import SessionLocal, ThreadMemory, PostedBacklink
from src.gaper_scraper import get_brand_profile
from src.waterfall import ingest_thread
from src.brain import draft_reply, evaluate_seo_geo_aeo
from src.adapters import get_adapter
import config

logger = logging.getLogger(__name__)

# Celery Setup (Block 7)
celery_app = None
if config.USE_CELERY:
    try:
        from celery import Celery
        celery_app = Celery('gaper_pipeline', broker=config.REDIS_URL)
        celery_app.conf.update(
            task_serializer='json',
            accept_content=['json'],
            result_serializer='json',
            timezone='UTC',
            enable_utc=True,
        )
        logger.info("Celery configured as background task broker.")
    except ImportError:
        logger.warning("Celery library not found. Falling back to local threadpool queue broker.")

# Local Thread-Based Broker Fallback
class LocalTaskBroker:
    def __init__(self):
        self.task_queue = queue.Queue()
        self.worker_thread = None
        self.running = False

    def start(self):
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
            self.worker_thread.start()
            logger.info("Local thread broker worker thread started.")

    def stop(self):
        self.running = False

    def delay(self, func, *args, **kwargs):
        self.task_queue.put((func, args, kwargs))
        logger.info(f"Task queued in local broker. Queue size: {self.task_queue.qsize()}")

    def _process_queue(self):
        while self.running:
            try:
                # Rate limit: max 10 posts per minute (6 seconds sleep between tasks)
                time.sleep(6)
                if not self.task_queue.empty():
                    func, args, kwargs = self.task_queue.get()
                    logger.info(f"Local Broker executing task: {func.__name__}")
                    try:
                        func(*args, **kwargs)
                    except Exception as e:
                        logger.error(f"Error executing task in local broker: {e}")
                    finally:
                        self.task_queue.task_done()
            except Exception as e:
                logger.error(f"Error in local broker loop: {e}")

local_broker = LocalTaskBroker()
local_broker.start()


def execute_post_task(thread_id: int):
    """
    Main post execution task (Block 7).
    Only ever called from approve_and_queue_post(), which requires the
    thread to already be in 'approved' status - i.e. a human has looked
    at it. Never call this directly from discovery or drafting code.
    """
    db = SessionLocal()
    try:
        thread = db.query(ThreadMemory).filter(ThreadMemory.id == thread_id).first()
        if not thread:
            logger.error(f"Thread {thread_id} not found in database.")
            return

        if thread.status != 'approved':
            logger.error(f"Refusing to post thread {thread_id}: status is '{thread.status}', not 'approved'. "
                         f"A post must go through human approval before execution.")
            return

        logger.info(f"Executing post task for Thread ID {thread_id} ({thread.url})")
        adapter = get_adapter(thread.platform)

        res = adapter.execute_post(thread.url, thread.generated_reply, thread.is_ghost)

        if res["status"] in ("success", "simulated_success"):
            thread.status = 'posted'
            if thread.is_ghost:
                logger.info(f"Ghost post executed for thread {thread.url}. Skipping 7-day link checking trigger.")
            else:
                due_at = datetime.datetime.utcnow() + datetime.timedelta(days=7)
                db.add(PostedBacklink(
                    platform=thread.platform or "unknown",
                    target_url=thread.url,
                    content=thread.generated_reply,
                    status="live",
                    note="Posted via backlink outreach pipeline",
                    follow_up_due_at=due_at,
                ))
                logger.info(f"Citation post executed. 7-day backlink verification due {due_at.isoformat()} for {thread.url}.")
        else:
            thread.status = 'failed'
            logger.error(f"Execution failed: {res['detail']}")

        db.commit()
    except Exception as e:
        logger.error(f"Error in execute_post_task: {e}")
    finally:
        db.close()


if celery_app:
    @celery_app.task(rate_limit="10/m")
    def celery_post_task(thread_id: int):
        execute_post_task(thread_id)


def run_pipeline(url: str) -> dict:
    """
    Full pipeline run (Block 7):
    Ingests, drafts, scores, and saves threads in DB.
    Always stops at 'pending_approval' - a human (CLI prompt or dashboard)
    must explicitly call approve_and_queue_post() before anything posts.
    No auto-pilot bypass exists here - review is never optional.
    """
    logger.info(f"Running pipeline for URL: {url}")
    db = SessionLocal()
    thread = None
    try:
        thread = db.query(ThreadMemory).filter(ThreadMemory.url == url).first()

        thread_data = ingest_thread(url)

        if not thread:
            thread = ThreadMemory(url=url, platform=thread_data.get("title", ""))
            db.add(thread)

        thread.scraped_content = thread_data.get("content", "")
        thread.comment_count = thread_data.get("comments_count", 0)
        thread.status = 'processing'
        db.commit()

        draft = draft_reply(thread_data)

        thread.generated_reply = draft["reply_text"]
        thread.is_ghost = draft["is_ghost"]
        thread.status = 'pending_approval'
        db.commit()

        return {
            "thread_id": thread.id,
            "url": thread.url,
            "status": thread.status,
            "reply_text": thread.generated_reply,
            "is_ghost": thread.is_ghost,
            "scores": draft["scores"],
            "is_mock": draft.get("is_mock", False),
        }
    except Exception as e:
        logger.error(f"Pipeline failure for {url}: {e}")
        if thread:
            thread.status = 'failed'
            db.commit()
        raise e
    finally:
        db.close()


def approve_and_queue_post(thread_id: int):
    """
    Called ONLY when a human has explicitly approved a draft (CLI 'y' or
    dashboard approve button). Queues the execution task using the active
    broker.
    """
    db = SessionLocal()
    try:
        thread = db.query(ThreadMemory).filter(ThreadMemory.id == thread_id).first()
        if not thread:
            return

        thread.status = 'approved'
        db.commit()

        if config.USE_CELERY and celery_app:
            celery_post_task.delay(thread_id)
        else:
            local_broker.delay(execute_post_task, thread_id)

        logger.info(f"Thread {thread_id} approved and sent to broker queue.")
    finally:
        db.close()


def run_backlink_health_check() -> dict:
    """
    The other half of the 7-day follow-up trigger: run this (via dashboard
    button or a cron/Celery beat schedule) to actually check every
    backlink whose 7-day window is up. Does a plain HTTP fetch of the
    target thread and looks for gaper.io in the page - if it's gone
    (deleted comment, moderated thread, etc.) that's flagged so a human
    can decide whether to re-post.
    """
    import requests
    from src.database import get_overdue_backlinks, record_backlink_check

    overdue = get_overdue_backlinks()
    checked, still_live, missing = 0, 0, 0

    for bl in overdue:
        checked += 1
        try:
            resp = requests.get(bl.target_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            is_live = resp.status_code == 200 and "gaper" in resp.text.lower()
        except Exception as e:
            logger.warning(f"Could not verify backlink {bl.target_url}: {e}")
            is_live = False  # can't confirm it's there - flag for a human look, don't assume it's fine

        record_backlink_check(bl.id, is_live)
        if is_live:
            still_live += 1
        else:
            missing += 1

    logger.info(f"Backlink health check: {checked} checked, {still_live} still live, {missing} missing/unverifiable.")
    return {"checked": checked, "still_live": still_live, "missing": missing}


def run_global_discovery() -> int:
    """
    Runs BOTH discovery tracks:
      Track A - threads/articles to write a reply/article on
      Track B - directories/platforms where Gaper itself could be listed
    Both always stop at a human-review status ('pending_approval' for
    threads, 'discovered' for listing candidates) - nothing posts or gets
    added anywhere without you explicitly approving it in the dashboard.
    """
    logger.info("Starting Global Automated Discovery Job...")
    from src.discovery import discover_threads, discover_listing_platforms

    fresh_urls = discover_threads()
    for url in fresh_urls:
        try:
            run_pipeline(url)
        except Exception as e:
            logger.error(f"Failed to process discovered URL {url}: {e}")

    new_listings = discover_listing_platforms()  # was missing entirely before - Track B never ran

    return len(fresh_urls) + len(new_listings)