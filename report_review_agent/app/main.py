from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from report_review_agent.app import config
from report_review_agent.app.models import ReviewResponse
from report_review_agent.app.parsers import ParseError
from report_review_agent.app.service import ReviewService


def create_app() -> FastAPI:
    app = FastAPI(title="Report Review Agent", version="0.1.0")
    service = ReviewService()
    app.state.review_service = service

    static_dir = config.STATIC_DIR
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    async def root() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/healthz")
    async def healthz() -> dict[str, object]:
        return {
            "status": "ok",
            "llm_guidance_live": service.guidance.is_live,
            "output_dir": str(config.OUTPUT_DIR),
        }

    @app.post("/api/reviews", response_model=ReviewResponse)
    async def create_review(file: UploadFile = File(...)) -> ReviewResponse:
        filename = file.filename or "uploaded.txt"
        payload = await file.read()
        if not payload:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        try:
            bundle = await service.review_upload(filename, payload)
        except ParseError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        result = bundle.result
        base = f"/api/reviews/{result.review_id}/artifacts"
        return ReviewResponse(
            review_id=result.review_id,
            overall_score=result.overall_score,
            status=result.status,
            passed=result.passed,
            executive_summary=result.executive_summary,
            strengths=result.strengths,
            findings=result.findings,
            improvement_actions=result.improvement_actions,
            download_urls={
                "markdown": f"{base}/markdown",
                "pdf": f"{base}/pdf",
                "json": f"{base}/json",
                "source": f"{base}/source",
            },
        )

    @app.get("/api/reviews/{review_id}", response_model=ReviewResponse)
    async def get_review(review_id: str) -> ReviewResponse:
        try:
            bundle = service.load_review(review_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        result = bundle.result
        base = f"/api/reviews/{result.review_id}/artifacts"
        return ReviewResponse(
            review_id=result.review_id,
            overall_score=result.overall_score,
            status=result.status,
            passed=result.passed,
            executive_summary=result.executive_summary,
            strengths=result.strengths,
            findings=result.findings,
            improvement_actions=result.improvement_actions,
            download_urls={
                "markdown": f"{base}/markdown",
                "pdf": f"{base}/pdf",
                "json": f"{base}/json",
                "source": f"{base}/source",
            },
        )

    @app.get("/api/reviews/{review_id}/artifacts/{kind}")
    async def get_artifact(review_id: str, kind: str):
        try:
            path = service.artifact_path(review_id, kind)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        media_type = {
            "markdown": "text/markdown; charset=utf-8",
            "pdf": "application/pdf",
            "json": "application/json",
            "source": "application/octet-stream",
        }.get(kind, "application/octet-stream")
        filename = _artifact_filename(review_id, kind, path)
        return FileResponse(path, media_type=media_type, filename=filename)

    return app


def _artifact_filename(review_id: str, kind: str, path: Path) -> str:
    if kind == "markdown":
        return f"{review_id}_review.md"
    if kind == "pdf":
        return f"{review_id}_review.pdf"
    if kind == "json":
        return f"{review_id}_review.json"
    return path.name
