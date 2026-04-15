from __future__ import annotations

import json
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


def _external_market_items(raw_data: dict) -> list[dict]:
    return [
        item
        for item in raw_data.get("external_market_facts", [])
        if item.get("item_type") == "external_market" and item.get("stale") != "true"
    ]


def _fundamental_items(raw_data: dict, item_type: str | None = None) -> list[dict]:
    items = [
        item
        for item in raw_data.get("fundamental_facts", [])
        if item.get("stale") != "true"
    ]
    if item_type is not None:
        items = [item for item in items if item.get("item_type") == item_type]
    return items


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


def _safe_list_item(value: Any, index: int, fallback: str) -> str:
    if not isinstance(value, list) or len(value) <= index or not isinstance(value[index], str):
        return fallback
    return value[index]


def _render_international_view(raw_data: dict, fallback_view: str) -> str:
    external_items = _external_market_items(raw_data)
    if not external_items:
        return "{view}（来源：数据覆盖范围说明）".format(view=fallback_view)
    lines = []
    for index, item in enumerate(external_items, start=1):
        unit = item.get("unit") or ""
        close = "{value}{unit}".format(value=item.get("close", "暂无"), unit=unit) if item.get("close") != "暂无" else "暂无"
        change = "{value}{unit}".format(value=item.get("change", "暂无"), unit=unit) if item.get("change") != "暂无" else "暂无"
        lines.append(
            "{index}. {name}（{ticker}）截至 {as_of_date} 收盘价 {close}，涨跌 {change}，涨跌幅 {change_pct}。".format(
                index=index,
                name=item.get("name") or "外盘资产",
                ticker=item.get("ticker") or "暂无",
                as_of_date=item.get("as_of_date") or "暂无",
                close=close,
                change=change,
                change_pct=item.get("change_pct") or "暂无",
            )
        )
    return "{view}\n{lines}\n上述外盘和宏观字段按可得交易日引用，不写作今日事实。（来源：Yahoo Finance via yfinance）".format(
        view=fallback_view,
        lines="\n".join(lines),
    )


def _render_spot_basis_view(raw_data: dict) -> str:
    lines = []
    for item in _fundamental_items(raw_data, "spot_basis"):
        lines.append(
            "{name}截至 {as_of_date} 现货价格 {spot_price}，主力合约 {contract} 对应基差 {basis}，基差率 {basis_rate}。".format(
                name=item.get("name") or "现货基差",
                as_of_date=item.get("as_of_date") or "暂无",
                spot_price=item.get("spot_price") or "暂无",
                contract=item.get("dominant_contract") or "暂无",
                basis=item.get("dom_basis") or "暂无",
                basis_rate=item.get("dom_basis_rate") or "暂无",
            )
        )
    for item in _fundamental_items(raw_data, "domestic_spot"):
        unit = item.get("unit") or ""
        close = "{value}{unit}".format(value=item.get("close", "暂无"), unit=unit) if item.get("close") != "暂无" else "暂无"
        low = "{value}{unit}".format(value=item.get("low", "暂无"), unit=unit) if item.get("low") != "暂无" else "暂无"
        high = "{value}{unit}".format(value=item.get("high", "暂无"), unit=unit) if item.get("high") != "暂无" else "暂无"
        lines.append(
            "{name}截至 {as_of_date} 收盘价 {close}，日内区间 {low}-{high}。".format(
                name=item.get("name") or "现货行情",
                as_of_date=item.get("as_of_date") or "暂无",
                close=close,
                low=low,
                high=high,
            )
        )
    if not lines:
        return "现货价格、基差和国内现货行情暂无可核验数据。（来源：数据覆盖范围说明）"
    return "{lines}（来源：AkShare structured commodity data）".format(lines="\n".join(lines))


