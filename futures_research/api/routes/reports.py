from __future__ import annotations

from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from futures_research.models.state import WorkflowState
from futures_research.storage import ReportRepository, ReportSummary

router = APIRouter()


class DeleteReportsRequest(BaseModel):
    run_ids: List[UUID] = Field(default_factory=list)


class DeleteReportsResponse(BaseModel):
    deleted: int


class AskReportRequest(BaseModel):
    question: str
    persona: str = ""


class AskReportResponse(BaseModel):
    answer: str
    source_refs: List[str] = Field(default_factory=list)
    data_gaps: List[str] = Field(default_factory=list)


def get_report_repository(request: Request) -> ReportRepository:
    repository = getattr(request.app.state, "report_repository", None)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DATABASE_URL is not configured, report storage is unavailable.",
        )
    return repository


@router.get("", response_model=List[ReportSummary])
def list_reports(
    symbol: Optional[str] = Query(default=None),
    variety_code: Optional[str] = Query(default=None),
    target_date: Optional[date] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    repository: ReportRepository = Depends(get_report_repository),
) -> List[ReportSummary]:
    return repository.list_reports(
        symbol=symbol,
        variety_code=variety_code,
        target_date=target_date,
        limit=limit,
        offset=offset,
    )


@router.get("/{run_id}", response_model=WorkflowState)
def get_report_detail(
    run_id: UUID,
    repository: ReportRepository = Depends(get_report_repository),
) -> WorkflowState:
    state = repository.get_workflow_state(run_id)
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    return state


@router.post("/{run_id}/ask", response_model=AskReportResponse)
def ask_report(
    run_id: UUID,
    payload: AskReportRequest,
    repository: ReportRepository = Depends(get_report_repository),
) -> AskReportResponse:
    state = repository.get_workflow_state(run_id)
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question is required.")
    return _answer_from_saved_report(state, question)


@router.delete("/{run_id}", response_model=DeleteReportsResponse)
def delete_report(
    run_id: UUID,
    repository: ReportRepository = Depends(get_report_repository),
) -> DeleteReportsResponse:
    deleted = 1 if repository.delete_workflow_state(run_id) else 0
    if deleted == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    return DeleteReportsResponse(deleted=deleted)


@router.post("/delete-batch", response_model=DeleteReportsResponse)
def delete_reports_batch(
    payload: DeleteReportsRequest,
    repository: ReportRepository = Depends(get_report_repository),
) -> DeleteReportsResponse:
    deleted = repository.delete_workflow_states(payload.run_ids)
    return DeleteReportsResponse(deleted=deleted)


def _answer_from_saved_report(state: WorkflowState, question: str) -> AskReportResponse:
    report = state.final_report
    raw_data = state.raw_data or {}
    sources = list(report.data_sources if report is not None else raw_data.get("sources", []))
    gaps = list(raw_data.get("data_gaps", []))
    normalized_question = question.lower()
    content = report.content if report is not None else state.report_draft
    summary = report.summary if report is not None else ""
    risk_points = list(report.risk_points if report is not None else [])
    key_factors = list(report.key_factors if report is not None else [])

    if any(token in question for token in ["来源", "数据", "哪里来", "依据"]) or "source" in normalized_question:
        answer = "这份报告只引用已登记的结构化来源：{sources}。".format(
            sources="；".join(sources) if sources else "暂无可核验来源"
        )
        if gaps:
            answer += " 当前仍有数据缺口：{gaps}".format(gaps="；".join(gaps[:4]))
        return AskReportResponse(answer=answer, source_refs=sources, data_gaps=gaps)

    if any(token in question for token in ["风险", "注意", "担心"]):
        if risk_points:
            answer = "报告已列出的主要风险是：{risks}".format(risks="；".join(risk_points[:4]))
        else:
            answer = _extract_section(content, "风险提示") or "当前报告没有额外可展开的风险字段。"
        return AskReportResponse(answer=answer, source_refs=sources, data_gaps=gaps)

    if any(token in question for token in ["为什么", "原因", "证据", "逻辑"]):
        pieces = []
        if summary:
            pieces.append("核心结论：{summary}".format(summary=summary))
        if key_factors:
            pieces.append("报告提到的核心驱动包括：{factors}".format(factors="；".join(key_factors[:4])))
        if sources:
            pieces.append("这些判断的可引用来源为：{sources}".format(sources="；".join(sources)))
        if gaps:
            pieces.append("需要注意的数据缺口：{gaps}".format(gaps="；".join(gaps[:4])))
        return AskReportResponse(
            answer=" ".join(pieces) if pieces else "当前报告暂无足够结构化事实解释该问题。",
            source_refs=sources,
            data_gaps=gaps,
        )

    fallback = summary or _extract_section(content, "核心观点") or "当前报告暂无可核验内容可用于回答该问题。"
    if gaps:
        fallback += " 仍需注意：{gaps}".format(gaps="；".join(gaps[:3]))
    return AskReportResponse(answer=fallback, source_refs=sources, data_gaps=gaps)


def _extract_section(content: str, title: str) -> str:
    if not content:
        return ""
    marker = "##"
    start = content.find(title)
    if start == -1:
        return ""
    section_start = content.rfind(marker, 0, start)
    section_start = section_start if section_start != -1 else start
    next_section = content.find("\n##", start + len(title))
    section = content[section_start: next_section if next_section != -1 else len(content)]
    return section.strip()
