from __future__ import annotations

import logging

from fastapi import FastAPI

from src.routers import health, proxy

app = FastAPI(
    title="Runtime Knowledge Streaming API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(health.router)
app.include_router(proxy.router)
