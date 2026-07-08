import os
import uuid
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database import init_db, get_db, DATABASE_DIR, Session as DBSession, Participant as DBParticipant, AudioSample as DBAudioSample, Generation as DBGeneration
from safety import check_content_policy, add_watermark_to_wav
from providers import MockVoiceProvider, BrowserTTSProvider

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice_cloning_backend")

app = FastAPI(title="Consent-Based Voice Cloning Demo API")

# Allow CORS for Next.js dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup data storage subdirectories
CONSENT_DIR = os.path.join(DATABASE_DIR, "consent_recordings")
SAMPLES_DIR = os.path.join(DATABASE_DIR, "audio_samples")
GENERATIONS_DIR = os.path.join(DATABASE_DIR, "generations")

for directory in [CONSENT_DIR, SAMPLES_DIR, GENERATIONS_DIR]:
    os.makedirs(directory, exist_ok=True)

# Mount files under /static for easy frontend playback
app.mount("/static", StaticFiles(directory=DATABASE_DIR), name="static")

# Lifespan background task runner
cleanup_task = None

@app.on_event("startup")
async def startup_event():
    global cleanup_task
    await init_db()
    cleanup_task = asyncio.create_task(cleanup_expired_data_loop())
    logger.info("Database initialized and background TTL cleanup task started.")

@app.on_event("shutdown")
async def shutdown_event():
    if cleanup_task:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        logger.info("Background TTL cleanup task stopped.")

async def cleanup_expired_data_loop():
    while True:
        try:
            await cleanup_expired_data()
        except Exception as e:
            logger.error(f"Error during TTL cleanup: {e}", exc_info=True)
        await asyncio.sleep(15)  # Check every 15 seconds for accuracy

async def cleanup_expired_data():
    now = datetime.utcnow()
    from database import async_session
    async with async_session() as db:
        # 1. Clean ended or expired sessions
        stmt = select(DBSession).where((DBSession.expires_at < now) | (DBSession.ended_at.isnot(None)))
        result = await db.execute(stmt)
        sessions = result.scalars().all()
        
        for sess in sessions:
            # Select related participants
            p_stmt = select(DBParticipant).where(DBParticipant.session_id == sess.id)
            p_res = await db.execute(p_stmt)
            participants = p_res.scalars().all()
            
            for p in participants:
                # Delete consent recording
                if p.consent_recording_path and os.path.exists(p.consent_recording_path):
                    try:
                        os.remove(p.consent_recording_path)
                    except OSError:
                        pass
                
                # Delete audio samples
                as_stmt = select(DBAudioSample).where(DBAudioSample.participant_id == p.id)
                as_res = await db.execute(as_stmt)
                samples = as_res.scalars().all()
                for s in samples:
                    if s.file_path and os.path.exists(s.file_path):
                        try:
                            os.remove(s.file_path)
                        except OSError:
                            pass
            
            # Delete generations
            g_stmt = select(DBGeneration).where(DBGeneration.session_id == sess.id)
            g_res = await db.execute(g_stmt)
            generations = g_res.scalars().all()
            for g in generations:
                if g.output_file_path:
                    filename = os.path.basename(g.output_file_path)
                    filepath = os.path.join(GENERATIONS_DIR, filename)
                    if os.path.exists(filepath):
                        try:
                            os.remove(filepath)
                        except OSError:
                            pass
                            
            # Delete session from DB (cascades to participants, audio_samples, generations)
            await db.delete(sess)
        
        # 2. Clean individual expired samples
        as_stmt = select(DBAudioSample).where(DBAudioSample.expires_at < now)
        as_res = await db.execute(as_stmt)
        expired_samples = as_res.scalars().all()
        for s in expired_samples:
            if s.file_path and os.path.exists(s.file_path):
                try:
                    os.remove(s.file_path)
                except OSError:
                    pass
            await db.delete(s)
            
        # 3. Clean individual expired generations
        g_stmt = select(DBGeneration).where(DBGeneration.expires_at < now)
        g_res = await db.execute(g_stmt)
        expired_gens = g_res.scalars().all()
        for g in expired_gens:
            if g.output_file_path:
                filename = os.path.basename(g.output_file_path)
                filepath = os.path.join(GENERATIONS_DIR, filename)
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                    except OSError:
                        pass
            await db.delete(g)
            
        await db.commit()

