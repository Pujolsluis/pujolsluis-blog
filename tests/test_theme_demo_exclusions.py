"""The public Hugo selection excludes only source-verified WordPress theme demos."""

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "migration" / "theme-demo-exclusions.json").read_text(encoding="utf-8"))
EXPECTED_DEMO_CONTENT_IDS = {
    "wp:86", "wp:93", "wp:117", "wp:1997", "wp:1998", "wp:1999", "wp:2001",
    "wp:333", "wp:342", "wp:347", "wp:354", "wp:359", "wp:365", "wp:367",
    "wp:369", "wp:371", "wp:373", "wp:375", "wp:380",
}
EXPECTED_DEMO_ASSETS = {
    "static/wp-content/uploads/2016/08/06-1.jpg",
    "static/wp-content/uploads/2016/08/07-1.jpg",
    "static/wp-content/uploads/2016/08/about.jpg",
    "static/wp-content/uploads/2017/02/blank1.jpg",
    "static/wp-content/uploads/2017/02/branding-exploration.png",
    "static/wp-content/uploads/2017/02/changes.jpg",
    "static/wp-content/uploads/2017/02/chemistry.jpg",
    "static/wp-content/uploads/2017/02/disclosure.jpg",
    "static/wp-content/uploads/2017/02/kennes1.jpg",
    "static/wp-content/uploads/2017/02/makeba.jpg",
    "static/wp-content/uploads/2017/02/matin2.jpg",
    "static/wp-content/uploads/2017/02/stages1.jpg",
    "static/wp-content/uploads/2017/02/thekitchens.jpg",
    "static/wp-content/uploads/2017/02/unknown.jpg",
    "static/wp-content/uploads/2017/02/various1.jpg",
    "static/wp-content/uploads/2017/03/logo.png",
    "static/wp-content/uploads/sites/12/2016/08/01.jpg",
    "static/wp-content/uploads/sites/12/2017/02/kennes1.jpg",
}
EXPECTED_SHARED_ASSETS = {
    "static/wp-content/uploads/2018/07/Pujolsluis-Icon.png",
    "static/wp-content/uploads/2018/07/cropped-Pujolsluis-Icon-2.png",
}
EXPECTED_RETAINED_ATTACHMENTS = {
    "wp:6", "wp:7", "wp:11", "wp:12", "wp:27", "wp:28", "wp:31", "wp:34",
    "wp:41", "wp:44", "wp:46", "wp:91", "wp:92", "wp:926", "wp:929",
    "wp:1160", "wp:1162", "wp:1947", "wp:2012", "wp:2014", "wp:2060", "wp:2102",
}


def source_ids(directory, extension):
    pattern = re.compile(r"wp-([1-9][0-9]*)" + re.escape(extension) + r"$")
    return {
        "wp:" + match.group(1)
        for path in directory.glob("wp-*" + extension)
        if (match := pattern.fullmatch(path.name))
    }


class ThemeDemoExclusionTests(unittest.TestCase):
    def test_exclusion_ledger_is_exact_and_hash_bound(self):
        self.assertEqual(POLICY["schemaVersion"], "1.0.0")
        self.assertEqual(POLICY["wxrSha256"],
                         "deae8936282e86fd03376bcced44e0e698b1bfa141029ad79c3a406493ae3d11")
        self.assertEqual(set(POLICY["excludedItems"]), EXPECTED_DEMO_CONTENT_IDS)
        self.assertEqual(len(POLICY["excludedItems"]), 19)
        self.assertEqual(len(POLICY["excludedAttachments"]), 76)
        self.assertTrue(all(row["reason"] == "theme-demo"
                            and row["kind"] in {"page", "portfolio"}
                            for row in POLICY["excludedItems"].values()))
        self.assertTrue(all(row["reason"] == "theme-demo"
                            for row in POLICY["excludedAttachments"].values()))
        self.assertEqual(set(POLICY["themeDemoOnlyAssets"]), EXPECTED_DEMO_ASSETS)
        self.assertEqual(set(POLICY["sharedAssets"]), EXPECTED_SHARED_ASSETS)

    def test_all_authored_posts_and_non_demo_routes_remain(self):
        self.assertEqual(source_ids(ROOT / "content" / "posts", ".md"),
                         set(POLICY["retainedPostIds"]))
        self.assertEqual(len(POLICY["retainedPostIds"]), 45)
        self.assertEqual(source_ids(ROOT / "content" / "page", ".html"),
                         {"wp:1946", "wp:1948"})
        self.assertEqual(set(POLICY["retainedPageIds"]), {"wp:1946", "wp:1948"})
        self.assertEqual(source_ids(ROOT / "content" / "attachment", ".html"),
                         EXPECTED_RETAINED_ATTACHMENTS)
        self.assertEqual(set(POLICY["retainedAttachmentIds"]), EXPECTED_RETAINED_ATTACHMENTS)
        self.assertEqual(list((ROOT / "content" / "portfolio").glob("*.html")), [])

    def test_demo_only_media_is_absent_and_shared_post_branding_stays(self):
        for relative in EXPECTED_DEMO_ASSETS:
            self.assertFalse((ROOT / relative).exists(), relative)
        for relative in EXPECTED_SHARED_ASSETS:
            self.assertTrue((ROOT / relative).is_file(), relative)

        post_bodies = [path.read_text(encoding="utf-8")
                       for path in (ROOT / "content" / "posts").glob("*.md")]
        for relative in EXPECTED_DEMO_ASSETS:
            upload_path = relative.removeprefix("static/")
            self.assertFalse(any(upload_path in body for body in post_bodies), relative)


if __name__ == "__main__":
    unittest.main()
