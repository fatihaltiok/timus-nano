import { useState, useRef, useEffect, useCallback } from "react"
import { askStream, sendFeedback, summarizeConversation, generateReport, researchStream } from "../api"

// Anzahl abgeschlossener Austausche, ab der zusammengefasst wird
const SUMMARY_THRESHOLD = 8   // 4 user + 4 ai = 8 abgeschlossene Nachrichten
const KEEP_RECENT = 4         // Letzte 2 Austausche (4 Nachrichten) immer als Volltext

function SummaryBlock({ summary, open, onToggle }) {
  return (
    <div style={{
      margin: "0 0 28px",
      border: "1px solid var(--line)",
      borderRadius: "12px",
      background: "rgba(124,111,205,0.04)",
      overflow: "hidden",
    }}>
      <button
        onClick={onToggle}
        style={{
          width: "100%", appearance: "none", background: "none", border: "none",
          cursor: "pointer", padding: "12px 18px",
          display: "flex", alignItems: "center", justifyContent: "space-between",
          color: "var(--ink-3)", fontFamily: "var(--mono)", fontSize: "11.5px",
          letterSpacing: "0.08em", textTransform: "uppercase",
        }}
      >
        <span style={{display: "flex", alignItems: "center", gap: "10px"}}>
          <span style={{color: "var(--accent-2)"}}>◈</span>
          Gesprächszusammenfassung
        </span>
        <span style={{
          display: "inline-block",
          transform: open ? "rotate(90deg)" : "none",
          transition: "transform 220ms ease",
          color: "var(--accent)",
        }}>›</span>
      </button>
      {open && (
        <div style={{
          padding: "4px 18px 16px",
          borderTop: "1px solid var(--line-2)",
          fontSize: "14px",
          lineHeight: "1.75",
          color: "var(--ink-2)",
          whiteSpace: "pre-wrap",
        }}>
          {summary}
        </div>
      )}
    </div>
  )
}

