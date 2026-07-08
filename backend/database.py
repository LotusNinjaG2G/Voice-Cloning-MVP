import os
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base, relationship

DATABASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATABASE_DIR, exist_ok=True)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = f"sqlite+aiosqlite:///{os.path.join(DATABASE_DIR, 'voice_cloning.db')}"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

Base = declarative_base()

class Session(Base):
    __tablename__ = 'sessions'
    
    id = Column(String, primary_key=True)
    retention_ttl_seconds = Column(Integer, default=86400)
    expires_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    participants = relationship("Participant", back_populates="session", cascade="all, delete-orphan")
    generations = relationship("Generation", back_populates="session", cascade="all, delete-orphan")

class Participant(Base):
    __tablename__ = 'participants'
    
    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey('sessions.id'), nullable=False)
    display_name = Column(String, nullable=False)
    participant_token = Column(String, nullable=False)
    consent_status = Column(String, default='pending')  # pending, consented, revoked
    consent_timestamp = Column(DateTime, nullable=True)
    revoke_timestamp = Column(DateTime, nullable=True)
    
    # Track the consent recording
    consent_capture_session_id = Column(String, nullable=True)
    consent_recording_path = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    session = relationship("Session", back_populates="participants")
    audio_samples = relationship("AudioSample", back_populates="participant", cascade="all, delete-orphan")
    generations = relationship("Generation", back_populates="participant", cascade="all, delete-orphan")

class AudioSample(Base):
    __tablename__ = 'audio_samples'
    
    id = Column(String, primary_key=True)
    participant_id = Column(String, ForeignKey('participants.id'), nullable=False)
    capture_session_id = Column(String, nullable=False)
    source = Column(String, default='live_recording')  # must always be live_recording
    file_path = Column(String, nullable=False)
    duration_seconds = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    
    participant = relationship("Participant", back_populates="audio_samples")

class Generation(Base):
    __tablename__ = 'generations'
    
    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey('sessions.id'), nullable=False)
    participant_id = Column(String, ForeignKey('participants.id'), nullable=False)
    input_text = Column(String, nullable=False)
    output_file_path = Column(String, nullable=True)
    safety_label = Column(String, nullable=False)  # safe, blocked
    blocked = Column(Boolean, default=False)
    blocked_reason = Column(String, nullable=True)
    requested_by = Column(String, default='host')
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    
    session = relationship("Session", back_populates="generations")
    participant = relationship("Participant", back_populates="generations")

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
