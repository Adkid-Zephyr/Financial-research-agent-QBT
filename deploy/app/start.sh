#!/bin/sh
set -eu

mkdir -p /app/outputs /app/logs /app/memory

if [ -n "${DATABASE_URL:-}" ]; then
  echo "Waiting for PostgreSQL to become available..."
  until python -c "from sqlalchemy import create_engine; engine = create_engine('${DATABASE_URL}'); connection = engine.connect(); connection.close()"; do
    sleep 2
  done
fi

exec uvicorn "${APP_MODULE:-futures_research.api.app:app}" \
  --host "${APP_HOST:-0.0.0.0}" \
  --port "${APP_PORT:-8000}"
