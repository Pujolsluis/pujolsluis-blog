#!/usr/bin/env python3
"""Add image URLs observed in private rendered page snapshots to the inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

try:
    from .inventory import PageMediaParser
except ImportError:
    from inventory import PageMediaParser


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_path(url_path: str) -> str:
    return re.sub(r"^sites/\d+/", "", url_path)


def augment(manifest: dict, snapshot_dirs: list[Path], attachment_audit: Path | None = None) -> None:
    assets_by_source = {asset["source_path"]: asset for asset in manifest["assets"]}
    evidence_records = []
    missing = {item["url_path"]: item for item in manifest["missing_references"]}
    rendered_paths: set[str] = set()
    attachment_paths: set[str] = set()
    for snapshot_dir in snapshot_dirs:
        map_path = snapshot_dir / "manifest.json"
        page_manifest = json.loads(map_path.read_text())
        records = page_manifest.get("records", [])
        if not records:
            raise ValueError(f"no snapshot records in {map_path}")
        for record in records:
            if str(record.get("status")) != "200":
                continue
            snapshot = snapshot_dir / record["file"]
            parser = PageMediaParser()
            parser.feed(snapshot.read_text(errors="replace"))
            evidence_records.append({"url": record["url"], "file": record["file"], "sha256": record.get("sha256") or sha256(snapshot)})
            for url_path, refs in parser.references.items():
                rendered_paths.add(url_path)
                details = [{"url_path": url_path, "page_url": record["url"], "snapshot": record["file"], "element": ref["element"], "attribute": ref["attribute"], "url": ref["url"]} for ref in refs]
                asset = assets_by_source.get(source_path(url_path))
                if asset is not None:
                    asset["referenced_url_paths"] = sorted(set(asset["referenced_url_paths"]) | {url_path})
                    current = asset.setdefault("rendered_page_references", [])
                    current.extend(detail for detail in details if detail not in current)
                    if asset["disposition"] != "required-content-candidate":
                        asset["disposition"] = "required-content-candidate"
                        asset["reason"] = "Observed in published WXR or live rendered page output, including active image cards/share metadata."
                        asset["compatibility_disposition"] = "Preserve every observed public URL path and extension under static/wp-content/uploads/."
                elif url_path in missing:
                    current = missing[url_path].setdefault("rendered_page_references", [])
                    current.extend(detail for detail in details if detail not in current)
                    missing[url_path]["reason"] = "Live rendered page references this public path; no matching source file exists in the backup uploads tree."
                else:
                    missing[url_path] = {
                        "url_path": url_path,
                        "reason": "Live rendered page references this public path; no matching source file exists in the backup uploads tree.",
                        "compatibility_disposition": "Hard blocker: preserve this live URL until bytes are recovered or the owner approves a documented replacement.",
                        "rendered_page_references": details,
                        "body_references": [], "metadata_references": [], "social_metadata_references": [],
                        "homepage_references": [], "attachment_records": [],
                    }
    attachment_records = []
    if attachment_audit is not None:
        audit = json.loads(attachment_audit.read_text())
        for record in audit.get("items", []):
            if record.get("status") != 200 or record.get("contentType", "").split(";", 1)[0] != "text/html":
                continue
            snapshot = attachment_audit.parent / "pujolsluis-source-attachments-20261025" / f"{record['bodySha256']}.html"
            if not snapshot.is_file():
                raise FileNotFoundError(f"attachment page snapshot missing: {snapshot}")
            parser = PageMediaParser()
            parser.feed(snapshot.read_text(errors="replace"))
            attachment_records.append({"url": record["url"], "snapshot_sha256": record["bodySha256"], "status": record["status"], "kind": record.get("kind")})
            for url_path, refs in parser.references.items():
                attachment_paths.add(url_path)
                details = [{"url_path": url_path, "page_url": record["url"], "snapshot_sha256": record["bodySha256"], "element": ref["element"], "attribute": ref["attribute"], "url": ref["url"]} for ref in refs]
                asset = assets_by_source.get(source_path(url_path))
                if asset is not None:
                    asset["referenced_url_paths"] = sorted(set(asset["referenced_url_paths"]) | {url_path})
                    current = asset.setdefault("attachment_route_references", [])
                    current.extend(detail for detail in details if detail not in current)
                    if asset["disposition"] != "required-content-candidate":
                        asset["disposition"] = "required-content-candidate"
                        asset["reason"] = "Observed in published WXR or live rendered page output, including active image cards/share metadata and attachment HTML routes."
                        asset["compatibility_disposition"] = "Preserve every observed public URL path and extension under static/wp-content/uploads/."
                elif url_path in missing:
                    current = missing[url_path].setdefault("attachment_route_references", [])
                    current.extend(detail for detail in details if detail not in current)
                else:
                    missing[url_path] = {
                        "url_path": url_path,
                        "reason": "Live attachment HTML page references this public path; no matching source file exists in the backup uploads tree.",
                        "compatibility_disposition": "Hard blocker: preserve this live URL until bytes are recovered or the owner approves a documented replacement.",
                        "attachment_route_references": details,
                        "body_references": [], "metadata_references": [], "social_metadata_references": [], "homepage_references": [], "attachment_records": [],
                    }
    manifest["missing_references"] = sorted(missing.values(), key=lambda item: item["url_path"])
    manifest["evidence"]["rendered_page_snapshots"] = evidence_records
    manifest["evidence"]["rendered_snapshot_roots"] = [directory.name for directory in snapshot_dirs]
    manifest["evidence"]["rendered_pages_evidence"] = "Image src/srcset/lazy attributes and actual OG/Twitter meta images parsed from private HTML snapshots of pages and portfolio routes; snapshots remain outside Git."
    manifest["counts"]["rendered_page_paths"] = len(rendered_paths)
    manifest["evidence"]["attachment_route_audit"] = attachment_records
    manifest["evidence"]["attachment_route_audit_source"] = attachment_audit.name if attachment_audit else None
    manifest["evidence"]["attachment_route_evidence"] = "For each 200 text/html attachment route, page source was parsed for image src/srcset/lazy attributes and actual Open Graph/Twitter meta images; raw HTML remains outside Git."
    manifest["counts"]["attachment_route_paths"] = len(attachment_paths)
    manifest["counts"]["missing_referenced_paths"] = len(manifest["missing_references"])
    manifest["counts"]["required_asset_files"] = sum(a["disposition"] == "required-content-candidate" for a in manifest["assets"])
    manifest["counts"]["required_public_paths"] = len({p for a in manifest["assets"] if a["disposition"] == "required-content-candidate" for p in a["referenced_url_paths"]})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--snapshots", type=Path, nargs="+", required=True)
    parser.add_argument("--attachment-audit", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    augment(manifest, args.snapshots, args.attachment_audit)
    args.manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({key: manifest["counts"][key] for key in ("rendered_page_paths", "attachment_route_paths", "required_asset_files", "required_public_paths", "missing_referenced_paths")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
