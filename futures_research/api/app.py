from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
import os
from pathlib import Path
from typing import AsyncIterator, Optional

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from futures_research import config
from futures_research.api.routes import events_router, reports_router, runs_router
from futures_research.events import EventBus, get_event_bus
from futures_research.main import run_research
from futures_research.scheduler import run_batch_research
from futures_research.storage import ReportRepository, build_report_repository

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(repository: Optional[ReportRepository] = None, event_bus: Optional[EventBus] = None) -> FastAPI:
    resolved_repository = repository if repository is not None else build_report_repository()
    resolved_event_bus = event_bus if event_bus is not None else get_event_bus()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            repository = getattr(app.state, "report_repository", None)
            if repository is not None and hasattr(repository, "close"):
                repository.close()

    app = FastAPI(title="Futures Research API", version="0.3.0", lifespan=lifespan)
    app.state.started_at = datetime.now(UTC)
    app.state.process_id = os.getpid()
    app.state.cwd = str(Path.cwd())
    app.state.report_repository = resolved_repository
    app.state.event_bus = resolved_event_bus
    app.state.run_single = run_research
    app.state.run_batch = run_batch_research
    if app.state.report_repository is not None:
        app.state.report_repository.initialize_schema()

    @app.middleware("http")
    async def disable_cache_for_debug_surfaces(request: Request, call_next):
        response = await call_next(request)
        if request.method == "GET":
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    @app.get("/healthz")
    def healthcheck():
        return {
            "status": "ok",
            "storage_enabled": app.state.report_repository is not None,
            "llm_model": config.LLM_MODEL,
            "llm_base_url": config.ANTHROPIC_BASE_URL or "default",
            "web_search_enabled": config.ENABLE_ANTHROPIC_WEB_SEARCH,
            "started_at": app.state.started_at,
            "process_id": app.state.process_id,
            "cwd": app.state.cwd,
        }

    @app.get("/", include_in_schema=False)
    def frontend():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/admin", include_in_schema=False)
    def admin_frontend():
        return FileResponse(STATIC_DIR / "admin.html")

    app.mount("/outputs", StaticFiles(directory=config.OUTPUT_DIR), name="outputs")
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(reports_router, prefix="/reports", tags=["reports"])
    app.include_router(events_router, tags=["events"])
    app.include_router(runs_router, tags=["runs"])
    return app


app = create_app()
