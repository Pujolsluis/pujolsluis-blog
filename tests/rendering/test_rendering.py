"""Build sanitized fixtures in preview and production URL modes."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

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
        self.assertIn("noindex, nofollow", html)
        self.assertIn("/pujolsluis-blog/theme/css/main.css", html)
        self.assertIn("https://www.pujolsluis.com/2024/02/03/renderer-fixture/", html)
        self.assertIn("data-source=fixture", html)
        self.assertIn("youtube-nocookie.com/embed/dQw4w9WgXcQ?start=30", html)
        self.assertIn('aria-label="Synthetic gallery"', html)
        self.assertIn('href=/pujolsluis-blog/categories/fixture/', html)
        self.assertIn('href=/pujolsluis-blog/tags/renderer/', html)
        self.assertIn("Disallow: /", (out / "robots.txt").read_text())
        self.assertFalse((out / "sitemap.xml").exists())
        self.assertNotIn('class="comments"', html)
        self.assertNotIn("Synthetic reader", html)
        self.assertNotIn("Sanitized synthetic comment.", html)

    def test_home_shell_and_portfolio_templates(self):
        out = self.build("https://pujolsluis.github.io/pujolsluis-blog/", False)
        home = (out / "index.html").read_text()
        self.assertIn("id=masthead", home)
        self.assertIn('class="content-area with-sidebar"', home)
        self.assertIn("id=secondary", home)
        self.assertIn("noindex, nofollow, max-image-preview:large", home)
        portfolio = (out / "portfolio/index.html").read_text()
        self.assertIn("class=portfolio-grid", portfolio)
        self.assertIn("Synthetic project", portfolio)
        detail = (out / "portfolio/fixture-project/index.html").read_text()
        self.assertIn("Synthetic studio", detail)
        self.assertIn('property="og:image" content="https://pujolsluis.github.io/pujolsluis-blog/media/synthetic-project.jpg"', detail)
        self.assertIn('property="og:image:alt" content="Synthetic room with natural light"', detail)
        self.assertIn('property="og:image:width" content="1200"', detail)

    def test_html_import_uses_exact_source_head_sidecar(self):
        out = self.build("https://pujolsluis.github.io/pujolsluis-blog/", False)
        html = (out / "source-head-fixture/index.html").read_text()
        self.assertIn("<title>Exact source SEO title — café</title>", html)
        self.assertIn('name=description content="Exact source description."', html)
        self.assertIn('rel=canonical href=https://www.pujolsluis.com/source-head-fixture/', html)
        self.assertIn('property="og:title" content="Exact Open Graph title"', html)
        self.assertIn('property="og:description" content="Exact Open Graph description."', html)
        self.assertIn('property="og:image" content="https://www.pujolsluis.com/wp-content/uploads/source-image.jpg"', html)
        self.assertIn('name=twitter:title content="Exact Twitter title"', html)
        self.assertIn('name=twitter:description content="Exact Twitter description."', html)
        self.assertIn('name=twitter:image content="https://www.pujolsluis.com/wp-content/uploads/source-image.jpg"', html)
        self.assertIn("<p data-source=html-fixture>HTML content remains HTML.</p>", html)

    def test_explicit_null_source_head_fields_suppress_fallback_metadata(self):
        out = self.build("https://pujolsluis.github.io/pujolsluis-blog/", False)
        html = (out / "null-head-fixture/index.html").read_text()
        self.assertIn("<title>Exact title retained with null metadata</title>", html)
        self.assertNotIn("name=description", html)
        self.assertNotIn("rel=canonical", html)
        self.assertNotIn('property="og:title"', html)
        self.assertNotIn('property="og:description"', html)
        self.assertNotIn('property="og:image"', html)
        self.assertNotIn("name=twitter:title", html)
        self.assertNotIn("name=twitter:description", html)
        self.assertNotIn("name=twitter:image", html)
        self.assertIn("noindex, nofollow", html)

    def test_production_root_and_indexing(self):
        out = self.build("https://www.pujolsluis.com/", True)
        html = (out / "2024/02/03/renderer-fixture/index.html").read_text()
        self.assertIn('content="max-image-preview:large"', html)
        self.assertNotIn('content="index, follow"', html)
        self.assertIn("https://www.pujolsluis.com/2024/02/03/renderer-fixture/", html)
        self.assertIn("/theme/css/main.css", html)
        self.assertNotIn("/pujolsluis-blog/", html)
        self.assertIn("Sitemap: https://www.pujolsluis.com/sitemap.xml", (out / "robots.txt").read_text())
        self.assertTrue((out / "sitemap.xml").exists())
        feed = (out / "posts/index.xml").read_text()
        feed_item = ET.fromstring(feed).find("./channel/item")
        self.assertEqual(feed_item.findtext("guid"), "urn:fixture:renderer-001")
        self.assertEqual(feed_item.findtext("description"), "<p>Stable synthetic excerpt for feed validation.</p>")
        imported = (out / "source-head-fixture/index.html").read_text()
        self.assertIn("<title>Exact source SEO title — café</title>", imported)
        self.assertIn("https://www.pujolsluis.com/source-head-fixture/", imported)
        self.assertIn("max-image-preview:large", imported)
        self.assertNotIn("noindex", imported)
