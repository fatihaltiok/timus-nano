import { useState, useEffect, useRef } from "react"
import { getStatus, getStats, getFeedbackStats } from "../api"

function useCountUp(target, active) {
  const [value, setValue] = useState(0)
  const startedRef = useRef(false)

  useEffect(() => {
    if (!active || startedRef.current) return
    if (!target) return
    startedRef.current = true
    const dur = 900
    const t0 = performance.now()
    function step(t) {
      const k = Math.min(1, (t - t0) / dur)
      const eased = 1 - Math.pow(1 - k, 3)
      setValue(target * eased)
      if (k < 1) requestAnimationFrame(step)
      else setValue(target)
    }
    requestAnimationFrame(step)
  }, [active, target])

  return value
}

function StatCard({ label, num, suffix, active, foot }) {
  const animated = useCountUp(num, active)

  let formatted
  if (num >= 1000) formatted = Math.round(animated).toLocaleString("de-DE")
  else if (num % 1 !== 0) formatted = animated.toFixed(1).replace(".", ",")
  else formatted = Math.round(animated).toLocaleString("de-DE")

  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-num">
        {formatted}
        {suffix && <span className="unit">{suffix}</span>}
      </div>
      {foot && <div className="stat-foot">{foot}</div>}
    </div>
  )
}

function LogRow({ entry }) {
  const ok = entry.status === "success"
  return (
    <tr className={ok ? "" : "err"}>
      <td className="ts">{entry.created_at?.slice(11, 19) ?? "—"}</td>
      <td className="event">{ok ? "indexed" : "failed"}</td>
      <td className="src">{entry.source}</td>
      <td>{entry.chunks_count ?? "—"}</td>
      <td className={ok ? "ok" : "bad"}>{ok ? "ok" : "fehler"}</td>
    </tr>
  )
}

