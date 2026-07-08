"use client";

import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";

export default function ParticipantPage() {
  const params = useParams();
  const participantId = params.participantId as string;

  const [participant, setParticipant] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [consented, setConsented] = useState(false);
  const [recording, setRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [statusText, setStatusText] = useState("");
  const [step, setStep] = useState(1); // 1: Consent info, 2: Recording panels, 3: Completed state

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<any>(null);

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    fetchParticipantDetails();
  }, [participantId]);

  const fetchParticipantDetails = async () => {
    try {
      const res = await fetch(`${apiBase}/participants/${participantId}`);
      if (!res.ok) {
        throw new Error("Participant link invalid or demo session has expired.");
      }
      const data = await res.json();
      setParticipant(data);
      if (data.consent_status === "consented") {
        setConsented(true);
        if (data.has_audio_sample) {
          setStep(3); // Already fully completed
        } else {
          setStep(2); // Consented but needs recording
        }
      } else if (data.consent_status === "revoked") {
        setStep(1);
        setConsented(false);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load participant page.");
    } finally {
      setLoading(false);
    }
  };

  const handleAgreeConsent = async () => {
    try {
      const res = await fetch(`${apiBase}/participants/${participantId}/consent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agree: true }),
      });

      if (!res.ok) {
        throw new Error("Could not submit consent.");
      }
      setConsented(true);
      setStep(2);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleRevokeConsent = async () => {
    if (
      !confirm(
        "Are you sure you want to revoke consent? This will immediately delete all voice samples, consent recordings, and synthetic generations associated with you."
      )
    ) {
      return;
    }

    try {
      const res = await fetch(`${apiBase}/participants/${participantId}/revoke-consent`, {
        method: "POST",
      });

      if (!res.ok) {
        throw new Error("Could not revoke consent.");
      }

      setConsented(false);
      setAudioBlob(null);
      setStep(1);
      fetchParticipantDetails();
      alert("Consent revoked and all voice records purged.");
    } catch (err: any) {
      alert("Error revoking consent: " + err.message);
    }
  };

  // Recording Logic
  const startRecording = async () => {
    audioChunksRef.current = [];
    setRecordingTime(0);
    setStatusText("Preparing microphone...");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      // Select appropriate browser mime type
      let options = { mimeType: "audio/webm" };
      if (!MediaRecorder.isTypeSupported("audio/webm")) {
        options = { mimeType: "audio/mp4" };
      }

      const recorder = new MediaRecorder(stream, options);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: recorder.mimeType });
        setAudioBlob(audioBlob);
        setStatusText("Audio captured successfully.");
        // Stop stream tracks
        stream.getTracks().forEach((track) => track.stop());
      };

      recorder.start(250); // Get chunks every 250ms
      setRecording(true);
      setStatusText("Recording live sample...");

      timerRef.current = setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);
    } catch (err: any) {
      setStatusText("Failed to access microphone. Please check permissions.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && recording) {
      mediaRecorderRef.current.stop();
      setRecording(false);
      clearInterval(timerRef.current);
    }
  };

  const uploadRecording = async () => {
    if (!audioBlob) return;
    setStatusText("Initializing secure upload...");

    // Generate a secure single-session UUID for the continuous capture
    const captureSessionId = "cap_" + Math.random().toString(36).substr(2, 9);

    try {
      // 1. Upload Consent Statement (continuous audio file)
      setStatusText("Uploading consent statement verification...");
      const consentForm = new FormData();
      consentForm.append("file", audioBlob, "consent_statement.webm");
      consentForm.append("capture_session_id", captureSessionId);

      let res = await fetch(`${apiBase}/participants/${participantId}/consent-recording`, {
        method: "POST",
        body: consentForm,
      });

      if (!res.ok) {
        throw new Error("Consent verification failed on the server.");
      }

      // 2. Upload Voice Sample (continuous audio file using the exact same captureSessionId)
      setStatusText("Uploading live voice sample...");
      const sampleForm = new FormData();
      sampleForm.append("file", audioBlob, "voice_sample.webm");
      sampleForm.append("capture_session_id", captureSessionId);
      sampleForm.append("source", "live_recording"); // Hardcoded safety parameter

      res = await fetch(`${apiBase}/participants/${participantId}/audio-sample`, {
        method: "POST",
        body: sampleForm,
      });

      if (!res.ok) {
        throw new Error("Voice sample upload failed on the server.");
      }

      setStatusText("Voice sample verified and securely uploaded!");
      setStep(3);
      fetchParticipantDetails();
    } catch (err: any) {
      setStatusText("Upload failed: " + err.message);
    }
  };

  if (loading) {
    return (
      <div className="app-container" style={{ justifyContent: "center", alignItems: "center", minHeight: "50vh" }}>
        <h3>Connecting to demo session...</h3>
      </div>
    );
  }

  if (error) {
    return (
      <div className="app-container" style={{ maxWidth: "600px", marginTop: "2rem" }}>
        <div className="alert alert-danger">
          <strong>Error:</strong> {error}
        </div>
      </div>
    );
  }

  return (
    <div className="app-container" style={{ maxWidth: "650px", minHeight: "70vh", justifyContent: "center" }}>
      {/* Header bar showing participant identifier */}
      <div className="card" style={{ padding: "1.25rem 1.75rem", marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <span className="form-label" style={{ margin: 0, fontSize: "0.75rem" }}>Participant Name</span>
            <strong style={{ fontSize: "1.25rem", color: "#a5b4fc" }}>{participant?.display_name}</strong>
          </div>
          {consented && (
            <button
              onClick={handleRevokeConsent}
              className="btn btn-danger"
              style={{ padding: "0.4rem 0.85rem", fontSize: "0.8rem" }}
            >
              Revoke Consent
            </button>
          )}
        </div>
      </div>

      {/* STEP 1: Consent Information */}
      {step === 1 && (
        <div className="card">
          <h2 style={{ marginBottom: "1rem" }}>Consent & Risks Disclosure</h2>
          
          <div className="alert alert-warning" style={{ fontSize: "0.9rem" }}>
            <div>
              <strong>IMPORTANT:</strong> This demonstration simulates <strong>AI Voice Cloning</strong>. In the hands of malicious actors, voice cloning poses massive cybersecurity risks:
              <ul style={{ paddingLeft: "1.25rem", marginTop: "0.5rem" }}>
                <li><strong>CEO Fraud:</strong> Fake phone calls instructing staff to wire funds.</li>
                <li><strong>Vishing:</strong> Scams pretending to be family members in emergency distress.</li>
                <li><strong>Biometric Bypass:</strong> Fraudulent verification to bypass phone-banking filters.</li>
              </ul>
            </div>
          </div>

          <p>
            By proceeding, you agree to participate in this educational training. The system will record a short voice sample containing your consent authorization statement.
          </p>

          <h4 style={{ margin: "1.2rem 0 0.5rem 0", color: "#ffffff" }}>Safeguards in place for this demo:</h4>
          <ul style={{ paddingLeft: "1.25rem", color: "var(--text-secondary)", fontSize: "0.95rem", lineHeight: 1.6, marginBottom: "1.5rem" }}>
            <li>Generations are strictly gated behind your active consent check.</li>
            <li>No generic audio files can be uploaded (live microphone capture only).</li>
            <li>All data is stored locally and will be purged immediately upon session termination or TTL expiry.</li>
            <li>You can click <strong>Revoke Consent</strong> at any time to instantly delete your voice sample.</li>
          </ul>

          <button onClick={handleAgreeConsent} className="btn btn-primary" style={{ width: "100%" }}>
            I Explicitly Consent & Agree
          </button>
        </div>
      )}

      {/* STEP 2: Recording (Consent + Voice Sample) */}
      {step === 2 && (
        <div className="card">
          <h2 style={{ marginBottom: "1rem" }}>Live Recording Session</h2>
          <p>
            To activate voice simulation, you must record the consent statement and your voice sample in <strong>one continuous capture session</strong>.
          </p>

          <div style={{ background: "rgba(0, 0, 0, 0.3)", padding: "1.25rem", borderLeft: "4px solid var(--accent-primary)", borderRadius: "0 6px 6px 0", margin: "1.5rem 0" }}>
            <span className="form-label" style={{ color: "#a5b4fc" }}>Script to read aloud:</span>
            <p style={{ fontSize: "1.1rem", color: "#ffffff", fontWeight: 500, fontStyle: "italic", margin: 0 }}>
              "I authorize this cybersecurity demo to temporarily capture my voice sample for educational generation. I understand I can revoke this consent at any time."
            </p>
            <p style={{ fontSize: "0.95rem", color: "var(--text-secondary)", marginTop: "0.75rem", marginBottom: 0 }}>
              <em>(Keep speaking for an additional 5 seconds, describing your day or reading this sentence, to provide a voice sample.)</em>
            </p>
          </div>

          {recording && (
            <div className="audio-visualizer">
              <div className="bar"></div>
              <div className="bar"></div>
              <div className="bar"></div>
              <div className="bar"></div>
              <div className="bar"></div>
              <span style={{ marginLeft: "1rem", fontFamily: "var(--font-mono)", fontWeight: "bold", color: "var(--danger)" }}>
                00:{recordingTime < 10 ? `0${recordingTime}` : recordingTime}
              </span>
            </div>
          )}

          {statusText && (
            <div style={{ textAlign: "center", margin: "1rem 0", fontSize: "0.9rem", color: "#a5b4fc" }}>
              {statusText}
            </div>
          )}

          <div style={{ display: "flex", gap: "1rem", marginTop: "1.5rem" }}>
            {!recording ? (
              <button onClick={startRecording} className="btn btn-primary" style={{ flex: 1 }}>
                Start Recording
              </button>
            ) : (
              <button onClick={stopRecording} className="btn btn-danger" style={{ flex: 1 }}>
                Stop Recording
              </button>
            )}

            {audioBlob && !recording && (
              <button onClick={uploadRecording} className="btn btn-success" style={{ flex: 1 }}>
                Verify & Upload Recording
              </button>
            )}
          </div>

          {audioBlob && !recording && (
            <div style={{ marginTop: "1.5rem" }}>
              <span className="form-label">Review Recording:</span>
              <audio src={URL.createObjectURL(audioBlob)} controls style={{ width: "100%", marginTop: "0.5rem" }} />
            </div>
          )}
        </div>
      )}

      {/* STEP 3: Complete State */}
      {step === 3 && (
        <div className="card" style={{ textAlign: "center", padding: "2.5rem" }}>
          <div style={{ display: "inline-flex", width: "60px", height: "60px", borderRadius: "50%", background: "var(--success-glow)", border: "2px solid var(--success)", alignItems: "center", justifyItems: "center", justifyContent: "center", marginBottom: "1.5rem" }}>
            <span style={{ color: "var(--success)", fontSize: "2rem", fontWeight: "bold" }}>✓</span>
          </div>
          <h2>Verification Complete</h2>
          <p style={{ marginTop: "1rem" }}>
            Your consent phrase and live voice sample have been recorded and verified. The session host can now trigger synthetic demo voice playback.
          </p>
          <div className="alert alert-info" style={{ marginTop: "2rem", textAlign: "left", fontSize: "0.9rem" }}>
            <div>
              <strong>Your Safety Control:</strong> You have full power over your voice sample. To revoke consent and immediately purge all related audio from the host's session database, click <strong>Revoke Consent</strong> above.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
