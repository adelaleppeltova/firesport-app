#!/bin/bash
# Entrypoint script pro backend - spustí automatický import dat
set -e

echo "🔧 Backend entrypoint started..."

# Čekání na MongoDB
echo "⏳ Čekání na MongoDB..."
python /app/scripts/wait_for_mongodb.py

# Automatický import dat
if [ "$IMPORT_DATA" = "true" ]; then
  echo "📥 Spouštím import dat..."
  python /app/scripts/load_data.py
fi

if [ "$DEBUG" = "true" ]; then
  echo "🐞 Debug mode ON"
  exec python -m debugpy --listen 0.0.0.0:5679 \
    -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
else
  exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
fi