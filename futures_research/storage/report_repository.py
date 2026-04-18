from __future__ import annotations

from datetime import date, datetime
import json
import re
from typing import Any, Dict, List, Optional, Protocol
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import delete, insert, select
from sqlalchemy.engine import RowMapping

from futures_research import config
from futures_research.models.report import ResearchReport
from futures_research.models.review import ReviewResult
from futures_research.models.state import WorkflowState
from futures_research.storage.postgres import create_database_engine, initialize_database, research_reports


class ReportSummary(BaseModel):
    run_id: UUID
    symbol: str
    variety_code: str
    variety: str
    target_date: date
    generated_at: Optional[datetime] = None
    final_score: Optional[float] = None
    summary: str = ""
    sentiment: str = ""
    confidence: str = ""
    review_passed: bool = False
    data_sources: List[str] = Field(default_factory=list)
    char_count: int = 0
    estimated_tokens: int = 0


class ReportRepository(Protocol):
    def initialize_schema(self) -> None:
        ...

    def close(self) -> None:
        ...

    def save_workflow_state(self, state: WorkflowState) -> None:
        ...

    def list_reports(
        self,
        *,
        symbol: Optional[str] = None,
        variety_code: Optional[str] = None,
        target_date: Optional[date] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[ReportSummary]:
        ...

    def get_workflow_state(self, run_id: UUID) -> Optional[WorkflowState]:
        ...

    def delete_workflow_state(self, run_id: UUID) -> bool:
        ...

    def delete_workflow_states(self, run_ids: List[UUID]) -> int:
        ...


class SqlAlchemyReportRepository:
    def __init__(self, database_url: str):
        self.engine = create_database_engine(database_url)

    def initialize_schema(self) -> None:
        initialize_database(self.engine)

    def close(self) -> None:
        self.engine.dispose()

    def save_workflow_state(self, state: WorkflowState) -> None:
        final_report = state.final_report
        review_result = state.review_result
        payload = {
            "run_id": str(state.run_id),
            "report_id": str(final_report.id) if final_report is not None else None,
            "symbol": state.symbol,
            "variety_code": state.variety_code,
            "variety": state.variety,
            "target_date": state.target_date,
            "current_step": state.current_step,
            "review_round": state.review_round,
            "max_review_rounds": state.max_review_rounds,
            "generated_at": final_report.generated_at if final_report is not None else None,
            "final_score": final_report.final_score if final_report is not None else None,
            "summary": final_report.summary if final_report is not None else "",
            "sentiment": final_report.sentiment if final_report is not None else "",
            "confidence": final_report.confidence if final_report is not None else "",
            "report_draft": state.report_draft,
            "analysis_result": state.analysis_result,
            "raw_data": self._json_payload(state.raw_data),
            "review_result": self._serialize_review_result(review_result),
            "review_history": [self._serialize_review_result(item) for item in state.review_history],
            "final_report": self._serialize_report(final_report),
            "key_factors": list(final_report.key_factors) if final_report is not None else [],
            "risk_points": list(final_report.risk_points) if final_report is not None else [],
            "data_sources": list(final_report.data_sources) if final_report is not None else [],
            "data_sources_used": list(state.data_sources_used),
            "error": state.error,
        }
        with self.engine.begin() as connection:
            connection.execute(delete(research_reports).where(research_reports.c.run_id == payload["run_id"]))
            connection.execute(insert(research_reports).values(**payload))

    def list_reports(
        self,
        *,
        symbol: Optional[str] = None,
        variety_code: Optional[str] = None,
        target_date: Optional[date] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[ReportSummary]:
        statement = select(
            research_reports.c.run_id,
            research_reports.c.symbol,
            research_reports.c.variety_code,
            research_reports.c.variety,
            research_reports.c.target_date,
            research_reports.c.generated_at,
            research_reports.c.final_score,
            research_reports.c.summary,
            research_reports.c.sentiment,
            research_reports.c.confidence,
            research_reports.c.review_result,
            research_reports.c.data_sources,
            research_reports.c.report_draft,
            research_reports.c.final_report,
        ).order_by(research_reports.c.generated_at.desc(), research_reports.c.run_id.desc())
        if symbol:
            statement = statement.where(research_reports.c.symbol == symbol)
        if variety_code:
            statement = statement.where(research_reports.c.variety_code == variety_code)
        if target_date:
            statement = statement.where(research_reports.c.target_date == target_date)
        statement = statement.limit(limit).offset(offset)
        with self.engine.begin() as connection:
            rows = connection.execute(statement).mappings().all()
        return [self._row_to_summary(row) for row in rows]

    def get_workflow_state(self, run_id: UUID) -> Optional[WorkflowState]:
        statement = select(research_reports).where(research_reports.c.run_id == str(run_id))
        with self.engine.begin() as connection:
            row = connection.execute(statement).mappings().first()
        if row is None:
            return None
        return self._row_to_workflow_state(row)

    def delete_workflow_state(self, run_id: UUID) -> bool:
        return self.delete_workflow_states([run_id]) > 0

    def delete_workflow_states(self, run_ids: List[UUID]) -> int:
        normalized_ids = [str(run_id) for run_id in run_ids]
        if not normalized_ids:
            return 0
        existing_states = [state for state in (self.get_workflow_state(UUID(run_id)) for run_id in normalized_ids) if state]
        with self.engine.begin() as connection:
            result = connection.execute(delete(research_reports).where(research_reports.c.run_id.in_(normalized_ids)))
        for state in existing_states:
            self._remove_artifacts_for_state(state)
        return int(result.rowcount or 0)

    def _row_to_summary(self, row: RowMapping) -> ReportSummary:
        review_result = row["review_result"] or {}
        summary = row["summary"] or self._summary_from_row(row)
        return ReportSummary(
            run_id=row["run_id"],
            symbol=row["symbol"],
            variety_code=row["variety_code"],
            variety=row["variety"],
            target_date=row["target_date"],
            generated_at=row["generated_at"],
            final_score=row["final_score"],
            summary=summary,
            sentiment=row["sentiment"] or "",
            confidence=row["confidence"] or "",
            review_passed=bool(review_result.get("passed", False)),
            data_sources=list(row["data_sources"] or []),
            char_count=self._char_count_from_row(row),
            estimated_tokens=self._estimate_tokens(self._char_count_from_row(row)),
        )

    def _row_to_workflow_state(self, row: RowMapping) -> WorkflowState:
        payload = {
            "run_id": row["run_id"],
            "symbol": row["symbol"],
            "variety_code": row["variety_code"],
            "variety": row["variety"],
            "target_date": row["target_date"],
            "current_step": row["current_step"],
            "review_round": row["review_round"],
            "max_review_rounds": row["max_review_rounds"],
            "raw_data": row["raw_data"] or {},
            "analysis_result": row["analysis_result"] or "",
            "report_draft": row["report_draft"] or "",
            "review_result": row["review_result"],
            "review_history": row["review_history"] or [],
            "final_report": row["final_report"],
            "data_sources_used": row["data_sources_used"] or [],
            "error": row["error"],
        }
        return WorkflowState.model_validate(payload)

    def _serialize_report(self, report: Optional[ResearchReport]) -> Optional[Dict[str, Any]]:
        if report is None:
            return None
        return report.model_dump(mode="json")

    def _serialize_review_result(self, review_result: Any) -> Optional[Dict[str, Any]]:
        if review_result is None:
            return None
        if isinstance(review_result, ReviewResult):
            return review_result.model_dump(mode="json")
        return ReviewResult.model_validate(review_result).model_dump(mode="json")

    def _json_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return json.loads(json.dumps(payload, ensure_ascii=False, default=str))

    def _char_count_from_row(self, row: RowMapping) -> int:
        report = row.get("final_report") or {}
        content = report.get("content") if isinstance(report, dict) else None
        if content:
            return len(content)
        draft = row.get("report_draft") or ""
        return len(draft)

    def _summary_from_row(self, row: RowMapping) -> str:
        report = row.get("final_report") or {}
        content = report.get("content") if isinstance(report, dict) else None
        return self._extract_summary(content or row.get("report_draft") or "")

    @staticmethod
    def _extract_summary(content: str) -> str:
        cleaned = _clean_report_text(content)
        for line in cleaned.splitlines():
            stripped = line.strip()
            if stripped.startswith("> **核心观点**："):
                return _compact_summary(stripped.replace("> **核心观点**：", ""))
            if stripped.startswith("> 核心观点"):
                return _compact_summary(stripped.replace("> 核心观点", "").lstrip("：:"))
        for heading in ["## 核心观点", "## 一、结论先行", "## 一、行情回顾"]:
            section = _section_after_heading(cleaned, heading)
            if section:
                return _compact_summary(section)
        for line in cleaned.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
                return _compact_summary(stripped)
        return ""

    def _remove_artifacts_for_state(self, state: WorkflowState) -> None:
        from futures_research.storage.artifacts import remove_report_artifacts

        remove_report_artifacts(state.final_report)

    @staticmethod
    def _estimate_tokens(char_count: int) -> int:
        if char_count <= 0:
            return 0
        return max(1, round(char_count / 1.6))


def build_report_repository(database_url: Optional[str] = None) -> Optional[ReportRepository]:
    resolved_database_url = database_url if database_url is not None else config.DATABASE_URL
    if not resolved_database_url:
        return None
    return SqlAlchemyReportRepository(resolved_database_url)


def _clean_report_text(content: str) -> str:
    cleaned = _strip_internal_report_blocks(content or "")
    cleaned = re.sub(r"\[(?:F|G)\d+\]", "", cleaned)
    cleaned = re.sub(r"(?<![A-Za-z0-9])(?:F|G)\d+(?![A-Za-z0-9])", "", cleaned)
    cleaned = re.sub(r"[ \t]+([，。；：、,.])", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return "\n".join(line.rstrip() for line in cleaned.splitlines()).strip()


def _strip_internal_report_blocks(content: str) -> str:
    without_comments = re.sub(r"<!--.*?-->", "", content or "", flags=re.DOTALL)
    lines = without_comments.splitlines()
    visible = []
    skip_mode = ""
    for line in lines:
        stripped = line.strip()
        if re.match(r"^##\s+七、数据说明与待补充项", stripped):
            skip_mode = "section"
            continue
        if stripped == "写作约束：":
            skip_mode = "constraint"
            continue
        if skip_mode:
            can_resume = (
                re.match(r"^#{1,6}\s+", stripped)
                or stripped == "---"
                or (skip_mode == "constraint" and not stripped)
            )
            if can_resume:
                skip_mode = ""
            else:
                continue
        if re.match(r"^\d+\.\s+\*\*研究边界\*\*", stripped):
            continue
        visible.append(line)
    return "\n".join(visible)


def _compact_summary(text: str) -> str:
    stripped = _clean_report_text(text)
    stripped = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", stripped)
    stripped = re.sub(r"`([^`]+)`", r"\1", stripped)
    stripped = stripped.replace("**", "").replace("*", "")
    stripped = stripped.lstrip("> ").strip(" ：:")
    return re.sub(r"\s+", " ", stripped)[:120]


def _section_after_heading(content: str, heading: str) -> str:
    if heading not in content:
        return ""
    section = content.split(heading, 1)[1]
    lines = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped:
            if lines:
                break
            continue
        if stripped.startswith("## "):
            break
        lines.append(stripped.lstrip("> ").strip())
    return " ".join(lines)
