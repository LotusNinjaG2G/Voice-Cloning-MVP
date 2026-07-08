import os
import shutil
import pytest
import pytest_asyncio
import asyncio
import io
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Use a separate test database
TEST_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
TEST_DB_PATH = os.path.join(TEST_DB_DIR, "test_voice_cloning.db")
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"

# Import app components
from database import Base, engine, async_session, get_db, Session as DBSession, Participant as DBParticipant, AudioSample as DBAudioSample, Generation as DBGeneration
from main import app, cleanup_expired_data

test_engine = engine
test_async_session = async_session

# Setup test client
client = TestClient(app)

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    # Make sure database directory exists
    os.makedirs(TEST_DB_DIR, exist_ok=True)
    # Create test database tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Clean up test database tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    # Release connection pool resources
    await test_engine.dispose()
    # Delete test database file and static files if exist
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except OSError:
            pass
            
    # Clean test dirs
    for subdir in ["consent_recordings", "audio_samples", "generations"]:
        dirpath = os.path.join(TEST_DB_DIR, subdir)
        if os.path.exists(dirpath):
            for file in os.listdir(dirpath):
                if file.startswith("consent_test") or file.startswith("sample_test") or file.startswith("gen_test"):
                    try:
                        os.remove(os.path.join(dirpath, file))
                    except OSError:
                        pass

