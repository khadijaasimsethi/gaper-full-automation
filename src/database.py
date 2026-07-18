# import datetime
# from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text
# from sqlalchemy.ext.declarative import declarative_base
# from sqlalchemy.orm import sessionmaker
# import config

# Base = declarative_base()

# class ThreadMemory(Base):
#     __tablename__ = 'thread_memory'
    
#     id = Column(Integer, primary_key=True)
#     url = Column(String(500), unique=True, nullable=False)
#     platform = Column(String(100))
#     comment_count = Column(Integer, default=0)
#     status = Column(String(50), default='discovered') # discovered, processing, pending_approval, approved, posted, skipped
#     scraped_content = Column(Text, nullable=True)
#     generated_reply = Column(Text, nullable=True)
#     is_ghost = Column(Boolean, default=False)
#     created_at = Column(DateTime, default=datetime.datetime.utcnow)
#     updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

# class PlatformConfig(Base):
#     __tablename__ = 'platform_config'
    
#     id = Column(Integer, primary_key=True)
#     domain = Column(String(255), unique=True, nullable=False)
#     ingestion_type = Column(String(100)) # Type1ApiRss, Type2StaticSoup, Type3PlaywrightAuth, Type4LlmVision
#     last_checked = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

# class GuidelinesCache(Base):
#     __tablename__ = 'guidelines_cache'
    
#     id = Column(Integer, primary_key=True)
#     domain = Column(String(255), unique=True, nullable=False)
#     guidelines = Column(Text, nullable=False)
#     updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

# class ListingOpportunity(Base):
#     __tablename__ = 'listing_opportunity'
    
#     id = Column(Integer, primary_key=True)
#     url = Column(String(500), unique=True, nullable=False)
#     domain = Column(String(255))
#     competitors_found = Column(String(500))
#     status = Column(String(50), default='discovered') # discovered, pitch_generated, outreach_sent, completed, skipped
#     generated_pitch = Column(Text, nullable=True)
#     created_at = Column(DateTime, default=datetime.datetime.utcnow)
#     updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

# class BrandProfile(Base):
#     __tablename__ = 'brand_profile'
    
#     id = Column(Integer, primary_key=True)
#     description = Column(Text)
#     logo_url = Column(String(500))
#     usps = Column(Text) # JSON or newline separated USPs
#     updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


# # Database Engine and Sessions setup
# engine = create_engine(f"sqlite:///{config.DB_PATH}", echo=False, connect_args={"check_same_thread": False})
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# def init_db():
#     Base.metadata.create_all(bind=engine)

# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()

# # Block 2 Database Helpers
# def is_duplicate(url: str, current_comments: int = 0) -> bool:
#     """
#     Checks if a thread URL is a duplicate.
#     If comment_count has increased since last checked, it's NOT considered duplicate (returns False).
#     Otherwise, returns True if it already exists in the database.
#     """
#     db = SessionLocal()
#     try:
#         thread = db.query(ThreadMemory).filter(ThreadMemory.url == url).first()
#         if not thread:
#             return False
        
#         # If the number of comments has increased, we should process it again
#         if current_comments > (thread.comment_count or 0):
#             # Update comment count in DB so we don't trigger again unless it increases more
#             thread.comment_count = current_comments
#             thread.status = 'processing'
#             db.commit()
#             return False
            
#         return True
#     finally:
#         db.close()

# def get_platform_config(domain: str) -> str:
#     db = SessionLocal()
#     try:
#         cfg = db.query(PlatformConfig).filter(PlatformConfig.domain == domain).first()
#         return cfg.ingestion_type if cfg else None
#     finally:
#         db.close()

# def set_platform_config(domain: str, ingestion_type: str):
#     db = SessionLocal()
#     try:
#         cfg = db.query(PlatformConfig).filter(PlatformConfig.domain == domain).first()
#         if cfg:
#             cfg.ingestion_type = ingestion_type
#         else:
#             cfg = PlatformConfig(domain=domain, ingestion_type=ingestion_type)
#             db.add(cfg)
#         db.commit()
#     finally:
#         db.close()

