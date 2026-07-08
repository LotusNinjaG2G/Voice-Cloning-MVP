# SecureVoice | Consent-Based AI Voice-Cloning MVP

SecureVoice is a complete, local proof-of-concept web application demonstrating a **consent-based AI voice-cloning workflow**. 

Developed for cybersecurity education and awareness training, this project demonstrates how secure-by-design principles can protect users from impersonation, fraud, vishing, and social-engineering risks.

---

## 📸 Core Concept & Architecture

SecureVoice allows an administrator (Host) to coordinate a safe voice-cloning demonstration:
1. **Create Session:** Host sets a Time-To-Live (TTL) retention window.
2. **Invite Participants:** Host adds participant display names and shares unique consent links.
3. **Record Consent & Sample:** Participants review the cybersecurity risks, agree to consent, and capture a **single continuous live browser recording** containing both their spoken consent statement and a voice sample.
4. **Generate Demo Speech:** Host types a script, selects a consenting participant, and triggers a mock or browser-based voice synthesis.
5. **Enforce Safety Controls:** The backend checks active consent, prevents manual file uploads, filters out unsafe or fraudulent text scripts, prepends watermark tones, and automatically purges all files upon TTL expiry or session termination.

---

## 🛠️ Local Development Setup

The application is structured into two main components:
- **Backend:** FastAPI with SQLite (Python)
- **Frontend:** Next.js with TypeScript and Vanilla CSS

### Prerequisites
- Python 3.9+
- Node.js 18+ and npm

### 1. Start the FastAPI Backend
1. Open a terminal and navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a Python virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the backend development server:
   ```bash
   uvicorn main:app --reload --port 8000
   ```
   The backend will be running at `http://localhost:8000`. You can access the Swagger docs at `http://localhost:8000/docs`.

### 2. Start the Next.js Frontend
1. Open a new terminal and navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the frontend development server:
   ```bash
   npm run dev
   ```
   The web application will be running at `http://localhost:3000`.

---

## 🧪 Running the Backend Tests

The backend includes a comprehensive pytest suite verifying all safety boundaries:
1. Block generation if consent is missing or revoked.
2. Block generation if the participant has no audio sample.
3. Reject audio uploads where `capture_session_id` does not match the consent statement.
4. Block generic file uploads (forcing live browser capture only).
5. Intercept and block flagged scam terms (wire transfer prompts, credentials, public figures).
6. Verify database logging of blocked attempts.
7. Verify immediate session purges and auto-expiry deletions.

To run the test suite:
```bash
cd backend
source venv/bin/activate
PYTHONPATH=. venv/bin/pytest tests/test_api.py -v
```

---

## 🔒 Built-In Safety Controls

These safeguards are hardcoded directly into the application's architecture:
* **Consent Gating:** Voice generation API checks active consent flags. If consent is revoked or missing, the generation immediately fails.
* **Live-Capture Only:** Generic upload forms are blocked. The API enforces that voice samples must be tagged with a valid browser recording `capture_session_id` generated during the consent statement capture.
* **Content Filtering:** Scans input text and intercepts fraudulent scripts (urgency prompts, wire payments, verification codes, CEO/family impersonation) prior to synthesizing. Blocked attempts are logged for dashboard audit logs.
* **Embedded Watermarks:** prepends a distinct dual-beep tone sequence on generated WAV files. The mock voice provider includes a spoken synthetic disclaimer.
* **Time-to-Live Auto-Expiry:** All SQLite rows, consent statements, samples, and generated WAV files on disk automatically expire and are purged by a background loop thread.
* **Instant Session Purge:** Ending a session from the Host Dashboard triggers an immediate physical deletion of all audio assets and session databases.

---

## ⚠️ Real-World Safeguards (Missing in this MVP)

While this MVP demonstrates a secure flow, a commercial voice-cloning product requires more advanced controls:
1. **Liveness Detection:** Deep audio algorithms analyzing phase and sub-harmonic frequencies to verify the microphone input is a live speaker rather than a recorded playback (replay attack prevention).
2. **Cryptographic Consent Signing:** Having the client generate a public/private key pair (e.g. via WebAuthn) and cryptographically sign the consent recording metadata, ensuring proof of consent is tamper-proof and legally auditable.
3. **Active/Inaudible Watermarking:** Embedding inaudible acoustic patterns directly into the generated voice spectrum that survive compression, screen recording, and conversions.
4. **Multi-Modal Identity Verification:** Requiring the user to upload government ID or perform facial recognition to verify that their legal name matches their displayed participant profile.
5. **Legal & Jurisdictional Review:** Undergoing compliance checks under regional biometric laws (such as BIPA, CCPA, and GDPR).