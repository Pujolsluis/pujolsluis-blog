"""Keep duplicated public-output metadata derived from the selected asset records."""

from __future__ import annotations

from typing import Any

PROJECTION_SECTIONS = (
    "published_body_path_mappings",
    "rendered_page_path_mappings",
    "attachment_route_path_mappings",
)


def canonical_outputs(manifest: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Index selected asset outputs and identify conflicts within that source of truth."""
    outputs: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for asset in manifest.get("assets", []):
        if asset.get("disposition") != "required-content-candidate":
            continue
        for output in asset.get("output_paths", []):
            path = output.get("path", "")
            record = {
                "path": path,
                "sha256": output.get("sha256"),
                "bytes": output.get("bytes"),
                "content_type": asset.get("content_type"),
                "extension": asset.get("extension"),
            }
            prior = outputs.get(path)
            if prior and prior != record:
                errors.append(f"conflicting selected-asset output records: {path}")
            else:
                outputs[path] = record
    return outputs, errors


def projection_conflicts(manifest: dict[str, Any]) -> list[str]:
    """Check every mapping projection against the selected asset output records."""
    canonical, errors = canonical_outputs(manifest)
    for section in PROJECTION_SECTIONS:
        for mapping in manifest.get(section, []):
            for source in mapping.get("source_assets", []):
                output = source.get("output")
                if not output:
                    continue
                path = output.get("path", "")
                expected = canonical.get(path)
                where = f"{section}:{mapping.get('public_url_path')}: {path}"
                if expected is None:
                    errors.append(f"projection references an unselected output: {where}")
                    continue
                public_path = mapping.get("public_url_path", "")
                expected_public_path = path.removeprefix("wp-content/uploads/")
                if public_path != expected_public_path:
                    errors.append(f"manifest projection conflict (public path): {where}")
                for field in ("sha256", "bytes"):
                    if output.get(field) != expected[field]:
                        errors.append(f"manifest projection conflict ({field}): {where}")
                extension = path.rsplit(".", 1)[-1].lower()
                if expected["extension"] and extension != expected["extension"].lstrip(".").lower():
                    errors.append(f"manifest projection conflict (extension): {where}")
                for projected_type in (output.get("content_type"), source.get("content_type"), mapping.get("content_type")):
                    if projected_type and projected_type != expected["content_type"]:
                        errors.append(f"manifest projection conflict (content_type): {where}")
    return errors


def sync_output_projections(manifest: dict[str, Any]) -> int:
    """Refresh all mapping projections from canonical selected-asset output records."""
    canonical, errors = canonical_outputs(manifest)
    if errors:
        raise ValueError("; ".join(errors))
    updated = 0
    for section in PROJECTION_SECTIONS:
        for mapping in manifest.get(section, []):
            mapping_types = set()
            for source in mapping.get("source_assets", []):
                output = source.get("output")
                if not output:
                    continue
                expected = canonical.get(output.get("path", ""))
                if expected is None:
                    raise ValueError(f"projection references an unselected output: {section}:{mapping.get('public_url_path')}")
                normalized = {key: expected[key] for key in ("path", "sha256", "bytes")}
                mapping_types.add(expected["content_type"])
                if output != normalized:
                    source["output"] = normalized
                    updated += 1
                if source.get("content_type") and source["content_type"] != expected["content_type"]:
                    source["content_type"] = expected["content_type"]
                    updated += 1
            if mapping.get("content_type") and len(mapping_types) == 1:
                canonical_type = next(iter(mapping_types))
                if mapping["content_type"] != canonical_type:
                    mapping["content_type"] = canonical_type
                    updated += 1
    return updated
