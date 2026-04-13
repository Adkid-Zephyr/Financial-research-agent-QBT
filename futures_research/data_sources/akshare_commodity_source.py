from __future__ import annotations

import asyncio
import contextlib
from datetime import date, datetime
import io
from typing import Any, Dict, List, Optional

from futures_research import config
from futures_research.data_sources.base import DataSourceAdapter
from futures_research.models.source import DataFetchRequest, SourcePayload


class AkShareCommoditySource(DataSourceAdapter):
    source_type = "akshare_commodity"
    source_label = "AkShare structured commodity data"

    async def fetch(self, request: DataFetchRequest, params: Dict[str, Any] | None = None) -> SourcePayload:
        params = params or {}
        if not config.ENABLE_AKSHARE_COMMODITY_SOURCE:
            return SourcePayload(
                source_type=self.source_type,
                summary="AkShare 商品基本面数据源未启用。",
                data_gaps=["AkShare 商品基本面数据源未启用。"],
            )

        modules = params.get("modules") or []
        if not modules:
            return SourcePayload(
                source_type=self.source_type,
                summary="未配置 AkShare 商品基本面模块。",
                data_gaps=["未配置 AkShare 商品基本面模块。"],
            )

        try:
            self._load_akshare()
        except Exception:
            return SourcePayload(
                source_type=self.source_type,
                summary="当前环境未安装 akshare，商品基本面数据待补充。",
                data_gaps=["当前环境未安装 akshare，商品基本面数据待补充。"],
            )

        raw_items: List[Dict[str, str]] = []
        highlights: List[str] = []
        metrics: Dict[str, str] = {}
        data_gaps: List[str] = []
        sources: List[str] = []
        max_stale_days = int(params.get("max_stale_days", config.AKSHARE_COMMODITY_MAX_STALE_DAYS))

        for module in modules:
            module_type = str(module.get("type") or "").strip()
            item = await self._fetch_module(
                module_type=module_type,
                module=module,
                request=request,
                max_stale_days=max_stale_days,
            )
            if item is None:
                data_gaps.append("{name} 暂无可核验 AkShare 结构化数据。".format(name=self._module_name(module)))
                continue
            if item.get("stale") == "true":
                data_gaps.append(
                    "{name} 最新可得数据截至 {as_of_date}，与目标日期 {target_date} 相差超过 {max_stale_days} 天。".format(
                        name=item.get("name") or self._module_name(module),
                        as_of_date=item.get("as_of_date") or "未知",
                        target_date=request.target_date,
                        max_stale_days=max_stale_days,
                    )
                )
                continue
            raw_items.append(item)
            source = item.get("source") or self.source_label
            if source not in sources:
                sources.append(source)
            self._append_metrics(metrics, item)
            highlight = self._build_highlight(item)
            if highlight:
                highlights.append(highlight)

        summary = (
            "已获取 {count} 条 AkShare 商品基本面结构化数据。".format(count=len(raw_items))
            if raw_items
            else "未获取到可用于正文引用的 AkShare 商品基本面结构化数据。"
        )
        return SourcePayload(
            source_type=self.source_type,
            summary=summary,
            highlights=highlights,
            metrics=metrics,
            sources=sources,
            raw_items=raw_items,
            data_gaps=data_gaps,
        )

    async def _fetch_module(
        self,
        *,
        module_type: str,
        module: Dict[str, Any],
        request: DataFetchRequest,
        max_stale_days: int,
    ) -> Optional[Dict[str, str]]:
        try:
            if module_type == "spot_basis":
                return await asyncio.to_thread(self._fetch_spot_basis, request, module)
            if module_type == "sge_spot":
                return await asyncio.to_thread(self._fetch_sge_spot, request, module, max_stale_days)
            if module_type == "comex_inventory":
                return await asyncio.to_thread(self._fetch_comex_inventory, request, module, max_stale_days)
        except Exception:
            return None
        return None

    def _fetch_spot_basis(self, request: DataFetchRequest, module: Dict[str, Any]) -> Optional[Dict[str, str]]:
        ak = self._load_akshare()
        df = ak.futures_spot_price(
            date=self._date_token(request.target_date),
            vars_list=[str(module.get("symbol") or request.variety_code).upper()],
        )
        if getattr(df, "empty", True):
            return None
        symbol = str(module.get("symbol") or request.variety_code).upper()
        matches = df[df["symbol"].astype(str).str.upper() == symbol] if "symbol" in df.columns else df
        if getattr(matches, "empty", True):
            return None
        row = matches.iloc[0]
        return {
            "item_type": "spot_basis",
            "role": "spot_basis",
            "name": str(module.get("name") or "{variety}现货基差".format(variety=request.variety_name)),
            "symbol": str(row.get("symbol") or symbol),
            "as_of_date": self._date_text(row.get("date") or request.target_date),
            "spot_price": self._fmt(row.get("spot_price")),
            "dominant_contract": str(row.get("dominant_contract") or ""),
            "dominant_contract_price": self._fmt(row.get("dominant_contract_price")),
            "dom_basis": self._fmt(row.get("dom_basis")),
            "dom_basis_rate": self._fmt_pct(row.get("dom_basis_rate"), ratio=True),
            "near_contract": str(row.get("near_contract") or ""),
            "near_basis": self._fmt(row.get("near_basis")),
            "source": "AkShare: 生意社现货与基差",
            "stale": "false",
        }

    def _fetch_sge_spot(
        self,
        request: DataFetchRequest,
        module: Dict[str, Any],
        max_stale_days: int,
    ) -> Optional[Dict[str, str]]:
        ak = self._load_akshare()
        symbol = str(module.get("symbol") or "")
        if not symbol:
            return None
        df = ak.spot_hist_sge(symbol=symbol)
        if getattr(df, "empty", True) or "date" not in df.columns:
            return None
        rows = []
        for _, row in df.iterrows():
            row_date = self._coerce_date(row.get("date"))
            if row_date is not None and row_date <= request.target_date:
                rows.append((row_date, row))
        if not rows:
            return None
        as_of_date, row = rows[-1]
        stale_days = (request.target_date - as_of_date).days
        return {
            "item_type": "domestic_spot",
            "role": "sge_spot",
            "name": str(module.get("name") or symbol),
            "symbol": symbol,
            "as_of_date": as_of_date.isoformat(),
            "open": self._fmt(row.get("open")),
            "close": self._fmt(row.get("close")),
            "low": self._fmt(row.get("low")),
            "high": self._fmt(row.get("high")),
            "unit": str(module.get("unit") or ""),
            "source": "AkShare: 上海黄金交易所历史行情",
            "stale": "true" if stale_days > max_stale_days else "false",
        }

    def _fetch_comex_inventory(
        self,
        request: DataFetchRequest,
        module: Dict[str, Any],
        max_stale_days: int,
    ) -> Optional[Dict[str, str]]:
        ak = self._load_akshare()
        symbol = str(module.get("symbol") or "")
        if symbol not in {"黄金", "白银"}:
            return None
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            df = ak.futures_comex_inventory(symbol=symbol)
        if getattr(df, "empty", True) or "日期" not in df.columns:
            return None
        rows = []
        for _, row in df.iterrows():
            row_date = self._coerce_date(row.get("日期"))
            if row_date is not None and row_date <= request.target_date:
                rows.append((row_date, row))
        if not rows:
            return None
        as_of_date, row = rows[-1]
        stale_days = (request.target_date - as_of_date).days
        ton_col = "COMEX{symbol}库存量-吨".format(symbol=symbol)
        ounce_col = "COMEX{symbol}库存量-盎司".format(symbol=symbol)
        return {
            "item_type": "inventory",
            "role": "comex_inventory",
            "name": str(module.get("name") or "COMEX{symbol}库存".format(symbol=symbol)),
            "symbol": symbol,
            "as_of_date": as_of_date.isoformat(),
            "inventory_ton": self._fmt(row.get(ton_col)),
            "inventory_ounce": self._fmt(row.get(ounce_col)),
            "source": "AkShare: 东方财富COMEX库存",
            "stale": "true" if stale_days > max_stale_days else "false",
        }

    def _append_metrics(self, metrics: Dict[str, str], item: Dict[str, str]) -> None:
        prefix = "基本面:{name}".format(name=item.get("name") or item.get("role") or "未知")
        if item["item_type"] == "spot_basis":
            metrics["{prefix}:现货价格".format(prefix=prefix)] = item["spot_price"]
            metrics["{prefix}:主力基差".format(prefix=prefix)] = item["dom_basis"]
            metrics["{prefix}:主力基差率".format(prefix=prefix)] = item["dom_basis_rate"]
            metrics["{prefix}:数据日期".format(prefix=prefix)] = item["as_of_date"]
        elif item["item_type"] == "domestic_spot":
            metrics["{prefix}:收盘价".format(prefix=prefix)] = self._with_unit(item["close"], item.get("unit", ""))
            metrics["{prefix}:数据日期".format(prefix=prefix)] = item["as_of_date"]
        elif item["item_type"] == "inventory":
            metrics["{prefix}:库存吨".format(prefix=prefix)] = item["inventory_ton"]
            metrics["{prefix}:数据日期".format(prefix=prefix)] = item["as_of_date"]

    def _build_highlight(self, item: Dict[str, str]) -> str:
        if item["item_type"] == "spot_basis":
            return (
                "{source} 显示 {name}截至 {as_of_date} 现货价格 {spot_price}，"
                "主力合约 {contract} 对应基差 {basis}，基差率 {basis_rate}。"
            ).format(
                source=item["source"],
                name=item["name"],
                as_of_date=item["as_of_date"],
                spot_price=item["spot_price"],
                contract=item.get("dominant_contract") or "暂无",
                basis=item["dom_basis"],
                basis_rate=item["dom_basis_rate"],
            )
        if item["item_type"] == "domestic_spot":
            return (
                "{source} 显示 {name}截至 {as_of_date} 收盘价 {close}，日内区间 {low}-{high}。"
            ).format(
                source=item["source"],
                name=item["name"],
                as_of_date=item["as_of_date"],
                close=self._with_unit(item["close"], item.get("unit", "")),
                low=self._with_unit(item["low"], item.get("unit", "")),
                high=self._with_unit(item["high"], item.get("unit", "")),
            )
        if item["item_type"] == "inventory":
            return (
                "{source} 显示 {name}截至 {as_of_date} 库存 {inventory_ton} 吨。"
            ).format(
                source=item["source"],
                name=item["name"],
                as_of_date=item["as_of_date"],
                inventory_ton=item["inventory_ton"],
            )
        return ""

    @staticmethod
    def _load_akshare():
        import akshare as ak  # type: ignore

        return ak

    @staticmethod
    def _module_name(module: Dict[str, Any]) -> str:
        return str(module.get("name") or module.get("symbol") or module.get("type") or "AkShare模块")

    @staticmethod
    def _date_token(value: date) -> str:
        return value.strftime("%Y%m%d")

    @classmethod
    def _date_text(cls, value: Any) -> str:
        parsed = cls._coerce_date(value)
        return parsed.isoformat() if parsed is not None else str(value or "")

    @staticmethod
    def _coerce_date(value: Any) -> Optional[date]:
        if isinstance(value, date):
            return value
        if hasattr(value, "date"):
            return value.date()
        text = str(value or "").strip()
        if not text:
            return None
        for fmt in ("%Y-%m-%d", "%Y%m%d"):
            try:
                return datetime.strptime(text[:10] if fmt == "%Y-%m-%d" else text[:8], fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _fmt(value: Any) -> str:
        if value is None or value == "":
            return "暂无"
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)
        if number.is_integer():
            return str(int(number))
        return ("%.4f" % number).rstrip("0").rstrip(".")

    @classmethod
    def _fmt_pct(cls, value: Any, *, ratio: bool = False) -> str:
        if value is None or value == "":
            return "暂无"
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)
        if ratio:
            number *= 100
        return "{value}%".format(value=cls._fmt(number))

    @staticmethod
    def _with_unit(value: str, unit: str) -> str:
        return "{value}{unit}".format(value=value, unit=unit) if unit and value != "暂无" else value
