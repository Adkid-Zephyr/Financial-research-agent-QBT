from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Optional

from fastapi import FastAPI
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
    app.state.report_repository = resolved_repository
    app.state.event_bus = resolved_event_bus
    app.state.run_single = run_research
    app.state.run_batch = run_batch_research
    if app.state.report_repository is not None:
        app.state.report_repository.initialize_schema()

    @app.get("/healthz")
    def healthcheck():
        return {
            "status": "ok",
            "storage_enabled": app.state.report_repository is not None,
            "llm_model": config.LLM_MODEL,
            "llm_base_url": config.ANTHROPIC_BASE_URL or "default",
            "web_search_enabled": config.ENABLE_ANTHROPIC_WEB_SEARCH,
        }

    @app.get("/", include_in_schema=False)
    def frontend():
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/outputs", StaticFiles(directory=config.OUTPUT_DIR), name="outputs")
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(reports_router, prefix="/reports", tags=["reports"])
    app.include_router(events_router, tags=["events"])
    app.include_router(runs_router, tags=["runs"])
    return app


app = create_app()
