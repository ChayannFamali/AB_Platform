# AB Platform

Open source, self-hosted A/B testing platform.  
Deploy in one command. Start testing in minutes.

![CI](https://github.com/your-org/ab-platform/actions)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![FastAPI](https://img.shields.io/badge/fastapi-0.109%2B-green)

---

## The problem

Your team wants to test hypotheses — does the red button convert better than blue?  
Does the new ranking algorithm increase revenue?

Commercial solutions (Optimizely, LaunchDarkly) cost tens of thousands of dollars  
per year and send your data to external servers.

**AB Platform gives you the same for free, inside your own infrastructure.**

---

## Quick start

```bash
# 1. Clone
git clone https://github.com/your-org/ab-platform
cd ab-platform

# 2. Configure
cp .env.example .env
# Edit .env: set POSTGRES_PASSWORD and SECRET_KEY

# 3. Run
docker compose up -d

# 4. Open
# UI:     http://localhost
# API:    http://localhost:8000
# Docs:   http://localhost:8000/docs
```

First visit → register → you're the admin.  
Create an API key at http://localhost/api-keys

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         AB Platform                             │
├─────────────────┬───────────────────┬───────────────────────────┤
│    Frontend     │    Backend API    │          Worker           │
│  React 18+Vite  │ FastAPI+uvicorn   │     ARQ (async queue)     │
│  nginx proxy    │   structlog       │  Cron: analysis hourly    │
│  Recharts       │   PyJWT auth      │  Cron: daily snapshots    │
└────────┬────────┴────────┬──────────┴───────────┬───────────────┘
         │                 │                       │
         │         ┌───────▼────────┐    ┌────────▼────────┐
         │         │  PostgreSQL 16 │    │    Redis 7      │
         │         │                │    │                 │
         │         │ experiments    │    │ task queue      │
         │         │ assignments    │    │ assignment cache│
         │         │ events ───────►│    │ AOF persistence │
         │         │  (partitioned  │    └─────────────────┘
         │         │   by month)    │
         │         │ results        │
         │         │ results_daily  │
         │         └────────────────┘
         │
         ▼
┌────────────────┐    ┌────────────────┐
│   Python SDK   │    │    JS SDK      │
│  pip install   │    │  npm install   │
│  abplatform    │    │  abplatform    │
└────────────────┘    └────────────────┘
```

---

## How it works

```
Analyst                Developer               Platform
   │                       │                       │
   │  Create experiment    │                       │
   │──────────────────────►│                       │
   │                       │  get_variant(user_id) │
   │                       │──────────────────────►│ deterministic bucketing
   │                       │◄──────────────────────│ "treatment"
   │                       │                       │
   │                       │  track_event("click") │
   │                       │──────────────────────►│ append to events
   │                       │                       │
   │  Analyze              │                       │ hourly cron
   │──────────────────────────────────────────────►│ stats engine
   │◄──────────────────────────────────────────────│ p-value, CI, winner
   │                       │                       │
```

---

## SDK

### Python

```python
from abplatform import ABPlatformClient

client = ABPlatformClient(
    api_url="http://your-server",
    api_key="abp_xxx",
)

# Get variant (cached, < 1ms after first call)
variant = client.get_variant(user_id, experiment_id, default="control")

if variant == "treatment":
    show_new_feature()

# Track event (batched, async flush)
client.track_event(user_id, "purchase", value=49.99)

client.close()
```

### JavaScript

```javascript
const { ABPlatformClient } = require('abplatform')

const client = new ABPlatformClient({
  apiUrl: 'http://your-server',
  apiKey: 'abp_xxx',
})

const variant = await client.getVariant(userId, experimentId, 'control')

if (variant === 'treatment') showNewFeature()

client.trackEvent(userId, 'purchase', 49.99)
```

---

## Statistics engine

The platform automatically selects the correct statistical test:

| Metric type          | Test                                           |
|----------------------|------------------------------------------------|
| Conversion           | Z-test for proportions                         |
| Revenue/Duration     | Shapiro-Wilk → Welch t-test or Mann-Whitney   |
| Ratio (X/Y)          | Delta method (Taylor linearization)            |

### Why Delta method matters:

Naive t-test on ratio metrics (e.g. "revenue per session") ignores  
the covariance between numerator and denominator — producing incorrect p-values.

The delta method linearizes each observation:

```
θ = Σ(X) / Σ(Y)          ← ratio estimate
Z_i = X_i − θ · Y_i      ← linearized per-user observation
t-test on Z_control vs Z_treatment
```

### Additional protections:

- **SRM check** — chi-squared test detects broken assignment logic
- **BH correction** — controls false discovery rate across multiple metrics
- **Achieved MDE** — for non-significant results: "we would have seen ≥ X% effect if it existed"
- **Decomposition** — for ratio metrics: shows numerator and denominator lift separately

---

## Optional AI interpretation

```bash
# With local LLM (Ollama)
docker compose -f docker-compose.yml -f docker-compose.ai.yml up -d

# With OpenAI
AI_PROVIDER=openai OPENAI_API_KEY=sk-... docker compose up -d
```

---

## Development

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
docker compose up postgres redis -d
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Worker (separate terminal)
python -m arq app.worker.WorkerSettings

# Frontend
cd frontend && npm install && npm run dev
```

---

## Tests

```bash
# Unit tests — stats engine (no DB required)
cd backend && PYTHONPATH=. pytest tests/test_stats.py -v

# Integration tests (requires running PostgreSQL)
cd backend && PYTHONPATH=. pytest tests/test_integration.py -v

# SDK tests
cd sdk/python && pytest tests/ -v
cd sdk/js && npm test
```

## License

MIT

---

## Dependencies

### requirements.txt

```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
sqlalchemy>=2.0.25
asyncpg>=0.29.0
alembic>=1.13.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
python-multipart>=0.0.6
redis>=5.0.0
arq>=0.25.0
structlog>=24.0.0
scipy>=1.11.0
numpy>=1.26.0
```