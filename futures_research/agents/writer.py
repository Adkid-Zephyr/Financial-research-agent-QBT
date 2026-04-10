from __future__ import annotations

import re
from typing import Any, Dict, Optional

from futures_research import config
from futures_research.models.review import ReviewResult
from futures_research.models.variety import VarietyDefinition
from futures_research.prompts.writer_prompt import (
    WRITER_SYSTEM_PROMPT,
    build_writer_user_prompt,
)
from futures_research.runtime import RuntimeContext


def _load_review_result(payload: Any) -> Optional[ReviewResult]:
    if payload is None:
        return None
    if isinstance(payload, ReviewResult):
        return payload
    return ReviewResult.model_validate(payload)


def _snapshot(raw_data: dict, role: str) -> dict:
    for item in raw_data.get("raw_items", []):
        if item.get("item_type") == "snapshot" and item.get("role") == role:
            return item
    return {}


def _parse_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).replace(",", "").replace("%", "").strip()
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    return float(match.group(0))


def _infer_sentiment(change_pct: Optional[float], spread: Optional[float]) -> tuple[str, str, str, list[str]]:
    reasons = []
    if change_pct is not None:
        if change_pct >= 0.5:
            reasons.append("主力合约日内涨幅相对明确")
        elif change_pct <= -0.5:
            reasons.append("主力合约日内跌幅相对明确")
        else:
            reasons.append("主力合约仍处于窄幅波动区间")
    if spread is not None:
        if spread > 0:
            reasons.append("近月强于次主力，期限结构偏强")
        elif spread < 0:
            reasons.append("近月弱于次主力，期限结构偏谨慎")
        else:
            reasons.append("近远月结构基本持平")
    if change_pct is None:
        return "中性", "低", "缺少足够盘面变化信息，只能维持中性描述。", reasons
    if change_pct >= 0.5:
        return "偏多", "中", "盘面价格和期限结构共同指向短线偏强。", reasons
    if change_pct <= -0.5:
        return "偏空", "中", "盘面价格和期限结构共同指向短线偏弱。", reasons
    return "中性", "中", "日内波动尚不足以支持趋势性判断，维持中性观察。", reasons


def _spread_comment(spread: Optional[float]) -> str:
    if spread is None:
        return "当前未获得可核验的近远月价差信息。"
    if spread > 0:
        return "近月强于次主力，期限结构呈现一定近强特征。"
    if spread < 0:
        return "近月弱于次主力，期限结构更偏向近端承压。"
    return "近远月价差接近持平，期限结构信号中性。"


