from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from futures_research import config
from futures_research.models.review import ReviewResult
from futures_research.models.variety import VarietyDefinition
from futures_research.prompts.analyzer_prompt import (
    ANALYZER_SYSTEM_PROMPT,
    build_analyzer_user_prompt,
)
from futures_research.runtime import RuntimeContext


def _load_review_result(payload: Any) -> Optional[ReviewResult]:
    if payload is None:
        return None
    if isinstance(payload, ReviewResult):
        return payload
    return ReviewResult.model_validate(payload)


def _parse_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).replace(",", "").replace("%", "").strip()
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    return float(match.group(0))


def _infer_sentiment(change_pct: Optional[float], spread: Optional[float]) -> tuple[str, str, str]:
    if change_pct is None:
        return "中性", "低", "当前缺少足够盘面变化信息，观点只能保持克制。"
    if change_pct >= 0.5:
        if spread is not None and spread < 0:
            return "偏多", "中", "盘面涨幅较为明确，但期限结构仍偏近弱，说明强势中仍带谨慎色彩。"
        return "偏多", "中", "盘面涨幅较为明确，短线资金定价偏强。"
    if change_pct <= -0.5:
        if spread is not None and spread < 0:
            return "偏空", "中", "盘面下行且近端承压，短线情绪偏弱。"
        return "偏空", "中", "盘面跌幅较为明确，短线定价偏弱。"
    return "中性", "中", "日内波动仍处窄幅区间，更适合维持震荡观察。"


def _describe_spread(spread: Optional[float]) -> str:
    if spread is None:
        return "当前未取得可核验的近远月价差信息。"
    if spread > 0:
        return "近月强于次主力，期限结构偏强。"
    if spread < 0:
        return "近月弱于次主力，期限结构偏谨慎。"
    return "近远月价差接近持平，期限结构信号有限。"


def _build_local_brief(state: Dict[str, Any], variety_definition: VarietyDefinition) -> Dict[str, Any]:
    raw_data = state["raw_data"]
    metrics = raw_data.get("metrics", {})
    data_gaps = raw_data.get("data_gaps", [])
    workflow = raw_data.get("research_workflow", {})
    spread = _parse_number(metrics.get("近月-远月价差"))
    change_pct = _parse_number(metrics.get("主力合约涨跌幅"))
    sentiment, confidence, reasoning = _infer_sentiment(change_pct, spread)
    factor_1 = variety_definition.key_factors[0] if variety_definition.key_factors else "供给端节奏"
    factor_2 = variety_definition.key_factors[1] if len(variety_definition.key_factors) > 1 else "需求端表现"
    factor_3 = variety_definition.key_factors[2] if len(variety_definition.key_factors) > 2 else "期限结构"
    factor_4 = variety_definition.key_factors[3] if len(variety_definition.key_factors) > 3 else "外部联动"
    return {
        "sentiment": sentiment,
        "confidence": confidence,
        "core_view": "当前盘面观点为{sentiment}，{reasoning}".format(sentiment=sentiment, reasoning=reasoning),
        "supply_view": "{factor} 仍是研究主线，但当前缺少直接验证数据，供给端只保留待验证框架。".format(
            factor=factor_1
        ),
        "demand_view": "{factor} 对价格中枢重要，但当前没有真实结构化数字，因此需求端暂不扩写为确定结论。".format(
            factor=factor_2
        ),
        "inventory_view": "当前只能确认盘面活跃度与期限结构，库存和仓单数据仍待补充。",
        "international_view": "{factor} 需要继续跟踪，但在国际盘与海外供需数字接入前，只保留框架提醒。".format(
            factor=factor_4
        ),
        "event_view": "最新快照与期限结构已可核验，其余重要事件仍需等结构化数据继续补全。",
        "key_factor_views": [
            "盘面涨跌反映日内资金定价方向。",
            _describe_spread(spread),
            "交易活跃度说明盘面并非无量波动。",
            "研究边界需要被明确写出，不能把缺口伪装成结论。",
        ],
        "risk_views": [
            "旧快照不能替代今日事实。",
            "缺少基本面数字时，盘面判断不能等同于产业链结论。",
            "若后续真实基本面数据与盘面信号背离，观点需要及时修正。",
        ],
        "fact_pack_summary": {
            "price": metrics.get("主力合约参考价", "暂无"),
            "change": metrics.get("主力合约涨跌", "暂无"),
            "change_pct": metrics.get("主力合约涨跌幅", "暂无"),
            "spread": metrics.get("近月-远月价差", "暂无"),
            "open_interest": metrics.get("主力合约持仓量", "暂无"),
            "volume": metrics.get("主力合约成交量", "暂无"),
            "trading_day": metrics.get("主力合约交易日", "暂无"),
            "update_time": metrics.get("主力合约更新时间", "暂无"),
            "blocking_reason": workflow.get("blocking_reason") or "无",
            "data_gap_1": data_gaps[0] if data_gaps else "暂无",
        },
    }


