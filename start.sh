#!/bin/bash
# PKC starten — Backend + Frontend
# Ausführen: bash start.sh

PKC_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🧠 PKC wird gestartet..."
echo ""

# Docker-Container prüfen
if ! docker compose ps --quiet 2>/dev/null | grep -q .; then
  echo "▶ Docker-Container starten..."
  docker compose up -d
  sleep 5
fi

# FastAPI Backend
echo "▶ Backend starten (Port 8080)..."
cd "$PKC_DIR"
conda run -n pkc uvicorn src.api.main:app --host 0.0.0.0 --port 8080 &
BACKEND_PID=$!

# React Frontend
echo "▶ Frontend starten (Port 5173)..."
cd "$PKC_DIR/dashboard"
npm run dev -- --host 0.0.0.0 --port 5173 &
FRONTEND_PID=$!

echo ""
echo "✓ PKC läuft:"
echo "  Dashboard:  http://localhost:5173"
echo "  API:        http://localhost:8080"
echo "  API-Docs:   http://localhost:8080/docs"
echo ""
echo "  Zum Beenden: Ctrl+C"

# Beide Prozesse beenden wenn Ctrl+C gedrückt wird
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'PKC gestoppt.'" EXIT
wait
