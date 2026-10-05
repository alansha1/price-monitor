"""
Application entry point.
Initialises the database, mounts the router, and starts the background scheduler.
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine
from app import models
from app.routes import router
from app.scheduler import start_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCHEDULER_INTERVAL = int(os.getenv("POLL_INTERVAL_MINUTES", "60"))


# Run setup work when the app starts and stop background tasks when it shuts down.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    models.Base.metadata.create_all(bind=engine)
    logger.info("Database tables created / verified.")
    scheduler = start_scheduler(interval_minutes=SCHEDULER_INTERVAL)
    yield
    # ── Shutdown ──────────────────────────────────────────────────────────────
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped.")


app = FastAPI(
    title="Price Monitor API",
    description=(
        "Track product prices over time, query history, and set threshold alerts. "
        "Prices are polled automatically in the background via a configurable scheduler."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


# Simple check to confirm the API is running.
@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "message": "Price Monitor API is running."}


# Quick health endpoint for basic service checks.
@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy"}