def _build_fact_pack_for_llm(state: Dict[str, Any], variety_definition: VarietyDefinition, next_round: int) -> Dict[str, Any]:
    raw_data = state["raw_data"]
    metrics = raw_data.get("metrics", {})
    workflow = raw_data.get("research_workflow", {})
    return {
        "variety": variety_definition.name,
        "variety_code": variety_definition.code,
        "contract": state["symbol"],
        "target_date": str(state["target_date"]),
        "key_factors": variety_definition.key_factors,
        "market_context": raw_data.get("market_context", ""),
        "verified_facts": raw_data.get("verified_facts", []),
        "metrics": {
            "price": metrics.get("主力合约参考价", "暂无"),
            "change": metrics.get("主力合约涨跌", "暂无"),
            "change_pct": metrics.get("主力合约涨跌幅", "暂无"),
            "spread": metrics.get("近月-远月价差", "暂无"),
            "open_interest": metrics.get("主力合约持仓量", "暂无"),
            "volume": metrics.get("主力合约成交量", "暂无"),
            "trading_day": metrics.get("主力合约交易日", "暂无"),
            "update_time": metrics.get("主力合约更新时间", "暂无"),
        },
        "data_gaps": raw_data.get("data_gaps", []),
        "constraints": {
            "no_new_numbers": True,
            "no_new_sources": True,
            "no_digits_in_output": True,
            "no_source_labels_in_output": True,
            "only_describe_relationships_and_views": True,
            "can_write_formal_report": workflow.get("can_write_formal_report", False),
            "blocking_reason": workflow.get("blocking_reason") or "无",
        },
        "requested_review_round": next_round,
    }


def _extract_json_object(text: str) -> Dict[str, Any]:
    fenced = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.S)
    candidate = fenced.group(1) if fenced else text.strip()
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model response.")
    return json.loads(candidate[start : end + 1])


def _validate_hybrid_brief(payload: Dict[str, Any]) -> Dict[str, Any]:
    required_keys = [
        "sentiment",
        "confidence",
        "core_view",
        "supply_view",
        "demand_view",
        "inventory_view",
        "international_view",
        "event_view",
        "key_factor_views",
        "risk_views",
    ]
    for key in required_keys:
        if key not in payload:
            raise ValueError("Hybrid analysis payload missing key: %s" % key)
    text_fields = [
        payload["sentiment"],
        payload["confidence"],
        payload["core_view"],
        payload["supply_view"],
        payload["demand_view"],
        payload["inventory_view"],
        payload["international_view"],
        payload["event_view"],
        *payload.get("key_factor_views", []),
        *payload.get("risk_views", []),
    ]
    for value in text_fields:
        if not isinstance(value, str):
            raise ValueError("Hybrid analysis payload contains non-string text field.")
        if re.search(r"\d", value):
            raise ValueError("Hybrid analysis payload must not contain digits.")
        if "来源" in value or "CTP" in value or "http" in value:
            raise ValueError("Hybrid analysis payload must not contain source labels.")
    return payload


def _render_analysis_markdown(brief: Dict[str, Any], state: Dict[str, Any]) -> str:
    raw_data = state["raw_data"]
    metrics = raw_data.get("metrics", {})
    facts = raw_data.get("verified_facts", [])
    workflow = raw_data.get("research_workflow", {})
    return """
## 核心观点
{core_view}

## 基本面分析
### 供给端
{supply_view}
### 需求端
{demand_view}
### 库存
{inventory_view}

## 国际联动
{international_view}

## 近期重要事件
{event_view}

## 核心驱动因子
1. {factor_1}
2. {factor_2}
3. {factor_3}
4. {factor_4}

## 风险提示
1. {risk_1}
2. {risk_2}
3. {risk_3}

## 情绪判断
{sentiment}，置信度：{confidence}。

已核验事实：
{facts}

写作约束：
- can_write_formal_report = {can_write_formal_report}
- blocking_reason = {blocking_reason}
- 真实价格 = {price}
- 真实涨跌 = {change}
- 真实涨跌幅 = {change_pct}
- 真实近远月价差 = {spread}
""".strip().format(
        core_view=brief["core_view"],
        supply_view=brief["supply_view"],
        demand_view=brief["demand_view"],
        inventory_view=brief["inventory_view"],
        international_view=brief["international_view"],
        event_view=brief["event_view"],
        factor_1=brief["key_factor_views"][0],
        factor_2=brief["key_factor_views"][1],
        factor_3=brief["key_factor_views"][2],
        factor_4=brief["key_factor_views"][3],
        risk_1=brief["risk_views"][0],
        risk_2=brief["risk_views"][1],
        risk_3=brief["risk_views"][2],
        sentiment=brief["sentiment"],
        confidence=brief["confidence"],
        facts="\n".join("- {fact}".format(fact=fact) for fact in facts) or "- 暂无",
        can_write_formal_report=workflow.get("can_write_formal_report", False),
        blocking_reason=workflow.get("blocking_reason") or "无",
        price=metrics.get("主力合约参考价", "暂无"),
        change=metrics.get("主力合约涨跌", "暂无"),
        change_pct=metrics.get("主力合约涨跌幅", "暂无"),
        spread=metrics.get("近月-远月价差", "暂无"),
    )