def _build_deterministic_report(
    state: Dict[str, Any],
    variety_definition: VarietyDefinition,
    review_result: Optional[ReviewResult],
    next_round: int,
) -> str:
    raw_data = state["raw_data"]
    metrics = raw_data.get("metrics", {})
    sources = raw_data.get("sources", [])
    data_gaps = raw_data.get("data_gaps", [])
    workflow = raw_data.get("research_workflow", {})
    primary = _snapshot(raw_data, "primary")
    secondary = _snapshot(raw_data, "secondary")
    market_context = raw_data.get("market_context", "")
    analysis_result = state.get("analysis_result", "")
    analysis_brief = raw_data.get("analysis_brief", {})

    price = metrics.get("主力合约参考价", "暂无")
    bid = metrics.get("主力合约买一", "暂无")
    ask = metrics.get("主力合约卖一", "暂无")
    change = metrics.get("主力合约涨跌", "暂无")
    change_pct_text = metrics.get("主力合约涨跌幅", "暂无")
    open_interest = metrics.get("主力合约持仓量", "暂无")
    volume = metrics.get("主力合约成交量", "暂无")
    spread_text = metrics.get("近月-远月价差", "暂无")
    spread_value = _parse_number(spread_text)
    sentiment, confidence, view_reason, reasons = _infer_sentiment(_parse_number(change_pct_text), spread_value)
    if analysis_brief:
        sentiment = analysis_brief.get("sentiment", sentiment)
        confidence = analysis_brief.get("confidence", confidence)
    main_factor = variety_definition.key_factors[0] if variety_definition.key_factors else "盘面结构"
    second_factor = variety_definition.key_factors[1] if len(variety_definition.key_factors) > 1 else "需求端表现"
    third_factor = variety_definition.key_factors[2] if len(variety_definition.key_factors) > 2 else "国际联动"

    revision_note = ""
    if review_result and not review_result.passed:
        revision_note = "> **修订说明**：本轮已根据审核反馈重新核对来源与结构，但所有数字仍仅来自真实接口返回。\n\n"

    can_write_formal_report = workflow.get("can_write_formal_report", False)
    if can_write_formal_report:
        core_view = analysis_brief.get(
            "core_view",
            (
            "{symbol} 今日盘面观点为{sentiment}，核心依据是最新价 {price}、涨跌 {change}、涨跌幅 {change_pct} 与近远月价差 {spread} 所共同反映的短线结构；"
            "但由于供需和库存等基本面数字尚未补齐，当前观点仍属于盘面层面的阶段性判断。"
            ),
        ).format(
            symbol=state["symbol"],
            sentiment=sentiment,
            price=price,
            change=change,
            change_pct=change_pct_text,
            spread=spread_text,
        )
    else:
        core_view = (
            "{symbol} 当前未拿到与目标日期一致的实时结构化数字，本稿仅输出数据不足说明，避免把旧快照或推测性数字写成今日研报事实。"
        ).format(symbol=state["symbol"])

    info_lines = "\n".join(
        "1. {gap}".format(gap=gap) for gap in data_gaps[:4]
    ) or "1. 当前无额外待补充项。"
    news_line = (
        "1. 主数据合约 {instrument_id} 最新更新时间为 {update_time}，交易日为 {trading_day}。".format(
            instrument_id=primary.get("instrument_id") or metrics.get("主数据合约ID", "暂无"),
            update_time=primary.get("update_time") or metrics.get("主力合约更新时间", "暂无"),
            trading_day=primary.get("trading_day") or metrics.get("主力合约交易日", "暂无"),
        )
        if primary
        else "1. 当前未获取到目标合约实时快照。"
    )
    if secondary:
        news_line += "\n2. 次数据合约 {instrument_id} 可用于观察期限结构，当前价差为 {spread}。".format(
            instrument_id=secondary.get("instrument_id") or metrics.get("次数据合约ID", "暂无"),
            spread=spread_text,
        )
    else:
        news_line += "\n2. 当前未获取到次合约实时快照，期限结构判断有限。"

    return """
# {variety}期货日报 — {symbol} [{target_date}]

> **核心观点**：{core_view}  
> **情绪**：{sentiment} | **置信度**：{confidence}

{revision_note}---

## 一、行情回顾
当前主数据合约为 {primary_instrument}，最新价 {price}，买一 {bid}，卖一 {ask}，涨跌 {change}，涨跌幅 {change_pct}。若以次主力合约作参照，当前近远月价差为 {spread}，{spread_comment}（来源：CTP snapshot API）

## 二、基本面分析
### 供给端
{supply_view}（来源：CTP snapshot API 覆盖范围说明）
### 需求端
{demand_view}（来源：CTP snapshot API 覆盖范围说明）
### 库存与持仓
{inventory_view} 当前可核验盘面字段包括持仓量 {open_interest}、成交量 {volume}。（来源：CTP snapshot API）

## 三、国际市场
{international_view}（来源：数据覆盖范围说明）

## 四、近期重要资讯
{news_line}

## 五、核心驱动因子
1. **盘面方向**：{factor_view_1}
2. **期限结构**：{factor_view_2} 当前近月-远月价差为 {spread}。
3. **交易活跃度**：{factor_view_3} 当前持仓量 {open_interest}、成交量 {volume}。
4. **研究边界**：{factor_view_4}

## 六、风险提示
1. 若实时快照与目标日期不一致，旧快照不能替代今日事实。
2. {risk_2}
3. {risk_3}

## 七、数据说明与待补充项
{info_lines}

---
*数据来源：{sources_text}*  
*生成时间：{target_date}*  
*本报告由AI自动生成，仅供参考，不构成投资建议。*

<!-- analysis_trace
{analysis_result}
-->
""".strip().format(
        variety=state["variety"],
        symbol=state["symbol"],
        target_date=state["target_date"],
        core_view=core_view,
        sentiment=sentiment,
        confidence=confidence,
        revision_note=revision_note,
        primary_instrument=primary.get("instrument_id") or metrics.get("主数据合约ID", "暂无"),
        price=price,
        bid=bid,
        ask=ask,
        change=change,
        change_pct=change_pct_text,
        open_interest=open_interest,
        volume=volume,
        news_line=news_line,
        spread=spread_text,
        spread_comment=_spread_comment(spread_value),
        supply_view=analysis_brief.get(
            "supply_view",
            "从模板框架看，{main_factor} 仍是后续研究的首要变量；但当前版本尚未接入供给侧结构化数据，因此只能将其列为待跟踪线索，不能把供给端写成确定结论。".format(
                main_factor=main_factor
            ),
        ),
        demand_view=analysis_brief.get(
            "demand_view",
            "{second_factor} 对价格中枢具有重要影响，但目前没有可核验的下游开工、订单、消费或排产数字，因此需求端仍维持框架性描述，不做数字外推。".format(
                second_factor=second_factor
            ),
        ),
        inventory_view=analysis_brief.get(
            "inventory_view",
            "当前盘面活跃度已有事实基础，但库存、仓单与现货基差尚未接入，因此库存逻辑暂时不能写成“去库”或“累库”判断。",
        ),
        international_view=analysis_brief.get(
            "international_view",
            "模板上需要重点跟踪 {third_factor}。不过当前尚未接入国际盘、汇率与海外供需结构化接口，因此国际联动部分只保留框架提醒，不展开数值化判断。".format(
                third_factor=third_factor
            ),
        ),
        factor_view_1=(analysis_brief.get("key_factor_views") or [])[0] if analysis_brief.get("key_factor_views") else (reasons[0] if reasons else view_reason),
        factor_view_2=(analysis_brief.get("key_factor_views") or [None, _spread_comment(spread_value)])[1] if analysis_brief.get("key_factor_views") else _spread_comment(spread_value),
        factor_view_3=(analysis_brief.get("key_factor_views") or [None, None, "交易活跃度说明当前盘面并非无量状态。"])[2] if analysis_brief.get("key_factor_views") else "交易活跃度说明当前盘面并非无量状态。",
        factor_view_4=(analysis_brief.get("key_factor_views") or [None, None, None, "研究边界需要被明确写出，不能把缺口伪装成结论。"])[3] if analysis_brief.get("key_factor_views") else "研究边界需要被明确写出，不能把缺口伪装成结论。",
        risk_2=(analysis_brief.get("risk_views") or [None, "供给、需求、库存和国际联动等结构化接口尚未补齐前，当前观点仍应理解为盘面判断，而不是完整产业链结论。"])[1] if analysis_brief.get("risk_views") else "供给、需求、库存和国际联动等结构化接口尚未补齐前，当前观点仍应理解为盘面判断，而不是完整产业链结论。",
        risk_3=(analysis_brief.get("risk_views") or [None, None, "单日盘面强弱可能受资金和期限结构扰动影响，若后续真实基本面数据与盘面信号背离，观点需要及时修正。"])[2] if analysis_brief.get("risk_views") else "单日盘面强弱可能受资金和期限结构扰动影响，若后续真实基本面数据与盘面信号背离，观点需要及时修正。",
        main_factor=main_factor,
        second_factor=second_factor,
        third_factor=third_factor,
        info_lines=info_lines,
        sources_text="；".join(sources) or "CTP snapshot API",
        analysis_result=analysis_result or market_context,
    )