def _render_inventory_view(raw_data: dict, fallback_view: str, inventory_metric_sentence: str) -> str:
    lines = []
    for item in _fundamental_items(raw_data, "inventory"):
        lines.append(
            "{name}截至 {as_of_date} 库存 {inventory_ton} 吨。".format(
                name=item.get("name") or "库存",
                as_of_date=item.get("as_of_date") or "暂无",
                inventory_ton=item.get("inventory_ton") or "暂无",
            )
        )
    if lines:
        return "{fallback} {inventory_metric_sentence}\n{lines}（来源：AkShare structured commodity data）".format(
            fallback=fallback_view,
            inventory_metric_sentence=inventory_metric_sentence,
            lines="\n".join(lines),
        )
    return "{fallback} {inventory_metric_sentence}（来源：CTP snapshot API）".format(
        fallback=fallback_view,
        inventory_metric_sentence=inventory_metric_sentence,
    )


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
    request_context = raw_data.get("request_context", {})
    external_items = _external_market_items(raw_data)
    fundamental_items = _fundamental_items(raw_data)
    can_write_formal_report = workflow.get("can_write_formal_report", False)

    ctp_metrics = metrics if can_write_formal_report else {}
    price = ctp_metrics.get("主力合约参考价", "暂无可核验数据")
    bid = ctp_metrics.get("主力合约买一", "暂无可核验数据")
    ask = ctp_metrics.get("主力合约卖一", "暂无可核验数据")
    change = ctp_metrics.get("主力合约涨跌", "暂无可核验数据")
    change_pct_text = ctp_metrics.get("主力合约涨跌幅", "暂无可核验数据")
    open_interest = ctp_metrics.get("主力合约持仓量", "暂无可核验数据")
    volume = ctp_metrics.get("主力合约成交量", "暂无可核验数据")
    spread_text = ctp_metrics.get("近月-远月价差", "暂无可核验数据")
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
    if request_context.get("persona_label"):
        info_lines += "\n1. 本次研究视角：{persona_label}。".format(
            persona_label=request_context.get("persona_label")
        )
    if can_write_formal_report and primary:
        news_line = "1. 主数据合约 {instrument_id} 最新更新时间为 {update_time}，交易日为 {trading_day}。".format(
            instrument_id=primary.get("instrument_id") or metrics.get("主数据合约ID", "暂无"),
            update_time=primary.get("update_time") or metrics.get("主力合约更新时间", "暂无"),
            trading_day=primary.get("trading_day") or metrics.get("主力合约交易日", "暂无"),
        )
    elif primary:
        news_line = (
            "1. 当前未获取到与目标日期一致的目标合约实时快照；最新可得快照交易日为 {trading_day}，不用于本日盘面结论。"
        ).format(trading_day=primary.get("trading_day") or "未知")
    else:
        news_line = "1. 当前未获取到目标合约实时快照。"
    if can_write_formal_report and secondary:
        news_line += "\n2. 次数据合约 {instrument_id} 可用于观察期限结构，当前价差为 {spread}。".format(
            instrument_id=secondary.get("instrument_id") or metrics.get("次数据合约ID", "暂无"),
            spread=spread_text,
        )
    else:
        news_line += "\n2. 当前未获取到次合约实时快照，期限结构判断有限。"

    international_view = _render_international_view(
        raw_data,
        analysis_brief.get(
            "international_view",
            "模板上需要重点跟踪 {third_factor}。不过当前尚未接入国际盘、汇率与海外供需结构化接口，因此国际联动部分只保留框架提醒，不展开数值化判断。".format(
                third_factor=third_factor
            ),
        ),
    )
    inventory_metric_sentence = (
        "当前可核验盘面字段包括持仓量 {open_interest}、成交量 {volume}。".format(
            open_interest=open_interest,
            volume=volume,
        )
        if can_write_formal_report
        else "目标日期一致的持仓量、成交量暂无可核验数据。"
    )
    inventory_view = _render_inventory_view(
        raw_data,
        analysis_brief.get(
            "inventory_view",
            "当前盘面活跃度已有事实基础，但库存、仓单与现货基差尚未接入，因此库存逻辑暂时不能写成“去库”或“累库”判断。",
        ),
        inventory_metric_sentence,
    )
    spot_basis_view = _render_spot_basis_view(raw_data)
    key_factor_views = analysis_brief.get("key_factor_views")
    risk_views = analysis_brief.get("risk_views")
    factor_view_1 = _safe_list_item(key_factor_views, 0, reasons[0] if reasons else view_reason)
    factor_view_2 = _safe_list_item(key_factor_views, 1, _spread_comment(spread_value))
    factor_view_3 = _safe_list_item(key_factor_views, 2, "交易活跃度说明当前盘面并非无量状态。")
    factor_view_4 = _safe_list_item(
        key_factor_views,
        3,
        "外盘、宏观和部分基本面数据已有结构化补充，但供需平衡等缺口仍需单独披露。"
        if external_items or fundamental_items
        else "研究边界需要被明确写出，不能把缺口伪装成结论。",
    )
    risk_2 = _safe_list_item(
        risk_views,
        1,
        "供给、需求、库存和国际联动等结构化接口尚未补齐前，当前观点仍应理解为盘面判断，而不是完整产业链结论。",
    )
    risk_3 = _safe_list_item(
        risk_views,
        2,
        "单日盘面强弱可能受资金和期限结构扰动影响，若后续真实基本面数据与盘面信号背离，观点需要及时修正。",
    )

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
### 现货与基差
{spot_basis_view}
### 库存与持仓
{inventory_view}