# --- Pydantic Schemas ---
class SessionCreate(BaseModel):
    retention_ttl_seconds: int = Field(default=86400, ge=1)

class SessionResponse(BaseModel):
    id: str
    retention_ttl_seconds: int
    expires_at: datetime
    created_at: datetime
    ended_at: Optional[datetime] = None

class ParticipantCreate(BaseModel):
    display_name: str

class ParticipantResponse(BaseModel):
    id: str
    session_id: str
    display_name: str
    participant_token: str
    consent_status: str
    consent_timestamp: Optional[datetime] = None
    revoke_timestamp: Optional[datetime] = None
    has_audio_sample: bool = False
    capture_session_id: Optional[str] = None

class SessionDetailsResponse(BaseModel):
    id: str
    retention_ttl_seconds: int
    expires_at: datetime
    created_at: datetime
    ended_at: Optional[datetime] = None
    participants: List[ParticipantResponse] = []
    generations: List[dict] = []

class ConsentSubmit(BaseModel):
    agree: bool

class GenerateVoiceRequest(BaseModel):
    session_id: str
    participant_id: str
    input_text: str
    provider: str  # mock or browser_tts
    requested_by: str = "host"

# --- Endpoints ---

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.post("/sessions", response_model=SessionResponse)
async def create_session(payload: SessionCreate, db: AsyncSession = Depends(get_db)):
    session_id = str(uuid.uuid4())
    now = datetime.utcnow()
    expires_at = now + timedelta(seconds=payload.retention_ttl_seconds)
    
    sess = DBSession(
        id=session_id,
        retention_ttl_seconds=payload.retention_ttl_seconds,
        expires_at=expires_at,
        created_at=now
    )
    db.add(sess)
    await db.commit()
    await db.refresh(sess)
    return sess

@app.get("/sessions/{session_id}", response_model=SessionDetailsResponse)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    # Verify session active
    sess_stmt = select(DBSession).where(DBSession.id == session_id)
    res = await db.execute(sess_stmt)
    sess = res.scalar_one_or_none()
    
    if not sess or sess.ended_at or sess.expires_at < datetime.utcnow():
        raise HTTPException(status_code=404, detail="Session not found or expired")
        
    # Get participants
    p_stmt = select(DBParticipant).where(DBParticipant.session_id == session_id)
    p_res = await db.execute(p_stmt)
    participants = p_res.scalars().all()
    
    # Map participants to include whether they have an audio sample
    mapped_participants = []
    for p in participants:
        as_stmt = select(DBAudioSample).where(DBAudioSample.participant_id == p.id, DBAudioSample.deleted_at.is_(None))
        as_res = await db.execute(as_stmt)
        sample = as_res.scalar_one_or_none()
        
        mapped_participants.append(
            ParticipantResponse(
                id=p.id,
                session_id=p.session_id,
                display_name=p.display_name,
                participant_token=p.participant_token,
                consent_status=p.consent_status,
                consent_timestamp=p.consent_timestamp,
                revoke_timestamp=p.revoke_timestamp,
                has_audio_sample=sample is not None,
                capture_session_id=p.consent_capture_session_id
            )
        )
        
    # Get generations
    g_stmt = select(DBGeneration).where(DBGeneration.session_id == session_id).order_by(DBGeneration.created_at.desc())
    g_res = await db.execute(g_stmt)
    generations = g_res.scalars().all()
    
    mapped_generations = [
        {
            "id": g.id,
            "participant_id": g.participant_id,
            "input_text": g.input_text,
            "output_file_path": g.output_file_path,
            "safety_label": g.safety_label,
            "blocked": g.blocked,
            "blocked_reason": g.blocked_reason,
            "requested_by": g.requested_by,
            "created_at": g.created_at
        } for g in generations
    ]
    
    return SessionDetailsResponse(
        id=sess.id,
        retention_ttl_seconds=sess.retention_ttl_seconds,
        expires_at=sess.expires_at,
        created_at=sess.created_at,
        ended_at=sess.ended_at,
        participants=mapped_participants,
        generations=mapped_generations
    )

