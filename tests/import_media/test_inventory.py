from __future__ import annotations

import struct
import tempfile
import unittest
import zlib
import hashlib
from pathlib import Path

from scripts.import_media.inventory import build_inventory
from scripts.import_media.check import check as check_manifest_outputs
from scripts.import_media.augment_rendered import augment
from scripts.import_media.optimize import PNG_SIGNATURE, png_chunks, png_lossless_optimize, strip_jpeg_gps, strip_tiff_gps
from scripts.import_media.output_projections import projection_conflicts, sync_output_projections


WXR = """<?xml version='1.0'?>
<rss xmlns:wp="http://wordpress.org/export/1.2/" xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel>
  <item><title>Published sample</title><wp:post_id>42</wp:post_id><wp:post_type>post</wp:post_type><wp:status>publish</wp:status>
    <content:encoded><![CDATA[<img src="https://example.test/wp-content/uploads/sites/12/2020/01/photo.jpg" />
    <img srcset="https://example.test/wp-content/uploads/sites/12/2020/01/photo-300x200.jpg 300w" />
    <iframe src="https://www.youtube.com/embed/abc123"></iframe>]]></content:encoded>
    <wp:postmeta><wp:meta_key>_thumbnail_id</wp:meta_key><wp:meta_value>77</wp:meta_value></wp:postmeta>
    <wp:postmeta><wp:meta_key>essb_cached_image</wp:meta_key><wp:meta_value>https://example.test/wp-content/uploads/2020/01/social.png</wp:meta_value></wp:postmeta>
  </item>
  <item><title>Draft sample</title><wp:post_id>43</wp:post_id><wp:post_type>post</wp:post_type><wp:status>draft</wp:status>
    <content:encoded><![CDATA[<img src="https://example.test/wp-content/uploads/2020/01/private.jpg" />]]></content:encoded>
  </item>
  <item><title>Photo</title><wp:post_id>77</wp:post_id><wp:post_type>attachment</wp:post_type><wp:status>inherit</wp:status>
    <wp:post_parent>42</wp:post_parent><wp:attachment_url>https://example.test/wp-content/uploads/sites/12/2020/01/photo.jpg</wp:attachment_url>
  </item>
</channel></rss>"""


