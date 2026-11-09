from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.import_content.media import selected_media_map
from scripts.import_media.check import check as check_media


class RecoveryEvidenceTests(unittest.TestCase):
    def fixture(self, root: Path):
        source_path = "2018/06/cropped-Pujolsluis-Icon.png"
        public_path = "2018/06/cropped-Pujolsluis-icon.png"
        output_path = "wp-content/uploads/2018/06/cropped-Pujolsluis-Icon.png"
        alias_path = "wp-content/uploads/2018/06/cropped-Pujolsluis-icon.png"
        payload = b"\x89PNG\r\n\x1a\nfixture"
        digest = hashlib.sha256(payload).hexdigest()
        source_digest = "f" * 64
        for path in (output_path, alias_path):
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        output = {"path": output_path, "sha256": digest, "bytes": len(payload)}
        asset = {
            "source_path": source_path,
            "source_sha256": source_digest,
            "source_bytes": 10,
            "extension": ".png",
            "content_type": "image/png",
            "disposition": "required-content-candidate",
            "output_paths": [output],
        }
        missing = [
            {
                "url_path": public_path,
                "case_variant_candidates": [{
                    "source_path": source_path,
                    "source_sha256": source_digest,
                }],
                "body_references": [{"url": "https://example.test/" + public_path}],
            },
            {
                "url_path": "sites/12/2017/02/demo.jpg",
                "rendered_page_references": [{"url": "https://themes.pixelwars.org/demo.jpg"}],
            },
        ]
        manifest = {"schema_version": "1.0.0", "assets": [asset], "missing_references": missing}
        evidence = {
            "recovered_references": [{
                "url_path": public_path,
                "source_path": source_path,
                "source_sha256": source_digest,
                "output_path": alias_path,
                "output_sha256": digest,
                "output_bytes": len(payload),
            }],
            "external_dependencies": [{
                "url_path": "sites/12/2017/02/demo.jpg",
                "category": "third-party-theme-demo",
                "evidence": "captured theme-demo dependency",
            }],
        }
        return manifest, evidence, alias_path

    def test_hash_verified_recovery_maps_media_and_external_theme_is_warning(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, evidence, alias_path = self.fixture(root)
            source_url = (
                "https://i0.wp.com/www.pujolsluis.com/wp-content/uploads/"
                "2018/06/cropped-Pujolsluis-icon.png?fit=512%2C512&ssl=1"
            )
            document, unresolved = selected_media_map(
                manifest, [source_url], "/project/", root, evidence
            )
            self.assertEqual(unresolved, [])
            self.assertEqual(
                document["mappings"],
                [{"sourceUrl": source_url, "targetPath": "/" + alias_path}],
            )
            errors, warnings, _ = check_media(manifest, root, evidence)
            self.assertFalse(errors)
            self.assertTrue(any("third-party theme-demo image remains external" in item
                                for item in warnings))

    def test_committed_recovery_evidence_matches_optimized_aliases_and_attachment_html(self):
        repository = Path(__file__).resolve().parents[1]
        manifest = json.loads((repository / "migration/assets/manifest.json").read_text())
        evidence = json.loads(
            (repository / "migration/assets/recovery-evidence.json").read_text()
        )
        for recovery in evidence["recovered_references"]:
            missing = next(
                item for item in manifest["missing_references"]
                if item["url_path"] == recovery["url_path"]
            )
            candidate = next(
                item for item in missing["case_variant_candidates"]
                if item["source_path"] == recovery["source_path"]
            )
            self.assertEqual(candidate["source_sha256"], recovery["source_sha256"])
            asset = next(
                item for item in manifest["assets"]
                if item["source_path"] == recovery["source_path"]
            )
            self.assertEqual(asset["source_sha256"], recovery["source_sha256"])
            selected = next(
                item for item in asset["output_paths"]
                if item["path"].casefold() == recovery["output_path"].casefold()
            )
            self.assertEqual(selected["sha256"], recovery["output_sha256"])
            self.assertEqual(selected["bytes"], recovery["output_bytes"])
            target = repository / "static" / recovery["output_path"]
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(),
                             recovery["output_sha256"])
            self.assertEqual(target.stat().st_size, recovery["output_bytes"])
            backup_case_path = repository / "static" / selected["path"]
            self.assertEqual(target.read_bytes(), backup_case_path.read_bytes())

        for source_id, public_path in (
            ("wp-31", "cropped-Pujolsluis-icon.png"),
            ("wp-34", "cropped-Pujolsluis-icon-1.png"),
        ):
            body = (repository / "content/attachment" / f"{source_id}.html").read_text()
            rendered_body = body.split("}\n\n", 1)[1]
            self.assertNotIn("i0.wp.com/www.pujolsluis.com/wp-content/uploads/2018/06/"
                             + public_path, rendered_body)
            self.assertIn("/pujolsluis-blog/wp-content/uploads/2018/06/" + public_path,
                          rendered_body)


if __name__ == "__main__":
    unittest.main()
