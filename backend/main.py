"""
QA Test Case Generator
Copyright © 2026 Arnol Ferney Pérez & Jesus Andres Cabezas
Todos los derechos reservados.
"""

import logging
import os
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import ALLOWED_ORIGINS
from backend.routes.generate import router
from backend.routes.evaluate import router as eval_router
from backend.utils.logging_config import configure_logging, set_request_id

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Called AFTER uvicorn has applied its own dictConfig, so our config wins.
    configure_logging()
    logger.info("application started", extra={"event": "app_start"})
    yield
    logger.info("application shutdown", extra={"event": "app_shutdown"})


app = FastAPI(title="QA Test Case Generator", lifespan=lifespan)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Stamp every request with a unique ID visible in all downstream logs."""
    rid = request.headers.get("X-Request-ID") or uuid4().hex[:12]
    set_request_id(rid)
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(eval_router)

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "../frontend")), name="static")


@app.get("/")
async def serve_frontend():
    return FileResponse(os.path.join(os.path.dirname(__file__), "../frontend/index.html"))
