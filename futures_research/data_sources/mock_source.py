from __future__ import annotations

from typing import Dict, List

from futures_research.data_sources.base import DataSourceAdapter
from futures_research.models.source import DataFetchRequest, SourcePayload


class MockDataSource(DataSourceAdapter):
    source_type = "mock"

    async def fetch(self, request: DataFetchRequest) -> SourcePayload:
        highlights = self._build_highlights(request.key_factors, request.variety_name)
        metrics = self._build_metrics(request)
        sources = [
            "MockMarketWire",
            "MockExchangeBulletin",
            "MockIndustryPanel",
        ]
        summary = (
            f"{request.variety_name}{request.contract} 的模拟数据已生成，覆盖"
            f"{len(request.key_factors)}个核心驱动因子。"
        )
        raw_items = [
            {
                "title": factor,
                "snippet": "围绕%s构造的语义相关占位数据，用于切片1联调。" % factor,
            }
            for factor in request.key_factors
        ]
        return SourcePayload(
            source_type=self.source_type,
            summary=summary,
            highlights=highlights,
            metrics=metrics,
            sources=sources,
            raw_items=raw_items,
        )

    def _build_highlights(self, key_factors: List[str], variety_name: str) -> List[str]:
        highlights = []
        for index, factor in enumerate(key_factors, start=1):
            highlights.append(
                "驱动因子%d：围绕“%s”生成与%s相关的占位研判，用于验证端到端流程。"
                % (index, factor, variety_name)
            )
        return highlights

    def _build_metrics(self, request: DataFetchRequest) -> Dict[str, str]:
        seed = sum(ord(char) for char in request.contract)
        base_price = 12000 + seed % 1800
        inventory = 45 + seed % 20
        open_interest = 28 + seed % 15
        return {
            "主力合约参考价": "%d 元/吨" % base_price,
            "近月-远月价差": "%d 元/吨" % (80 + seed % 120),
            "社会库存": "%d 万吨" % inventory,
            "主力持仓变化": "%d%%" % (2 + seed % 6),
            "下游开工率": "%d%%" % (58 + seed % 12),
            "国际联动指数": "%d" % (70 + seed % 20),
            "持仓规模": "%d 万手" % open_interest,
        }
