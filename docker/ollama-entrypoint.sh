#!/bin/bash
set -e

MODEL=${OLLAMA_MODEL:-llama3.2:latest}

echo "🦙 Запускаем Ollama сервер..."
ollama serve &
SERVER_PID=$!

# Используем ollama CLI для проверки готовности — он точно есть в образе
echo "⏳ Ждём готовности сервера..."
until ollama list > /dev/null 2>&1; do
  sleep 2
done

echo "Сервер готов"

# Скачиваем модель если нет
if ollama list 2>/dev/null | grep -q "${MODEL%%:*}"; then
  echo "Модель $MODEL уже загружена"
else
  echo "📥 Загружаем модель $MODEL (2GB, подождите)..."
  ollama pull "$MODEL"
  echo "Модель загружена"
fi

echo "🚀 Ollama готова: $MODEL"
wait $SERVER_PID
