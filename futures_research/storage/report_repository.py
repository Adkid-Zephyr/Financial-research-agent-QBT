from __future__ import annotations

from datetime import date, datetime
import json
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

    def _row_to_summary(self, row: RowMapping) -> ReportSummary:
        review_result = row["review_result"] or {}
        return ReportSummary(
            run_id=row["run_id"],
            symbol=row["symbol"],
            variety_code=row["variety_code"],
            variety=row["variety"],
            target_date=row["target_date"],
            generated_at=row["generated_at"],
            final_score=row["final_score"],
            summary=row["summary"] or "",
            sentiment=row["sentiment"] or "",
            confidence=row["confidence"] or "",
            review_passed=bool(review_result.get("passed", False)),
            data_sources=list(row["data_sources"] or []),
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


def build_report_repository(database_url: Optional[str] = None) -> Optional[ReportRepository]:
    resolved_database_url = database_url if database_url is not None else config.DATABASE_URL
    if not resolved_database_url:
        return None
    return SqlAlchemyReportRepository(resolved_database_url)
