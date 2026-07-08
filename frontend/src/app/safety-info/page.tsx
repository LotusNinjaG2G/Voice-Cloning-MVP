"use client";

export default function SafetyInfoPage() {
  return (
    <div className="app-container" style={{ maxWidth: "800px" }}>
      <div className="card" style={{ padding: "2.5rem", marginBottom: "2rem" }}>
        <h1 style={{ fontSize: "2.25rem", marginBottom: "1rem" }}>
          AI Voice Cloning: Threats & Safeguards
        </h1>
        <p style={{ fontSize: "1.1rem" }}>
          This application serves as a proof-of-concept for a consent-based AI voice-cloning flow, built for cybersecurity training. Voice cloning is a powerful utility, but it presents major vector vulnerabilities.
        </p>

        <hr style={{ border: 0, borderBottom: "1px solid var(--border-glass)", margin: "2rem 0" }} />

        <h2 style={{ color: "#a5b4fc", marginBottom: "1rem" }}>1. Cybersecurity Threat Vectors</h2>
        <p>
          AI-generated synthetic voice allows attackers to execute highly targeted and convincing impersonation attacks:
        </p>

        <div style={{ display: "flex", flexDirection: "column", gap: "1rem", margin: "1.5rem 0" }}>
          <div style={{ background: "rgba(239, 68, 68, 0.05)", padding: "1.25rem", borderRadius: "8px", borderLeft: "4px solid var(--danger)" }}>
            <h4 style={{ color: "var(--danger)" }}>CEO Fraud / Business Email Compromise (BEC)</h4>
            <p style={{ fontSize: "0.95rem", margin: 0 }}>
              Attackers clone an executive's voice and call a finance staff member, instructing them to perform an urgent, confidential wire transfer. The voice authority bypasses standard email verification protocols.
            </p>
          </div>

          <div style={{ background: "rgba(239, 68, 68, 0.05)", padding: "1.25rem", borderRadius: "8px", borderLeft: "4px solid var(--danger)" }}>
            <h4 style={{ color: "var(--danger)" }}>Vishing & Urgent Scams</h4>
            <p style={{ fontSize: "0.95rem", margin: 0 }}>
              Scammers clone a relative's voice (often scraped from public social media videos) and call elderly grandparents, claiming they are in distress, arrested, or hospitalized, demanding immediate payment via gift cards or wire transfers.
            </p>
          </div>

          <div style={{ background: "rgba(239, 68, 68, 0.05)", padding: "1.25rem", borderRadius: "8px", borderLeft: "4px solid var(--danger)" }}>
            <h4 style={{ color: "var(--danger)" }}>Bypassing Voice Biometrics</h4>
            <p style={{ fontSize: "0.95rem", margin: 0 }}>
              Many financial services use voice recognition ("my voice is my password") to authenticate users over the phone. Attackers can synthesize a customer's voice to bypass banking telephone verification filters.
            </p>
          </div>
        </div>

        <h2 style={{ color: "#a5b4fc", marginBottom: "1rem", marginTop: "2rem" }}>2. MVP Built-In Safeguards</h2>
        <p>
          To demonstrate secure-by-design principles, this app implements strict safety controls directly in the backend architecture:
        </p>

        <ul style={{ paddingLeft: "1.25rem", color: "var(--text-secondary)", lineHeight: 1.7, display: "flex", flexDirection: "column", gap: "0.75rem", margin: "1.5rem 0" }}>
          <li>
            <strong>Consent Gating:</strong> The API rejects generation requests unless the participant has signed active consent. Revoking consent instantly deletes their voice profiles from the database and disk.
          </li>
          <li>
            <strong>Live Capture Only:</strong> Uploading pre-recorded audio files is blocked. The backend matches the upload's `capture_session_id` against the unique browser consent-recording session.
          </li>
          <li>
            <strong>Content Filtering:</strong> Every generation request scans for financial authorization triggers ("wire money", "send cash"), urgent keywords, credentials, public figures, or unauthorized names, blocking violations instantly.
          </li>
          <li>
            <strong>Embedded Audio Watermarks:</strong> Every generated audio WAV file has a distinct double-beep tone prepended, ensuring it is immediately recognizable as synthetic.
          </li>
          <li>
            <strong>Auto-Expiry (TTL):</strong> All session data, recordings, and synthetic generations have a strict Time-to-Live (TTL) and auto-expire from the server.
          </li>
        </ul>

        <h2 style={{ color: "#a5b4fc", marginBottom: "1rem", marginTop: "2rem" }}>3. Production Safeguards (Missing in MVP)</h2>
        <p>
          A production-grade voice-cloning application requires advanced mitigation controls that go beyond this local PoC:
        </p>

        <div style={{ display: "flex", flexDirection: "column", gap: "1rem", margin: "1.5rem 0" }}>
          <div style={{ background: "rgba(99, 102, 241, 0.05)", padding: "1.25rem", borderRadius: "8px", borderLeft: "4px solid var(--accent-primary)" }}>
            <h4 style={{ color: "#a5b4fc" }}>Liveness Verification</h4>
            <p style={{ fontSize: "0.95rem", margin: 0 }}>
              Advanced algorithms that detect whether the captured voice is generated live or is a replay of a previous recording (anti-replay attacks).
            </p>
          </div>

          <div style={{ background: "rgba(99, 102, 241, 0.05)", padding: "1.25rem", borderRadius: "8px", borderLeft: "4px solid var(--accent-primary)" }}>
            <h4 style={{ color: "#a5b4fc" }}>Cryptographic Signing</h4>
            <p style={{ fontSize: "0.95rem", margin: 0 }}>
              Signing consent statements and voice models using asymmetric cryptography. The public key verifies the consent originates directly from the participant.
            </p>
          </div>

          <div style={{ background: "rgba(99, 102, 241, 0.05)", padding: "1.25rem", borderRadius: "8px", borderLeft: "4px solid var(--accent-primary)" }}>
            <h4 style={{ color: "#a5b4fc" }}>Active Watermarking</h4>
            <p style={{ fontSize: "0.95rem", margin: 0 }}>
              Embedding inaudible, robust digital watermarks into the generated audio spectrum. This allows forensics scanners to detect synthetic audio even if it is transcoded or compressed.
            </p>
          </div>

          <div style={{ background: "rgba(99, 102, 241, 0.05)", padding: "1.25rem", borderRadius: "8px", borderLeft: "4px solid var(--accent-primary)" }}>
            <h4 style={{ color: "#a5b4fc" }}>Multi-Modal Identity Verification</h4>
            <p style={{ fontSize: "0.95rem", margin: 0 }}>
              Pairing voice consent with identity verification checks (e.g. government ID matching, video face-matching scans) to verify the participant's name matches their legal identity.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