# def get_cached_guidelines(domain: str) -> str:
#     """
#     Retrieves cached guidelines if they are within the CACHE_TTL_DAYS window.
#     """
#     db = SessionLocal()
#     try:
#         cache = db.query(GuidelinesCache).filter(GuidelinesCache.domain == domain).first()
#         if not cache:
#             return None
            
#         age = datetime.datetime.utcnow() - cache.updated_at
#         if age.days < config.CACHE_TTL_DAYS:
#             return cache.guidelines
            
#         return None
#     finally:
#         db.close()

# def set_cached_guidelines(domain: str, guidelines: str):
#     db = SessionLocal()
#     try:
#         cache = db.query(GuidelinesCache).filter(GuidelinesCache.domain == domain).first()
#         if cache:
#             cache.guidelines = guidelines
#             cache.updated_at = datetime.datetime.utcnow()
#         else:
#             cache = GuidelinesCache(domain=domain, guidelines=guidelines)
#             db.add(cache)
#         db.commit()
#     finally:
#         db.close()




import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import config

Base = declarative_base()

class ThreadMemory(Base):
    __tablename__ = 'thread_memory'
    
    id = Column(Integer, primary_key=True)
    url = Column(String(500), unique=True, nullable=False)
    platform = Column(String(100))
    comment_count = Column(Integer, default=0)
    status = Column(String(50), default='discovered') # discovered, processing, pending_approval, approved, posted, skipped
    scraped_content = Column(Text, nullable=True)
    generated_reply = Column(Text, nullable=True)
    is_ghost = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class PlatformConfig(Base):
    __tablename__ = 'platform_config'
    
    id = Column(Integer, primary_key=True)
    domain = Column(String(255), unique=True, nullable=False)
    ingestion_type = Column(String(100)) # Type1ApiRss, Type2StaticSoup, Type3PlaywrightAuth, Type4LlmVision
    last_checked = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class GuidelinesCache(Base):
    __tablename__ = 'guidelines_cache'
    
    id = Column(Integer, primary_key=True)
    domain = Column(String(255), unique=True, nullable=False)
    guidelines = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class ListingOpportunity(Base):
    __tablename__ = 'listing_opportunity'
    
    id = Column(Integer, primary_key=True)
    url = Column(String(500), unique=True, nullable=False)
    domain = Column(String(255))
    competitors_found = Column(String(500))
    status = Column(String(50), default='discovered') # discovered, pitch_generated, outreach_sent, completed, skipped
    generated_pitch = Column(Text, nullable=True)
    relevance_score = Column(Integer, default=0)  # 0-100, how relevant this listing is to Gaper's niche
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class ArticleDraft(Base):
    """
    Drafts for the Articles tab's generate -> edit -> improve -> submit
    flow. Separate from ThreadMemory on purpose: Notion articles have no
    target thread URL (target_url is nullable), while Contra drafts are
    always a reply to a specific thread.
    """
    __tablename__ = 'article_draft'

    id = Column(Integer, primary_key=True)
    platform = Column(String(50), nullable=False)  # 'contra' or 'notion'
    topic = Column(String(500))
    target_url = Column(String(500), nullable=True)  # required for contra, null for notion
    title = Column(String(255), nullable=True)  # notion articles only
    content = Column(Text)
    status = Column(String(50), default='draft')  # draft, posted, discarded, failed
    detail = Column(Text, nullable=True)  # last submit result message
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class BrandProfile(Base):
    __tablename__ = 'brand_profile'
    
    id = Column(Integer, primary_key=True)
    description = Column(Text)
    logo_url = Column(String(500))
    usps = Column(Text) # JSON or newline separated USPs
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class PostedBacklink(Base):
    """
    A record of every backlink actually posted live (Contra, Notion, etc).
    Created by adapters._log_backlink() right after a genuinely successful
    post - this is what the dashboard's 'New Backlinks' tab reads from.
    platform_post_id is the platform's own ID for the post (Notion page_id)
    needed to edit/delete the LIVE post later, not just this local row.
    status: 'live' (default), 'edited', 'deleted'.
    """
    __tablename__ = 'posted_backlink'

    id = Column(Integer, primary_key=True)
    platform = Column(String(100), nullable=False)
    target_url = Column(String(500))
    content = Column(Text)
    platform_post_id = Column(String(255), nullable=True)
    status = Column(String(50), default='live')
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class CaseStudy(Base):
    """
    Small local knowledge base Gemini cites from when drafting content -
    this is the 'RAG' referenced in brain.py. Seeded with defaults on
    first run via seed_case_studies_if_empty().
    """
    __tablename__ = 'case_study'

    id = Column(Integer, primary_key=True)
    title = Column(String(255))
    content = Column(Text)
    tags = Column(String(500))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


