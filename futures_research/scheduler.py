from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from typing import Awaitable, Callable, Iterable, List, Sequence
from uuid import UUID, uuid4

from futures_research.events import batch_event_context, publish_event
from futures_research.main import run_research
from futures_research.models.batch import BatchResearchItem, BatchResearchSummary
from futures_research.models.state import WorkflowState

BatchRunner = Callable[[str, date], Awaitable[WorkflowState]]


class ResearchScheduler:
    def __init__(self, runner: BatchRunner = run_research):
        self.runner = runner

    async def run_batch(
        self,
        symbols: Sequence[str],
        target_date: date,
        concurrency: int = 2,
    ) -> BatchResearchSummary:
        started_at = datetime.now(UTC)
        batch_id = uuid4()
        try:
            normalized_symbols = self._normalize_symbols(symbols)
            normalized_concurrency = max(1, min(concurrency, max(1, len(normalized_symbols))))
            semaphore = asyncio.Semaphore(normalized_concurrency)
            publish_event(
                channel="batch",
                event_type="batch_started",
                batch_id=batch_id,
                target_date=target_date,
                payload={
                    "requested_symbols": normalized_symbols,
                    "concurrency": normalized_concurrency,
                },
            )

            async def _guarded_run(requested_symbol: str) -> BatchResearchItem:
                async with semaphore:
                    with batch_event_context(batch_id):
                        return await self._run_one(requested_symbol, target_date, batch_id=batch_id)

            items = await asyncio.gather(*[_guarded_run(symbol) for symbol in normalized_symbols])
            completed_at = datetime.now(UTC)
            summary = self._build_summary(
                items=items,
                target_date=target_date,
                requested_symbols=normalized_symbols,
                concurrency=normalized_concurrency,
                started_at=started_at,
                completed_at=completed_at,
                batch_id=batch_id,
            )
        except Exception as exc:
            publish_event(
                channel="batch",
                event_type="batch_failed",
                batch_id=batch_id,
                target_date=target_date,
                payload={"error": str(exc)},
            )
            raise

        publish_event(
            channel="batch",
            event_type="batch_completed",
            batch_id=summary.batch_id,
            target_date=summary.target_date,
            payload={
                "total": summary.total,
                "succeeded": summary.succeeded,
                "failed": summary.failed,
                "passed": summary.passed,
                "marginal": summary.marginal,
                "average_score": summary.average_score,
            },
        )
        return summary

    async def _run_one(self, requested_symbol: str, target_date: date, *, batch_id) -> BatchResearchItem:
        publish_event(
            channel="batch",
            event_type="batch_item_started",
            batch_id=batch_id,
            requested_symbol=requested_symbol,
            target_date=target_date,
        )
        try:
            state = await self.runner(requested_symbol, target_date)
        except Exception as exc:  # pragma: no cover - exercised via tests with injected runner
            publish_event(
                channel="batch",
                event_type="batch_item_failed",
                batch_id=batch_id,
                requested_symbol=requested_symbol,
                target_date=target_date,
                payload={"error": str(exc)},
            )
            return BatchResearchItem(requested_symbol=requested_symbol, status="failed", error=str(exc))
        item = self._state_to_item(requested_symbol, state)
        publish_event(
            channel="batch",
            event_type="batch_item_completed",
            batch_id=batch_id,
            run_id=item.run_id,
            requested_symbol=requested_symbol,
            resolved_symbol=item.resolved_symbol,
            variety_code=item.variety_code,
            variety=item.variety,
            target_date=target_date,
            payload={
                "status": item.status,
                "final_score": item.final_score,
                "review_passed": item.review_passed,
            },
        )
        return item

    def _state_to_item(self, requested_symbol: str, state: WorkflowState) -> BatchResearchItem:
        review_result = state.review_result
        final_report = state.final_report
        status = "failed"
        if final_report is not None and review_result is not None:
            status = "passed" if review_result.passed else "marginal"
        elif not state.error:
            status = "marginal"

        return BatchResearchItem(
            requested_symbol=requested_symbol,
            resolved_symbol=state.symbol,
            variety_code=state.variety_code,
            variety=state.variety,
            run_id=state.run_id,
            final_score=final_report.final_score if final_report is not None else None,
            review_passed=bool(review_result.passed) if review_result is not None else False,
            status=status,
            error=state.error,
        )

    def _build_summary(
        self,
        *,
        items: List[BatchResearchItem],
        target_date: date,
        requested_symbols: List[str],
        concurrency: int,
        started_at: datetime,
        completed_at: datetime,
        batch_id: UUID,
    ) -> BatchResearchSummary:
        scored_items = [item.final_score for item in items if item.final_score is not None]
        return BatchResearchSummary(
            batch_id=batch_id,
            target_date=target_date,
            requested_symbols=requested_symbols,
            started_at=started_at,
            completed_at=completed_at,
            concurrency=concurrency,
            total=len(items),
            succeeded=sum(1 for item in items if item.status != "failed"),
            failed=sum(1 for item in items if item.status == "failed"),
            passed=sum(1 for item in items if item.status == "passed"),
            marginal=sum(1 for item in items if item.status == "marginal"),
            average_score=round(sum(scored_items) / len(scored_items), 2) if scored_items else None,
            items=items,
        )

    def _normalize_symbols(self, symbols: Iterable[str]) -> List[str]:
        normalized = []
        seen = set()
        for symbol in symbols:
            value = str(symbol).strip().upper()
            if not value or value in seen:
                continue
            normalized.append(value)
            seen.add(value)
        if not normalized:
            raise ValueError("At least one symbol is required for batch research.")
        return normalized


async def run_batch_research(
    symbols: Sequence[str],
    target_date: date,
    concurrency: int = 2,
    runner: BatchRunner = run_research,
) -> BatchResearchSummary:
    scheduler = ResearchScheduler(runner=runner)
    return await scheduler.run_batch(symbols=symbols, target_date=target_date, concurrency=concurrency)
