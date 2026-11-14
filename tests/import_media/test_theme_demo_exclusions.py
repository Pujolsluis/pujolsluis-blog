"""MIG-03 media validation respects reviewed theme-demo asset exclusions."""

import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.import_media.check import check


class ThemeDemoMediaCheckTests(unittest.TestCase):
    def test_excluded_demo_outputs_are_omitted_and_retained_outputs_stay_verified(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            retained = bytes((0xff, 0xd8, 0xff)) + b"authored-image"
            retained_output = {
                "path": "wp-content/uploads/2020/01/authored.jpg",
                "bytes": len(retained),
                "sha256": hashlib.sha256(retained).hexdigest(),
            }
            demo_output = {
                "path": "wp-content/uploads/2017/02/demo.jpg",
                "bytes": 500,
                "sha256": "a" * 64,
            }
            target = root / retained_output["path"]
            target.parent.mkdir(parents=True)
            target.write_bytes(retained)
            manifest = {
                "assets": [{
                    "disposition": "required-content-candidate",
                    "source_path": "2020/01/authored.jpg",
                    "extension": ".jpg",
                    "content_type": "image/jpeg",
                    "output_paths": [retained_output, demo_output],
                }],
                "missing_references": [],
                "rendered_page_path_mappings": [{
                    "public_url_path": "2017/02/demo.jpg",
                    "source_assets": [{"output": demo_output}],
                }],
            }
            exclusions = {
                "schemaVersion": "1.0.0",
                "wxrSha256": "b" * 64,
                "excludedItems": {},
                "excludedAttachments": {},
                "themeDemoOnlyAssets": ["static/" + demo_output["path"]],
            }

            errors, warnings, totals = check(manifest, root, theme_demo_exclusions=exclusions)
            self.assertFalse(errors)
            self.assertFalse(warnings)
            self.assertEqual(totals, {"images": 1, "output_bytes": len(retained)})

            excluded_target = root / demo_output["path"]
            excluded_target.parent.mkdir(parents=True, exist_ok=True)
            excluded_target.write_bytes(bytes((0xff, 0xd8, 0xff)) + b"theme-demo")
            errors, _, _ = check(manifest, root, theme_demo_exclusions=exclusions)
            self.assertTrue(any("theme-demo asset must not be published" in error
                                for error in errors))


if __name__ == "__main__":
    unittest.main()