@pytest.mark.asyncio
async def test_generation_blocked_when_consent_missing():
    # 1. Create a session
    resp = client.post("/sessions", json={"retention_ttl_seconds": 3600})
    assert resp.status_code == 200
    session_id = resp.json()["id"]
    
    # 2. Add a participant (default status: pending)
    resp = client.post(f"/sessions/{session_id}/participants", json={"display_name": "TestUser"})
    assert resp.status_code == 200
    participant_id = resp.json()["id"]
    
    # 3. Attempt to generate voice (should be blocked because consent is missing)
    resp = client.post("/generate-voice", json={
        "session_id": session_id,
        "participant_id": participant_id,
        "input_text": "Hello this is a safe sentence",
        "provider": "mock"
    })
    assert resp.status_code == 400
    assert "Blocked: Participant has not provided or has revoked consent" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_generation_blocked_after_consent_revoked():
    # 1. Create session
    sess_id = client.post("/sessions", json={"retention_ttl_seconds": 3600}).json()["id"]
    # 2. Add participant
    p_resp = client.post(f"/sessions/{sess_id}/participants", json={"display_name": "TestUser"}).json()
    p_id = p_resp["id"]
    
    # 3. Agree to consent
    client.post(f"/participants/{p_id}/consent", json={"agree": True})
    
    # 4. Upload consent recording
    capture_id = "test-capture-123"
    consent_file = io.BytesIO(b"RIFF....WAVEfmt...")
    client.post(
        f"/participants/{p_id}/consent-recording",
        data={"capture_session_id": capture_id},
        files={"file": ("consent.wav", consent_file, "audio/wav")}
    )
    
    # 5. Upload audio sample
    sample_file = io.BytesIO(b"RIFF....WAVEfmt...")
    client.post(
        f"/participants/{p_id}/audio-sample",
        data={"capture_session_id": capture_id, "source": "live_recording"},
        files={"file": ("sample.wav", sample_file, "audio/wav")}
    )
    
    # 6. Revoke consent
    client.post(f"/participants/{p_id}/revoke-consent")
    
    # 7. Attempt voice generation (should fail)
    resp = client.post("/generate-voice", json={
        "session_id": sess_id,
        "participant_id": p_id,
        "input_text": "Hello this is a safe sentence",
        "provider": "mock"
    })
    assert resp.status_code == 400
    assert "Blocked: Participant has not provided or has revoked consent" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_generation_blocked_if_no_audio_sample():
    # 1. Create session and participant
    sess_id = client.post("/sessions", json={"retention_ttl_seconds": 3600}).json()["id"]
    p_id = client.post(f"/sessions/{sess_id}/participants", json={"display_name": "TestUser"}).json()["id"]
    
    # 2. Give consent but DO NOT upload audio sample
    client.post(f"/participants/{p_id}/consent", json={"agree": True})
    
    # 3. Attempt generation (fails because no audio sample exists)
    resp = client.post("/generate-voice", json={
        "session_id": sess_id,
        "participant_id": p_id,
        "input_text": "Hello this is a safe sentence",
        "provider": "mock"
    })
    assert resp.status_code == 400
    assert "Blocked: Participant has no verified live-recorded audio sample" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_audio_sample_rejected_if_capture_session_id_mismatch():
    # 1. Create session and participant
    sess_id = client.post("/sessions", json={"retention_ttl_seconds": 3600}).json()["id"]
    p_id = client.post(f"/sessions/{sess_id}/participants", json={"display_name": "TestUser"}).json()["id"]
    
    # 2. Consent
    client.post(f"/participants/{p_id}/consent", json={"agree": True})
    
    # 3. Upload consent recording with capture_session_id = "session-A"
    consent_file = io.BytesIO(b"RIFF....WAVEfmt...")
    client.post(
        f"/participants/{p_id}/consent-recording",
        data={"capture_session_id": "session-A"},
        files={"file": ("consent.wav", consent_file, "audio/wav")}
    )
    
    # 4. Upload audio sample with capture_session_id = "session-B" (should be rejected)
    sample_file = io.BytesIO(b"RIFF....WAVEfmt...")
    resp = client.post(
        f"/participants/{p_id}/audio-sample",
        data={"capture_session_id": "session-B", "source": "live_recording"},
        files={"file": ("sample.wav", sample_file, "audio/wav")}
    )
    assert resp.status_code == 400
    assert "Audio sample session ID does not match consent recording session ID" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_no_generic_upload_endpoint_for_audio_samples():
    # 1. Create session and participant
    sess_id = client.post("/sessions", json={"retention_ttl_seconds": 3600}).json()["id"]
    p_id = client.post(f"/sessions/{sess_id}/participants", json={"display_name": "TestUser"}).json()["id"]
    client.post(f"/participants/{p_id}/consent", json={"agree": True})
    
    # Upload consent recording
    consent_file = io.BytesIO(b"RIFF....WAVEfmt...")
    client.post(
        f"/participants/{p_id}/consent-recording",
        data={"capture_session_id": "session-A"},
        files={"file": ("consent.wav", consent_file, "audio/wav")}
    )
    
    # 2. Try uploading audio with source = "upload" (should be rejected)
    sample_file = io.BytesIO(b"RIFF....WAVEfmt...")
    resp = client.post(
        f"/participants/{p_id}/audio-sample",
        data={"capture_session_id": "session-A", "source": "upload"},
        files={"file": ("sample.wav", sample_file, "audio/wav")}
    )
    assert resp.status_code == 400
    assert "Audio samples must only be recorded live in the browser" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_flagged_input_text_is_blocked_and_logged():
    # 1. Create session and participant
    sess_id = client.post("/sessions", json={"retention_ttl_seconds": 3600}).json()["id"]
    p_id = client.post(f"/sessions/{sess_id}/participants", json={"display_name": "TestUser"}).json()["id"]
    client.post(f"/participants/{p_id}/consent", json={"agree": True})
    
    # Consent recording
    consent_file = io.BytesIO(b"RIFF....WAVEfmt...")
    client.post(
        f"/participants/{p_id}/consent-recording",
        data={"capture_session_id": "session-A"},
        files={"file": ("consent.wav", consent_file, "audio/wav")}
    )
    
    # Audio sample
    sample_file = io.BytesIO(b"RIFF....WAVEfmt...")
    client.post(
        f"/participants/{p_id}/audio-sample",
        data={"capture_session_id": "session-A", "source": "live_recording"},
        files={"file": ("sample.wav", sample_file, "audio/wav")}
    )
    
    # 2. Attempt to generate voice with financial authorization scam text
    unsafe_text = "Authorize payment of $5000 right now"
    resp = client.post("/generate-voice", json={
        "session_id": sess_id,
        "participant_id": p_id,
        "input_text": unsafe_text,
        "provider": "mock"
    })
    assert resp.status_code == 400
    assert "Blocked" in resp.json()["detail"]
    
    # 3. Check that it was logged as blocked in database
    async with test_async_session() as db:
        g_stmt = select(DBGeneration).where(DBGeneration.session_id == sess_id)
        res = await db.execute(g_stmt)
        gens = res.scalars().all()
        assert len(gens) == 1
        assert gens[0].blocked is True
        assert "financial authorization" in gens[0].blocked_reason.lower()

