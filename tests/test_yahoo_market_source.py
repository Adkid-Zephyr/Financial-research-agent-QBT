import asyncio
from datetime import date
import unittest
from unittest.mock import patch

from futures_research import config
from futures_research.data_sources.base import DataSourceAdapter, DataSourceRegistry
from futures_research.data_sources.yahoo_market_source import YahooMarketSource
from futures_research.models.source import DataFetchRequest, SourcePayload
from futures_research.models.variety import DataSourceConfig


def _request():
    return DataFetchRequest(
        variety_code="AU",
        variety_name="沪金",
        contract="AU2606",
        contracts=["AU2606", "AU2612"],
        target_date=date(2026, 4, 10),
        exchange="SHFE",
        key_factors=[],
        news_keywords=[],
    )


class RecordingSource(DataSourceAdapter):
    source_type = "recording"

    def __init__(self):
        self.received_params = None

    async def fetch(self, request, params=None):
        del request
        self.received_params = params
        return SourcePayload(source_type=self.source_type, summary="ok")


class YahooMarketSourceTests(unittest.TestCase):
    def test_fetch_valid_assets_outputs_structured_payload(self):
        source = YahooMarketSource()

        with (
            patch.object(config, "ENABLE_YAHOO_MARKET_SOURCE", True),
            patch.object(source, "_load_yfinance", return_value=object()),
            patch.object(
                source,
                "_fetch_history_rows",
                return_value=[
                    {"as_of_date": date(2026, 4, 9), "close": 100.0},
                    {"as_of_date": date(2026, 4, 10), "close": 102.0},
                ],
            ),
        ):
            payload = asyncio.run(
                source.fetch(
                    _request(),
                    params={
                        "assets": [
                            {"ticker": "GC=F", "name": "COMEX黄金", "unit": "美元/盎司"},
                        ],
                        "max_stale_days": 2,
                    },
                )
            )

        self.assertEqual(payload.sources, ["Yahoo Finance via yfinance"])
        self.assertEqual(len(payload.raw_items), 1)
        self.assertEqual(payload.raw_items[0]["ticker"], "GC=F")
        self.assertEqual(payload.raw_items[0]["as_of_date"], "2026-04-10")
        self.assertIn("外盘/宏观:COMEX黄金:收盘价", payload.metrics)
        self.assertIn("Yahoo Finance via yfinance", payload.highlights[0])

    def test_fetch_stale_asset_becomes_data_gap_not_fact(self):
        source = YahooMarketSource()

        with (
            patch.object(config, "ENABLE_YAHOO_MARKET_SOURCE", True),
            patch.object(source, "_load_yfinance", return_value=object()),
            patch.object(
                source,
                "_fetch_history_rows",
                return_value=[{"as_of_date": date(2026, 4, 1), "close": 100.0}],
            ),
        ):
            payload = asyncio.run(
                source.fetch(
                    _request(),
                    params={
                        "assets": [{"ticker": "GC=F", "name": "COMEX黄金"}],
                        "max_stale_days": 2,
                    },
                )
            )

        self.assertEqual(payload.raw_items, [])
        self.assertEqual(payload.sources, [])
        self.assertTrue(payload.data_gaps)
        self.assertIn("超过 2 天", payload.data_gaps[0])

    def test_fetch_exception_becomes_data_gap_not_error(self):
        source = YahooMarketSource()

        with (
            patch.object(config, "ENABLE_YAHOO_MARKET_SOURCE", True),
            patch.object(source, "_load_yfinance", return_value=object()),
            patch.object(source, "_fetch_history_rows", side_effect=RuntimeError("rate limited")),
        ):
            payload = asyncio.run(
                source.fetch(
                    _request(),
                    params={"assets": [{"ticker": "GC=F", "name": "COMEX黄金"}]},
                )
            )

        self.assertEqual(payload.raw_items, [])
        self.assertTrue(payload.data_gaps)

    def test_registry_passes_data_source_params_without_breaking_fetch_many(self):
        registry = DataSourceRegistry()
        source = RecordingSource()
        registry.register(source)

        payloads = asyncio.run(
            registry.fetch_many(
                _request(),
                [DataSourceConfig(type="recording", params={"hello": "world"})],
            )
        )

        self.assertEqual(payloads[0].summary, "ok")
        self.assertEqual(source.received_params, {"hello": "world"})


if __name__ == "__main__":
    unittest.main()
