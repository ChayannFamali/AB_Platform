import time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.logging_config import configure_logging
from app.routers import assignments, audit, auth, custom_metrics, decisions, events, experiments, flags, guardrails, health, holdouts, results, roles, segments, sse, stats, webhooks
from app.logging_config import get_logger

configure_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ab_platform_starting", version="3.0.0")
    yield
    logger.info("ab_platform_stopping")


app = FastAPI(
    title="AB Platform",
    description="Open source self-hosted A/B testing platform",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests with timing."""
    start_time = time.time()
    
    response = await call_next(request)
    
    duration_ms = (time.time() - start_time) * 1000
    
    logger.info(
        "http_request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=round(duration_ms, 2),
    )
    
    return response

@app.on_event("startup")
async def startup_event():
    logger.info("application_startup", version="1.0.0")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("application_shutdown")
    
    
app.include_router(health.router,      tags=["health"])
app.include_router(auth.router,        prefix="/api/v1", tags=["auth"])
app.include_router(experiments.router, prefix="/api/v1", tags=["experiments"])
app.include_router(assignments.router, prefix="/api/v1", tags=["assignments"])
app.include_router(events.router,      prefix="/api/v1", tags=["events"])
app.include_router(results.router,     prefix="/api/v1", tags=["results"])
app.include_router(stats.router,       prefix="/api/v1", tags=["stats"])
app.include_router(roles.router,       tags=["roles"])  # already has prefix="/api/v1"
app.include_router(audit.router,       tags=["audit"])  # already has prefix="/api/v1/audit"
app.include_router(sse.router,         tags=["sse"])    # already has prefix="/api/v1/events"
app.include_router(flags.router,        tags=["flags"])  # already has prefix="/api/v1/flags"
app.include_router(flags.sdk_router,    tags=["sdk"])    # SDK flag evaluation
app.include_router(assignments.router, prefix="/api/v1/sdk", tags=["sdk"])
app.include_router(events.router,      prefix="/api/v1/sdk", tags=["sdk"])
app.include_router(segments.router,    tags=["segments"])  # already has prefix="/api/v1/segments"
app.include_router(holdouts.router,     tags=["holdouts"])  # already has prefix="/api/v1/holdouts"
app.include_router(custom_metrics.router, tags=["custom-metrics"])  # already has prefix="/api/v1/custom-metrics"
app.include_router(guardrails.router,     tags=["guardrails"])      # already has prefix="/api/v1/experiments"
app.include_router(decisions.router,      tags=["decisions"])       # already has prefix="/api/v1/experiments"
app.include_router(webhooks.router,       tags=["webhooks"])        # already has prefix="/api/v1/webhooks"