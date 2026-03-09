import unittest

from avsearcher.search import SearchService, canonicalize_url, load_source_configs, split_query_terms


class SearchHelpersTest(unittest.TestCase):
    def test_canonicalize_url_removes_query_and_slash_noise(self):
        self.assertEqual(
            canonicalize_url("http://Example.com/10609.html?from=rss/"),
            "https://example.com/10609.html",
        )

    def test_split_query_terms_keeps_full_phrase(self):
        terms = split_query_terms("GXP 中川美铃")
        self.assertEqual(terms[0], "gxp 中川美铃")
        self.assertIn("gxp", terms)
        self.assertIn("中川美铃", terms)


class SourceConfigTest(unittest.TestCase):
    def test_sources_file_contains_default_sources(self):
        configs = load_source_configs()
        self.assertGreaterEqual(len(configs), 2)
        self.assertTrue(any(config.key == "xkw" for config in configs))
        self.assertTrue(any(config.key == "cup001" for config in configs))

    def test_service_lists_sources(self):
        service = SearchService()
        sources = service.list_sources()
        self.assertTrue(any(item["key"] == "xkw" for item in sources))


if __name__ == "__main__":
    unittest.main()

