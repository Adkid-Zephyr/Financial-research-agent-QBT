from __future__ import annotations

from datetime import datetime

from report_review_agent.app.exporters import build_markdown, write_json, write_pdf
from report_review_agent.app.heuristics import HeuristicReviewer
from report_review_agent.app.llm import GuidanceGenerator, coerce_actions
from report_review_agent.app.models import ReviewArtifacts, ReviewResult, StoredReviewBundle
from report_review_agent.app.parsers import parse_document
from report_review_agent.app.storage import ReviewStorage


class ReviewService:
    def __init__(self) -> None:
        self.storage = ReviewStorage()
        self.heuristics = HeuristicReviewer()
        self.guidance = GuidanceGenerator()

    async def review_upload(self, filename: str, payload: bytes) -> StoredReviewBundle:
        parsed = parse_document(filename, payload)
        heuristic_snapshot = self.heuristics.review(parsed)
        guidance_payload = await self.guidance.generate(parsed, heuristic_snapshot)

        review_id, workspace = self.storage.create_workspace(filename)
        original_file_path = self.storage.save_original(workspace, filename, payload)
        markdown_path = workspace / "review.md"
        pdf_path = workspace / "review.pdf"
        json_path = workspace / "review.json"

        actions = coerce_actions(guidance_payload.get("improvement_actions")) or heuristic_snapshot.improvement_actions
        result = ReviewResult(
            review_id=review_id,
            created_at=datetime.now(),
            filename=parsed.filename,
            document_format=parsed.format,
            overall_score=heuristic_snapshot.overall_score,
            status=heuristic_snapshot.status,  # type: ignore[arg-type]
            passed=heuristic_snapshot.passed,
            executive_summary=guidance_payload.get("executive_summary") or heuristic_snapshot.executive_summary,
            strengths=guidance_payload.get("strengths") or heuristic_snapshot.strengths,
            dimension_scores=heuristic_snapshot.dimension_scores,
            findings=heuristic_snapshot.findings,
            improvement_actions=actions,
            suggested_outline=guidance_payload.get("suggested_outline") or heuristic_snapshot.suggested_outline,
            metadata={
                "char_count": parsed.char_count,
                "page_count": parsed.page_count,
                "parser_metadata": parsed.metadata,
                "heuristic_metrics": heuristic_snapshot.metrics,
                "blocking_issues": heuristic_snapshot.blocking_issues,
                "llm_guidance_live": self.guidance.is_live,
            },
            artifacts=ReviewArtifacts(
                markdown_path=str(markdown_path),
                pdf_path=str(pdf_path),
                json_path=str(json_path),
                original_file_path=str(original_file_path),
            ),
        )

        markdown_content = build_markdown(result)
        markdown_path.write_text(markdown_content, encoding="utf-8")
        write_pdf(markdown_content, pdf_path)
        write_json(result, json_path)
        return StoredReviewBundle(result=result, markdown_content=markdown_content)

    def load_review(self, review_id: str) -> StoredReviewBundle:
        workspace = self.storage.resolve_workspace(review_id)
        markdown_path = workspace / "review.md"
        json_path = workspace / "review.json"
        from report_review_agent.app.models import ReviewResult  # local import to avoid cycles during startup
        import json

        result = ReviewResult.model_validate(json.loads(json_path.read_text(encoding="utf-8")))
        markdown_content = markdown_path.read_text(encoding="utf-8")
        return StoredReviewBundle(result=result, markdown_content=markdown_content)

    def artifact_path(self, review_id: str, kind: str):
        workspace = self.storage.resolve_workspace(review_id)
        mapping = {
            "markdown": workspace / "review.md",
            "pdf": workspace / "review.pdf",
            "json": workspace / "review.json",
            "source": next(iter(sorted(workspace.glob("source.*"))), None),
        }
        path = mapping.get(kind)
        if path is None:
            raise FileNotFoundError(f"Unknown artifact kind: {kind}")
        return path
