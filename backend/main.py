"""
QA Test Case Generator
Copyright © 2026 Arnol Ferney Pérez & Jesus Andres Cabezas
Todos los derechos reservados.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import ALLOWED_ORIGINS, OPIK_API_KEY, OPIK_WORKSPACE, OPIK_PROJECT_NAME
from backend.observability import tracer
from backend.observability.middleware import ObservabilityMiddleware
from backend.routes.generate import router
from backend.routes.evaluate import router as eval_router
from backend.utils.logging_config import configure_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    tracer.init_tracer(OPIK_API_KEY, OPIK_WORKSPACE, OPIK_PROJECT_NAME)
    logger.info("application started", extra={"event": "app_start"})
    yield
    logger.info("application shutdown", extra={"event": "app_shutdown"})


app = FastAPI(title="QA Test Case Generator", lifespan=lifespan)

# ObservabilityMiddleware must run BEFORE CORSMiddleware so request_id is
# available in all downstream handlers including preflight OPTIONS requests.
app.add_middleware(ObservabilityMiddleware)


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(eval_router)

_base_dir = os.path.dirname(__file__)
_dist_dir = os.path.join(_base_dir, "../frontend/dist")
_legacy_dir = os.path.join(_base_dir, "../frontend")

if os.path.isdir(_dist_dir):
    app.mount("/", StaticFiles(directory=_dist_dir, html=True), name="static")
else:
    app.mount("/static", StaticFiles(directory=_legacy_dir), name="static")

    @app.get("/")
    async def serve_frontend():
        return FileResponse(os.path.join(_legacy_dir, "index.html"))