@pytest.mark.asyncio
async def test_data_purged_on_ttl_expiry():
    # 1. Create a session with 1 second TTL
    sess_resp = client.post("/sessions", json={"retention_ttl_seconds": 1}).json()
    sess_id = sess_resp["id"]
    
    p_id = client.post(f"/sessions/{sess_id}/participants", json={"display_name": "TestUser"}).json()["id"]
    client.post(f"/participants/{p_id}/consent", json={"agree": True})
    
    # Consent recording
    consent_file = io.BytesIO(b"RIFF....WAVEfmt...")
    client.post(
        f"/participants/{p_id}/consent-recording",
        data={"capture_session_id": "session-A"},
        files={"file": ("consent.wav", consent_file, "audio/wav")}
    )
    
    # Audio sample
    sample_file = io.BytesIO(b"RIFF....WAVEfmt...")
    client.post(
        f"/participants/{p_id}/audio-sample",
        data={"capture_session_id": "session-A", "source": "live_recording"},
        files={"file": ("sample.wav", sample_file, "audio/wav")}
    )
    
    # Wait 2 seconds for TTL to expire
    await asyncio.sleep(2)
    
    # Call the cleanup function manually
    await cleanup_expired_data()
    
    # Verify DB records are gone
    async with test_async_session() as db:
        sess_stmt = select(DBSession).where(DBSession.id == sess_id)
        res = await db.execute(sess_stmt)
        assert res.scalar_one_or_none() is None
        
        p_stmt = select(DBParticipant).where(DBParticipant.id == p_id)
        res = await db.execute(p_stmt)
        assert res.scalar_one_or_none() is None

@pytest.mark.asyncio
async def test_data_purged_when_session_ended():
    # 1. Create session and participant
    sess_id = client.post("/sessions", json={"retention_ttl_seconds": 3600}).json()["id"]
    p_id = client.post(f"/sessions/{sess_id}/participants", json={"display_name": "TestUser"}).json()["id"]
    client.post(f"/participants/{p_id}/consent", json={"agree": True})
    
    # Consent recording
    consent_file = io.BytesIO(b"RIFF....WAVEfmt...")
    client.post(
        f"/participants/{p_id}/consent-recording",
        data={"capture_session_id": "session-A"},
        files={"file": ("consent.wav", consent_file, "audio/wav")}
    )
    
    # Audio sample
    sample_file = io.BytesIO(b"RIFF....WAVEfmt...")
    client.post(
        f"/participants/{p_id}/audio-sample",
        data={"capture_session_id": "session-A", "source": "live_recording"},
        files={"file": ("sample.wav", sample_file, "audio/wav")}
    )
    
    # 2. Delete/End the session
    del_resp = client.delete(f"/sessions/{sess_id}")
    assert del_resp.status_code == 200
    
    # 3. Verify DB records are gone
    async with test_async_session() as db:
        sess_stmt = select(DBSession).where(DBSession.id == sess_id)
        res = await db.execute(sess_stmt)
        assert res.scalar_one_or_none() is None
