"""Keep duplicated public-output metadata derived from the selected asset records."""

from __future__ import annotations

from typing import Any

PROJECTION_SECTIONS = (
    "published_body_path_mappings",
    "rendered_page_path_mappings",
    "attachment_route_path_mappings",
    "live_rendered_body_path_mappings",
)


def sync_live_body_mappings(manifest: dict[str, Any]) -> int:
    """Build live rendered-body path mappings from hash-bound body evidence."""
    canonical, errors = canonical_outputs(manifest)
    if errors:
        raise ValueError("; ".join(errors))
    assets_by_url = {
        path: asset
        for asset in manifest.get("assets", [])
        for path in asset.get("referenced_url_paths", [])
        if asset.get("disposition") == "required-content-candidate"
    }
    refs_by_path: dict[str, list[dict[str, Any]]] = {}
    for record in manifest.get("live_rendered_body_evidence", {}).get("records", []):
        for path in record.get("owned_upload_url_paths", []):
            refs_by_path.setdefault(path, []).append({
                "post_id": record["post_id"],
                "route": record["route"],
                "body_html_sha256": record["body_html_sha256"],
                "source_reference": record["source_reference"],
                "selector": record["selector"],
            })
    blockers = {item["url_path"] for item in manifest.get("missing_references", [])}
    mappings = []
    for path, references in sorted(refs_by_path.items()):
        asset = assets_by_url.get(path)
        if asset is None:
            if path not in blockers:
                raise ValueError(f"live rendered-body path is neither selected nor blocked: {path}")
            mappings.append({"public_url_path": path, "status": "blocked", "source_assets": [], "source_references": references})
            continue
        output_path = "wp-content/uploads/" + path
        output = canonical.get(output_path)
        if output is None:
            raise ValueError(f"live rendered-body path has no exact selected output: {path}")
        mappings.append({
            "public_url_path": path,
            "status": "included",
            "content_type": output["content_type"],
            "source_assets": [{
                "source_path": asset["source_path"],
                "source_sha256": asset["source_sha256"],
                "content_type": asset["content_type"],
                "output": {key: output[key] for key in ("path", "sha256", "bytes")},
            }],
            "source_references": references,
        })
    manifest["live_rendered_body_path_mappings"] = mappings
    return len(mappings)


def live_body_coverage_errors(manifest: dict[str, Any]) -> list[str]:
    """Fail closed if any owned upload in hash-bound live HTML lacks selection/blocking."""
    selected = {
        path
        for asset in manifest.get("assets", [])
        if asset.get("disposition") == "required-content-candidate"
        for path in asset.get("referenced_url_paths", [])
    }
    blocked = {item.get("url_path") for item in manifest.get("missing_references", [])}
    errors = []
    for record in manifest.get("live_rendered_body_evidence", {}).get("records", []):
        for path in record.get("owned_upload_url_paths", []):
            if path not in selected and path not in blocked:
                errors.append(f"unselected owned live-body upload: wp:{record.get('post_id')}:{path}")
    return errors


def refresh_inventory_totals(manifest: dict[str, Any]) -> None:
    """Recompute selected/excluded byte and path totals after live-body promotion."""
    assets = manifest.get("assets", [])
    selected = [asset for asset in assets if asset.get("disposition") == "required-content-candidate"]
    selected_outputs = [output for asset in selected for output in asset.get("output_paths", [])]
    excluded: dict[str, dict[str, int]] = {}
    for asset in assets:
        disposition = asset.get("disposition", "unknown")
        if disposition.startswith("excluded-"):
            aggregate = excluded.setdefault(disposition, {"files": 0, "source_bytes": 0})
            aggregate["files"] += 1
            aggregate["source_bytes"] += int(asset.get("source_bytes", 0))
    totals = manifest.setdefault("totals", {})
    totals.update({
        "included_source_files": len(selected),
        "included_exact_public_paths": len(selected_outputs),
        "included_source_bytes": sum(int(asset.get("source_bytes", 0)) for asset in selected),
        "included_source_bytes_counted_per_public_path": sum(int(asset.get("source_bytes", 0)) * len(asset.get("output_paths", [])) for asset in selected),
        "optimized_output_paths": len(selected_outputs),
        "optimized_output_bytes": sum(int(output.get("bytes", 0)) for output in selected_outputs),
        "max_output_path_bytes": max((int(output.get("bytes", 0)) for output in selected_outputs), default=0),
        "output_paths_above_1mb": sum(int(output.get("bytes", 0)) > 1_000_000 for output in selected_outputs),
        "lossless_bytes_saved_per_public_path": sum(int(asset.get("source_bytes", 0)) * len(asset.get("output_paths", [])) for asset in selected) - sum(int(output.get("bytes", 0)) for output in selected_outputs),
        "excluded_by_disposition": excluded,
    })
    manifest.setdefault("counts", {}).update({
        "required_asset_files": len(selected),
        "required_public_paths": len(selected_outputs),
        "live_rendered_body_paths": len(manifest.get("live_rendered_body_path_mappings", [])),
        "live_rendered_body_records": len(manifest.get("live_rendered_body_evidence", {}).get("records", [])),
    })
    selected_by_path = {
        path: asset
        for asset in selected
        for path in asset.get("referenced_url_paths", [])
    }
    live_paths = [row["public_url_path"] for row in manifest.get("live_rendered_body_path_mappings", []) if row.get("status") == "included"]
    live_assets = {selected_by_path[path]["source_path"]: selected_by_path[path] for path in live_paths if path in selected_by_path}
    live_outputs = [
        output
        for path in live_paths
        for asset in [selected_by_path[path]]
        if path in selected_by_path
        for output in asset.get("output_paths", [])
        if output.get("path") == "wp-content/uploads/" + path
    ]
    role_totals = manifest.setdefault("role_totals", [])
    live_role = {
        "role": "hash_bound_live_rendered_bodies",
        "referenced_paths": len(manifest.get("live_rendered_body_path_mappings", [])),
        "included_paths": len(live_paths),
        "blocked_paths": len(manifest.get("live_rendered_body_path_mappings", [])) - len(live_paths),
        "source_files": len(live_assets),
        "source_bytes": sum(int(asset.get("source_bytes", 0)) for asset in live_assets.values()),
        "mapped_output_bytes": sum(int(output.get("bytes", 0)) for output in live_outputs),
    }
    prior_role = next((row for row in role_totals if row.get("role") == live_role["role"]), None)
    if prior_role is None:
        role_totals.append(live_role)
    else:
        prior_role.update(live_role)


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
