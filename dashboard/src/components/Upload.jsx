import { useState, useRef } from "react"
import { uploadFile } from "../api"

const SUPPORTED = [".pdf", ".md", ".txt", ".py", ".rst", ".epub"]

function fmtSize(b) {
  if (b < 1024) return b + " B"
  if (b < 1024 * 1024) return (b / 1024).toFixed(0) + " KB"
  return (b / 1024 / 1024).toFixed(1).replace(".", ",") + " MB"
}

function FileRow({ entry }) {
  const { file, status, result, error, progress } = entry
  const base = file.name.replace(/\.[^.]+$/, "")
  const ext = file.name.includes(".") ? "." + file.name.split(".").pop() : ""

  let chunksText = "wartet"
  if (status === "done" && result) chunksText = `${result.chunks_hinzugefuegt} Chunks`
  else if (status === "loading") chunksText = `— · ${Math.round(progress)}%`
  else if (status === "error") chunksText = error?.slice(0, 22) || "Fehler"

  let stateText = "in queue"
  if (status === "done") stateText = "indiziert"
  else if (status === "loading") stateText = "indexing"
  else if (status === "error") stateText = "fehler"

  return (
    <div className="file-row" data-status={status} style={{"--p": `${progress ?? 0}%`}}>
      <span className="status-dot" />
      <span className="file-name">
        {base}<span className="ext">{ext}</span>
      </span>
      <span className="file-size">{fmtSize(file.size)}</span>
      <span className="file-chunks">{chunksText}</span>
      <span className="file-state" data-status={status}>{stateText}</span>
      <div className="file-progress" />
    </div>
  )
}

export default function Upload() {
  const [files, setFiles] = useState([])
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)

  const processFiles = async (newFiles) => {
    const entries = Array.from(newFiles).map(f => ({
      id: `${f.name}-${Date.now()}-${Math.random()}`,
      file: f,
      status: "loading",
      result: null,
      error: null,
      progress: 5,
    }))

    setFiles(prev => [...entries, ...prev])

    for (const entry of entries) {
      const tick = setInterval(() => {
        setFiles(prev => prev.map(f =>
          f.id === entry.id && f.status === "loading"
            ? { ...f, progress: Math.min(f.progress + 7 + Math.random() * 6, 90) }
            : f
        ))
      }, 320)

      try {
        const result = await uploadFile(entry.file)
        clearInterval(tick)
        setFiles(prev => prev.map(f =>
          f.id === entry.id ? { ...f, status: "done", progress: 100, result } : f
        ))
      } catch (e) {
        clearInterval(tick)
        setFiles(prev => prev.map(f =>
          f.id === entry.id ? { ...f, status: "error", progress: 0, error: e.message } : f
        ))
      }
    }
  }

  const totalChunks = files.reduce((s, f) => s + (f.result?.chunks_hinzugefuegt ?? 0), 0)

  return (
    <div className="upload-wrap">
      <div className="pane-title">
        <h1>Wissen hinzufügen</h1>
        <span className="sub">LOKAL · KEINE CLOUD · KEINE TELEMETRIE</span>
      </div>

      <label
        className={`dropzone${dragging ? " is-drag" : ""}`}
        htmlFor="file-input"
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => { e.preventDefault(); setDragging(false); processFiles(e.dataTransfer.files) }}
      >
        <input
          id="file-input"
          ref={inputRef}
          type="file"
          multiple
          style={{display: "none"}}
          accept={SUPPORTED.join(",")}
          onChange={e => { processFiles(e.target.files); e.target.value = "" }}
        />
        <div className="dz-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z"/>
            <path d="M14 3v5h5"/>
            <path d="M12 18v-6"/>
            <path d="m9 15 3-3 3 3"/>
          </svg>
        </div>
        <div className="dz-title">Dateien hier ablegen</div>
        <div className="dz-sub">oder klicken zum Auswählen — PKC indexiert automatisch</div>
        <div className="dz-formats">
          {SUPPORTED.map(s => <span key={s}>{s}</span>)}
        </div>
      </label>

      {files.length > 0 && (
        <div className="queue">
          <div className="queue-head">
            <h3>Warteschlange</h3>
            <span className="count">
              {files.length} DATEIEN
              {totalChunks > 0 && ` · ${totalChunks.toLocaleString("de-DE")} CHUNKS INDIZIERT`}
            </span>
          </div>
          <div>
            {files.map(f => <FileRow key={f.id} entry={f} />)}
          </div>
        </div>
      )}
    </div>
  )
}
