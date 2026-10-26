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


if __name__ == "__main__":
    unittest.main()
