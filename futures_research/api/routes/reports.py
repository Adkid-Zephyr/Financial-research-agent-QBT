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
