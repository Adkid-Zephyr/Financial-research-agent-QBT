from __future__ import annotations

from typing import Any, Dict, List

from futures_research.models.source import DataFetchRequest
from futures_research.prompts.aggregator_prompt import build_aggregator_context
from futures_research.runtime import RuntimeContext


async def aggregate_node(state: Dict[str, Any], runtime: RuntimeContext) -> Dict[str, Any]:
    variety_definition = runtime.variety_registry.get(state["variety_code"])
    request = DataFetchRequest(
        variety_code=variety_definition.code,
        variety_name=variety_definition.name,
        contract=state["symbol"],
        contracts=variety_definition.contracts,
        target_date=state["target_date"],
        exchange=variety_definition.exchange,
        key_factors=variety_definition.key_factors,
        news_keywords=variety_definition.news_keywords,
    )
    active_source_configs = [
        item for item in variety_definition.data_sources if runtime.data_source_registry.has(item.type)
    ]
    active_source_types: List[str] = [item.type for item in active_source_configs]
    payloads = await runtime.data_source_registry.fetch_many(request, active_source_configs)
    raw_items = [item for payload in payloads for item in payload.raw_items]
    primary_snapshot = next(
        (item for item in raw_items if item.get("item_type") == "snapshot" and item.get("role") == "primary"),
        None,
    )
    current_target_date = str(state["target_date"])
    data_gaps = [
        "当前版本未接入现货、库存、开工率、基差、国际联动等结构化数字。",
        "当前版本未接入逐日持仓变化，需要后续补历史序列接口。",
    ]
    data_gaps.extend(gap for payload in payloads for gap in payload.data_gaps)
    external_market_facts = [
        item
        for item in raw_items
        if item.get("item_type") == "external_market" and item.get("stale") != "true"
    ]
    fundamental_facts = [
        item
        for item in raw_items
        if item.get("item_type") in {"spot_basis", "domestic_spot", "inventory", "warehouse_receipt"}
        and item.get("stale") != "true"
    ]
    if external_market_facts:
        data_gaps[0] = "当前版本未接入现货、库存、开工率、基差等结构化数字。"
    if fundamental_facts:
        data_gaps[0] = "当前版本未接入开工率、产量、进口、消费和供需平衡表等结构化数字。"
    if primary_snapshot is None:
        data_gaps.insert(0, "未获取到目标合约的实时快照。")
    elif primary_snapshot.get("trading_day") != current_target_date:
        data_gaps.insert(
            0,
            "目标日期为 {target_date}，但当前最新可得快照交易日为 {trading_day}。".format(
                target_date=current_target_date,
                trading_day=primary_snapshot.get("trading_day") or "未知",
            ),
        )
    can_write_formal_report = primary_snapshot is not None and primary_snapshot.get("trading_day") == current_target_date
    blocking_reason = None
    if primary_snapshot is None:
        blocking_reason = "未从 CTP 快照接口获取到目标合约的实时数据。"
    elif not can_write_formal_report:
        blocking_reason = "最新快照交易日与目标日期不一致，不能把旧数字写成今日数据。"
    verified_facts = []
    for payload in payloads:
        if payload.source_type == "ctp_snapshot" and not can_write_formal_report:
            continue
        verified_facts.extend(payload.highlights)
    raw_data = {
        "market_context": build_aggregator_context(variety_definition, runtime.prompt_repository),
        "summary": " | ".join(payload.summary for payload in payloads),
        "highlights": verified_facts,
        "metrics": {k: v for payload in payloads for k, v in payload.metrics.items()},
        "sources": [item for payload in payloads for item in payload.sources],
        "raw_items": raw_items,
        "verified_facts": verified_facts,
        "external_market_facts": external_market_facts,
        "fundamental_facts": fundamental_facts,
        "data_gaps": data_gaps,
        "research_workflow": {
            "principle": "所有具体数字只能来自当前可核验的真实结构化数据源；没有真实数字时必须明确写没有。",
            "analysis_order": [
                "先确认目标合约是否有实时快照",
                "再确认可直接引用的价格/持仓/成交量/价差",
                "最后把缺失的基本面字段显式写成待补充项",
            ],
            "verified_facts": verified_facts,
            "can_write_formal_report": can_write_formal_report,
            "blocking_reason": blocking_reason,
        },
    }
    return {
        "current_step": "aggregate",
        "raw_data": raw_data,
        "data_sources_used": active_source_types,
    }
