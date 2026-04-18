from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from futures_research import config
from futures_research.events import get_current_batch_id, publish_event
from futures_research.models.state import WorkflowState
from futures_research.runtime import build_runtime
from futures_research.storage import build_report_repository, persist_report_artifacts
from futures_research.workflow.graph import build_workflow


def _build_request_context(research_profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    profile = research_profile or {}
    allowed_personas = {
        "institution": "机构研究",
        "short_term": "散户短线",
        "hedging": "产业套保",
        "large_trader": "大户交易",
        "event": "事件驱动",
    }
    persona = str(profile.get("persona") or "institution")
    return {
        "persona": persona if persona in allowed_personas else "institution",
        "persona_label": allowed_personas.get(persona, "机构研究"),
        "user_focus": str(profile.get("user_focus") or profile.get("prompt") or "").strip(),
        "report_render_mode": config.normalize_report_render_mode(profile.get("report_render_mode")),
    }


async def run_research(symbol: str, target_date: date, research_profile: Optional[Dict[str, Any]] = None) -> WorkflowState:
    runtime = build_runtime()
    variety_definition = runtime.variety_registry.get(symbol)
    contract = runtime.variety_registry.resolve_contract(symbol)

    initial_state = WorkflowState(
        symbol=contract,
        variety_code=variety_definition.code,
        variety=variety_definition.name,
        target_date=target_date,
        raw_data={"request_context": _build_request_context(research_profile)},
    )
    publish_event(
        channel="run",
        event_type="run_started",
        run_id=initial_state.run_id,
        batch_id=get_current_batch_id(),
        requested_symbol=symbol.strip().upper(),
        resolved_symbol=contract,
        variety_code=variety_definition.code,
        variety=variety_definition.name,
        target_date=target_date,
    )
    workflow = build_workflow(runtime)
    try:
        result = await workflow.ainvoke(initial_state.model_dump())
        final_state = WorkflowState.model_validate(result)
        if final_state.final_report is not None:
            final_state.final_report = persist_report_artifacts(final_state.final_report, run_id=final_state.run_id)

        report_repository = build_report_repository()
        if report_repository is not None:
            report_repository.initialize_schema()
            report_repository.save_workflow_state(final_state)
    except Exception as exc:
        publish_event(
            channel="run",
            event_type="run_failed",
            run_id=initial_state.run_id,
            batch_id=get_current_batch_id(),
            requested_symbol=symbol.strip().upper(),
            resolved_symbol=contract,
            variety_code=variety_definition.code,
            variety=variety_definition.name,
            target_date=target_date,
            payload={"error": str(exc)},
        )
        raise

    publish_event(
        channel="run",
        event_type="run_completed",
        run_id=final_state.run_id,
        batch_id=get_current_batch_id(),
        requested_symbol=symbol.strip().upper(),
        resolved_symbol=final_state.symbol,
        variety_code=final_state.variety_code,
        variety=final_state.variety,
        target_date=target_date,
        review_round=final_state.review_round,
        payload={
            "final_score": final_state.final_report.final_score if final_state.final_report is not None else None,
            "passed": final_state.review_result.passed if final_state.review_result is not None else False,
        },
    )
    return final_state