export default function Monitor({ active }) {
  const [status, setStatus] = useState(null)
  const [stats, setStats] = useState(null)
  const [feedback, setFeedback] = useState(null)
  const [error, setError] = useState(null)
  const [lastUpdate, setLastUpdate] = useState(null)
  const [clock, setClock] = useState(() => {
    const d = new Date()
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`
  })

  const load = async () => {
    try {
      const [s, st, fb] = await Promise.all([getStatus(), getStats(), getFeedbackStats()])
      setStatus(s)
      setStats(st)
      setFeedback(fb)
      setLastUpdate(new Date().toLocaleTimeString("de-DE"))
      setError(null)
    } catch {
      setError("Backend nicht erreichbar — läuft der PKC-Server?")
    }
  }

  useEffect(() => {
    load()
    const loadId = setInterval(load, 15000)
    const clockId = setInterval(() => {
      const d = new Date()
      setClock(`${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`)
    }, 30000)
    return () => { clearInterval(loadId); clearInterval(clockId) }
  }, [])

  const chunks = status?.chunks_indexed ?? 0
  const entities = status?.entities_in_graph ?? 0
  const total = feedback?.stats?.total ?? 0
  const satisfaction = feedback?.stats?.zufriedenheit ?? 0
  const positiv = feedback?.stats?.positiv ?? 0
  const negativ = feedback?.stats?.negativ ?? 0

  return (
    <div className="monitor-wrap">
      <div className="pane-title">
        <h1>System</h1>
        <span className="sub" style={{display: "flex", alignItems: "center", gap: "8px"}}>
          <span className="breathing-dot" style={{display: "inline-block"}} />
          {error ? "OFFLINE" : `ONLINE · ${clock}`}
          {lastUpdate && !error && (
            <span style={{color: "var(--ink-4)"}}>· {lastUpdate}</span>
          )}
          <button
            onClick={load}
            style={{
              appearance: "none", background: "none", border: "none", cursor: "pointer",
              color: "var(--accent-2)", fontFamily: "var(--mono)", fontSize: "10.5px",
              letterSpacing: "0.06em", padding: "0 0 0 8px",
            }}
          >
            ↻
          </button>
        </span>
      </div>

      {error && (
        <div style={{
          background: "rgba(217,122,122,0.06)",
          border: "1px solid rgba(217,122,122,0.25)",
          borderRadius: "12px",
          padding: "12px 18px",
          marginBottom: "24px",
          fontSize: "13px",
          color: "var(--bad)",
          fontFamily: "var(--mono)",
        }}>
          {error}
        </div>
      )}

      <div className="stats">
        <StatCard
          label="Chunks"
          num={chunks}
          active={active}
          foot={<><span className="delta-up">▲ Index</span><span>aktuell</span></>}
        />
        <StatCard
          label="Entitäten"
          num={entities}
          active={active}
          foot={<><span className="delta-up">▲ Graph</span><span>aktuell</span></>}
        />
        <StatCard
          label="Zufriedenheit"
          num={satisfaction}
          suffix="%"
          active={active}
          foot={
            total > 0
              ? <><span className="delta-up">↑ {positiv}</span><span style={{color: "var(--ink-4)"}}>·</span><span>↓ {negativ}</span></>
              : <span>kein Feedback</span>
          }
        />
        <StatCard
          label="Feedback Total"
          num={total}
          active={active}
          foot={<><span>Bewertungen gesamt</span></>}
        />
      </div>

      <div className="monitor-row">
        <div className="panel">
          <div className="panel-head">
            <h3>Ingestion-Log</h3>
            <span className="status-inline">LETZTE EREIGNISSE</span>
          </div>
          <div className="panel-body">
            <table className="log">
              <thead>
                <tr>
                  <th>Zeit</th>
                  <th>Ereignis</th>
                  <th>Quelle</th>
                  <th>Chunks</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {stats?.recent_ingestions?.length > 0
                  ? stats.recent_ingestions.map((e, i) => <LogRow key={i} entry={e} />)
                  : (
                    <tr>
                      <td colSpan={5} style={{color: "var(--ink-4)", padding: "18px 22px", textAlign: "center"}}>
                        Noch keine Ingestions
                      </td>
                    </tr>
                  )
                }
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <h3>Verbesserungswürdige Anfragen</h3>
            <span className="status-inline">FEEDBACK · NEGATIV</span>
          </div>
          <div className="panel-body dist">
            {feedback?.schlechte_queries?.length > 0
              ? feedback.schlechte_queries.slice(0, 7).map((q, i) => (
                <div key={i} className="dist-row">
                  <div className="dist-name" style={{overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap"}}>
                    {q.query?.slice(0, 20) ?? "—"}
                  </div>
                  <div className="dist-bar" style={{"--w": "100%"}} />
                  <div className="dist-val">{q.created_at?.slice(5, 10) ?? "—"}</div>
                </div>
              ))
              : (
                <div style={{padding: "22px", color: "var(--ink-4)", fontSize: "12px", fontFamily: "var(--mono)"}}>
                  Keine negativen Bewertungen
                </div>
              )
            }
          </div>
        </div>
      </div>

      <div className="panel" style={{marginBottom: "28px"}}>
        <div className="panel-head">
          <h3>Index-Übersicht</h3>
          <span className="status-inline">LIVE · LOKAL</span>
        </div>
        <div className="panel-body" style={{
          padding: "22px",
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: "24px",
        }}>
          <div>
            <div className="stat-label">Chunks im Index</div>
            <div className="stat-num" style={{fontSize: "28px", marginTop: "8px"}}>
              {chunks.toLocaleString("de-DE")}
            </div>
            <div className="dist-bar" style={{"--w": "100%", marginTop: "10px"}} />
          </div>
          <div>
            <div className="stat-label">Entitäten im Graph</div>
            <div className="stat-num" style={{fontSize: "28px", marginTop: "8px"}}>
              {entities.toLocaleString("de-DE")}
            </div>
            <div className="dist-bar" style={{"--w": entities > 0 ? "60%" : "0%", marginTop: "10px"}} />
          </div>
          <div>
            <div className="stat-label">Bewertungen</div>
            <div className="stat-num" style={{fontSize: "28px", marginTop: "8px"}}>
              {total.toLocaleString("de-DE")}
            </div>
            <div className="dist-bar" style={{"--w": total > 0 ? "40%" : "0%", marginTop: "10px"}} />
          </div>
          <div>
            <div className="stat-label">Zufriedenheit</div>
            <div className="stat-num" style={{fontSize: "28px", marginTop: "8px"}}>
              {satisfaction}<span className="unit">%</span>
            </div>
            <div className="dist-bar" style={{"--w": `${satisfaction}%`, marginTop: "10px"}} />
          </div>
        </div>
      </div>
    </div>
  )
}
