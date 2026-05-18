# Timus-Nano — Personal Knowledge Companion

> A local, privacy-first AI knowledge system. No cloud. No telemetry. Your data stays yours.

Timus-Nano (PKC) is a fully local RAG system that indexes your documents, understands your conversations, and helps you think deeper — powered by Gemma 4 running on your own GPU.

---

## Features

- **Semantic search** over your personal vault (Qdrant vector database)
- **Knowledge graph** for entity relationships (Neo4j)
- **Conversational memory** with automatic summarization — never loses context
- **Web search** integrated via DuckDuckGo — current information flows into every answer
- **Iterative deep research** — autonomous multi-round research agent with 20,000+ word reports
- **Auto-ingestion** — reports and research are automatically indexed back into the knowledge base
- **Streaming responses** — token-by-token via Server-Sent Events
- **Glassmorphism dashboard** — React frontend with Chat, Upload and Monitor tabs

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  React Dashboard                 │
│         Chat · Upload · Monitor · Research       │
└────────────────────┬────────────────────────────┘
                     │ SSE / REST
┌────────────────────▼────────────────────────────┐
│              FastAPI Backend                     │
│   /ask/stream · /research/stream · /report       │
│   /upload · /summarize · /feedback               │
└──────┬──────────┬──────────┬────────────────────┘
       │          │          │
  ┌────▼───┐ ┌───▼────┐ ┌───▼──────┐
  │ Qdrant │ │ Neo4j  │ │ Postgres │
  │ Vectors│ │  Graph │ │  Logs    │
  └────────┘ └────────┘ └──────────┘
       │
  ┌────▼──────────────────────┐
  │  Gemma 4 · 4-bit · GPU   │
  │  Local inference only     │
  └───────────────────────────┘
```

---

## Stack

| Component | Technology |
|-----------|-----------|
| LLM | Gemma 4 4B (4-bit quantized, HuggingFace Transformers) |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 |
| Vector DB | Qdrant (local) |
| Graph DB | Neo4j 5 |
| Relational DB | PostgreSQL 15 |
| Backend | FastAPI + uvicorn |
| Frontend | React + Vite + Tailwind |
| Web Search | DuckDuckGo (no API key needed) |

---

## Token Limits

| Context | Max Tokens |
|---------|-----------|
| Chat response (stream) | 8,192 |
| Report generation | 16,384 |
| Conversation summary | 4,096 |
| Research plan | 2,048 |
| Research section (per subtopic) | 8,192 |
| Research synthesis | 16,384 |

Deep research across 5 subtopics yields up to **~50,000 tokens** of accumulated content per report.

---

## Requirements

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- NVIDIA GPU with 12GB+ VRAM (for 4-bit Gemma 4)
- Conda (recommended)

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/fatihaltiok/timus-nano.git
cd timus-nano

# 2. Environment
cp .env.example .env
# Edit .env with your settings

# 3. Python dependencies
conda create -n pkc python=3.11
conda activate pkc
pip install -r requirements.txt

# 4. Frontend dependencies
cd dashboard && npm install && cd ..

# 5. Start everything
bash start.sh
```

Dashboard: http://localhost:5173  
API Docs: http://localhost:8080/docs

---

## Configuration

Copy `.env.example` to `.env` and configure:

```env
# LLM Model (downloaded automatically from HuggingFace)
LLM_MODEL=google/gemma-4-E4B-it
LLM_MAX_TOKENS=1024

# Embedding Model
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DEVICE=cuda  # or cpu

# Databases (defaults work with docker-compose)
NEO4J_URI=bolt://localhost:7687
QDRANT_HOST=localhost
POSTGRES_HOST=localhost
```

---

## Ingest your documents

```bash
# Single file
python pkc_add.py /path/to/document.pdf

# Directory
curl -X POST http://localhost:8080/ingest/directory \
  -H "Content-Type: application/json" \
  -d '{"directory": "/path/to/vault", "extensions": [".md", ".pdf", ".txt"]}'

# Or drag & drop in the dashboard Upload tab
```

---

## Deep Research

The research agent autonomously explores a topic across multiple rounds:

1. **Planning** — identifies 3–5 subtopics
2. **Deep dives** — Vault + Web search per subtopic (4,096 tokens each)
3. **Synthesis** — full report generation (8,192 tokens)
4. **Auto-index** — report saved to `reports/` and ingested into PKC

Trigger via the **"Tiefenrecherche"** button in the Chat dashboard.

---

## License

MIT — use freely, build on it, share it.

---

*Part of the Timus ecosystem — a powerful but not limitless, consciously multi-agent assistant platform.*
