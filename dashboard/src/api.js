const BASE = "http://localhost:8080"

export async function getStatus() {
  const r = await fetch(`${BASE}/status`)
  return r.json()
}

export async function getStats() {
  const r = await fetch(`${BASE}/stats`)
  return r.json()
}

export async function getFeedbackStats() {
  const r = await fetch(`${BASE}/feedback/stats`)
  return r.json()
}

export async function summarizeConversation(messages) {
  const r = await fetch(`${BASE}/summarize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
  })
  if (!r.ok) throw new Error("Zusammenfassung fehlgeschlagen")
  return r.json()
}

export async function sendFeedback(query, rating, response, comment = "") {
  await fetch(`${BASE}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, rating, response, comment }),
  })
}

export async function uploadFile(file, onProgress) {
  const form = new FormData()
  form.append("file", file)
  const r = await fetch(`${BASE}/upload`, { method: "POST", body: form })
  if (!r.ok) {
    const err = await r.json()
    throw new Error(err.detail || "Upload fehlgeschlagen")
  }
  return r.json()
}

export function researchStream(topic, maxRounds = 5, useWeb = true, onEvent, onDone, onError) {
  const controller = new AbortController()

  fetch(`${BASE}/research/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic, max_rounds: maxRounds, use_web: useWeb }),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) throw new Error(`Server-Fehler: ${res.status}`)
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n")
        buffer = lines.pop()
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue
          try {
            const data = JSON.parse(line.slice(6))
            if (data.type === "done") onDone(data)
            else onEvent(data)
          } catch {}
        }
      }
    })
    .catch(e => { if (e.name !== "AbortError") onError(e.message) })

  return () => controller.abort()
}

export async function generateReport(topic, history = [], useWeb = true) {
  const r = await fetch(`${BASE}/report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic, history, use_web: useWeb }),
  })
  if (!r.ok) {
    const err = await r.json()
    throw new Error(err.detail || "Bericht fehlgeschlagen")
  }
  return r.json()
}

export function askStream(query, topK = 5, history = [], useWeb = true, onMeta, onToken, onDone, onError) {
  const controller = new AbortController()

  fetch(`${BASE}/ask/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, top_k: topK, history, use_web: useWeb }),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) throw new Error(`Server-Fehler: ${res.status}`)
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n")
        buffer = lines.pop()

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue
          try {
            const data = JSON.parse(line.slice(6))
            if (data.type === "meta") onMeta(data)
            else if (data.type === "token") onToken(data.text)
            else if (data.type === "done") onDone()
          } catch {}
        }
      }
    })
    .catch((e) => { if (e.name !== "AbortError") onError(e.message) })

  return () => controller.abort()
}
