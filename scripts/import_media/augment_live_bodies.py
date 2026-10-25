#!/usr/bin/env python3
"""Select owned upload images referenced by hash-bound rendered post bodies."""

from __future__ import annotations

import argparse
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from typing import Any


class BodyImageParser(HTMLParser):
    """Collect upload paths referenced by image sources in rendered post HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        for name in ("src", "srcset", "data-orig-file", "data-large-file", "data-src", "data-lazy-src"):
            value = attributes.get(name)
            if not value:
                continue
            candidates = value.split(",") if name == "srcset" else [value]
            for candidate in candidates:
                url = candidate.strip().split()[0]
                path = unquote(urlsplit(url).path)
                marker = "/wp-content/uploads/"
                if marker in path:
                    self.references.append(path.split(marker, 1)[1])


def extract_upload_url_paths(html: str) -> list[str]:
    parser = BodyImageParser()
    parser.feed(html)
    return sorted(set(parser.references))


def augment(manifest: dict[str, Any], body_manifest: dict[str, Any], uploads_root: Path, routes: dict[str, str]) -> int:
    assets = manifest["assets"]
    by_source = {asset["source_path"]: asset for asset in assets}
    by_public_path = {
        url_path: asset
        for asset in assets
        for url_path in asset.get("referenced_url_paths", [])
    }
    missing_paths = {item["url_path"] for item in manifest.get("missing_references", [])}
    grouped_references: dict[str, list[dict[str, str]]] = {}
    evidence_records = []

    for item_id, route in sorted(routes.items()):
        item = body_manifest["items"][item_id]
        html = item["html"]
        html_hash = hashlib.sha256(html.encode()).hexdigest()
        if html_hash != item.get("htmlSha256"):
            raise ValueError(f"rendered body hash mismatch: {item_id}")
        item_paths = extract_upload_url_paths(html)
        references = []
        for path in item_paths:
            reference = {
                "post_id": item_id.removeprefix("wp:"),
                "route": route,
                "body_html_sha256": html_hash,
                "source_reference": item["reference"],
                "url_path": path,
            }
            references.append(reference)
            grouped_references.setdefault(path, []).append(reference)

        evidence_records.append({
            "post_id": item_id.removeprefix("wp:"),
            "route": route,
            "body_html_sha256": html_hash,
            "original_content_sha256": item["originalSha256"],
            "source_reference": item["reference"],
            "selector": ".entry-content",
            "owned_upload_url_paths": item_paths,
        })

    promoted = 0
    for path, references in grouped_references.items():
        asset = by_public_path.get(path) or by_source.get(path)
        if asset and asset.get("disposition") == "required-content-candidate":
            pass
        elif path in missing_paths:
            continue
        else:
            source_path = asset["source_path"] if asset else path
            source = uploads_root / source_path
            if not asset or not source.is_file():
                raise ValueError(f"owned rendered-body upload has no source asset or explicit blocker: {path}")
            if asset.get("disposition") not in {"excluded-unreferenced-upload", "excluded-unused-generated-size"}:
                raise ValueError(f"rendered-body upload is excluded for a different reason: {path}: {asset.get('disposition')}")
            asset.update({
                "disposition": "required-content-candidate",
                "reason": "Referenced by a hash-bound live rendered post body; exact owner upload exists in the backup.",
                "compatibility_disposition": "Preserve the exact URL path and extension under static/wp-content/uploads/.",
                "referenced_url_paths": sorted(set(asset.get("referenced_url_paths", [])) | {path}),
            })
            promoted += 1
        asset["live_rendered_body_url_paths"] = sorted(set(asset.get("live_rendered_body_url_paths", [])) | {path})
        prior_refs = asset.get("live_rendered_body_references", [])
        seen = {(ref.get("post_id"), ref.get("url_path"), ref.get("body_html_sha256")) for ref in prior_refs}
        asset["live_rendered_body_references"] = prior_refs + [
            ref for ref in references
            if (ref["post_id"], ref["url_path"], ref["body_html_sha256"]) not in seen
        ]

    manifest["live_rendered_body_evidence"] = {
        "schema_version": 1,
        "source_reference": body_manifest["sourceReference"],
        "records": evidence_records,
    }
    return promoted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--bodies-json", required=True, type=Path)
    parser.add_argument("--uploads", required=True, type=Path)
    parser.add_argument("--routes-json", required=True, type=Path, help="JSON object mapping wp:post IDs to their public route paths")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    body_manifest = json.loads(args.bodies_json.read_text())
    routes = json.loads(args.routes_json.read_text())
    promoted = augment(manifest, body_manifest, args.uploads, routes)
    args.manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    paths = sorted({path for item in manifest["live_rendered_body_evidence"]["records"] for path in item["owned_upload_url_paths"]})
    print(json.dumps({"promoted_source_files": promoted, "live_body_upload_paths": len(paths), "routes": len(routes)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
