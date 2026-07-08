# Build a Consent-Based AI Voice Demo App

Build a complete proof-of-concept web application that demonstrates how a consent-based AI voice-cloning product could work.

This is for a cybersecurity education video showing how this type of technology can create security, privacy, impersonation, fraud, and social-engineering risks.

The first version should be simple, local, and runnable. Prioritize demonstrating the complete product flow over advanced UI design.

## Core Concept

The app should allow a host to:

1. Create a demo session.
2. Add participants.
3. Collect explicit consent from each participant.
4. Record a short live voice sample from each consenting participant.
5. Type a sentence.
6. Generate or simulate synthetic audio for the selected consenting participant.
7. Show safety controls that prevent misuse.

## Important Safety Requirements

These are non-negotiable product requirements:

1. The app must be consent-based by design.
2. Do not create hidden recording features.
3. Do not record anyone without a visible consent step.
4. Do not allow voice generation unless the participant has consented.
5. Do not allow generation after consent has been revoked.
6. Do not allow generation if the participant has no verified live-recorded audio sample.
7. Do not include file uploads for voice data.
8. Do not include drag-and-drop audio upload.
9. Do not include paste-a-link audio import.
10. The app must only accept audio captured live through the browser microphone during an active consent session.
11. Consent-phrase recording and voice-sample recording must happen in one continuous capture session.
12. The backend must reject audio samples whose `capture_session_id` does not match a completed consent recording for that participant.
13. The app must block unsafe generation text before calling any voice provider.
14. Blocked attempts must be logged and shown on the host dashboard.
15. Every generated clip must include an embedded audio disclosure, such as a spoken line or watermark tone, saying the audio is synthetic and was generated for a cybersecurity education demo.
16. Consent records, audio samples, and generated clips must auto-expire.
17. The host must be able to end a session and immediately purge all session data.
18. Do not build features for deception, impersonation, bypassing consent, covert recording, or unauthorized cloning.

## Recommended MVP Scope

For the first version, use a mock voice provider by default.

The mock provider can return placeholder audio or browser text-to-speech output, clearly labeled as:

> Fallback demo audio. This does not clone the participant’s voice.

Structure the app so a real consent-based voice provider could be added later, but do not require a paid API key for the first version.

## Tech Stack

Use:

- Frontend: Next.js with TypeScript
- Backend: FastAPI with Python
- Database: SQLite
- Audio capture: Browser `MediaRecorder` API only
- Voice generation: Provider interface with a mock provider for MVP
- Local development only

## Voice Provider Architecture

Create a provider-agnostic voice generation system.

Include:

- `VoiceCloneProvider` interface
- `MockVoiceProvider`
- Optional `BrowserTTSProvider` fallback, clearly labeled as non-cloning
- Content-filter wrapper that runs before any provider call
- Audio-disclosure/watermark wrapper that runs after any provider call

Generation must fail if:

- Participant has not consented
- Participant revoked consent
- Participant has no verified live-recorded audio sample
- Audio sample does not match a valid capture session
- Input text violates the content policy

## Content Filter

Before generation, block or flag text containing:

- Financial authorization language
- Payment instructions
- Wire transfer requests
- “Send money now” urgency
- One-time codes
- PINs
- Passwords
- Requests to impersonate a public figure
- Requests to impersonate someone not in the participant list

Blocked requests should be logged in the database and displayed on the host dashboard.

## Required User Flow

1. Host creates a session.
2. Host optionally sets a retention TTL. Default: 24 hours.
3. Host manually adds participant names.
4. Each participant receives or opens a unique participant page.
5. Participant sees a clear consent explanation.
6. Participant must explicitly consent.
7. Participant records the required consent phrase and voice sample in one continuous browser recording session.
8. Host dashboard shows which participants are ready.
9. Host types a sentence.
10. Host selects a consenting participant.
11. App runs the text through the content filter.
12. If blocked, the host sees the reason and the attempt is logged.
13. If allowed, the app generates demo synthetic audio.
14. The generated audio includes an embedded synthetic-audio disclosure.
15. The host can revoke or delete participant audio.
16. The participant can revoke consent.
17. The host can end the session, immediately deleting all related data.

## Required Pages

Build these pages:

- Create session page
- Host dashboard
- Participant consent page
- Participant recording page
- Generation/playback page
- Safety and risk explanation page

## Required Backend Endpoints

Create these endpoints:

- `POST /sessions`
- `GET /sessions/{session_id}`
- `DELETE /sessions/{session_id}`
- `POST /sessions/{session_id}/participants`
- `GET /participants/{participant_id}`
- `POST /participants/{participant_id}/consent`
- `POST /participants/{participant_id}/revoke-consent`
- `POST /participants/{participant_id}/consent-recording`
- `POST /participants/{participant_id}/audio-sample`
- `DELETE /participants/{participant_id}/audio-sample`
- `POST /generate-voice`
- `GET /health`

Important: `/audio-sample` must only accept live browser capture data tagged with a valid `capture_session_id`. Do not create a generic upload endpoint.

## Required Database Tables

Create these SQLite tables:

### `sessions`

- `id`
- `retention_ttl_seconds`
- `expires_at`
- `ended_at`
- `created_at`

### `participants`

- `id`
- `session_id`
- `display_name`
- `participant_token`
- `consent_status`
- `consent_timestamp`
- `revoke_timestamp`
- `created_at`

### `audio_samples`

- `id`
- `participant_id`
- `capture_session_id`
- `source`
- `file_path`
- `duration_seconds`
- `created_at`
- `expires_at`
- `deleted_at`

The `source` value must always be `live_recording`.

### `generations`

- `id`
- `session_id`
- `participant_id`
- `input_text`
- `output_file_path`
- `safety_label`
- `blocked`
- `blocked_reason`
- `requested_by`
- `created_at`
- `expires_at`

Blocked generation attempts can be stored in `generations` with `blocked = true`.

## Required Deliverables

The project should include:

1. Full project folder structure
2. Complete frontend code
3. Complete backend code
4. Database models
5. API routes
6. Setup instructions
7. `.env.example`
8. `README.md`
9. `SECURITY.md`
10. Tests

## Required Tests

Add tests proving:

1. Generation is blocked when consent is missing.
2. Generation is blocked after consent is revoked.
3. Generation is blocked if the participant has no audio sample.
4. Audio-sample submission is rejected if its `capture_session_id` does not match a completed consent recording.
5. There is no generic upload endpoint for audio samples.
6. Flagged input text is blocked before reaching the voice provider.
7. Blocked generation attempts are logged.
8. Session, participant, audio, and generation data are deleted when the TTL expires.
9. Session data is deleted when the host ends the session.

## README Requirements

`README.md` should explain:

- What the app does
- How to run it locally
- Why this is a cybersecurity education demo
- What risks voice cloning creates
- What safeguards are included
- Consent gating
- Live-capture-only audio
- Content filtering
- Embedded audio disclosure
- Auto-expiry
- What safeguards are still missing in a real-world product, such as:
  - Liveness detection
  - Anti-replay detection
  - Cryptographic consent signing
  - Stronger identity verification
  - Production-grade moderation
  - Legal review by jurisdiction

## SECURITY.md Requirements

`SECURITY.md` should include:

- Consent requirements
- Why uploads are disallowed
- What upload prevention helps prevent
- Data deletion and retention behavior
- Social-engineering risks
- Synthetic audio labeling
- Embedded audio disclosure
- Content-filtering scope and limitations
- Recommended production safeguards

## Final Instruction

Make the first version simple, local, and runnable.

Prioritize the complete consent-based product flow, safety controls, audit logging, and clear cybersecurity education value.
