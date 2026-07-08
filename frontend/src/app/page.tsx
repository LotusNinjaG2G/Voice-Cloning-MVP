"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function CreateSessionPage() {
  const [ttlHours, setTtlHours] = useState(24);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();

  const handleTtlChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setTtlHours(parseInt(e.target.value) || 1);
  };

  const handleCreateSession = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiBase}/sessions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          retention_ttl_seconds: ttlHours * 3600,
        }),
      });

      if (!res.ok) {
        throw new Error("Could not initialize the demonstration session.");
      }

      const data = await res.json();
      router.push(`/host/${data.id}`);
    } catch (err: any) {
      setError(err.message || "Unable to connect to the backend server.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container" style={{ maxWidth: "600px", justifyContent: "center", minHeight: "60vh" }}>
      <div className="card" style={{ padding: "2.5rem" }}>
        <h1 style={{ fontSize: "2rem", marginBottom: "1rem", textAlign: "center" }}>
          Initialize Voice Clone Demo
        </h1>
        <p style={{ textAlign: "center", marginBottom: "2rem" }}>
          Set up a temporary, sandboxed simulation session. All session recordings and generated audios automatically expire based on the selected retention TTL.
        </p>

        {error && (
          <div className="alert alert-danger">
            <div>
              <strong>Error:</strong> {error}
            </div>
          </div>
        )}

        <form onSubmit={handleCreateSession}>
          <div className="form-group">
            <label className="form-label">Data Retention Window (TTL)</label>
            <div className="range-container" style={{ margin: "0.5rem 0" }}>
              <input
                type="range"
                className="range-slider"
                min="1"
                max="48"
                value={ttlHours}
                onChange={handleTtlChange}
              />
              <span className="range-val">{ttlHours} hour{ttlHours > 1 ? "s" : ""}</span>
            </div>
            <p className="form-helper">
              After this timeframe, all database records, consent files, live recording samples, and generated synthetic audios will be deleted from disk.
            </p>
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            style={{ width: "100%", marginTop: "1rem" }}
            disabled={loading}
          >
            {loading ? "Initializing..." : "Create Demo Session"}
          </button>
        </form>
      </div>

      <div className="alert alert-info" style={{ marginTop: "1.5rem" }}>
        <div>
          <strong>Educational Notice:</strong> This is a secure simulation for cybersecurity training. No real cloning is performed unless active consent is recorded and validated. Generic audio uploads are blocked by design.
        </div>
      </div>
    </div>
  );
}
