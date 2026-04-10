from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import urlopen

from futures_research import config
from futures_research.data_sources.base import DataSourceAdapter
from futures_research.models.source import DataFetchRequest, SourcePayload


class CTPSnapshotSource(DataSourceAdapter):
    source_type = "ctp_snapshot"

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or config.CTP_SNAPSHOT_BASE_URL).rstrip("/")

    async def fetch(self, request: DataFetchRequest) -> SourcePayload:
        primary_snapshot = await self._resolve_best_snapshot(
            contract=request.contract,
            exchange=request.exchange,
            target_date=str(request.target_date),
        )

        secondary_snapshot = None
        for candidate_contract in request.contracts:
            if candidate_contract == request.contract:
                continue
            secondary_snapshot = await self._resolve_best_snapshot(
                contract=candidate_contract,
                exchange=request.exchange,
                target_date=str(request.target_date),
            )
            if secondary_snapshot is not None:
                break

        metrics: Dict[str, str] = {}
        highlights: List[str] = []
        raw_items: List[Dict[str, str]] = []
        summary = "未从 CTP 快照接口获取到可核验的盘面数据。"

        if primary_snapshot is not None:
            metrics.update(
                {
                    "主数据合约ID": primary_snapshot["instrument_id"],
                    "主力合约参考价": self._fmt(primary_snapshot.get("price")),
                    "主力合约买一": self._fmt(primary_snapshot.get("bid")),
                    "主力合约卖一": self._fmt(primary_snapshot.get("ask")),
                    "主力合约涨跌": self._fmt(primary_snapshot.get("change")),
                    "主力合约涨跌幅": self._fmt_pct(primary_snapshot.get("change_pct")),
                    "主力合约持仓量": self._fmt_int(primary_snapshot.get("open_interest")),
                    "主力合约成交量": self._fmt_int(primary_snapshot.get("volume")),
                    "主力合约交易日": str(primary_snapshot.get("trading_day") or ""),
                    "主力合约更新时间": str(primary_snapshot.get("update_time") or ""),
                }
            )
            highlights.extend(
                [
                    "CTP快照显示 {instrument_id} 最新价 {price}，涨跌 {change}，涨跌幅 {change_pct}，更新时间 {update_time}。".format(
                        instrument_id=primary_snapshot["instrument_id"],
                        price=self._fmt(primary_snapshot.get("price")),
                        change=self._fmt(primary_snapshot.get("change")),
                        change_pct=self._fmt_pct(primary_snapshot.get("change_pct")),
                        update_time=primary_snapshot.get("update_time") or "未知",
                    ),
                    "当前可核验持仓量 {open_interest}，成交量 {volume}。".format(
                        open_interest=self._fmt_int(primary_snapshot.get("open_interest")),
                        volume=self._fmt_int(primary_snapshot.get("volume")),
                    ),
                ]
            )
            raw_items.append(self._snapshot_to_raw_item("primary", request.contract, primary_snapshot))
            summary = "已从 CTP 快照接口获取 {contract} 的实时盘面数据。".format(contract=request.contract)

        if secondary_snapshot is not None:
            spread = (primary_snapshot or {}).get("price")
            secondary_price = secondary_snapshot.get("price")
            metrics["次数据合约ID"] = secondary_snapshot["instrument_id"]
            metrics["次主力合约参考价"] = self._fmt(secondary_price)
            if spread is not None and secondary_price is not None:
                metrics["近月-远月价差"] = self._fmt(spread - secondary_price)
                highlights.append(
                    "{primary}-{secondary} 当前价差 {spread}。".format(
                        primary=(primary_snapshot or {}).get("instrument_id", request.contract),
                        secondary=secondary_snapshot["instrument_id"],
                        spread=self._fmt(spread - secondary_price),
                    )
                )
            raw_items.append(self._snapshot_to_raw_item("secondary", secondary_snapshot["instrument_id"], secondary_snapshot))

        return SourcePayload(
            source_type=self.source_type,
            summary=summary,
            highlights=highlights,
            metrics=metrics,
            sources=["CTP snapshot API: {base}/api/snapshots".format(base=self.base_url)],
            raw_items=raw_items,
        )

    async def _resolve_best_snapshot(
        self,
        *,
        contract: str,
        exchange: str,
        target_date: str,
    ) -> Optional[Dict[str, Any]]:
        candidates = self._build_candidates(contract, exchange)
        matches: List[Dict[str, Any]] = []
        for candidate in candidates:
            payload = await asyncio.to_thread(self._fetch_snapshot_payload, candidate)
            items = payload.get("items") or []
            if not items:
                continue
            item = dict(items[0])
            item["_queried_instrument"] = candidate
            matches.append(item)
        if not matches:
            return None
        return max(matches, key=lambda item: self._snapshot_score(item, expected_exchange=exchange, target_date=target_date))

    def _fetch_snapshot_payload(self, instrument: str) -> Dict[str, Any]:
        url = "{base}/api/snapshots?{query}".format(
            base=self.base_url,
            query=urlencode({"instruments": instrument}),
        )
        with urlopen(url, timeout=config.CTP_REQUEST_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))

    def _build_candidates(self, contract: str, exchange: str) -> List[str]:
        normalized = contract.strip()
        candidates: List[str] = []

        def add(value: str) -> None:
            if value and value not in candidates:
                candidates.append(value)

        add(normalized)
        add(normalized.lower())
        add(normalized.upper())

        match = re.match(r"^([A-Za-z]+)(\d+)$", normalized)
        if match and exchange.upper() == "CZCE":
            letters, digits = match.groups()
            if len(digits) == 4:
                short_contract = "{letters}{digits}".format(letters=letters.upper(), digits=digits[1:])
                add(short_contract)
                add(short_contract.lower())
                add(short_contract.upper())
        return candidates

    def _snapshot_score(self, item: Dict[str, Any], *, expected_exchange: str, target_date: str) -> tuple:
        trading_day = str(item.get("trading_day") or "")
        source_name = str(item.get("source") or "")
        return (
            trading_day == target_date,
            source_name != "akshare_bootstrap",
            str(item.get("exchange") or "").upper() == expected_exchange.upper(),
            float(item.get("timestamp") or 0.0),
        )

    def _snapshot_to_raw_item(self, role: str, requested_contract: str, snapshot: Dict[str, Any]) -> Dict[str, str]:
        return {
            "item_type": "snapshot",
            "role": role,
            "requested_contract": requested_contract,
            "instrument_id": str(snapshot.get("instrument_id") or ""),
            "exchange": str(snapshot.get("exchange") or ""),
            "trading_day": str(snapshot.get("trading_day") or ""),
            "update_time": str(snapshot.get("update_time") or ""),
            "price": self._fmt(snapshot.get("price")),
            "bid": self._fmt(snapshot.get("bid")),
            "ask": self._fmt(snapshot.get("ask")),
            "change": self._fmt(snapshot.get("change")),
            "change_pct": self._fmt_pct(snapshot.get("change_pct")),
            "open_interest": self._fmt_int(snapshot.get("open_interest")),
            "volume": self._fmt_int(snapshot.get("volume")),
            "source": str(snapshot.get("source") or ""),
            "queried_instrument": str(snapshot.get("_queried_instrument") or ""),
        }

    @staticmethod
    def _fmt(value: Any) -> str:
        if value is None or value == "":
            return "暂无"
        number = float(value)
        if number.is_integer():
            return str(int(number))
        return ("%.2f" % number).rstrip("0").rstrip(".")

    @staticmethod
    def _fmt_int(value: Any) -> str:
        if value is None or value == "":
            return "暂无"
        return "{:,}".format(int(float(value)))

    @staticmethod
    def _fmt_pct(value: Any) -> str:
        if value is None or value == "":
            return "暂无"
        return "{value}%".format(value=CTPSnapshotSource._fmt(value))
