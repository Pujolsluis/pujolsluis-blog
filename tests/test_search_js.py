"""Run the dependency-free browser search tests with Node's built-in runner."""

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("node"), "Node.js is not installed")
class SearchJavaScriptTests(unittest.TestCase):
    def test_search_ranking_matching_and_snippets(self):
        result = subprocess.run(
            ["node", "--test", "tests/search.test.cjs"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_search_templates_route_queries_to_a_paginated_page(self):
        menu = (ROOT / "layouts/partials/search.html").read_text(encoding="utf-8")
        page = (ROOT / "layouts/search/list.html").read_text(encoding="utf-8")
        self.assertIn('method="get"', menu)
        self.assertIn('name="q"', menu)
        self.assertIn("site.Home.RelPermalink", menu)
        self.assertNotIn("data-search-results", menu)
        for hook in (
            "data-search-page",
            "data-search-query",
            "data-search-status",
            "data-search-results",
            "data-search-pagination",
            "data-search-previous",
            "data-search-next",
            "data-search-page-number",
        ):
            with self.subTest(hook=hook):
                self.assertIn(hook, page)


if __name__ == "__main__":
    unittest.main()
