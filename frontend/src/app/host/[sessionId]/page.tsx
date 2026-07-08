"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";

interface Participant {
  id: string;
  display_name: string;
  participant_token: string;
  consent_status: "pending" | "consented" | "revoked";
  consent_timestamp?: string;
  revoke_timestamp?: string;
  has_audio_sample: boolean;
  capture_session_id?: string;
}

interface GenerationLog {
  id: string;
  participant_id: string;
  input_text: string;
  output_file_path?: string;
  safety_label: "safe" | "blocked";
  blocked: boolean;
  blocked_reason?: string;
  requested_by: string;
  created_at: string;
}

export default function HostDashboard() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;

  const [session, setSession] = useState<any>(null);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [generations, setGenerations] = useState<GenerationLog[]>([]);
  
  const [newParticipantName, setNewParticipantName] = useState("");
  const [selectedParticipantId, setSelectedParticipantId] = useState("");
  const [scriptText, setScriptText] = useState("");
  const [selectedProvider, setSelectedProvider] = useState("mock");

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [actionSuccess, setActionSuccess] = useState("");
  
  const [genLoading, setGenLoading] = useState(false);
  const [generatedAudioUrl, setGeneratedAudioUrl] = useState("");
  const [ttsSpeechTriggered, setTtsSpeechTriggered] = useState(false);
  const [copiedParticipantId, setCopiedParticipantId] = useState("");

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // Poll for updates every 3 seconds
  useEffect(() => {
    fetchSessionDetails();
    const interval = setInterval(fetchSessionDetails, 3000);
    return () => clearInterval(interval);
  }, [sessionId]);

  const fetchSessionDetails = async () => {
    try {
      const res = await fetch(`${apiBase}/sessions/${sessionId}`);
      if (!res.ok) {
        if (res.status === 404) {
          router.push("/");
          return;
        }
        throw new Error("Unable to fetch session details.");
      }
      const data = await res.json();
      setSession(data);
      setParticipants(data.participants || []);
      setGenerations(data.generations || []);
      setError("");
    } catch (err: any) {
      setError(err.message || "Lost connection to backend.");
    } finally {
      setLoading(false);
    }
  };

  const handleAddParticipant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newParticipantName.trim()) return;
    setActionError("");
    setActionSuccess("");

    try {
      const res = await fetch(`${apiBase}/sessions/${sessionId}/participants`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display_name: newParticipantName.trim() }),
      });

      if (!res.ok) {
        throw new Error("Failed to add participant.");
      }

      setNewParticipantName("");
      setActionSuccess("Participant added successfully!");
      fetchSessionDetails();
    } catch (err: any) {
      setActionError(err.message);
    }
  };

  const handleDeleteSample = async (participantId: string) => {
    if (!confirm("Are you sure you want to delete this participant's live audio sample?")) return;
    setActionError("");
    setActionSuccess("");

    try {
      const res = await fetch(`${apiBase}/participants/${participantId}/audio-sample`, {
        method: "DELETE",
      });

      if (!res.ok) {
        throw new Error("Failed to delete audio sample.");
      }

      setActionSuccess("Voice sample deleted successfully.");
      fetchSessionDetails();
    } catch (err: any) {
      setActionError(err.message);
    }
  };

  const handleGenerateVoice = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedParticipantId || !scriptText.trim()) return;

    setActionError("");
    setActionSuccess("");
    setGeneratedAudioUrl("");
    setTtsSpeechTriggered(false);
    setGenLoading(true);

    try {
      const res = await fetch(`${apiBase}/generate-voice`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          participant_id: selectedParticipantId,
          input_text: scriptText.trim(),
          provider: selectedProvider,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Voice generation was blocked or failed.");
      }

      if (data.provider === "browser_tts") {
        // Trigger Speech Synthesis in the browser
        const utterance = new SpeechSynthesisUtterance(data.text);
        window.speechSynthesis.speak(utterance);
        setTtsSpeechTriggered(true);
        setActionSuccess("Browser Text-to-Speech triggered successfully.");
      } else if (data.provider === "mock") {
        // Build direct URL to the static wav file
        setGeneratedAudioUrl(`${apiBase}${data.audio_url}`);
        setActionSuccess("Mock synthetic voice generated with embedded audio disclosure.");
      }
      setScriptText("");
      fetchSessionDetails();
    } catch (err: any) {
      setActionError(err.message);
      fetchSessionDetails(); // Refresh list to instantly show blocked logs
    } finally {
      setGenLoading(false);
    }
  };

  const handleEndSession = async () => {
    if (
      !confirm(
        "WARNING: Ending the session will immediately purge all session files, database records, consent history, and recorded voice samples. This action is irreversible. Proceed?"
      )
    ) {
      return;
    }

    try {
      await fetch(`${apiBase}/sessions/${sessionId}`, { method: "DELETE" });
      router.push("/");
    } catch (err: any) {
      setActionError("Failed to purge session data properly.");
    }
  };

  const copyInviteLink = (pId: string) => {
    const origin = window.location.origin;
    const link = `${origin}/participant/${pId}`;
    navigator.clipboard.writeText(link);
    setCopiedParticipantId(pId);
    setTimeout(() => setCopiedParticipantId(""), 2000);
  };

  if (loading) {
    return (
      <div className="app-container" style={{ justifyContent: "center", alignItems: "center", minHeight: "50vh" }}>
        <h3>Loading session details...</h3>
      </div>
    );
  }

  if (error) {
    return (
      <div className="app-container">
        <div className="alert alert-danger" style={{ marginTop: "2rem" }}>
          <strong>Error:</strong> {error}
        </div>
      </div>
    );
  }

  // Filter list of participants that are eligible for generation (consented and have audio sample)
  const readyParticipants = participants.filter((p) => p.consent_status === "consented" && p.has_audio_sample);

  return (
    <div className="app-container">
      {/* Session Details Bar */}
      <div className="card" style={{ padding: "1.25rem 1.75rem", marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
          <div>
            <span className="form-label" style={{ margin: 0, fontSize: "0.75rem" }}>Active Demo Session ID</span>
            <code style={{ fontSize: "1.1rem", color: "#a5b4fc", fontWeight: "bold" }}>{sessionId}</code>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "1.5rem" }}>
            <div>
              <span className="form-label" style={{ margin: 0, fontSize: "0.75rem" }}>Expires At (UTC)</span>
              <span style={{ fontWeight: 600 }}>{session ? new Date(session.expires_at).toLocaleTimeString() : ""}</span>
            </div>
            <button className="btn btn-danger" onClick={handleEndSession} style={{ padding: "0.5rem 1rem", fontSize: "0.85rem" }}>
              End & Purge Session
            </button>
          </div>
        </div>
      </div>

      {actionError && (
        <div className="alert alert-danger">
          <strong>Security Action Blocked:</strong> {actionError}
        </div>
      )}

      {actionSuccess && (
        <div className="alert alert-info">
          <strong>Success:</strong> {actionSuccess}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "1.5rem" }} className="grid-main">
        {/* Left Side: Participant Management */}
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          <div className="card">
            <div className="card-title-bar">
              <h3>1. Add Participant</h3>
            </div>
            <form onSubmit={handleAddParticipant} style={{ display: "flex", gap: "0.5rem" }}>
              <input
                type="text"
                className="form-input"
                placeholder="Participant's Display Name (e.g. Alice)"
                value={newParticipantName}
                onChange={(e) => setNewParticipantName(e.target.value)}
              />
              <button type="submit" className="btn btn-primary" style={{ whiteSpace: "nowrap" }}>
                Add
              </button>
            </form>
          </div>

          <div className="card">
            <div className="card-title-bar">
              <h3>2. Demonstration Participants</h3>
            </div>
            {participants.length === 0 ? (
              <p style={{ fontStyle: "italic" }}>No participants added yet. Add a participant above to begin.</p>
            ) : (
              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>Display Name</th>
                      <th>Consent Status</th>
                      <th>Live Audio</th>
                      <th>Participant Access Link</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {participants.map((p) => (
                      <tr key={p.id}>
                        <td style={{ fontWeight: 600 }}>{p.display_name}</td>
                        <td>
                          <span
                            className={`badge badge-${
                              p.consent_status === "consented"
                                ? "consented"
                                : p.consent_status === "revoked"
                                ? "revoked"
                                : "pending"
                            }`}
                          >
                            {p.consent_status}
                          </span>
                        </td>
                        <td>
                          {p.has_audio_sample ? (
                            <span className="badge badge-consented">Recorded</span>
                          ) : (
                            <span className="badge badge-pending">Missing</span>
                          )}
                        </td>
                        <td>
                          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                            <button
                              onClick={() => copyInviteLink(p.id)}
                              className="btn btn-secondary"
                              style={{ padding: "0.35rem 0.75rem", fontSize: "0.8rem", width: "120px" }}
                            >
                              {copiedParticipantId === p.id ? "Copied!" : "Copy Invite"}
                            </button>
                            <a
                              href={`/participant/${p.id}`}
                              target="_blank"
                              rel="noreferrer"
                              style={{ fontSize: "0.8rem", color: "#818cf8", textDecoration: "underline" }}
                            >
                              Open Link
                            </a>
                          </div>
                        </td>
                        <td>
                          <button
                            className="btn btn-danger"
                            onClick={() => handleDeleteSample(p.id)}
                            disabled={!p.has_audio_sample}
                            style={{ padding: "0.35rem 0.75rem", fontSize: "0.8rem" }}
                          >
                            Purge Voice
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* Right Side: Voice Generation */}
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          <div className="card">
            <div className="card-title-bar">
              <h3>3. Trigger Voice Clone Simulation</h3>
            </div>
            
            <form onSubmit={handleGenerateVoice} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div className="form-group">
                <label className="form-label">Select Ready Participant</label>
                <select
                  className="form-input"
                  style={{ background: "#0b0f19", border: "1px solid var(--border-glass)" }}
                  value={selectedParticipantId}
                  onChange={(e) => setSelectedParticipantId(e.target.value)}
                  required
                >
                  <option value="">-- Choose an eligible participant --</option>
                  {readyParticipants.map((rp) => (
                    <option key={rp.id} value={rp.id}>
                      {rp.display_name} (Consent Verified)
                    </option>
                  ))}
                </select>
                <p className="form-helper">
                  Only participants who have given active consent and recorded a live voice sample are shown.
                </p>
              </div>

              <div className="form-group">
                <label className="form-label">Text to Synthesize</label>
                <textarea
                  className="form-input"
                  rows={3}
                  placeholder="Enter sentence for synthetic generation (e.g. Hello, welcome to this cybersecurity education training!)"
                  value={scriptText}
                  onChange={(e) => setScriptText(e.target.value)}
                  required
                  style={{ resize: "vertical", fontFamily: "inherit" }}
                />
                <p className="form-helper">
                  Security restriction: Sentences trying to request money transfers, passwords, PIN numbers, or impersonate people not in this demo session will be automatically blocked.
                </p>
              </div>

              <div className="form-group">
                <label className="form-label">Voice Provider</label>
                <div style={{ display: "flex", gap: "1.5rem" }}>
                  <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
                    <input
                      type="radio"
                      name="provider"
                      value="mock"
                      checked={selectedProvider === "mock"}
                      onChange={() => setSelectedProvider("mock")}
                    />
                    Mock Provider (Generates WAV file)
                  </label>
                  <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
                    <input
                      type="radio"
                      name="provider"
                      value="browser_tts"
                      checked={selectedProvider === "browser_tts"}
                      onChange={() => setSelectedProvider("browser_tts")}
                    />
                    Browser Text-To-Speech (Fallback)
                  </label>
                </div>
              </div>

              <button
                type="submit"
                className="btn btn-primary"
                disabled={genLoading || !selectedParticipantId || !scriptText.trim()}
              >
                {genLoading ? "Running Content Policies & Synthesizing..." : "Generate Synthetic Voice"}
              </button>
            </form>

            {generatedAudioUrl && (
              <div style={{ marginTop: "1.5rem", padding: "1rem", background: "rgba(0,0,0,0.3)", borderRadius: "6px" }}>
                <span className="form-label">Generated Output:</span>
                <p style={{ fontSize: "0.85rem", color: "#f59e0b", margin: "0.25rem 0 0.75rem 0" }}>
                  *Embedded synthetic audio disclaimer dual-beep tone prepended.
                </p>
                <audio src={generatedAudioUrl} controls autoPlay style={{ width: "100%" }} />
              </div>
            )}

            {ttsSpeechTriggered && (
              <div style={{ marginTop: "1.5rem", padding: "1rem", background: "rgba(99, 102, 241, 0.1)", borderRadius: "6px", border: "1px solid rgba(99, 102, 241, 0.2)" }}>
                <span className="badge badge-active" style={{ marginBottom: "0.5rem" }}>Browser TTS Active</span>
                <p style={{ fontSize: "0.9rem", color: "#ffffff", margin: 0 }}>
                  <strong>Speech Synthesized:</strong> Played fallback audio natively in the browser. <em>This does not clone the participant's voice.</em>
                </p>
              </div>
            )}
          </div>

          {/* Audit / Safety Logs */}
          <div className="card">
            <div className="card-title-bar">
              <h3>Safety Policy & Audit Log</h3>
            </div>
            {generations.length === 0 ? (
              <p style={{ fontStyle: "italic" }}>No generation attempts logged yet.</p>
            ) : (
              <div className="table-wrapper" style={{ maxHeight: "300px", overflowY: "auto" }}>
                <table>
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Target</th>
                      <th>Text Prompt</th>
                      <th>Safety Check</th>
                    </tr>
                  </thead>
                  <tbody>
                    {generations.map((g) => (
                      <tr key={g.id}>
                        <td style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                          {new Date(g.created_at).toLocaleTimeString()}
                        </td>
                        <td style={{ fontWeight: 600, fontSize: "0.85rem" }}>
                          {participants.find((p) => p.id === g.participant_id)?.display_name || "Unknown"}
                        </td>
                        <td style={{ fontSize: "0.85rem", whiteSpace: "normal", wordBreak: "break-all" }}>
                          "{g.input_text}"
                        </td>
                        <td>
                          {g.blocked ? (
                            <div>
                              <span className="badge badge-revoked" style={{ fontSize: "0.7rem", padding: "0.15rem 0.4rem" }}>Blocked</span>
                              <div style={{ fontSize: "0.75rem", color: "var(--danger)", marginTop: "0.25rem", maxWidth: "250px" }}>
                                {g.blocked_reason}
                              </div>
                            </div>
                          ) : (
                            <span className="badge badge-consented" style={{ fontSize: "0.7rem", padding: "0.15rem 0.4rem" }}>Passed (Safe)</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>

      <style jsx>{`
        .grid-main {
          grid-template-columns: 1.1fr 0.9fr;
        }
        @media (max-width: 900px) {
          .grid-main {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  );
}
