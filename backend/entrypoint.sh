#!/bin/bash
set -e

echo "Применяем миграции..."
alembic upgrade head

if [ "$#" -gt 0 ]; then
    echo "Запускаем: $*"
    exec "$@"
else
    echo "Запускаем API..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi
