from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from futures_research.models.research import ResearchOptionsCatalog, ResearchPreview, ResearchProfile
from futures_research.research_profile import (
    build_preview_fallback_payload,
    build_research_preview,
    build_variety_option,
    list_horizon_options,
    list_persona_options,
)
from futures_research.runtime import build_runtime

router = APIRouter(prefix="/research")


class ResearchPreviewRequest(BaseModel):
    symbol: str
    research_profile: ResearchProfile = Field(default_factory=ResearchProfile)


@router.get("/options", response_model=ResearchOptionsCatalog)
def get_research_options() -> ResearchOptionsCatalog:
    runtime = build_runtime()
    return ResearchOptionsCatalog(
        varieties=[
            build_variety_option(runtime.variety_registry.get(code))
            for code in runtime.variety_registry.list_codes()
        ],
        horizons=list_horizon_options(),
        personas=list_persona_options(),
    )


@router.post("/preview", response_model=ResearchPreview)
async def preview_research_request(payload: ResearchPreviewRequest) -> ResearchPreview:
    runtime = build_runtime()
    variety_definition = runtime.variety_registry.get(payload.symbol)
    contract = runtime.variety_registry.resolve_contract(payload.symbol)
    fallback = build_preview_fallback_payload(variety_definition, contract, payload.research_profile)
    preview_payload = await runtime.llm_client.generate_research_preview(
        {
            "variety_code": variety_definition.code,
            "variety_name": variety_definition.name,
            "contract": contract,
            "key_factors": list(variety_definition.key_factors),
            "user_focus": payload.research_profile.user_focus,
            "horizon": payload.research_profile.horizon,
            "persona": payload.research_profile.persona,
            "fallback_summary": fallback["summary"],
            "fallback_key_points": fallback["key_points"],
            "fallback_writing_directives": fallback["writing_directives"],
            "fallback_template": fallback["recommended_template"],
        }
    )
    merged_profile = payload.research_profile.model_copy(
        update={
            "briefing_summary": str(preview_payload.get("summary") or fallback["summary"]),
            "key_points": list(preview_payload.get("key_points") or fallback["key_points"]),
            "writing_directives": list(preview_payload.get("writing_directives") or fallback["writing_directives"]),
            "recommended_template": str(
                preview_payload.get("recommended_template") or fallback["recommended_template"]
            ),
        }
    )
    return build_research_preview(variety_definition, contract, merged_profile)
