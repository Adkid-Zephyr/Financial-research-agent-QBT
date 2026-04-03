from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Awaitable, Callable, List
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, model_validator

from futures_research.main import run_research
from futures_research.models.batch import BatchResearchSummary
from futures_research.models.research import ResearchProfile
from futures_research.models.state import WorkflowState
from futures_research.scheduler import run_batch_research
from futures_research.varieties import VarietyRegistry

router = APIRouter()
logger = logging.getLogger(__name__)

SingleRunner = Callable[..., Awaitable[WorkflowState]]
BatchRunner = Callable[[List[str], date, int], Awaitable[BatchResearchSummary]]


class RunTriggerRequest(BaseModel):
    symbol: str
    target_date: date = Field(default_factory=date.today)
    research_profile: ResearchProfile = Field(default_factory=ResearchProfile)


class RunTriggerAccepted(BaseModel):
    status: str = "accepted"
    run_id: UUID
    requested_symbol: str
    resolved_symbol: str
    target_date: date


class BatchTriggerRequest(BaseModel):
    symbols: List[str] = Field(default_factory=list)
    all_varieties: bool = False
    target_date: date = Field(default_factory=date.today)
    concurrency: int = Field(default=2, ge=1, le=16)

    @model_validator(mode="after")
    def validate_request(self):
        if not self.all_varieties and not self.symbols:
            raise ValueError("Either symbols or all_varieties must be provided.")
        return self


class BatchTriggerAccepted(BaseModel):
    status: str = "accepted"
    requested_symbols: List[str]
    target_date: date
    concurrency: int


def _get_single_runner(request: Request) -> SingleRunner:
    return getattr(request.app.state, "run_single", run_research)


def _get_batch_runner(request: Request) -> BatchRunner:
    return getattr(request.app.state, "run_batch", run_batch_research)


def _spawn_background_task(coroutine: Awaitable[object]) -> None:
    task = asyncio.create_task(coroutine)

    def _log_task_failure(completed_task: asyncio.Task) -> None:
        try:
            completed_task.result()
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("Background research task failed.")

    task.add_done_callback(_log_task_failure)


def _resolve_requested_symbols(payload: BatchTriggerRequest) -> List[str]:
    if payload.all_varieties:
        registry = VarietyRegistry()
        registry.scan()
        symbols = registry.list_codes()
    else:
        symbols = [item.strip().upper() for item in payload.symbols if item.strip()]
    if not symbols:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid symbols were resolved from the request.",
        )
    return symbols


@router.post("/runs", response_model=RunTriggerAccepted, status_code=status.HTTP_202_ACCEPTED)
async def trigger_single_run(payload: RunTriggerRequest, request: Request) -> RunTriggerAccepted:
    registry = VarietyRegistry()
    registry.scan()
    requested_symbol = payload.symbol.strip().upper()
    run_id = uuid4()
    resolved_symbol = registry.resolve_contract(requested_symbol)
    _spawn_background_task(
        _get_single_runner(request)(
            requested_symbol,
            payload.target_date,
            research_profile=payload.research_profile,
            run_id=run_id,
        )
    )
    return RunTriggerAccepted(
        run_id=run_id,
        requested_symbol=requested_symbol,
        resolved_symbol=resolved_symbol,
        target_date=payload.target_date,
    )


@router.post("/batches", response_model=BatchTriggerAccepted, status_code=status.HTTP_202_ACCEPTED)
async def trigger_batch_run(payload: BatchTriggerRequest, request: Request) -> BatchTriggerAccepted:
    symbols = _resolve_requested_symbols(payload)
    _spawn_background_task(_get_batch_runner(request)(symbols, payload.target_date, payload.concurrency))
    return BatchTriggerAccepted(
        requested_symbols=symbols,
        target_date=payload.target_date,
        concurrency=payload.concurrency,
    )