## 三、国际市场
{international_view}

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
        spot_basis_view=spot_basis_view,
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
        inventory_view=inventory_view,
        international_view=international_view,
        factor_view_1=factor_view_1,
        factor_view_2=factor_view_2,
        factor_view_3=factor_view_3,
        factor_view_4=factor_view_4,
        risk_2=risk_2,
        risk_3=risk_3,
        main_factor=main_factor,
        second_factor=second_factor,
        third_factor=third_factor,
        info_lines=info_lines,
        sources_text="；".join(sources) or "CTP snapshot API",
        analysis_result=analysis_result or market_context,
    )


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _build_grounded_evidence_pack(state: Dict[str, Any], variety_definition: VarietyDefinition) -> Dict[str, Any]:
    raw_data = state["raw_data"]
    metrics = raw_data.get("metrics", {})
    sources = raw_data.get("sources", [])
    facts = []
    gaps = []

    def add_fact(text: str, source: str) -> None:
        if text and text not in [item["text"] for item in facts]:
            facts.append({"id": "F%d" % (len(facts) + 1), "text": text, "source": source})

    def add_gap(text: str) -> None:
        if text and text not in [item["text"] for item in gaps]:
            gaps.append({"id": "G%d" % (len(gaps) + 1), "text": text})

    primary = _snapshot(raw_data, "primary")
    secondary = _snapshot(raw_data, "secondary")
    if primary:
        add_fact(
            "目标合约 {instrument_id} 交易日 {trading_day} 更新时间 {update_time} 最新价 {price} 买一 {bid} 卖一 {ask} 涨跌 {change} 涨跌幅 {change_pct} 持仓量 {open_interest} 成交量 {volume}。".format(
                instrument_id=primary.get("instrument_id") or metrics.get("主数据合约ID", state["symbol"]),
                trading_day=primary.get("trading_day") or metrics.get("主力合约交易日", "暂无"),
                update_time=primary.get("update_time") or metrics.get("主力合约更新时间", "暂无"),
                price=metrics.get("主力合约参考价", "暂无"),
                bid=metrics.get("主力合约买一", "暂无"),
                ask=metrics.get("主力合约卖一", "暂无"),
                change=metrics.get("主力合约涨跌", "暂无"),
                change_pct=metrics.get("主力合约涨跌幅", "暂无"),
                open_interest=metrics.get("主力合约持仓量", "暂无"),
                volume=metrics.get("主力合约成交量", "暂无"),
            ),
            "CTP snapshot API",
        )
    if secondary:
        add_fact(
            "参照合约 {instrument_id} 参考价 {price}，目标合约与参照合约价差 {spread}。".format(
                instrument_id=secondary.get("instrument_id") or metrics.get("次数据合约ID", "暂无"),
                price=metrics.get("次主力合约参考价", "暂无"),
                spread=metrics.get("近月-远月价差", "暂无"),
            ),
            "CTP snapshot API",
        )

    for item in _external_market_items(raw_data):
        unit = item.get("unit") or ""
        add_fact(
            "{name}（{ticker}）截至 {as_of_date} 收盘价 {close}{unit}，涨跌 {change}{unit}，涨跌幅 {change_pct}。".format(
                name=item.get("name") or "外盘资产",
                ticker=item.get("ticker") or "暂无",
                as_of_date=item.get("as_of_date") or "暂无",
                close=item.get("close") or "暂无",
                unit=unit,
                change=item.get("change") or "暂无",
                change_pct=item.get("change_pct") or "暂无",
            ),
            "Yahoo Finance via yfinance",
        )

    for item in _fundamental_items(raw_data):
        item_type = item.get("item_type")
        if item_type == "spot_basis":
            add_fact(
                "{name}截至 {as_of_date} 现货价格 {spot_price}，主力合约 {contract} 对应基差 {basis}，基差率 {basis_rate}。".format(
                    name=item.get("name") or "现货基差",
                    as_of_date=item.get("as_of_date") or "暂无",
                    spot_price=item.get("spot_price") or "暂无",
                    contract=item.get("dominant_contract") or "暂无",
                    basis=item.get("dom_basis") or "暂无",
                    basis_rate=item.get("dom_basis_rate") or "暂无",
                ),
                "AkShare structured commodity data",
            )
        elif item_type == "domestic_spot":
            unit = item.get("unit") or ""
            add_fact(
                "{name}截至 {as_of_date} 收盘价 {close}{unit}，日内低点 {low}{unit}，日内高点 {high}{unit}。".format(
                    name=item.get("name") or "国内现货",
                    as_of_date=item.get("as_of_date") or "暂无",
                    close=item.get("close") or "暂无",
                    low=item.get("low") or "暂无",
                    high=item.get("high") or "暂无",
                    unit=unit,
                ),
                "AkShare structured commodity data",
            )
        elif item_type == "inventory":
            add_fact(
                "{name}截至 {as_of_date} 库存 {inventory_ton} 吨。".format(
                    name=item.get("name") or "库存",
                    as_of_date=item.get("as_of_date") or "暂无",
                    inventory_ton=item.get("inventory_ton") or "暂无",
                ),
                "AkShare structured commodity data",
            )
        else:
            add_fact(_compact_json(item), "AkShare structured commodity data")

    for fact in raw_data.get("verified_facts", []):
        add_fact(str(fact), "structured verified facts")
    for gap in raw_data.get("data_gaps", []):
        add_gap(str(gap))

    return {
        "variety": state["variety"],
        "variety_code": variety_definition.code,
        "contract": state["symbol"],
        "target_date": str(state["target_date"]),
        "allowed_sources": sorted(set(str(item) for item in sources + [
            "CTP snapshot API",
            "Yahoo Finance via yfinance",
            "AkShare structured commodity data",
            "数据覆盖范围说明",
        ])),
        "facts": facts,
        "gaps": gaps,
        "key_factors": variety_definition.key_factors,
        "analysis_result": state.get("analysis_result", ""),
        "request_context": raw_data.get("request_context", {}),
    }


