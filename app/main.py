from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.rate_limiter import limiter
from app.streaming.publisher import event_publisher


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle manager."""
    # Startup: Connect to event broker (Kafka / RabbitMQ)
    await event_publisher.start()
    yield
    # Shutdown: Close connections
    await event_publisher.stop()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description=(
        "High-performance Secure Banking REST API integrated with an event-driven "
        "real-time AI/ML Fraud Detection & Risk Mitigation pipeline."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# Attach SlowAPI rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Middleware
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Register API v1 Routers (Mount at both /api/v1 and root for convenience matching PRD specs)
app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(api_router)


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Service liveness & health check."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/", tags=["Root"])
async def root() -> dict:
    """Root info endpoint."""
    return {
        "message": "Welcome to the Secure Banking API & AI Fraud Pipeline",
        "docs_url": "/docs",
        "api_v1": settings.API_V1_STR,
    }
