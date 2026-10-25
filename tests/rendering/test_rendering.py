"""Build sanitized fixtures in preview and production URL modes."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/rendering/fixtures/content"


@unittest.skipUnless(shutil.which("hugo"), "Install Hugo to run rendering checks")
class HugoRenderingTests(unittest.TestCase):
    def build(self, base_url: str, production: bool) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        output = Path(tmp.name) / "site"
        cmd = ["hugo", "--minify", "--noBuildLock", "--source", str(ROOT), "--contentDir", str(FIXTURES),
               "--destination", str(output), "--baseURL", base_url]
        if production:
            cmd.extend(["--config", "hugo.toml,hugo.production.toml"])
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return output

    def test_preview_prefix_links_and_robot_exclusion(self):
        out = self.build("https://pujolsluis.github.io/pujolsluis-blog/", False)
        html = (out / "2024/02/03/renderer-fixture/index.html").read_text()
        self.assertIn('content="noindex, nofollow"', html)
        self.assertIn("/pujolsluis-blog/theme/css/main.css", html)
        self.assertIn("data-source=fixture", html)
        self.assertIn("youtube-nocookie.com/embed/dQw4w9WgXcQ?start=30", html)
        self.assertIn('aria-label="Synthetic gallery"', html)
        self.assertIn("Disallow: /", (out / "robots.txt").read_text())
        self.assertFalse((out / "sitemap.xml").exists())

    def test_production_root_and_indexing(self):
        out = self.build("https://www.pujolsluis.com/", True)
        html = (out / "2024/02/03/renderer-fixture/index.html").read_text()
        self.assertIn('content="index, follow"', html)
        self.assertIn("https://www.pujolsluis.com/2024/02/03/renderer-fixture/", html)
        self.assertIn("/theme/css/main.css", html)
        self.assertNotIn("/pujolsluis-blog/", html)
        self.assertIn("Sitemap: https://www.pujolsluis.com/sitemap.xml", (out / "robots.txt").read_text())
        self.assertTrue((out / "sitemap.xml").exists())
