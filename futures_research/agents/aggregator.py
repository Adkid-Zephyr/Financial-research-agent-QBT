from __future__ import annotations

from typing import Any, Dict, List

from futures_research.models.source import DataFetchRequest
from futures_research.prompts.aggregator_prompt import build_aggregator_context
from futures_research.runtime import RuntimeContext


async def aggregate_node(state: Dict[str, Any], runtime: RuntimeContext) -> Dict[str, Any]:
    variety_definition = runtime.variety_registry.get(state["variety_code"])
    request_context = (state.get("raw_data") or {}).get("request_context", {})
    request = DataFetchRequest(
        variety_code=variety_definition.code,
        variety_name=variety_definition.name,
        contract=state["symbol"],
        target_date=state["target_date"],
        exchange=variety_definition.exchange,
        key_factors=variety_definition.key_factors,
        news_keywords=variety_definition.news_keywords,
        research_focus=str(request_context.get("user_focus", "")),
        focus_points=list(request_context.get("key_points", [])),
        horizon_label=str(request_context.get("horizon_label", "")),
        persona_label=str(request_context.get("persona_label", "")),
    )
    configured_source_types = [item.type for item in variety_definition.data_sources]
    active_source_types: List[str] = []
    if "mock" in configured_source_types:
        active_source_types.append("mock")
    if not active_source_types:
        active_source_types.append("mock")
    payloads = await runtime.data_source_registry.fetch_many(request, active_source_types)
    raw_data = {
        "request_context": request_context,
        "market_context": build_aggregator_context(variety_definition, runtime.prompt_repository),
        "summary": " | ".join(payload.summary for payload in payloads),
        "highlights": [item for payload in payloads for item in payload.highlights],
        "metrics": {k: v for payload in payloads for k, v in payload.metrics.items()},
        "sources": [item for payload in payloads for item in payload.sources],
        "raw_items": [item for payload in payloads for item in payload.raw_items],
    }
    return {
        "current_step": "aggregate",
        "raw_data": raw_data,
        "data_sources_used": active_source_types,
    }