function SourceCard({ source, score, url, web }) {
  const pct = Math.round((score ?? 0) * 100)
  return (
    <div className="source-card">
      <div className="src-name">
        {web && <span style={{color: "var(--good)", fontSize: "9px", marginRight: "6px", fontFamily: "var(--mono)"}}>WEB</span>}
        {url ? <a href={url} target="_blank" rel="noopener noreferrer" style={{color: "inherit", textDecoration: "none"}}>{source}</a> : source}
      </div>
      <div className="src-pct" style={{color: web ? "var(--good)" : "var(--accent-2)"}}>
        {web ? "↗" : `${pct}%`}
      </div>
      <div className="src-meta">{web ? url?.replace(/^https?:\/\//, "").split("/")[0] : "Vault"}</div>
      <div />
      {!web && <div className="src-bar" style={{"--w": `${pct}%`}} />}
    </div>
  )
}

function SerendipityChip({ concept, connected_to }) {
  return (
    <button className="chip">
      <span className="dia">◆</span>
      {concept}
      {connected_to && <span style={{color: "var(--ink-4)", marginLeft: "4px"}}>via {connected_to}</span>}
    </button>
  )
}

function AiMessage({ msg, onFeedback }) {
  const [rated, setRated] = useState(null)
  const [sourcesOpen, setSourcesOpen] = useState(false)

  const handleRating = async (rating) => {
    if (rated !== null) return
    setRated(rating)
    await sendFeedback(msg.query, rating, msg.text)
    onFeedback?.(rating)
  }

  return (
    <div className="msg-row msg-ai">
      <div className="ai-meta">
        PKC
        {msg.latencyMs ? ` · ${(msg.latencyMs / 1000).toFixed(1)} s` : ""}
        {msg.sources?.length ? ` · ${msg.sources.length} Quellen` : ""}
      </div>

      <div className="ai-body">
        {msg.text && (
          <p>
            {msg.text}
            {msg.streaming && <span className="stream-cursor" />}
          </p>
        )}
      </div>

      {!msg.streaming && msg.text && (
        <div className="ai-actions">
          <button
            title="Hilfreich"
            onClick={() => handleRating(1)}
            disabled={rated !== null}
            style={{opacity: rated === -1 ? 0.3 : 1}}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M7 11v9H4v-9h3Zm0 0 4-7c1 0 2 1 2 2v3h5a2 2 0 0 1 2 2.4l-1.5 7A2 2 0 0 1 16.5 20H7"/>
            </svg>
          </button>
          <button
            title="Nicht hilfreich"
            onClick={() => handleRating(-1)}
            disabled={rated !== null}
            style={{opacity: rated === 1 ? 0.3 : 1}}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{transform: "rotate(180deg)"}}>
              <path d="M7 11v9H4v-9h3Zm0 0 4-7c1 0 2 1 2 2v3h5a2 2 0 0 1 2 2.4l-1.5 7A2 2 0 0 1 16.5 20H7"/>
            </svg>
          </button>
          {rated !== null && <span className="thankyou">Danke!</span>}
        </div>
      )}

      {msg.sources?.length > 0 && (
        <div className="sources">
          <button
            className="sources-toggle"
            aria-expanded={sourcesOpen}
            onClick={() => setSourcesOpen(v => !v)}
          >
            <span className="caret">›</span> {msg.sources.length} Quellen
          </button>
          <div className="sources-list">
            {msg.sources.map((s, i) => <SourceCard key={i} {...s} />)}
          </div>
        </div>
      )}

      {msg.suggestions?.length > 0 && (
        <div className="serendipity">
          <span className="serendipity-label">Serendipity</span>
          {msg.suggestions.map((s, i) => <SerendipityChip key={i} {...s} />)}
        </div>
      )}
    </div>
  )
}

export default function Chat() {
  const [messages, setMessages] = useState([])
  const [summary, setSummary] = useState(null)
  const [summaryOpen, setSummaryOpen] = useState(false)
  const [summarizing, setSummarizing] = useState(false)
  const [input, setInput] = useState("")
  const [busy, setBusy] = useState(false)
  const [useWeb, setUseWeb] = useState(true)
  const [reportState, setReportState] = useState(null)
  const [research, setResearch] = useState(null)  // null | {active, log, result}
  const bottomRef = useRef(null)
  const textareaRef = useRef(null)
  const summaryInProgress = useRef(false)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  // Auto-Summarization: wenn genug abgeschlossene Nachrichten da sind
  useEffect(() => {
    const completed = messages.filter(m => !m.thinking && !m.streaming && m.text)
    if (
      completed.length >= SUMMARY_THRESHOLD &&
      !busy &&
      !summaryInProgress.current
    ) {
      triggerSummarization(completed)
    }
  }, [messages, busy])

  const triggerSummarization = useCallback(async (completed) => {
    // Nur die älteren Nachrichten zusammenfassen (nicht die letzten KEEP_RECENT)
    const toSummarize = completed.slice(0, completed.length - KEEP_RECENT)
    if (toSummarize.length < 4) return   // Mindestens 2 Austausche nötig

    summaryInProgress.current = true
    setSummarizing(true)

    try {
      const historyForSummary = toSummarize.map(m => ({
        role: m.type === "user" ? "user" : "assistant",
        content: m.text,
      }))

      // Bestehende Zusammenfassung einbeziehen wenn vorhanden
      const messagesForSummary = summary
        ? [
            { role: "user", content: `[Bisherige Zusammenfassung:\n${summary}]` },
            { role: "assistant", content: "Verstanden." },
            ...historyForSummary,
          ]
        : historyForSummary

      const result = await summarizeConversation(messagesForSummary)
      setSummary(result.summary)
      setSummaryOpen(false)

      // Zusammengefasste Nachrichten aus dem State entfernen
      const idsToRemove = new Set(toSummarize.map(m => m.id))
      setMessages(prev => prev.filter(m => !idsToRemove.has(m.id)))
    } catch (e) {
      console.error("Zusammenfassung fehlgeschlagen:", e)
    } finally {
      setSummarizing(false)
      summaryInProgress.current = false
    }
  }, [summary])

  const buildHistory = useCallback((currentMessages) => {
    const completed = currentMessages.filter(m => !m.thinking && !m.streaming && m.text)
    const recent = completed.slice(-10).map(m => ({
      role: m.type === "user" ? "user" : "assistant",
      content: m.text,
    }))

    // Zusammenfassung als Kontext-Anker voranstellen
    if (summary) {
      return [
        { role: "user", content: `[Gesprächszusammenfassung — enthält alle früheren Themen, Ideen und Erkenntnisse:\n${summary}]` },
        { role: "assistant", content: "Ich habe die Zusammenfassung des bisherigen Gesprächs und setze mit diesem vollständigen Kontext fort." },
        ...recent,
      ]
    }

    return recent
  }, [summary])

  const handleResearch = () => {
    if (busy || research?.active) return
    const lastUser = [...messages].reverse().find(m => m.type === "user")
    const topic = lastUser?.text || input || "Aktuelles Thema"
    setResearch({ active: true, topic, log: [], result: null })

    researchStream(
      topic,
      5,
      useWeb,
      (event) => setResearch(prev => ({
        ...prev,
        log: [...(prev?.log || []), event],
      })),
      (result) => setResearch(prev => ({
        ...prev,
        active: false,
        result,
        log: [...(prev?.log || []), result],
      })),
      (err) => setResearch(prev => ({
        ...prev,
        active: false,
        error: err,
      })),
    )
  }

  const handleReport = async () => {
    if (busy || reportState === "loading") return
    // Thema aus letzter Nutzerfrage ableiten
    const lastUser = [...messages].reverse().find(m => m.type === "user")
    const topic = lastUser?.text || input || "Aktuelles Gesprächsthema"
    setReportState("loading")
    try {
      const history = buildHistory(messages)
      const result = await generateReport(topic, history, useWeb)
      setReportState({ filename: result.filename, filepath: result.filepath })
      setTimeout(() => setReportState(null), 8000)
    } catch (e) {
      setReportState({ error: e.message })
      setTimeout(() => setReportState(null), 5000)
    }
  }

  const autoSize = () => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = "auto"
    ta.style.height = Math.min(ta.scrollHeight, 200) + "px"
  }

  const submit = (e) => {
    e?.preventDefault()
    if (!input.trim() || busy) return
    const query = input.trim()
    setInput("")
    setBusy(true)
    setTimeout(autoSize, 0)

    const uid = `u-${Date.now()}`
    const aid = `a-${Date.now()}`

    // History VOR setMessages bauen — nie innerhalb des Callbacks
    const history = buildHistory(messages)

    setMessages(prev => [
      ...prev,
      { id: uid, type: "user", text: query },
      { id: aid, type: "ai", query, text: "", thinking: true, streaming: false, sources: [], suggestions: [], latencyMs: 0 },
    ])

    const startMs = Date.now()
    const update = (patch) =>
      setMessages(msgs => msgs.map(m => m.id === aid ? { ...m, ...patch } : m))

    askStream(
      query,
      5,
      history,
      useWeb,
      (meta) => update({
        sources: meta.sources ?? [],
        suggestions: meta.suggestions ?? [],
        thinking: false,
        streaming: true,
      }),
      (token) => setMessages(msgs =>
        msgs.map(m => m.id === aid ? { ...m, text: (m.text || "") + token } : m)
      ),
      () => {
        update({ streaming: false, latencyMs: Date.now() - startMs })
        setBusy(false)
      },
      (err) => {
        update({ text: `Fehler: ${err}`, thinking: false, streaming: false })
        setBusy(false)
      },
    )
  }

  return (
    <div style={{display: "flex", flexDirection: "column", height: "100%"}}>
      <div className="chat-scroll">
        {messages.length === 0 && !summary ? (
          <div className="chat-empty">
            <div className="glyph">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="3"/>
                <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M5.6 18.4 7 17M17 7l1.4-1.4"/>
              </svg>
            </div>
            <h2>Stelle mir eine Frage über dein Wissen</h2>
            <p>Semantische Suche über deinen lokalen Vault — keine Cloud, keine Telemetrie.</p>
          </div>
        ) : (
          <>
            {/* Zusammenfassung älterer Nachrichten */}
            {summary && (
              <SummaryBlock
                summary={summary}
                open={summaryOpen}
                onToggle={() => setSummaryOpen(v => !v)}
              />
            )}

            {/* Research-Panel */}
            {research && (
              <div style={{
                margin: "0 0 24px",
                border: "1px solid var(--line)",
                borderRadius: "14px",
                background: "rgba(124,111,205,0.04)",
                overflow: "hidden",
              }}>
                <div style={{
                  padding: "14px 18px",
                  borderBottom: "1px solid var(--line-2)",
                  display: "flex", alignItems: "center", justifyContent: "space-between",
                }}>
                  <span style={{
                    fontFamily: "var(--mono)", fontSize: "11.5px",
                    letterSpacing: "0.08em", textTransform: "uppercase",
                    color: research.active ? "var(--accent-2)" : "var(--good)",
                    display: "flex", alignItems: "center", gap: "10px",
                  }}>
                    {research.active
                      ? <span className="typing"><span className="dots"><span /><span /><span /></span></span>
                      : <span>✓</span>
                    }
                    Tiefenrecherche — {research.topic?.slice(0, 50)}
                  </span>
                  {!research.active && (
                    <button onClick={() => setResearch(null)} style={{
                      appearance: "none", background: "none", border: "none",
                      cursor: "pointer", color: "var(--ink-4)", fontSize: "16px",
                    }}>×</button>
                  )}
                </div>
                <div style={{padding: "12px 18px", maxHeight: "260px", overflowY: "auto"}}>
                  {research.log.map((e, i) => (
                    <div key={i} style={{
                      display: "flex", gap: "10px", alignItems: "flex-start",
                      padding: "4px 0", borderBottom: "1px solid var(--line-2)",
                      fontSize: "12.5px",
                    }}>
                      <span style={{
                        fontFamily: "var(--mono)", fontSize: "10px",
                        color: e.type === "done" ? "var(--good)"
                          : e.type === "section" ? "var(--accent-2)"
                          : e.type === "plan" ? "var(--warn)"
                          : "var(--ink-4)",
                        flexShrink: 0, paddingTop: "2px",
                      }}>
                        {e.type === "done" ? "✓" : e.type === "section" ? "§" : e.type === "plan" ? "▸" : "·"}
                      </span>
                      <span style={{color: "var(--ink-2)"}}>{e.message}</span>
                      {e.type === "section" && (
                        <span style={{marginLeft: "auto", fontFamily: "var(--mono)", fontSize: "10px", color: "var(--ink-4)", flexShrink: 0}}>
                          ~{e.tokens?.toLocaleString("de-DE")} W
                        </span>
                      )}
                    </div>
                  ))}
                </div>
                {research.result && (
                  <div style={{
                    padding: "12px 18px",
                    borderTop: "1px solid var(--line-2)",
                    display: "flex", gap: "20px", flexWrap: "wrap",
                    fontFamily: "var(--mono)", fontSize: "11px", color: "var(--ink-3)",
                  }}>
                    <span><span style={{color: "var(--good)"}}>✓</span> {research.result.sections} Abschnitte</span>
                    <span>~{research.result.total_words?.toLocaleString("de-DE")} Wörter</span>
                    <span>{research.result.sources} Quellen</span>
                    <span style={{color: "var(--accent-2)"}}>{research.result.filename}</span>
                  </div>
                )}
              </div>
            )}

            {/* Laufende Zusammenfassung */}
            {summarizing && (
              <div style={{
                margin: "0 0 20px",
                padding: "10px 18px",
                borderRadius: "10px",
                border: "1px solid var(--line)",
                background: "rgba(124,111,205,0.04)",
                display: "flex", alignItems: "center", gap: "12px",
                fontSize: "13px", color: "var(--ink-3)",
                fontFamily: "var(--mono)",
              }}>
                <span className="typing">
                  <span className="dots"><span /><span /><span /></span>
                </span>
                Erstelle Gesprächszusammenfassung…
              </div>
            )}

            {/* Nachrichten */}
            {messages.map(msg => {
              if (msg.type === "user") {
                return (
                  <div key={msg.id} className="msg-row msg-user">
                    <div className="bubble">{msg.text}</div>
                  </div>
                )
              }
              if (msg.thinking) {
                return (
                  <div key={msg.id} className="typing-row">
                    <span className="typing">
                      <span className="dots"><span /><span /><span /></span>
                      <em>PKC denkt nach…</em>
                    </span>
                  </div>
                )
              }
              return <AiMessage key={msg.id} msg={msg} />
            })}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="dock">
        <form className="composer" onSubmit={submit}>
          <textarea
            ref={textareaRef}
            value={input}
            rows={1}
            placeholder="Frag PKC… (Enter zum Senden, Shift+Enter für neue Zeile)"
            onChange={e => { setInput(e.target.value); autoSize() }}
            onKeyDown={e => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit() }
            }}
          />
          <button className="send-btn" type="submit" disabled={busy || !input.trim()}>
            Senden
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12h14"/>
              <path d="m13 6 6 6-6 6"/>
            </svg>
          </button>
        </form>
        <div className="dock-hints">
          <span style={{display: "flex", alignItems: "center", gap: "14px"}}>
            {/* Web-Toggle */}
            <button
              onClick={() => setUseWeb(v => !v)}
              title={useWeb ? "Web-Suche aktiv — klicken zum Deaktivieren" : "Web-Suche inaktiv — klicken zum Aktivieren"}
              style={{
                appearance: "none", background: "none", border: "none", cursor: "pointer",
                display: "flex", alignItems: "center", gap: "6px",
                fontFamily: "var(--mono)", fontSize: "11px", letterSpacing: "0.04em",
                color: useWeb ? "var(--good)" : "var(--ink-4)",
                padding: 0,
              }}
            >
              <span style={{
                width: "6px", height: "6px", borderRadius: "50%",
                background: useWeb ? "var(--good)" : "var(--ink-4)",
                boxShadow: useWeb ? "0 0 6px var(--good)" : "none",
              }} />
              WEB {useWeb ? "AN" : "AUS"}
            </button>

            {summary && <span style={{color: "var(--accent)", fontFamily: "var(--mono)", fontSize: "11px"}}>◈ Zusammenfassung aktiv</span>}

            {/* Tiefenrecherche-Button */}
            <button
              onClick={handleResearch}
              disabled={busy || research?.active || messages.length === 0}
              title="Iterative Tiefenrecherche — mehrere Runden, Web + Vault, automatisch indexiert"
              style={{
                appearance: "none", background: "none",
                border: "1px solid rgba(124,111,205,0.3)",
                borderRadius: "6px", cursor: "pointer",
                display: "flex", alignItems: "center", gap: "6px",
                fontFamily: "var(--mono)", fontSize: "11px", letterSpacing: "0.04em",
                color: research?.active ? "var(--accent-2)" : "var(--accent)",
                padding: "3px 8px",
                opacity: (busy || messages.length === 0) ? 0.4 : 1,
              }}
            >
              {research?.active ? (
                <><span className="typing"><span className="dots"><span /><span /><span /></span></span> Recherche läuft…</>
              ) : (
                <>
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
                    <path d="M11 8v6M8 11h6"/>
                  </svg>
                  Tiefenrecherche
                </>
              )}
            </button>

            {/* Bericht-Button */}
            <button
              onClick={handleReport}
              disabled={busy || reportState === "loading" || messages.length === 0}
              title="Bericht zum aktuellen Thema erstellen und in PKC speichern"
              style={{
                appearance: "none", background: "none", border: "1px solid var(--line)",
                borderRadius: "6px", cursor: "pointer",
                display: "flex", alignItems: "center", gap: "6px",
                fontFamily: "var(--mono)", fontSize: "11px", letterSpacing: "0.04em",
                color: reportState === "loading" ? "var(--accent-2)" : "var(--ink-3)",
                padding: "3px 8px",
                transition: "color 200ms, border-color 200ms",
                opacity: (busy || messages.length === 0) ? 0.4 : 1,
              }}
            >
              {reportState === "loading" ? (
                <><span className="typing"><span className="dots"><span /><span /><span /></span></span> Bericht…</>
              ) : reportState?.filename ? (
                <><span style={{color: "var(--good)"}}>✓</span> {reportState.filename}</>
              ) : reportState?.error ? (
                <><span style={{color: "var(--bad)"}}>✗</span> Fehler</>
              ) : (
                <>
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z"/>
                    <path d="M14 3v5h5"/><path d="M9 12h6"/><path d="M9 16h4"/>
                  </svg>
                  Bericht erstellen
                </>
              )}
            </button>
          </span>

          <span>
            <kbd>↵</kbd> Senden &nbsp; <kbd>⇧ ↵</kbd> Neue Zeile
          </span>
        </div>
      </div>
    </div>
  )
}
