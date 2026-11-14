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


def jpeg_dimensions(path: Path) -> tuple[int, int] | None:
    """Return dimensions from the first JPEG frame header without optional libraries."""
    data = path.read_bytes()
    if data[:2] != bytes((0xFF, 0xD8)):
        return None
    frame_markers = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                     0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    index = 2
    while index < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            return None
        marker = data[index]
        index += 1
        if marker in (0xD8, 0xD9, 0x01) or 0xD0 <= marker <= 0xD7:
            continue
        if index + 2 > len(data):
            return None
        segment_length = int.from_bytes(data[index:index + 2], "big")
        if segment_length < 2 or index + segment_length > len(data):
            return None
        if marker in frame_markers and segment_length >= 7:
            height = int.from_bytes(data[index + 3:index + 5], "big")
            width = int.from_bytes(data[index + 5:index + 7], "big")
            return (width, height)
        index += segment_length
    return None


def _safe_upload_output(output_path: str) -> bool:
    return (isinstance(output_path, str) and output_path.startswith("wp-content/uploads/")
            and "\\" not in output_path
            and all(part not in ("", ".", "..") for part in output_path.split("/")))


def _verify_recovery_output(static_root: Path, output_path: str, expected_sha: str,
                            expected_bytes: int, errors: list[str], label: str) -> bool:
    if (not _safe_upload_output(output_path) or not isinstance(expected_sha, str)
            or len(expected_sha) != 64 or any(char not in "0123456789abcdef" for char in expected_sha)
            or not isinstance(expected_bytes, int) or isinstance(expected_bytes, bool)
            or expected_bytes < 1):
        errors.append(f"invalid recovery output record: {label}")
        return False
    target = static_root / output_path
    if not target.is_file() or target.is_symlink():
        errors.append(f"recovery output missing or unsafe: {output_path}")
        return False
    if sha256(target) != expected_sha or target.stat().st_size != expected_bytes:
        errors.append(f"recovery output checksum mismatch: {output_path}")
        return False
    return True


def _upload_suffix(url: str) -> str | None:
    from urllib.parse import unquote, urlsplit

    if not isinstance(url, str):
        return None
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    path = unquote(parts.path)
    marker = "/wp-content/uploads/"
    index = path.rfind(marker)
    if index < 0:
        return None
    suffix = path[index + len(marker):]
    if not suffix or any(part in ("", ".", "..") for part in suffix.split("/")):
        return None
    return suffix


