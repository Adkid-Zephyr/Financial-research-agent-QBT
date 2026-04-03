from __future__ import annotations

import re
from typing import Dict, List

from futures_research.models.research import ResearchOption, ResearchPreview, ResearchProfile, VarietyOption
from futures_research.models.variety import VarietyDefinition

DEFAULT_HORIZON_ID = "medium_term"
DEFAULT_PERSONA_ID = "futures_desk"

_HORIZON_OPTIONS = {
    "short_term": ResearchOption(
        id="short_term",
        label="短线",
        description="更关注日内到三日内的盘面节奏、持仓变化和突发消息。",
        prompt_directive="请优先突出盘面交易节奏、基差变化、资金博弈和日内/近三日风险点。",
        template_hint="tactical_intraday",
    ),
    "medium_term": ResearchOption(
        id="medium_term",
        label="中线",
        description="更关注一月以内的供需边际变化、库存与价差演变。",
        prompt_directive="请在周度到月度框架下突出供需边际变化、库存演进和跨期结构。",
        template_hint="swing_balanced",
    ),
    "long_term": ResearchOption(
        id="long_term",
        label="长线",
        description="更关注宏观周期、产业趋势和中长期配置逻辑。",
        prompt_directive="请强化宏观周期、产业链利润分配、中长期估值与政策变量分析。",
        template_hint="macro_cycle",
    ),
}

_PERSONA_OPTIONS = {
    "retail_day_trader": ResearchOption(
        id="retail_day_trader",
        label="散户短线高胜率交易者",
        description="偏执行与节奏感，关注高频驱动、关键价位和风控边界。",
        prompt_directive="请使用偏执行摘要的表达，突出关键价位、触发条件、节奏变化，但仍保持合规客观。",
        template_hint="execution_focus",
    ),
    "large_position_trader": ResearchOption(
        id="large_position_trader",
        label="期货大户交易者",
        description="更重视仓位结构、流动性和跨周期博弈。",
        prompt_directive="请补充仓位拥挤度、流动性约束、跨期和跨市场联动的判断。",
        template_hint="positioning_focus",
    ),
    "supplier": ResearchOption(
        id="supplier",
        label="大宗产品供应商",
        description="更重视套保、销售节奏和现货利润。",
        prompt_directive="请从现货经营和套保视角组织内容，突出基差、销售节奏和利润保护。",
        template_hint="hedging_focus",
    ),
    "futures_desk": ResearchOption(
        id="futures_desk",
        label="金融公司期货部门",
        description="偏机构研究口径，强调逻辑链、证据和风险对照。",
        prompt_directive="请保持机构研究日报语气，强调逻辑链完整度、数据证据和风险对照。",
        template_hint="institutional_research",
    ),
    "speculator": ResearchOption(
        id="speculator",
        label="投机者",
        description="更关注预期差、情绪切换和波动放大器。",
        prompt_directive="请强化预期差、情绪切换、波动放大器和事件驱动，但避免煽动性用语。",
        template_hint="expectation_gap",
    ),
}


def list_horizon_options() -> List[ResearchOption]:
    return list(_HORIZON_OPTIONS.values())


def list_persona_options() -> List[ResearchOption]:
    return list(_PERSONA_OPTIONS.values())


def get_horizon_option(option_id: str) -> ResearchOption:
    return _HORIZON_OPTIONS.get(option_id, _HORIZON_OPTIONS[DEFAULT_HORIZON_ID])


def get_persona_option(option_id: str) -> ResearchOption:
    return _PERSONA_OPTIONS.get(option_id, _PERSONA_OPTIONS[DEFAULT_PERSONA_ID])


def build_variety_option(variety_definition: VarietyDefinition) -> VarietyOption:
    contracts = list(variety_definition.contracts)
    return VarietyOption(
        code=variety_definition.code,
        name=variety_definition.name,
        exchange=variety_definition.exchange,
        contracts=contracts,
        default_contract=contracts[0] if contracts else variety_definition.code,
        key_factors=list(variety_definition.key_factors),
    )


