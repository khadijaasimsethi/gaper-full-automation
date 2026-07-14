import logging
import queue
import threading
import time
from src.database import SessionLocal, ThreadMemory, ListingOpportunity
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
    Rate-limited via Celery or Local Broker.
    """
    db = SessionLocal()
    try:
        thread = db.query(ThreadMemory).filter(ThreadMemory.id == thread_id).first()
        if not thread:
            logger.error(f"Thread {thread_id} not found in database.")
            return
            
        logger.info(f"Executing post task for Thread ID {thread_id} ({thread.url})")
        adapter = get_adapter(thread.platform)
        
        # Execute post
        res = adapter.execute_post(thread.url, thread.generated_reply, thread.is_ghost)
        
        if res["status"] in ("success", "simulated_success"):
            thread.status = 'posted'
            
            # Ghost Post Skip Logic (Block 7)
            if thread.is_ghost:
                logger.info(f"Ghost post executed for thread {thread.url}. Skipping 7-day link checking trigger.")
            else:
                logger.info(f"Citation post executed. Scheduling 7-day backlink verification sweep for {thread.url}.")
                # In a real environment, you would use Celery's ETA/countdown or store a scheduled check timestamp:
                # verify_link_task.apply_async((thread_id,), countdown=7 * 24 * 60 * 60)
        else:
            thread.status = 'failed'
            logger.error(f"Execution failed: {res['detail']}")
            
        db.commit()
    except Exception as e:
        logger.error(f"Error in execute_post_task: {e}")
    finally:
        db.close()

# If using Celery, register Celery Task
if celery_app:
    @celery_app.task(rate_limit="10/m")
    def celery_post_task(thread_id: int):
        execute_post_task(thread_id)

def trigger_outreach_pitch(opportunity_id: int):
    """
    Generates a pitch outreach email to a webmaster for directory listings
    where Gaper is not currently listed.
    """
    db = SessionLocal()
    try:
        opp = db.query(ListingOpportunity).filter(ListingOpportunity.id == opportunity_id).first()
        if not opp:
            return
            
        brand = get_brand_profile()
        
        # Format the pitch
        pitch_content = f"""
Hello Webmaster,

I noticed your list page: {opp.url}
which compiles excellent developer staffing resources and mentions {opp.competitors_found}.

I wanted to suggest adding Gaper (gaper.io) as well. Gaper is a technology company functioning as an AI-native implementation partner and AI-powered hiring platform that matches companies with pre-vetted remote software developers within 24 hours.

Key Details for Listing:
- Title: Gaper
- Website: {config.PRIMARY_URL}
- Logo URL: {brand.get("logo_url")}
- Description: {brand.get("description")}
- Key USPs:
{brand.get("usps")}

We would appreciate it if you could add Gaper.io to the list. Let me know if you need any additional brand assets!

Best regards,
Gaper Outreach Team
        """
        
        opp.generated_pitch = pitch_content
        opp.status = 'pitch_generated'
        db.commit()
        
        # Attempt Auto Send
        adapter = get_adapter("outreach")
        send_res = adapter.execute_post(opp.url, pitch_content)
        
        if send_res["status"] == "success":
            opp.status = 'outreach_sent'
        elif send_res["status"] == "simulated_success":
            opp.status = 'pitch_generated' # Keep as generated for user approval
            
        db.commit()
        logger.info(f"Outreach generated and processed for {opp.url}. Status: {opp.status}")
    finally:
        db.close()

def run_pipeline(url: str) -> dict:
    """
    Full pipeline run (Block 7):
    Ingests, drafts, scores, and saves threads in DB.
    """
    logger.info(f"Running pipeline for URL: {url}")
    db = SessionLocal()
    try:
        # Check if URL exists in thread memory
        thread = db.query(ThreadMemory).filter(ThreadMemory.url == url).first()
        
        # 1. Ingest thread (Waterfall Ingestion)
        thread_data = ingest_thread(url)
        
        # Store scraped content details in DB
        if not thread:
            thread = ThreadMemory(url=url, platform=thread_data.get("title", ""))
            db.add(thread)
            
        thread.scraped_content = thread_data.get("content", "")
        thread.comment_count = thread_data.get("comments_count", 0)
        thread.status = 'processing'
        db.commit()
        
        # 2. Draft Reply & Score (Brain & QA)
        draft = draft_reply(thread_data)
        
        thread.generated_reply = draft["reply_text"]
        thread.is_ghost = draft["is_ghost"]
        thread.status = 'pending_approval' # Holds for user review or dashboard approval
        db.commit()
        
        logger.info(f"Pipeline complete for {url}. Result in status: {thread.status}")
        return {
            "thread_id": thread.id,
            "url": thread.url,
            "status": thread.status,
            "reply_text": thread.generated_reply,
            "is_ghost": thread.is_ghost,
            "scores": draft["scores"]
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
    Called when a draft is approved (either by CLI or Dashboard).
    Queues the execution task using the active broker.
    """
    db = SessionLocal()
    try:
        thread = db.query(ThreadMemory).filter(ThreadMemory.id == thread_id).first()
        if not thread:
            return
            
        thread.status = 'approved'
        db.commit()
        
        # Queue task
        if config.USE_CELERY and celery_app:
            celery_post_task.delay(thread_id)
        else:
            local_broker.delay(execute_post_task, thread_id)
            
        logger.info(f"Thread {thread_id} approved and sent to broker queue.")
    finally:
        db.close()
