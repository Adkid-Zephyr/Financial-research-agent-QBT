import unittest

from futures_research.varieties import VarietyRegistry


class VarietyConfigTests(unittest.TestCase):
    def test_phase_one_varieties_declare_structured_auxiliary_sources(self):
        registry = VarietyRegistry()
        registry.scan()

        for code in ["AG", "AL", "AU", "CF", "CU", "LC", "M", "SI"]:
            with self.subTest(code=code):
                variety = registry.get(code)
                source_types = {source.type for source in variety.data_sources}
                self.assertIn("ctp_snapshot", source_types)
                self.assertIn("yahoo_market", source_types)
                self.assertIn("akshare_commodity", source_types)

                akshare_config = next(source for source in variety.data_sources if source.type == "akshare_commodity")
                module_types = {module.get("type") for module in akshare_config.params.get("modules", [])}
                self.assertIn("spot_basis", module_types)

    def test_catalog_varieties_have_snapshot_source(self):
        registry = VarietyRegistry()
        registry.scan()

        for code in ["A", "SC", "IF", "ZN"]:
            with self.subTest(code=code):
                variety = registry.get(code)
                source_types = {source.type for source in variety.data_sources}
                self.assertIn("ctp_snapshot", source_types)
                self.assertGreater(len(variety.contracts), 0)


if __name__ == "__main__":
    unittest.main()