@app.delete("/sessions/{session_id}")
async def end_session(session_id: str, db: AsyncSession = Depends(get_db)):
    sess_stmt = select(DBSession).where(DBSession.id == session_id)
    res = await db.execute(sess_stmt)
    sess = res.scalar_one_or_none()
    
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # Mark ended and trigger file purge via cleanup
    sess.ended_at = datetime.utcnow()
    await db.commit()
    await cleanup_expired_data()  # Run cleanup synchronously to immediately purge data
    return {"status": "success", "message": "Session ended and data purged successfully"}

@app.post("/sessions/{session_id}/participants", response_model=ParticipantResponse)
async def add_participant(session_id: str, payload: ParticipantCreate, db: AsyncSession = Depends(get_db)):
    sess_stmt = select(DBSession).where(DBSession.id == session_id)
    res = await db.execute(sess_stmt)
    sess = res.scalar_one_or_none()
    
    if not sess or sess.ended_at or sess.expires_at < datetime.utcnow():
        raise HTTPException(status_code=404, detail="Session not found or expired")
        
    part_id = str(uuid.uuid4())
    token = str(uuid.uuid4())
    
    part = DBParticipant(
        id=part_id,
        session_id=session_id,
        display_name=payload.display_name,
        participant_token=token,
        consent_status="pending",
        created_at=datetime.utcnow()
    )
    db.add(part)
    await db.commit()
    await db.refresh(part)
    return ParticipantResponse(
        id=part.id,
        session_id=part.session_id,
        display_name=part.display_name,
        participant_token=part.participant_token,
        consent_status=part.consent_status,
        has_audio_sample=False
    )

@app.get("/participants/{participant_id}", response_model=ParticipantResponse)
async def get_participant(participant_id: str, db: AsyncSession = Depends(get_db)):
    p_stmt = select(DBParticipant).where(DBParticipant.id == participant_id)
    res = await db.execute(p_stmt)
    p = res.scalar_one_or_none()
    
    if not p:
        raise HTTPException(status_code=404, detail="Participant not found")
        
    # Check if session ended/expired
    sess_stmt = select(DBSession).where(DBSession.id == p.session_id)
    s_res = await db.execute(sess_stmt)
    sess = s_res.scalar_one_or_none()
    if not sess or sess.ended_at or sess.expires_at < datetime.utcnow():
        raise HTTPException(status_code=404, detail="Session ended or expired")
        
    as_stmt = select(DBAudioSample).where(DBAudioSample.participant_id == p.id, DBAudioSample.deleted_at.is_(None))
    as_res = await db.execute(as_stmt)
    sample = as_res.scalar_one_or_none()
    
    return ParticipantResponse(
        id=p.id,
        session_id=p.session_id,
        display_name=p.display_name,
        participant_token=p.participant_token,
        consent_status=p.consent_status,
        consent_timestamp=p.consent_timestamp,
        revoke_timestamp=p.revoke_timestamp,
        has_audio_sample=sample is not None,
        capture_session_id=p.consent_capture_session_id
    )

@app.post("/participants/{participant_id}/consent")
async def give_consent(participant_id: str, payload: ConsentSubmit, db: AsyncSession = Depends(get_db)):
    p_stmt = select(DBParticipant).where(DBParticipant.id == participant_id)
    res = await db.execute(p_stmt)
    p = res.scalar_one_or_none()
    
    if not p:
        raise HTTPException(status_code=404, detail="Participant not found")
        
    if payload.agree:
        p.consent_status = "consented"
        p.consent_timestamp = datetime.utcnow()
        p.revoke_timestamp = None
    else:
        p.consent_status = "pending"
        p.consent_timestamp = None
        
    await db.commit()
    return {"status": "success", "consent_status": p.consent_status}

