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
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class BrandProfile(Base):
    __tablename__ = 'brand_profile'
    
    id = Column(Integer, primary_key=True)
    description = Column(Text)
    logo_url = Column(String(500))
    usps = Column(Text) # JSON or newline separated USPs
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


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