# Database Engine and Sessions setup
engine = create_engine(f"sqlite:///{config.DB_PATH}", echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Block 2 Database Helpers
def is_duplicate(url: str, current_comments: int = 0) -> bool:
    """
    Checks if a thread URL is a duplicate.
    If comment_count has increased since last checked, it's NOT considered duplicate (returns False).
    Otherwise, returns True if it already exists in the database.
    """
    db = SessionLocal()
    try:
        thread = db.query(ThreadMemory).filter(ThreadMemory.url == url).first()
        if not thread:
            return False
        
        # If the number of comments has increased, we should process it again
        if current_comments > (thread.comment_count or 0):
            # Update comment count in DB so we don't trigger again unless it increases more
            thread.comment_count = current_comments
            thread.status = 'processing'
            db.commit()
            return False
            
        return True
    finally:
        db.close()

def get_platform_config(domain: str) -> str:
    db = SessionLocal()
    try:
        cfg = db.query(PlatformConfig).filter(PlatformConfig.domain == domain).first()
        return cfg.ingestion_type if cfg else None
    finally:
        db.close()

def set_platform_config(domain: str, ingestion_type: str):
    db = SessionLocal()
    try:
        cfg = db.query(PlatformConfig).filter(PlatformConfig.domain == domain).first()
        if cfg:
            cfg.ingestion_type = ingestion_type
        else:
            cfg = PlatformConfig(domain=domain, ingestion_type=ingestion_type)
            db.add(cfg)
        db.commit()
    finally:
        db.close()

# --- Lightweight RAG (Block: case studies) ---
# Keyword-overlap retrieval, no embeddings/external API needed - always
# works, zero extra cost or failure surface. Add more entries here (or
# insert CaseStudy rows directly) as you get real Gaper case studies.
SEED_CASE_STUDIES = [
    {
        "title": "24-hour matching",
        "content": "Gaper matched a Series A startup with a senior backend engineer within 24 hours of the request, versus the 3-4 week average for traditional staffing agencies.",
        "tags": "speed, hiring, matching, fast, 24 hours, startup",
    },
    {
        "title": "AI agent deployment alongside hires",
        "content": "For one client, Gaper paired a placed developer with a custom AI agent handling ticket triage, cutting manual support workload by an estimated 40%.",
        "tags": "ai agent, automation, support, productivity, implementation",
    },
    {
        "title": "No long-term lock-in",
        "content": "Clients can scale their Gaper engagement up or down month to month, unlike typical 6-12 month staffing contracts.",
        "tags": "flexible, contract, scaling, pricing, engagement",
    },
]


def seed_case_studies_if_empty():
    db = SessionLocal()
    try:
        if db.query(CaseStudy).count() == 0:
            for cs in SEED_CASE_STUDIES:
                db.add(CaseStudy(title=cs["title"], content=cs["content"], tags=cs["tags"]))
            db.commit()
    finally:
        db.close()


def retrieve_relevant_case_studies(query_text: str, top_k: int = 3) -> list:
    """
    Simple keyword-overlap RAG: scores every CaseStudy by how many of its
    tags/title words appear in query_text, returns the top_k content
    strings (empty list if nothing matches - brain.py already handles
    that by telling Gemini not to invent facts).
    """
    seed_case_studies_if_empty()
    query_words = set(w.strip(".,!?").lower() for w in (query_text or "").split())
    if not query_words:
        return []

    db = SessionLocal()
    try:
        studies = db.query(CaseStudy).all()
        scored = []
        for cs in studies:
            tag_words = set(t.strip().lower() for t in (cs.tags or "").split(","))
            title_words = set(w.lower() for w in (cs.title or "").split())
            overlap = len(query_words & tag_words) * 2 + len(query_words & title_words)
            if overlap > 0:
                scored.append((overlap, cs.content))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [content for _, content in scored[:top_k]]
    finally:
        db.close()


def get_cached_guidelines(domain: str) -> str:
    """
    Retrieves cached guidelines if they are within the CACHE_TTL_DAYS window.
    """
    db = SessionLocal()
    try:
        cache = db.query(GuidelinesCache).filter(GuidelinesCache.domain == domain).first()
        if not cache:
            return None
            
        age = datetime.datetime.utcnow() - cache.updated_at
        if age.days < config.CACHE_TTL_DAYS:
            return cache.guidelines
            
        return None
    finally:
        db.close()

def set_cached_guidelines(domain: str, guidelines: str):
    db = SessionLocal()
    try:
        cache = db.query(GuidelinesCache).filter(GuidelinesCache.domain == domain).first()
        if cache:
            cache.guidelines = guidelines
            cache.updated_at = datetime.datetime.utcnow()
        else:
            cache = GuidelinesCache(domain=domain, guidelines=guidelines)
            db.add(cache)
        db.commit()
    finally:
        db.close()


# --- PostedBacklink helpers (used by dashboard's New Backlinks tab) ---

def get_posted_backlinks(platform: str = None) -> list:
    db = SessionLocal()
    try:
        q = db.query(PostedBacklink)
        if platform:
            q = q.filter(PostedBacklink.platform == platform)
        return q.order_by(PostedBacklink.created_at.desc()).all()
    finally:
        db.close()


def update_backlink_record(backlink_id: int, content: str = None, status: str = None, note: str = None):
    db = SessionLocal()
    try:
        row = db.query(PostedBacklink).filter(PostedBacklink.id == backlink_id).first()
        if not row:
            return None
        if content is not None:
            row.content = content
        if status is not None:
            row.status = status
        if note is not None:
            row.note = note
        db.commit()
        return row.id
    finally:
        db.close()


# --- ArticleDraft helpers (Articles tab: generate/edit/improve/submit) ---

def create_article_draft(platform: str, topic: str, content: str, target_url: str = None, title: str = None) -> int:
    db = SessionLocal()
    try:
        draft = ArticleDraft(platform=platform, topic=topic, content=content,
                              target_url=target_url, title=title, status='draft')
        db.add(draft)
        db.commit()
        return draft.id
    finally:
        db.close()


def get_article_drafts(status: str = None) -> list:
    db = SessionLocal()
    try:
        q = db.query(ArticleDraft)
        if status:
            q = q.filter(ArticleDraft.status == status)
        return q.order_by(ArticleDraft.created_at.desc()).all()
    finally:
        db.close()


def get_article_draft(draft_id: int):
    db = SessionLocal()
    try:
        return db.query(ArticleDraft).filter(ArticleDraft.id == draft_id).first()
    finally:
        db.close()


def update_article_draft(draft_id: int, content: str = None, title: str = None, status: str = None, detail: str = None):
    db = SessionLocal()
    try:
        d = db.query(ArticleDraft).filter(ArticleDraft.id == draft_id).first()
        if not d:
            return None
        if content is not None:
            d.content = content
        if title is not None:
            d.title = title
        if status is not None:
            d.status = status
        if detail is not None:
            d.detail = detail
        db.commit()
        return d.id
    finally:
        db.close()


def delete_article_draft(draft_id: int):
    db = SessionLocal()
    try:
        d = db.query(ArticleDraft).filter(ArticleDraft.id == draft_id).first()
        if d:
            db.delete(d)
            db.commit()
            return True
        return False
    finally:
        db.close()