async def _generate_hybrid_brief(
    state: Dict[str, Any],
    runtime: RuntimeContext,
    variety_definition: VarietyDefinition,
    review_result: Optional[ReviewResult],
    next_round: int,
) -> Dict[str, Any]:
    fact_pack = _build_fact_pack_for_llm(state, variety_definition, next_round)
    review_feedback = ""
    if review_result and not review_result.passed:
        review_feedback = "上一轮审核反馈：{feedback}\n必须修复：{issues}".format(
            feedback=review_result.feedback,
            issues="；".join(review_result.blocking_issues) or "无",
        )
    prompt = """
{system_prompt}

你现在处于混合模式：
1. 真实数据只来自下面的 fact pack。
2. 你只能做观点组织、语言润色、逻辑串联。
3. 绝对禁止新增任何数字、日期、百分比、来源、机构名、网址。
4. 输出中不能出现阿拉伯数字，不能出现“来源”、“CTP”、“http”。
5. 对缺失字段必须明确写成“缺少直接验证数据”或同义表达。
6. 允许基于 fact pack 做方向性总结，例如“盘面偏强”“近端承压”，但不允许编造新的事实。

请严格输出 JSON，对象结构如下：
{{
  "sentiment": "偏多/中性/偏空",
  "confidence": "高/中/低",
  "core_view": "...",
  "supply_view": "...",
  "demand_view": "...",
  "inventory_view": "...",
  "international_view": "...",
  "event_view": "...",
  "key_factor_views": ["...", "...", "...", "..."],
  "risk_views": ["...", "...", "..."]
}}

{review_feedback}

fact pack:
{fact_pack}
""".strip().format(
        system_prompt=ANALYZER_SYSTEM_PROMPT,
        review_feedback=review_feedback or "本轮为首轮分析。",
        fact_pack=json.dumps(fact_pack, ensure_ascii=False, indent=2),
    )
    raw_response = await runtime.llm_client.generate_analysis(prompt, context={"fact_pack": fact_pack})
    return _validate_hybrid_brief(_extract_json_object(raw_response))


async def analyze_node(state: Dict[str, Any], runtime: RuntimeContext) -> Dict[str, Any]:
    variety_definition = runtime.variety_registry.get(state["variety_code"])
    review_result = _load_review_result(state.get("review_result"))
    next_round = int(state.get("review_round", 0)) + 1
    raw_data = dict(state["raw_data"])

    if config.ANALYSIS_RENDER_MODE == "llm":
        user_prompt = build_analyzer_user_prompt(
            variety_definition=variety_definition,
            prompt_repository=runtime.prompt_repository,
            raw_data=raw_data,
            review_result=review_result,
            next_round=next_round,
        )
        analysis_result = await runtime.llm_client.generate_analysis(
            "%s\n\n%s" % (ANALYZER_SYSTEM_PROMPT, user_prompt),
            context={
                "variety_name": variety_definition.name,
                "contract": state["symbol"],
                "target_date": str(state["target_date"]),
                "key_factors": variety_definition.key_factors,
                "raw_data": raw_data,
                "review_feedback": review_result.feedback if review_result else "",
                "blocking_issues": review_result.blocking_issues if review_result else [],
                "requested_review_round": next_round,
            },
        )
        return {
            "current_step": "analyze",
            "analysis_result": analysis_result,
        }

    if config.ANALYSIS_RENDER_MODE == "hybrid" and runtime.llm_client.is_live:
        try:
            brief = await _generate_hybrid_brief(state, runtime, variety_definition, review_result, next_round)
        except Exception:
            brief = _build_local_brief(state, variety_definition)
    else:
        brief = _build_local_brief(state, variety_definition)

    raw_data["analysis_brief"] = brief
    analysis_result = _render_analysis_markdown(brief, state)
    return {
        "current_step": "analyze",
        "analysis_result": analysis_result,
        "raw_data": raw_data,
    }