@app.post("/participants/{participant_id}/revoke-consent")
async def revoke_consent(participant_id: str, db: AsyncSession = Depends(get_db)):
    p_stmt = select(DBParticipant).where(DBParticipant.id == participant_id)
    res = await db.execute(p_stmt)
    p = res.scalar_one_or_none()
    
    if not p:
        raise HTTPException(status_code=404, detail="Participant not found")
        
    p.consent_status = "revoked"
    p.revoke_timestamp = datetime.utcnow()
    
    # Instantly delete audio samples on disk & DB
    as_stmt = select(DBAudioSample).where(DBAudioSample.participant_id == p.id)
    as_res = await db.execute(as_stmt)
    samples = as_res.scalars().all()
    for s in samples:
        if s.file_path and os.path.exists(s.file_path):
            try:
                os.remove(s.file_path)
            except OSError:
                pass
        await db.delete(s)
        
    # Delete consent recording file
    if p.consent_recording_path and os.path.exists(p.consent_recording_path):
        try:
            os.remove(p.consent_recording_path)
        except OSError:
            pass
    p.consent_recording_path = None
    p.consent_capture_session_id = None
    
    await db.commit()
    return {"status": "success", "message": "Consent revoked and voice samples deleted"}

@app.post("/participants/{participant_id}/consent-recording")
async def upload_consent_recording(
    participant_id: str,
    file: UploadFile = File(...),
    capture_session_id: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    p_stmt = select(DBParticipant).where(DBParticipant.id == participant_id)
    res = await db.execute(p_stmt)
    p = res.scalar_one_or_none()
    
    if not p:
        raise HTTPException(status_code=404, detail="Participant not found")
        
    if p.consent_status != "consented":
        raise HTTPException(status_code=400, detail="Consent must be agreed to before uploading recording")
        
    # Store consent recording
    file_ext = os.path.splitext(file.filename)[1] or ".webm"
    file_name = f"consent_{p.id}_{capture_session_id}{file_ext}"
    dest_path = os.path.join(CONSENT_DIR, file_name)
    
    with open(dest_path, "wb") as buffer:
        shutil = await asyncio.to_thread(write_upload_file, file, buffer)
        
    p.consent_capture_session_id = capture_session_id
    p.consent_recording_path = dest_path
    await db.commit()
    
    return {"status": "success", "consent_capture_session_id": capture_session_id}

@app.post("/participants/{participant_id}/audio-sample")
async def upload_audio_sample(
    participant_id: str,
    file: UploadFile = File(...),
    capture_session_id: str = Form(...),
    source: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    # Enforce NO generic upload: source must be live_recording, capture_session_id must match consent
    if source != "live_recording":
        raise HTTPException(status_code=400, detail="Audio samples must only be recorded live in the browser.")
        
    p_stmt = select(DBParticipant).where(DBParticipant.id == participant_id)
    res = await db.execute(p_stmt)
    p = res.scalar_one_or_none()
    
    if not p:
        raise HTTPException(status_code=404, detail="Participant not found")
        
    if p.consent_status != "consented":
        raise HTTPException(status_code=400, detail="Voice generation requires active consent")
        
    if p.consent_capture_session_id != capture_session_id:
        raise HTTPException(status_code=400, detail="Audio sample session ID does not match consent recording session ID.")
        
    # Find session expires
    sess_stmt = select(DBSession).where(DBSession.id == p.session_id)
    s_res = await db.execute(sess_stmt)
    sess = s_res.scalar_one_or_none()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # Delete any existing active audio samples first
    as_del_stmt = select(DBAudioSample).where(DBAudioSample.participant_id == p.id)
    as_del_res = await db.execute(as_del_stmt)
    old_samples = as_del_res.scalars().all()
    for osamp in old_samples:
        if osamp.file_path and os.path.exists(osamp.file_path):
            try:
                os.remove(osamp.file_path)
            except OSError:
                pass
        await db.delete(osamp)
        
    file_ext = os.path.splitext(file.filename)[1] or ".webm"
    file_name = f"sample_{p.id}_{capture_session_id}{file_ext}"
    dest_path = os.path.join(SAMPLES_DIR, file_name)
    
    with open(dest_path, "wb") as buffer:
        await asyncio.to_thread(write_upload_file, file, buffer)
        
    sample_id = str(uuid.uuid4())
    now = datetime.utcnow()
    expires_at = now + timedelta(seconds=sess.retention_ttl_seconds)
    
    audio_sample = DBAudioSample(
        id=sample_id,
        participant_id=p.id,
        capture_session_id=capture_session_id,
        source="live_recording",
        file_path=dest_path,
        duration_seconds=10.0,  # approximate duration
        created_at=now,
        expires_at=expires_at
    )
    db.add(audio_sample)
    await db.commit()
    
    return {"status": "success", "audio_sample_id": sample_id}

@app.delete("/participants/{participant_id}/audio-sample")
async def delete_audio_sample(participant_id: str, db: AsyncSession = Depends(get_db)):
    as_stmt = select(DBAudioSample).where(DBAudioSample.participant_id == participant_id)
    res = await db.execute(as_stmt)
    samples = res.scalars().all()
    
    if not samples:
        raise HTTPException(status_code=404, detail="No audio sample found for this participant")
        
    for s in samples:
        if s.file_path and os.path.exists(s.file_path):
            try:
                os.remove(s.file_path)
            except OSError:
                pass
        await db.delete(s)
        
    await db.commit()
    return {"status": "success", "message": "Audio sample deleted"}

@app.post("/generate-voice")
async def generate_voice(payload: GenerateVoiceRequest, db: AsyncSession = Depends(get_db)):
    # 1. Verify session active
    sess_stmt = select(DBSession).where(DBSession.id == payload.session_id)
    s_res = await db.execute(sess_stmt)
    sess = s_res.scalar_one_or_none()
    if not sess or sess.ended_at or sess.expires_at < datetime.utcnow():
        raise HTTPException(status_code=404, detail="Session not found or expired")
        
    # 2. Verify participant exists
    p_stmt = select(DBParticipant).where(DBParticipant.id == payload.participant_id)
    p_res = await db.execute(p_stmt)
    p = p_res.scalar_one_or_none()
    if not p or p.session_id != payload.session_id:
        raise HTTPException(status_code=404, detail="Participant not found")
        
    # 3. Check consent
    if p.consent_status != "consented":
        # Log blocked attempt
        gen_id = str(uuid.uuid4())
        blocked_reason = "Blocked: Participant has not provided or has revoked consent."
        gen_log = DBGeneration(
            id=gen_id,
            session_id=payload.session_id,
            participant_id=payload.participant_id,
            input_text=payload.input_text,
            safety_label="blocked",
            blocked=True,
            blocked_reason=blocked_reason,
            requested_by=payload.requested_by,
            created_at=datetime.utcnow(),
            expires_at=sess.expires_at
        )
        db.add(gen_log)
        await db.commit()
        raise HTTPException(status_code=400, detail=blocked_reason)
        
    # 4. Check live audio sample exists
    as_stmt = select(DBAudioSample).where(DBAudioSample.participant_id == p.id, DBAudioSample.deleted_at.is_(None))
    as_res = await db.execute(as_stmt)
    sample = as_res.scalar_one_or_none()
    if not sample:
        # Log blocked attempt
        gen_id = str(uuid.uuid4())
        blocked_reason = "Blocked: Participant has no verified live-recorded audio sample."
        gen_log = DBGeneration(
            id=gen_id,
            session_id=payload.session_id,
            participant_id=payload.participant_id,
            input_text=payload.input_text,
            safety_label="blocked",
            blocked=True,
            blocked_reason=blocked_reason,
            requested_by=payload.requested_by,
            created_at=datetime.utcnow(),
            expires_at=sess.expires_at
        )
        db.add(gen_log)
        await db.commit()
        raise HTTPException(status_code=400, detail=blocked_reason)
        
    # 5. Check capture session matches
    if p.consent_capture_session_id != sample.capture_session_id:
        # Log blocked attempt
        gen_id = str(uuid.uuid4())
        blocked_reason = "Blocked: Audio sample session ID does not match consent recording session ID."
        gen_log = DBGeneration(
            id=gen_id,
            session_id=payload.session_id,
            participant_id=payload.participant_id,
            input_text=payload.input_text,
            safety_label="blocked",
            blocked=True,
            blocked_reason=blocked_reason,
            requested_by=payload.requested_by,
            created_at=datetime.utcnow(),
            expires_at=sess.expires_at
        )
        db.add(gen_log)
        await db.commit()
        raise HTTPException(status_code=400, detail=blocked_reason)
        
    # 6. Content filter check
    # Gather all participant names in this session to check impersonation
    all_p_stmt = select(DBParticipant.display_name).where(DBParticipant.session_id == payload.session_id)
    all_p_res = await db.execute(all_p_stmt)
    all_names = list(all_p_res.scalars().all())
    
    is_blocked, reason = check_content_policy(payload.input_text, p.display_name, all_names)
    if is_blocked:
        # Log blocked attempt
        gen_id = str(uuid.uuid4())
        gen_log = DBGeneration(
            id=gen_id,
            session_id=payload.session_id,
            participant_id=payload.participant_id,
            input_text=payload.input_text,
            safety_label="blocked",
            blocked=True,
            blocked_reason=reason,
            requested_by=payload.requested_by,
            created_at=datetime.utcnow(),
            expires_at=sess.expires_at
        )
        db.add(gen_log)
        await db.commit()
        raise HTTPException(status_code=400, detail=reason)
        
    # 7. Safety checks passed -> Generate Audio
    gen_id = str(uuid.uuid4())
    
    if payload.provider == "browser_tts":
        gen_log = DBGeneration(
            id=gen_id,
            session_id=payload.session_id,
            participant_id=payload.participant_id,
            input_text=payload.input_text,
            safety_label="safe",
            blocked=False,
            requested_by=payload.requested_by,
            created_at=datetime.utcnow(),
            expires_at=sess.expires_at
        )
        db.add(gen_log)
        await db.commit()
        return {
            "status": "success",
            "provider": "browser_tts",
            "text": f"Fallback demo audio. This does not clone the participant's voice. Spoken script: {payload.input_text}"
        }
        
    elif payload.provider == "mock":
        provider_impl = MockVoiceProvider()
        raw_audio = await provider_impl.generate(payload.input_text, sample.file_path)
        
        # Apply watermarking wrapper
        watermarked_audio = add_watermark_to_wav(raw_audio)
        
        file_name = f"gen_{gen_id}.wav"
        dest_path = os.path.join(GENERATIONS_DIR, file_name)
        
        with open(dest_path, "wb") as f_out:
            f_out.write(watermarked_audio)
            
        gen_log = DBGeneration(
            id=gen_id,
            session_id=payload.session_id,
            participant_id=payload.participant_id,
            input_text=payload.input_text,
            output_file_path=f"/static/generations/{file_name}",
            safety_label="safe",
            blocked=False,
            requested_by=payload.requested_by,
            created_at=datetime.utcnow(),
            expires_at=sess.expires_at
        )
        db.add(gen_log)
        await db.commit()
        
        return {
            "status": "success",
            "provider": "mock",
            "audio_url": f"/static/generations/{file_name}"
        }
        
    else:
        raise HTTPException(status_code=400, detail="Invalid voice provider option selected.")

def write_upload_file(file: UploadFile, buffer):
    # Helper to write files block-by-block synchronously
    while content := file.file.read(1024 * 1024):
        buffer.write(content)
