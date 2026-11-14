#!/usr/bin/env python3
"""Check selected image outputs against the MIG-03 inventory contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    from .output_projections import live_body_coverage_errors, projection_conflicts
except ImportError:  # Running as a script from the repository root.
    from output_projections import live_body_coverage_errors, projection_conflicts

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


def verify_recovery_evidence(manifest: dict, static_root: Path, evidence: dict | None) -> tuple[set[str], set[str], list[str]]:
    """Validate hash-bound icon recoveries and explicitly external theme assets."""
    if evidence is None:
        return set(), set(), []
    errors: list[str] = []
    missing_by_path = {row.get("url_path"): row for row in manifest.get("missing_references", [])}
    assets_by_path = {row.get("source_path"): row for row in manifest.get("assets", [])}
    recovered: set[str] = set()
    external: set[str] = set()
    for row in evidence.get("recovered_references", []):
        path = row.get("url_path", "")
        source_path = row.get("source_path", "")
        source_sha256 = row.get("source_sha256", "")
        output_path = row.get("output_path", "")
        output_sha256 = row.get("output_sha256", "")
        output_bytes = row.get("output_bytes")
        before = len(errors)
        missing = missing_by_path.get(path)
        if not missing:
            errors.append(f"recovery path is not a manifest missing reference: {path}")
            continue
        if not path or path.casefold() != source_path.casefold() or path == source_path:
            errors.append(f"recovery is not a case-only source path match: {path}")
        candidate = next((item for item in missing.get("case_variant_candidates", [])
                          if item.get("source_path") == source_path
                          and item.get("source_sha256") == source_sha256), None)
        asset = assets_by_path.get(source_path)
        if not candidate or not asset or asset.get("source_sha256") != source_sha256:
            errors.append(f"recovery source hash differs from MIG-03 evidence: {path}")
        if (not output_path.startswith("wp-content/uploads/")
                or any(part in ("", ".", "..") for part in Path(output_path).parts)):
            errors.append(f"recovery output is not a safe uploads path: {path}")
        selected = next((item for item in (asset or {}).get("output_paths", [])
                         if item.get("path", "").casefold() == output_path.casefold()), None)
        if (not selected or selected.get("sha256") != output_sha256
                or selected.get("bytes") != output_bytes):
            errors.append(f"recovery output differs from optimized selected asset: {path}")
        target = static_root / output_path
        if not target.is_file() or target.is_symlink():
            errors.append(f"recovery output missing or unsafe: {output_path}")
        elif sha256(target) != output_sha256 or target.stat().st_size != output_bytes:
            errors.append(f"recovery output checksum mismatch: {output_path}")
        if len(errors) == before:
            recovered.add(path)
    for row in evidence.get("external_dependencies", []):
        path = row.get("url_path", "")
        missing = missing_by_path.get(path)
        if not missing or not row.get("evidence"):
            errors.append(f"external dependency lacks manifest/evidence record: {path}")
            continue
        if row.get("category") != "third-party-theme-demo":
            errors.append(f"unsupported external dependency category: {path}")
            continue
        if path in recovered:
            errors.append(f"reference cannot be both recovered and external: {path}")
            continue
        external.add(path)
    return recovered, external, errors


def verify_theme_demo_exclusions(manifest: dict, static_root: Path, exclusions: dict | None) -> tuple[set[str], list[str]]:
    """Ensure exact demo-only selected outputs are absent from the public media tree."""
    if exclusions is None:
        return set(), []
    required = {"schemaVersion", "wxrSha256", "excludedItems", "excludedAttachments", "themeDemoOnlyAssets"}
    if (not isinstance(exclusions, dict) or not required <= set(exclusions)
            or exclusions.get("schemaVersion") != "1.0.0"
            or not isinstance(exclusions.get("wxrSha256"), str)
            or len(exclusions["wxrSha256"]) != 64
            or any(char not in "0123456789abcdef" for char in exclusions["wxrSha256"])
            or not isinstance(exclusions.get("excludedItems"), dict)
            or not isinstance(exclusions.get("excludedAttachments"), dict)
            or not isinstance(exclusions.get("themeDemoOnlyAssets"), list)):
        return set(), ["invalid hash-bound theme-demo exclusion policy"]
    outputs = {
        output.get("path", "")
        for asset in manifest.get("assets", [])
        for output in asset.get("output_paths", [])
        if isinstance(output, dict)
    }
    excluded: set[str] = set()
    errors: list[str] = []
    for public_path in exclusions["themeDemoOnlyAssets"]:
        if (not isinstance(public_path, str) or not public_path.startswith("static/wp-content/uploads/")
                or any(part in ("", ".", "..") for part in Path(public_path).parts)):
            errors.append(f"unsafe theme-demo output exclusion: {public_path}")
            continue
        relative = public_path.removeprefix("static/")
        if relative not in outputs:
            errors.append(f"theme-demo output is absent from media inventory: {relative}")
            continue
        target = static_root / relative
        if target.exists() or target.is_symlink():
            errors.append(f"theme-demo asset must not be published: {relative}")
        excluded.add(relative)
    if len(excluded) != len(exclusions["themeDemoOnlyAssets"]):
        errors.append("theme-demo output exclusions must be unique")
    return excluded, errors


def check(manifest: dict, static_root: Path, recovery_evidence: dict | None = None, theme_demo_exclusions: dict | None = None) -> tuple[list[str], list[str], dict[str, int]]:
    errors: list[str] = []
    warnings: list[str] = []
    recovered, external, recovery_errors = verify_recovery_evidence(manifest, static_root, recovery_evidence)
    errors.extend(recovery_errors)
    excluded_outputs, exclusion_errors = verify_theme_demo_exclusions(
        manifest, static_root, theme_demo_exclusions)
    errors.extend(exclusion_errors)
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
            if relative in excluded_outputs:
                continue
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
    errors.extend(live_body_coverage_errors(manifest))
    for section in ("published_body_path_mappings", "rendered_page_path_mappings", "attachment_route_path_mappings", "live_rendered_body_path_mappings"):
        for mapping in manifest.get(section, []):
            for source in mapping.get("source_assets", []):
                output = source.get("output")
                if not output:
                    continue
                relative = output.get("path", "")
                if relative in excluded_outputs:
                    continue
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
            if not any(missing.get(key) for key in ("body_references", "metadata_references", "rendered_page_references", "attachment_route_references")):
                continue
            path = missing["url_path"]
            if path in recovered:
                continue
            if path in external:
                warnings.append(f"third-party theme-demo image remains external: {path}")
                continue
            errors.append(f"unresolved published image reference: {path}")
    return errors, warnings, {"images": image_count, "output_bytes": total_bytes}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--static-root", type=Path, required=True)
    parser.add_argument("--recovery-evidence", type=Path,
                        default=Path(__file__).resolve().parents[2]
                        / "migration/assets/recovery-evidence.json")
    parser.add_argument("--theme-demo-exclusions", type=Path,
                        default=Path(__file__).resolve().parents[2]
                        / "migration/theme-demo-exclusions.json")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    evidence = (json.loads(args.recovery_evidence.read_text(encoding="utf-8"))
                if args.recovery_evidence.is_file() else None)
    exclusions = (json.loads(args.theme_demo_exclusions.read_text(encoding="utf-8"))
                  if args.theme_demo_exclusions.is_file() else None)
    errors, warnings, totals = check(manifest, args.static_root, evidence, exclusions)
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    print(json.dumps({**totals, "errors": len(errors), "warnings": len(warnings)}, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
