from __future__ import annotations

from dataclasses import dataclass

from futures_research import config
from futures_research.data_sources import AkShareCommoditySource, CTPSnapshotSource, DataSourceRegistry, YahooMarketSource
from futures_research.events import EventBus, get_event_bus
from futures_research.llm import LLMClient
from futures_research.prompts.loader import PromptRepository
from futures_research.varieties import VarietyRegistry


@dataclass
class RuntimeContext:
    variety_registry: VarietyRegistry
    data_source_registry: DataSourceRegistry
    prompt_repository: PromptRepository
    llm_client: LLMClient
    event_bus: EventBus


def build_runtime() -> RuntimeContext:
    variety_registry = VarietyRegistry()
    variety_registry.scan()

    data_source_registry = DataSourceRegistry()
    data_source_registry.register(CTPSnapshotSource())
    if config.ENABLE_YAHOO_MARKET_SOURCE:
        data_source_registry.register(YahooMarketSource())
    if config.ENABLE_AKSHARE_COMMODITY_SOURCE:
        data_source_registry.register(AkShareCommoditySource())

    return RuntimeContext(
        variety_registry=variety_registry,
        data_source_registry=data_source_registry,
        prompt_repository=PromptRepository(),
        llm_client=LLMClient(),
        event_bus=get_event_bus(),
    )