def verify_recovery_evidence(manifest: dict, static_root: Path, evidence: dict | None) -> tuple[set[str], set[str], list[str], list[dict]]:
    """Validate exact recoveries, generated derivatives, and explicitly external URL mappings."""
    if evidence is None:
        return set(), set(), [], []
    errors: list[str] = []
    missing_by_path = {row.get("url_path"): row for row in manifest.get("missing_references", [])}
    assets_by_path = {row.get("source_path"): row for row in manifest.get("assets", [])}
    recovered: set[str] = set()
    external: set[str] = set()
    derived_outputs: list[dict] = []
    derived_by_path: dict[str, dict] = {}
    for row in evidence.get("recovered_references", []):
        path = row.get("url_path", "")
        source_path = row.get("source_path", "")
        source_sha256 = row.get("source_sha256", "")
        before = len(errors)
        missing = missing_by_path.get(path)
        if not missing:
            errors.append(f"recovery path is not a manifest missing reference: {path}")
            continue
        asset = assets_by_path.get(source_path)
        if not asset or asset.get("source_sha256") != source_sha256:
            errors.append(f"recovery source hash differs from MIG-03 evidence: {path}")
            continue
        kind = row.get("recovery_kind", "case-variant")
        if kind == "case-variant":
            if not path or path.casefold() != source_path.casefold() or path == source_path:
                errors.append(f"recovery is not a case-only source path match: {path}")
            candidate = next((item for item in missing.get("case_variant_candidates", [])
                              if item.get("source_path") == source_path
                              and item.get("source_sha256") == source_sha256), None)
            if not candidate:
                errors.append(f"recovery source hash differs from MIG-03 candidate: {path}")
            output_path = row.get("output_path", "")
            output_sha256 = row.get("output_sha256", "")
            output_bytes = row.get("output_bytes")
            selected = next((item for item in asset.get("output_paths", [])
                             if item.get("path", "").casefold() == output_path.casefold()), None)
            if (not selected or selected.get("sha256") != output_sha256
                    or selected.get("bytes") != output_bytes):
                errors.append(f"recovery output differs from optimized selected asset: {path}")
            _verify_recovery_output(static_root, output_path, output_sha256, output_bytes, errors, path)
        elif kind == "owner-source-derived-variants":
            if row.get("source_bytes") != asset.get("source_bytes"):
                errors.append(f"recovery source byte count differs from MIG-03 evidence: {path}")
            dimensions = asset.get("dimensions", {})
            if row.get("source_dimensions") != f"{dimensions.get('width')}x{dimensions.get('height')}":
                errors.append(f"recovery source dimensions differ from MIG-03 evidence: {path}")
            source_output = row.get("source_output", {})
            if not isinstance(source_output, dict):
                errors.append(f"invalid recovery source output: {path}")
                source_output = {}
            source_output_path = source_output.get("path", "")
            selected_source = next((item for item in asset.get("output_paths", [])
                                    if item.get("path") == source_output_path
                                    and item.get("sha256") == source_output.get("sha256")
                                    and item.get("bytes") == source_output.get("bytes")), None)
            if not selected_source:
                errors.append(f"recovery source output differs from selected MIG-03 asset: {path}")
            elif _verify_recovery_output(static_root, source_output_path, source_output["sha256"],
                                         source_output["bytes"], errors, path + " source"):
                signature = SIGNATURES[".jpg"][0]
                if (static_root / source_output_path).read_bytes()[:len(signature)] != signature:
                    errors.append(f"recovery source output is not a JPEG: {source_output_path}")
            generated: dict[str, dict] = {}
            for output in row.get("generated_outputs", []):
                output_path = output.get("output_path", "")
                valid = _verify_recovery_output(static_root, output_path, output.get("sha256"),
                                                output.get("bytes"), errors, path)
                dims = output.get("dimensions", "")
                try:
                    expected_dimensions = tuple(int(value) for value in dims.split("x"))
                except (AttributeError, ValueError):
                    expected_dimensions = ()
                target = static_root / output_path
                if len(expected_dimensions) != 2 or any(value < 1 for value in expected_dimensions):
                    errors.append(f"invalid recovery output dimensions: {output_path}")
                    valid = False
                elif valid:
                    signature = SIGNATURES[".jpg"][0]
                    if target.suffix.lower() not in (".jpg", ".jpeg") or target.read_bytes()[:len(signature)] != signature:
                        errors.append(f"recovery generated output is not a JPEG: {output_path}")
                        valid = False
                    elif jpeg_dimensions(target) != (expected_dimensions[0], expected_dimensions[1]):
                        errors.append(f"recovery generated output dimensions mismatch: {output_path}")
                        valid = False
                if output_path in generated or output_path in derived_by_path:
                    errors.append(f"duplicate recovery output path: {output_path}")
                    valid = False
                if valid:
                    output_record = {
                        "output_path": output_path, "sha256": output["sha256"],
                        "bytes": output["bytes"], "dimensions": dims,
                        "source_path": source_path, "source_sha256": source_sha256,
                    }
                    generated[output_path] = output_record
                    derived_by_path[output_path] = output_record
            if not generated or row.get("primary_output_path") not in generated:
                errors.append(f"derived recovery lacks its primary output: {path}")
            allowed_urls = {
                reference.get("url")
                for key in ("body_references", "metadata_references", "rendered_page_references",
                            "attachment_route_references", "social_metadata_references")
                for reference in missing.get(key, []) if reference.get("url")
            }
            mapped_urls = set()
            for mapping in row.get("url_mappings", []):
                source_url = mapping.get("source_url")
                output_path = mapping.get("output_path")
                if source_url not in allowed_urls or output_path not in generated:
                    errors.append(f"derived recovery URL mapping lacks exact source/output evidence: {path}")
                    continue
                mapped_urls.add(source_url)
            if mapped_urls != allowed_urls:
                errors.append(f"derived recovery does not map every exact missing-reference URL: {path}")
            if len(errors) == before:
                recovered.add(path)
                derived_outputs.extend(generated.values())
        else:
            errors.append(f"unsupported recovery kind: {kind}")
        if kind == "case-variant" and len(errors) == before:
            recovered.add(path)
    explicit_urls: set[str] = set()
    for mapping in evidence.get("explicit_url_mappings", []):
        source_url = mapping.get("source_url", "")
        source_path = mapping.get("source_path", "")
        source_sha256 = mapping.get("source_sha256", "")
        asset = assets_by_path.get(source_path)
        if (not asset or asset.get("source_sha256") != source_sha256
                or _upload_suffix(source_url) not in asset.get("referenced_url_paths", [])):
            errors.append(f"explicit external URL lacks selected source-path evidence: {source_url}")
            continue
        output_path = mapping.get("output_path", "")
        output = derived_by_path.get(output_path)
        if output is not None:
            if output.get("source_path") != source_path or output.get("source_sha256") != source_sha256:
                errors.append(f"explicit URL maps to a derivative of a different source: {source_url}")
                continue
            if (output.get("sha256") != mapping.get("output_sha256")
                    or output.get("bytes") != mapping.get("output_bytes")):
                errors.append(f"explicit URL output hash/size differs from derived evidence: {source_url}")
                continue
        else:
            output = next((item for item in asset.get("output_paths", [])
                           if item.get("path") == output_path
                           and item.get("sha256") == mapping.get("output_sha256")
                           and item.get("bytes") == mapping.get("output_bytes")), None)
            if not output:
                errors.append(f"explicit URL target is not a selected source output: {source_url}")
                continue
        if source_url in explicit_urls:
            errors.append(f"duplicate explicit external URL mapping: {source_url}")
            continue
        explicit_urls.add(source_url)
        _verify_recovery_output(static_root, output_path, mapping.get("output_sha256"),
                                mapping.get("output_bytes"), errors, source_url)
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
    return recovered, external, errors, derived_outputs

def check(manifest: dict, static_root: Path, recovery_evidence: dict | None = None) -> tuple[list[str], list[str], dict[str, int]]:
    errors: list[str] = []
    warnings: list[str] = []
    recovered, external, recovery_errors, derived_outputs = verify_recovery_evidence(manifest, static_root, recovery_evidence)
    errors.extend(recovery_errors)
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
    for output in derived_outputs:
        relative = output['output_path']
        if relative in expected:
            errors.append(f'derived recovery duplicates selected output path: {relative}')
            continue
        expected.add(relative)
        total_bytes += output['bytes']
        image_count += 1
        if output['bytes'] > 1_000_000:
            warnings.append(
                f"above per-image target; measured-size review required: {relative} ({output['bytes']} bytes)"
            )
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
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    evidence = (json.loads(args.recovery_evidence.read_text(encoding="utf-8"))
                if args.recovery_evidence.is_file() else None)
    errors, warnings, totals = check(manifest, args.static_root, evidence)
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    print(json.dumps({**totals, "errors": len(errors), "warnings": len(warnings)}, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
