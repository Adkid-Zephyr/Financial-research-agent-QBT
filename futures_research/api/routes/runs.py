from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any, Awaitable, Callable, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, model_validator

from futures_research import config
from futures_research.main import run_research
from futures_research.models.batch import BatchResearchSummary
from futures_research.models.state import WorkflowState
from futures_research.scheduler import run_batch_research
from futures_research.varieties import VarietyRegistry

router = APIRouter()
logger = logging.getLogger(__name__)

SingleRunner = Callable[[str, date, Optional[Dict[str, Any]]], Awaitable[WorkflowState]]
BatchRunner = Callable[[List[str], date, int], Awaitable[BatchResearchSummary]]


class RunTriggerRequest(BaseModel):
    symbol: str
    contract: Optional[str] = None
    target_date: date = Field(default_factory=date.today)
    report_render_mode: Optional[str] = None
    research_profile: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_report_render_mode(self):
        mode = self.report_render_mode or self.research_profile.get("report_render_mode")
        if mode is None:
            return self
        normalized = str(mode).strip().lower()
        if normalized not in config.SUPPORTED_REPORT_RENDER_MODES:
            raise ValueError(
                "report_render_mode must be one of: %s"
                % ", ".join(sorted(config.SUPPORTED_REPORT_RENDER_MODES))
            )
        self.report_render_mode = normalized
        return self


class RunTriggerAccepted(BaseModel):
    status: str = "accepted"
    requested_symbol: str
    selected_contract: Optional[str] = None
    selected_report_render_mode: str
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


class VarietyOption(BaseModel):
    code: str
    name: str
    exchange: str
    contracts: List[str]
    default_contract: Optional[str] = None


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


def _resolve_single_symbol(payload: RunTriggerRequest) -> str:
    requested_symbol = payload.symbol.strip().upper()
    if not requested_symbol:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Symbol is required.")
    if not payload.contract:
        return requested_symbol

    registry = VarietyRegistry()
    registry.scan()
    try:
        variety = registry.get(requested_symbol)
        return registry.normalize_configured_contract(variety.code, payload.contract)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/varieties", response_model=List[VarietyOption])
def list_varieties() -> List[VarietyOption]:
    registry = VarietyRegistry()
    registry.scan()
    return [
        VarietyOption(
            code=item.code.upper(),
            name=item.name,
            exchange=item.exchange,
            contracts=[contract.upper() for contract in item.contracts],
            default_contract=item.contracts[0].upper() if item.contracts else None,
        )
        for item in registry.list_varieties()
    ]


@router.post("/runs", response_model=RunTriggerAccepted, status_code=status.HTTP_202_ACCEPTED)
async def trigger_single_run(payload: RunTriggerRequest, request: Request) -> RunTriggerAccepted:
    resolved_symbol = _resolve_single_symbol(payload)
    research_profile = dict(payload.research_profile)
    if payload.report_render_mode:
        research_profile["report_render_mode"] = payload.report_render_mode
    _spawn_background_task(
        _get_single_runner(request)(
            resolved_symbol,
            payload.target_date,
            research_profile,
        )
    )
    return RunTriggerAccepted(
        requested_symbol=payload.symbol.strip().upper(),
        selected_contract=resolved_symbol if payload.contract else None,
        selected_report_render_mode=config.normalize_report_render_mode(research_profile.get("report_render_mode")),
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