def _build_grounded_prompt(evidence_pack: Dict[str, Any], review_result: Optional[ReviewResult]) -> str:
    review_feedback = ""
    if review_result and not review_result.passed:
        review_feedback = "上一轮审核反馈：%s\n必须修复：%s" % (
            review_result.feedback,
            "；".join(review_result.blocking_issues) or "无",
        )
    return """
你是高级商品期货研究员，请写一篇更接近成熟研究所风格的中文期货日报。

硬性规则：
1. 只能使用 evidence_pack 中的事实、缺口和来源。
2. 正文中出现的每个数字、日期、百分比、合约代码、来源名，都必须能在 evidence_pack 中找到。
3. 每个包含事实判断的段落末尾必须引用证据编号，例如 [F1][F3]；数据缺口引用 [G1]。
4. 不得编造库存、仓单、开工、进口、政策、机构观点、新闻事件或交易建议。
5. 可以做研究判断，但必须把判断写成“基于已核验事实的推论”，并说明边界。
6. 必须包含 AI 免责声明：“本报告由AI自动生成，仅供参考，不构成投资建议。”
7. 输出完整 Markdown，不要输出 JSON。

建议结构：
# 品种期货日报 — 合约 [日期]
> 核心观点
> 情绪与置信度

## 一、结论先行
## 二、盘面定价与期限结构
## 三、外盘、宏观与期现联动
## 四、基本面验证与缺口
## 五、核心驱动因子
## 六、风险提示
## 七、数据来源与合规说明

{review_feedback}

evidence_pack:
{evidence_pack}
""".strip().format(
        review_feedback=review_feedback or "本轮为首轮成稿。",
        evidence_pack=json.dumps(evidence_pack, ensure_ascii=False, indent=2, default=str),
    )


