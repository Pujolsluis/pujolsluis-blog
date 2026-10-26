"""Integrity and preview-build checks for the reviewed public migration bundle."""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
EXPECTED_SECTIONS = {"posts": 45, "page": 8, "portfolio": 13, "attachment": 98}


def read_front_matter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    metadata, end = json.JSONDecoder().raw_decode(text)
    return metadata, text[end:]


class MigratedContentTests(unittest.TestCase):
    def test_public_records_have_exact_unique_routes_and_no_comment_records(self):
        routes = set()
        count = 0
        for section, expected in EXPECTED_SECTIONS.items():
            extension = "*.md" if section == "posts" else "*.html"
            files = sorted((CONTENT / section).glob(extension))
            self.assertEqual(len(files), expected, section)
            for path in files:
                metadata, body = read_front_matter(path)
                count += 1
                self.assertTrue(metadata["url"].startswith("/"), path)
                self.assertNotIn(metadata["url"], routes, path)
                routes.add(metadata["url"])
                migration = metadata.get("migration", {})
                self.assertNotIn("comments", migration, path)
                if section == "attachment":
                    for key in ("fragments", "duplicateFragments", "sourceFragments",
                                "duplicateSourceFragments"):
                        self.assertFalse(
                            any("comment" in fragment.lower() or "respond" in fragment.lower()
                                for fragment in migration.get(key, [])),
                            f"comment fragment exposed in {path}: {key}",
                        )
                if path.name != "_index.html":
                    self.assertTrue(body.strip(), path)
                self.assertNotRegex(body, r"<form\b")
                self.assertNotIn("wp-comments-post.php", body)
                self.assertNotIn('id="comments"', body)
                self.assertNotIn('id="respond"', body)
                self.assertNotRegex(body, r"\(<%20https?://")
                self.assertNotRegex(body, r"(?i)(?:href|action)=[\"'][^\"']*#(?:comments?|respond)")

        self.assertEqual(list((CONTENT / "posts").glob("*.html")), [])

        self.assertEqual(count, 164)
        self.assertFalse((CONTENT / ".hugo-import-report.json").exists())
        content_files = [path for section in EXPECTED_SECTIONS
                         for pattern in ("*.html", "*.md")
                         for path in (CONTENT / section).glob(pattern)]
        self.assertEqual(
            sum("migration-comment-bridge" in read_front_matter(path)[1]
                for path in content_files), 0)

    @unittest.skipUnless(shutil.which("hugo"), "Hugo is not installed in this environment")
    def test_hugo_preview_publishes_every_imported_route_and_lists_posts(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "site"
            subprocess.run(
                [
                    "hugo",
                    "--minify",
                    "--noBuildLock",
                    "--source",
                    str(ROOT),
                    "--destination",
                    str(output),
                    "--baseURL",
                    "https://pujolsluis.github.io/pujolsluis-blog/",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            home = (output / "index.html").read_text(encoding="utf-8")
            self.assertIn("Latest posts", home)
            self.assertNotIn("Posts will appear here when content is imported.", home)
            self.assertGreaterEqual(len(re.findall(r'class=(?:"post-card"|post-card)', home)), 10)
            self.assertTrue((output / "posts/index.xml").is_file())
            self.assertTrue((output / "search-index.json").is_file())

            for section, _ in EXPECTED_SECTIONS.items():
                extension = "*.md" if section == "posts" else "*.html"
                for path in sorted((CONTENT / section).glob(extension)):
                    metadata, _ = read_front_matter(path)
                    route = urlsplit(metadata["url"]).path.strip("/")
                    expected = output / route / "index.html"
                    self.assertTrue(expected.is_file(), metadata["url"])


if __name__ == "__main__":
    unittest.main()
