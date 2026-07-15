from __future__ import annotations

import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

from fastapi import FastAPI

from vcase.routers import health, proxy

app = FastAPI(
    title="Runtime Knowledge Streaming API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(health.router)
app.include_router(proxy.router)