def build_research_preview(
    variety_definition: VarietyDefinition,
    contract: str,
    profile: ResearchProfile | None = None,
) -> ResearchPreview:
    resolved = _resolve_profile(variety_definition, contract, profile)
    return ResearchPreview(
        resolved_symbol=contract,
        variety_code=variety_definition.code,
        variety=variety_definition.name,
        summary=resolved["briefing_summary"],
        key_points=resolved["key_points"],
        writing_directives=resolved["writing_directives"],
        recommended_template=resolved["recommended_template"],
    )


def build_research_request_context(
    variety_definition: VarietyDefinition,
    contract: str,
    profile: ResearchProfile | None = None,
) -> Dict[str, object]:
    resolved = _resolve_profile(variety_definition, contract, profile)
    horizon_option = resolved["horizon_option"]
    persona_option = resolved["persona_option"]
    return {
        "variety_code": variety_definition.code,
        "variety_name": variety_definition.name,
        "resolved_symbol": contract,
        "horizon": horizon_option.id,
        "horizon_label": horizon_option.label,
        "horizon_description": horizon_option.description,
        "horizon_prompt_directive": horizon_option.prompt_directive,
        "persona": persona_option.id,
        "persona_label": persona_option.label,
        "persona_description": persona_option.description,
        "persona_prompt_directive": persona_option.prompt_directive,
        "user_focus": resolved["user_focus"],
        "briefing_summary": resolved["briefing_summary"],
        "key_points": resolved["key_points"],
        "writing_directives": resolved["writing_directives"],
        "recommended_template": resolved["recommended_template"],
    }


def build_preview_fallback_payload(
    variety_definition: VarietyDefinition,
    contract: str,
    profile: ResearchProfile | None = None,
) -> Dict[str, object]:
    preview = build_research_preview(variety_definition, contract, profile)
    return preview.model_dump()


def _resolve_profile(
    variety_definition: VarietyDefinition,
    contract: str,
    profile: ResearchProfile | None,
) -> Dict[str, object]:
    resolved_profile = profile or ResearchProfile()
    horizon_option = get_horizon_option(resolved_profile.horizon)
    persona_option = get_persona_option(resolved_profile.persona)
    key_points = _dedupe(
        list(resolved_profile.key_points) + _extract_focus_points(resolved_profile.user_focus) + variety_definition.key_factors
    )[:4]
    writing_directives = _dedupe(
        list(resolved_profile.writing_directives)
        + [
            "按%s视角组织信息权重。" % persona_option.label,
            "采用%s框架安排论证节奏。" % horizon_option.label,
            "重点回应用户提出的自定义关注点，避免泛泛而谈。",
        ]
    )[:4]
    focus_headline = "、".join(key_points[:3]) if key_points else "盘面驱动与风险边界"
    briefing_summary = resolved_profile.briefing_summary.strip() or (
        "本次将以%s的视角，在%s框架下跟踪%s%s，重点梳理%s。"
        % (
            persona_option.label,
            horizon_option.label,
            variety_definition.name,
            contract,
            focus_headline,
        )
    )
    return {
        "horizon_option": horizon_option,
        "persona_option": persona_option,
        "user_focus": resolved_profile.user_focus.strip(),
        "briefing_summary": briefing_summary,
        "key_points": key_points,
        "writing_directives": writing_directives,
        "recommended_template": resolved_profile.recommended_template or horizon_option.template_hint or "balanced_futures",
    }


def _extract_focus_points(user_focus: str) -> List[str]:
    chunks = re.split(r"[，,。；;、\n]+", user_focus or "")
    candidates = []
    for raw in chunks:
        value = raw.strip()
        if len(value) < 2:
            continue
        candidates.append(value)
    return _dedupe(candidates)


def _dedupe(values: List[str]) -> List[str]:
    seen = set()
    deduped = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped
