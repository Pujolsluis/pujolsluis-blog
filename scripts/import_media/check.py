#!/usr/bin/env python3
"""Check selected image outputs against the MIG-03 inventory contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    from .output_projections import projection_conflicts
except ImportError:  # Running as a script from the repository root.
    from output_projections import projection_conflicts

SIGNATURES = {
    ".jpg": (b"\xff\xd8\xff", "image/jpeg"),
    ".jpeg": (b"\xff\xd8\xff", "image/jpeg"),
    ".png": (b"\x89PNG\r\n\x1a\n", "image/png"),
    ".gif": (b"GIF8", "image/gif"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check(manifest: dict, static_root: Path) -> tuple[list[str], list[str], dict[str, int]]:
    errors: list[str] = []
    warnings: list[str] = []
    expected: set[str] = set()
    total_bytes = 0
    image_count = 0
    for asset in manifest["assets"]:
        if asset["disposition"] != "required-content-candidate":
            continue
        outputs = asset.get("output_paths", [])
        if not outputs:
            errors.append(f"missing output record: {asset['source_path']}")
            continue
        if any(path.get("path", "").rsplit(".", 1)[-1].lower() != asset["extension"].lstrip(".") for path in outputs):
            errors.append(f"public extension differs from source: {asset['source_path']}")
        if asset.get("content_type") not in {"image/jpeg", "image/png", "image/gif"}:
            errors.append(f"unsupported or incorrectly typed image: {asset['source_path']}")
        for output in outputs:
            relative = output["path"]
            if relative in expected:
                errors.append(f"duplicate public output path: {relative}")
                continue
            expected.add(relative)
            target = static_root / relative
            if not target.is_file():
                errors.append(f"missing output file: {relative}")
                continue
            if sha256(target) != output.get("sha256"):
                errors.append(f"output SHA-256 mismatch: {relative}")
            size = target.stat().st_size
            if size != output.get("bytes"):
                errors.append(f"output byte count mismatch: {relative}")
            signature = SIGNATURES.get(asset["extension"])
            if signature and (target.read_bytes()[: len(signature[0])] != signature[0] or asset["content_type"] != signature[1]):
                errors.append(f"content type/signature mismatch: {relative}")
            total_bytes += size
            image_count += 1
            if size > asset.get("role_byte_budget_bytes", 1_000_000):
                warnings.append(f"above per-image target; measured-size review required: {relative} ({size} bytes)")
    # Every route/content mapping repeats the selected asset's output record.
    # Validate each projection against assets[].output_paths and against disk.
    errors.extend(projection_conflicts(manifest))
    for section in ("published_body_path_mappings", "rendered_page_path_mappings", "attachment_route_path_mappings"):
        for mapping in manifest.get(section, []):
            for source in mapping.get("source_assets", []):
                output = source.get("output")
                if not output:
                    continue
                relative = output.get("path", "")
                target = static_root / relative
                if not target.is_file():
                    errors.append(f"missing mapped output file: {section}:{mapping.get('public_url_path')}: {relative}")
                    continue
                if sha256(target) != output.get("sha256"):
                    errors.append(f"mapped output SHA-256 mismatch: {section}:{mapping.get('public_url_path')}: {relative}")
                if target.stat().st_size != output.get("bytes"):
                    errors.append(f"mapped output byte count mismatch: {section}:{mapping.get('public_url_path')}: {relative}")
    if manifest.get("missing_references"):
        for missing in manifest["missing_references"]:
            if any(missing.get(key) for key in ("body_references", "metadata_references", "rendered_page_references", "attachment_route_references")):
                errors.append(f"unresolved published image reference: {missing['url_path']}")
    return errors, warnings, {"images": image_count, "output_bytes": total_bytes}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--static-root", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    errors, warnings, totals = check(manifest, args.static_root)
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    print(json.dumps({**totals, "errors": len(errors), "warnings": len(warnings)}, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