class InventoryTests(unittest.TestCase):
    def test_checker_validates_rendered_mapping_hashes_against_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "wp-content/uploads/2020/01/photo.jpg"
            target.parent.mkdir(parents=True)
            payload = b"\xff\xd8\xffselected-image"
            target.write_bytes(payload)
            output = {
                "path": "wp-content/uploads/2020/01/photo.jpg",
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
            asset = {
                "disposition": "required-content-candidate",
                "source_path": "2020/01/photo.jpg",
                "extension": ".jpg",
                "content_type": "image/jpeg",
                "output_paths": [output],
            }
            manifest = {
                "assets": [asset],
                "missing_references": [],
                "rendered_page_path_mappings": [{
                    "public_url_path": "2020/01/photo.jpg",
                    "source_assets": [{"output": {**output, "sha256": "0" * 64}}],
                }],
            }

            errors, warnings, totals = check_manifest_outputs(manifest, root)
            self.assertEqual(totals["images"], 1)
            self.assertFalse(warnings)
            self.assertTrue(any("mapped output SHA-256 mismatch" in error for error in errors))

    def test_cross_projection_conflicts_are_rejected_and_synchronized(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "wp-content/uploads/2020/01/photo.jpg"
            target.parent.mkdir(parents=True)
            payload = b"\xff\xd8\xffselected-image"
            target.write_bytes(payload)
            output = {
                "path": "wp-content/uploads/2020/01/photo.jpg",
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
            asset = {
                "disposition": "required-content-candidate",
                "source_path": "2020/01/photo.jpg",
                "extension": ".jpg",
                "content_type": "image/jpeg",
                "output_paths": [output],
            }
            manifest = {
                "assets": [asset],
                "missing_references": [],
                "published_body_path_mappings": [{
                    "public_url_path": "2020/01/photo.jpg",
                    "content_type": "image/png",
                    "source_assets": [{"content_type": "image/png", "output": {**output, "sha256": "0" * 64, "bytes": len(payload) + 1, "content_type": "image/png"}}],
                }],
                "rendered_page_path_mappings": [{
                    "public_url_path": "2020/01/photo.jpg",
                    "source_assets": [{"output": output.copy()}],
                }],
                "attachment_route_path_mappings": [],
            }

            conflicts = projection_conflicts(manifest)
            self.assertTrue(any("manifest projection conflict (sha256)" in error for error in conflicts))
            self.assertTrue(any("manifest projection conflict (bytes)" in error for error in conflicts))
            self.assertTrue(any("manifest projection conflict (content_type)" in error for error in conflicts))
            errors, _, _ = check_manifest_outputs(manifest, root)
            self.assertTrue(any("manifest projection conflict (sha256)" in error for error in errors))

            self.assertEqual(sync_output_projections(manifest), 3)
            self.assertFalse(projection_conflicts(manifest))
            errors, warnings, totals = check_manifest_outputs(manifest, root)
            self.assertFalse(errors)
            self.assertFalse(warnings)
            self.assertEqual(totals["images"], 1)

    def test_rendered_page_image_card_and_share_metadata_select_existing_upload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshots = root / "snapshots"
            snapshots.mkdir()
            snapshot = snapshots / "page.html"
            snapshot.write_text('<meta property="og:image" content="https://example.test/wp-content/uploads/2020/01/social.png"><img srcset="https://example.test/wp-content/uploads/2020/01/social.png 640w">')
            (snapshots / "manifest.json").write_text('{"records":[{"url":"https://example.test/page/","file":"page.html","status":"200"}]}')
            asset = {
                "source_path": "2020/01/social.png", "disposition": "excluded-unverified-social-metadata",
                "reason": "cached metadata only", "compatibility_disposition": "excluded", "referenced_url_paths": [],
            }
            manifest = {"assets": [asset], "missing_references": [], "evidence": {}, "counts": {}}
            augment(manifest, [snapshots])

            self.assertEqual(asset["disposition"], "required-content-candidate")
            self.assertEqual(asset["referenced_url_paths"], ["2020/01/social.png"])
            self.assertEqual({ref["attribute"] for ref in asset["rendered_page_references"]}, {"meta-image", "srcset"})
            self.assertEqual(manifest["counts"]["required_asset_files"], 1)

    def test_published_references_relationships_social_metadata_and_exclusions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            uploads = root / "uploads"
            uploads.mkdir()
            for name, contents in {
                "2020/01/photo.jpg": b"required-original",
                "2020/01/photo-300x200.jpg": b"required-variant",
                "2020/01/social.png": b"social",
                "2020/01/orphan-640x480.jpg": b"generated-unused",
                "2020/01/orphan.jpg": b"orphan",
            }.items():
                target = uploads / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(contents)
            wxr = root / "export.xml"
            wxr.write_text(WXR)

            report = build_inventory(wxr, uploads)
            assets = {asset["source_path"]: asset for asset in report["assets"]}

            self.assertEqual(report["counts"]["published_body_paths"], 2)
            self.assertEqual(report["counts"]["social_metadata_only_paths"], 1)
            self.assertEqual(assets["2020/01/photo.jpg"]["disposition"], "required-content-candidate")
            self.assertEqual(assets["2020/01/photo.jpg"]["attachment_records"][0]["id"], "77")
            self.assertEqual(assets["2020/01/photo-300x200.jpg"]["disposition"], "required-content-candidate")
            self.assertEqual(assets["2020/01/social.png"]["disposition"], "excluded-unverified-social-metadata")
            self.assertEqual(assets["2020/01/orphan-640x480.jpg"]["disposition"], "excluded-unused-generated-size")
            self.assertEqual(assets["2020/01/orphan.jpg"]["disposition"], "excluded-unreferenced-upload")
            self.assertEqual(report["video_provider_references"][0]["provider_url"], "https://www.youtube.com/embed/abc123")
            self.assertEqual(len(assets["2020/01/photo.jpg"]["source_sha256"]), 64)

    def test_missing_referenced_path_remains_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            uploads = root / "uploads"
            uploads.mkdir()
            wxr = root / "export.xml"
            wxr.write_text(WXR)
            missing = build_inventory(wxr, uploads)["missing_references"]
            urls = {item["url_path"] for item in missing}
            self.assertIn("sites/12/2020/01/photo.jpg", urls)
            self.assertIn("sites/12/2020/01/photo-300x200.jpg", urls)

    def test_png_optimizer_preserves_decoded_pixels_and_metadata(self) -> None:
        def chunk(kind: bytes, payload: bytes) -> bytes:
            return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.png"
            destination = root / "output.png"
            width = height = 32
            scanline = b"\x00" + bytes((220, 120, 40, 255)) * width
            pixels = scanline * height
            compressed = zlib.compress(pixels, level=1)
            png = PNG_SIGNATURE + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            png += chunk(b"tEXt", b"Copyright\x00Unit test") + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")
            source.write_bytes(png)

            result = png_lossless_optimize(source, destination)
            chunks = png_chunks(destination.read_bytes())
            output_idat = zlib.decompress(b"".join(data for kind, data in chunks if kind == b"IDAT"))

            self.assertEqual(result["method"], "png-zlib-level-9")
            self.assertEqual(output_idat, pixels)
            self.assertIn((b"tEXt", b"Copyright\x00Unit test"), chunks)
            self.assertLess(destination.stat().st_size, source.stat().st_size)

    def test_jpeg_gps_ifd_is_removed_without_discarding_copyright(self) -> None:
        tiff = bytearray(80)
        tiff[0:2] = b"II"
        tiff[2:4] = (42).to_bytes(2, "little")
        tiff[4:8] = (8).to_bytes(4, "little")
        tiff[8:10] = (2).to_bytes(2, "little")
        tiff[10:12] = (0x8825).to_bytes(2, "little")
        tiff[12:14] = (4).to_bytes(2, "little")
        tiff[14:18] = (1).to_bytes(4, "little")
        tiff[18:22] = (38).to_bytes(4, "little")
        tiff[22:24] = (0x8298).to_bytes(2, "little")
        tiff[24:26] = (2).to_bytes(2, "little")
        tiff[26:30] = (4).to_bytes(4, "little")
        tiff[30:34] = b"ACME"
        tiff[38:40] = (1).to_bytes(2, "little")
        tiff[40:42] = (2).to_bytes(2, "little")
        tiff[42:44] = (5).to_bytes(2, "little")
        tiff[44:48] = (3).to_bytes(4, "little")
        tiff[48:52] = (56).to_bytes(4, "little")
        tiff[56:80] = bytes(range(24))
        original_tiff = bytes(tiff)
        self.assertTrue(strip_tiff_gps(tiff))
        self.assertFalse(strip_tiff_gps(tiff))
        self.assertIn(b"ACME", tiff)
        self.assertEqual(tiff[18:22], b"\x00" * 4)
        self.assertEqual(tiff[38:80], b"\x00" * 42)

        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "sample.jpg"
            exif = b"Exif\x00\x00" + original_tiff
            segment = b"\xff\xe1" + (len(exif) + 2).to_bytes(2, "big") + exif
            source.write_bytes(b"\xff\xd8" + segment + b"\xff\xda\x00\x02")
            self.assertTrue(strip_jpeg_gps(source))
            output = source.read_bytes()
            sanitized = output[12:12 + len(original_tiff)]
            self.assertEqual(sanitized[18:22], b"\x00" * 4)
            self.assertEqual(sanitized[38:80], b"\x00" * 42)
            self.assertIn(b"ACME", sanitized)


if __name__ == "__main__":
    unittest.main()
