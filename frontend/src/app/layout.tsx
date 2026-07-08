import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SecureVoice | Consent-Based AI Voice Cloning Demo",
  description: "A cybersecurity education proof-of-concept demonstrating how consent gating, active voice capture, and content filtering protect against unauthorized voice cloning and impersonation risks.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <header>
          <div className="header-inner">
            <a href="/" className="logo">
              <div className="logo-icon">V</div>
              <div className="logo-text">Secure<span>Voice</span></div>
            </a>
            <nav>
              <a href="/">Create Session</a>
              <a href="/safety-info">Safety & Risk Info</a>
            </nav>
          </div>
        </header>

        <main style={{ flex: 1, display: "flex", flexDirection: "column" }}>
          {children}
        </main>

        <footer>
          <div className="app-container" style={{ padding: "0 1.5rem" }}>
            <p style={{ fontSize: "0.85rem", margin: 0 }}>
              SecureVoice is a cybersecurity educational proof-of-concept. All session data, consent records, and audio recordings auto-expire and are stored strictly locally.
            </p>
            <p style={{ fontSize: "0.85rem", marginTop: "0.5rem", marginBottom: 0 }}>
              Created for security training purposes. Developed using Next.js & FastAPI.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