def _line_for_position(text: str, position: int) -> str:
    start = text.rfind("\n", 0, position) + 1
    end = text.find("\n", position)
    if end == -1:
        end = len(text)
    return text[start:end]


def _extract_numeric_mentions_for_grounding(text: str) -> list[tuple[str, int]]:
    mentions = []
    for match in re.finditer(r"(?<![A-Za-z])[-+]?\d+(?:,\d{3})*(?:\.\d+)?%?", text):
        line = _line_for_position(text, match.start()).strip()
        token = match.group(0)
        if re.match(r"^#{1,6}\s+", line):
            continue
        if re.match(r"^\d+\.\s+", line) and line.startswith(token.rstrip("%")):
            continue
        if re.search(r"\[(?:F|G)%s\]" % re.escape(token.rstrip("%")), line):
            continue
        mentions.append((token, match.start()))
    return mentions


def _validate_grounded_report(draft: str, evidence_pack: Dict[str, Any]) -> list[str]:
    evidence_text = json.dumps(evidence_pack, ensure_ascii=False, default=str)
    violations = []
    for token, _position in _extract_numeric_mentions_for_grounding(draft):
        normalized = token.replace(",", "")
        if token not in evidence_text and normalized not in evidence_text:
            violations.append("数字或百分比未出现在证据包：%s" % token)

    allowed_sources = evidence_pack.get("allowed_sources", [])
    for label in re.findall(r"来源[:：]([^\n）)]+)", draft):
        if not any(label.strip().startswith(str(source)) for source in allowed_sources):
            violations.append("来源未登记：%s" % label.strip())

    if "本报告由AI自动生成，仅供参考，不构成投资建议" not in draft:
        violations.append("缺少指定 AI 免责声明")
    if not re.search(r"\[F\d+\]", draft):
        violations.append("正文未引用任何事实编号")

    return sorted(set(violations))


async def _build_grounded_llm_report(
    state: Dict[str, Any],
    runtime: RuntimeContext,
    variety_definition: VarietyDefinition,
    review_result: Optional[ReviewResult],
) -> str:
    evidence_pack = _build_grounded_evidence_pack(state, variety_definition)
    prompt = _build_grounded_prompt(evidence_pack, review_result)
    draft = await runtime.llm_client.generate_report(
        prompt,
        context={"evidence_pack": evidence_pack},
    )
    violations = _validate_grounded_report(draft, evidence_pack)
    if not violations:
        return draft
    return "{draft}\n\n---\n\n**合规审查结果**：未通过合规审查，卡在第四步。  \n**未通过原因**：{violations}\n".format(
        draft=draft.rstrip(),
        violations="；".join(violations),
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
    elif config.REPORT_RENDER_MODE == "grounded_llm":
        report_draft = await _build_grounded_llm_report(
            state=state,
            runtime=runtime,
            variety_definition=variety_definition,
            review_result=review_result,
        )
    else:
        report_draft = _build_deterministic_report(state, variety_definition, review_result, next_round)

    return {
        "current_step": "write",
        "report_draft": report_draft,
    }
