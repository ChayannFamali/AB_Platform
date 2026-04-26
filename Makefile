.PHONY: up down dev logs ps clean

# ── Продакшн ──────────────────────────────────────
up:
	docker compose up -d --build
	@echo "Платформа запущена"
	@echo "   UI:  http://localhost"
	@echo "   API: http://localhost:8000"
	@echo "   Docs: http://localhost:8000/docs"

down:
	docker compose down

logs:
	docker compose logs -f

ps:
	docker compose ps

clean:
	docker compose down -v --remove-orphans

# ── Разработка ────────────────────────────────────
dev-api:
	cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

dev-worker:
	cd backend && source .venv/bin/activate && python -m arq app.worker.WorkerSettings

# ── AI вариант ────────────────────────────────────
up-ai:
	docker compose -f docker-compose.yml -f docker-compose.ai.yml up -d --build

# ── Утилиты ──────────────────────────────────────
migrate:
	cd backend && source .venv/bin/activate && alembic upgrade head

test-backend:
	cd backend && source .venv/bin/activate && PYTHONPATH=. pytest tests/ -v

test-sdk-py:
	cd sdk/python && pytest tests/ -v

test-sdk-js:
	cd sdk/js && npm test


up-ai:
	docker compose -f docker-compose.yml -f docker-compose.ai.yml up -d --build
	@echo "Платформа + Ollama запущены"
	@echo "   Ollama: http://localhost:11434"
	@echo "     Первый запуск: модель загружается, подождите 5-10 мин"

logs-ollama:
	docker compose logs -f ollama
