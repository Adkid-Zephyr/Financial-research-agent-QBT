from __future__ import annotations

from typing import Any, Dict

from futures_research.data_sources.base import DataSourceAdapter
from futures_research.models.source import DataFetchRequest, SourcePayload


class WebSearchSource(DataSourceAdapter):
    source_type = "web_search"

    async def fetch(self, request: DataFetchRequest, params: Dict[str, Any] | None = None) -> SourcePayload:
        del params
        return SourcePayload(
            source_type=self.source_type,
            summary=(
                "切片1保留 web_search 数据源接口，但默认不启用真实抓取。"
                "后续切片可在不改动品种配置结构的前提下直接接入。"
            ),
            highlights=[
                "已保留运行时动态注册能力。",
                "当前默认由 MockDataSource 承担数据层职责。",
            ],
            sources=["Anthropic web_search_20250305 (reserved)"],
        )
