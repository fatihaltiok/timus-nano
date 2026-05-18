import { useState, useEffect } from "react"
import Chat from "./components/Chat"
import Upload from "./components/Upload"
import Monitor from "./components/Monitor"
import { getStatus } from "./api"

export default function App() {
  const [tab, setTab] = useState("chat")
  const [status, setStatus] = useState(null)

  useEffect(() => {
    getStatus().then(setStatus).catch(() => setStatus(null))
    const id = setInterval(() => getStatus().then(setStatus).catch(() => null), 30000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round" style={{color: "var(--accent-2)"}}>
              <path d="M9 4.5a3 3 0 0 0-3 3v.4a3 3 0 0 0-2 2.83v.04A3 3 0 0 0 5 13.6V14a3 3 0 0 0 4 2.83v.67a3 3 0 0 0 3 3 3 3 0 0 0 3-3v-.67A3 3 0 0 0 19 14v-.4a3 3 0 0 0 1-2.83v-.04a3 3 0 0 0-2-2.83v-.4a3 3 0 0 0-3-3 3 3 0 0 0-3 1.2 3 3 0 0 0-3-1.2Z"/>
              <path d="M12 5.7V20"/>
              <path d="M9 9.5h1.5"/>
              <path d="M13.5 9.5H15"/>
              <path d="M9 14h6"/>
            </svg>
          </div>
          <div>
            <div className="brand-title">Personal Knowledge Companion</div>
            <div className="brand-sub">
              {status
                ? `${status.chunks_indexed?.toLocaleString("de-DE")} CHUNKS · ${status.entities_in_graph} ENTITIES`
                : "Verbinde…"}
            </div>
          </div>
        </div>
        <div className="header-right">
          <div className="model-pill">
            <span className="breathing-dot" aria-hidden="true" />
            <span>Gemma&nbsp;4</span>
            <span className="sep">·</span>
            <span>4-bit</span>
            <span className="sep">·</span>
            <span>GPU</span>
          </div>
        </div>
      </header>

      <nav className="tabs" role="tablist">
        <button
          className="tab"
          role="tab"
          aria-selected={tab === "chat"}
          onClick={() => setTab("chat")}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 6.5C4 5.12 5.12 4 6.5 4h11A2.5 2.5 0 0 1 20 6.5v7A2.5 2.5 0 0 1 17.5 16H9l-4 3.5V6.5Z"/>
          </svg>
          Chat
        </button>
        <button
          className="tab"
          role="tab"
          aria-selected={tab === "upload"}
          onClick={() => setTab("upload")}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 16V5"/>
            <path d="m7.5 9.5 4.5-4.5 4.5 4.5"/>
            <path d="M4 19h16"/>
          </svg>
          Upload
        </button>
        <button
          className="tab"
          role="tab"
          aria-selected={tab === "monitor"}
          onClick={() => setTab("monitor")}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 4h16v12H4z"/>
            <path d="M4 12l4-3 3 2 4-5 5 4"/>
            <path d="M9 20h6"/>
            <path d="M12 16v4"/>
          </svg>
          Monitor
        </button>
      </nav>

      <main className="main">
        <section className={`pane${tab === "chat" ? " active" : ""}`}>
          <Chat />
        </section>
        <section className={`pane${tab === "upload" ? " active" : ""}`}>
          <Upload />
        </section>
        <section className={`pane${tab === "monitor" ? " active" : ""}`}>
          <Monitor active={tab === "monitor"} />
        </section>
      </main>
    </div>
  )
}
