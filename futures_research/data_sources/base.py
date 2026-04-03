from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Iterable, List

from futures_research.models.source import DataFetchRequest, SourcePayload


class DataSourceAdapter(ABC):
    source_type = "base"

    @abstractmethod
    async def fetch(self, request: DataFetchRequest) -> SourcePayload:
        raise NotImplementedError


class DataSourceRegistry:
    def __init__(self):
        self._adapters: Dict[str, DataSourceAdapter] = {}

    def register(self, adapter: DataSourceAdapter) -> None:
        self._adapters[adapter.source_type] = adapter

    def get(self, source_type: str) -> DataSourceAdapter:
        if source_type not in self._adapters:
            raise KeyError("Data source '%s' is not registered" % source_type)
        return self._adapters[source_type]

    def has(self, source_type: str) -> bool:
        return source_type in self._adapters

    def list_types(self) -> List[str]:
        return sorted(self._adapters.keys())

    async def fetch_many(
        self,
        request: DataFetchRequest,
        source_types: Iterable[str],
    ) -> List[SourcePayload]:
        payloads = []
        for source_type in source_types:
            payloads.append(await self.get(source_type).fetch(request))
        return payloads