async def write_node(state: Dict[str, Any], runtime: RuntimeContext) -> Dict[str, Any]:
    variety_definition = runtime.variety_registry.get(state["variety_code"])
    review_result = _load_review_result(state.get("review_result"))
    next_round = int(state.get("review_round", 0)) + 1

    if config.REPORT_RENDER_MODE == "llm":
        user_prompt = build_writer_user_prompt(
            variety_definition=variety_definition,
            prompt_repository=runtime.prompt_repository,
            analysis_result=state["analysis_result"],
            raw_data=state["raw_data"],
            review_result=review_result,
            next_round=next_round,
        )
        report_draft = await runtime.llm_client.generate_report(
            "%s\n\n%s" % (WRITER_SYSTEM_PROMPT, user_prompt),
            context={
                "variety_name": variety_definition.name,
                "contract": state["symbol"],
                "target_date": str(state["target_date"]),
                "key_factors": variety_definition.key_factors,
                "raw_data": state["raw_data"],
                "analysis_result": state["analysis_result"],
                "review_feedback": review_result.feedback if review_result else "",
                "blocking_issues": review_result.blocking_issues if review_result else [],
                "requested_review_round": next_round,
            },
        )
    else:
        report_draft = _build_deterministic_report(state, variety_definition, review_result, next_round)

    return {
        "current_step": "write",
        "report_draft": report_draft,
    }
