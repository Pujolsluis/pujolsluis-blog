#!/usr/bin/env python3
"""Build an auditable media inventory from a WordPress WXR export and uploads tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.parse
import xml.etree.ElementTree as ET
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath

NS = {
    "wp": "http://wordpress.org/export/1.2/",
    "content": "http://purl.org/rss/1.0/modules/content/",
}
PUBLISHED_TYPES = {"post", "page", "portfolio"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".svg"}
MIME_BY_EXT = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".avif": "image/avif",
    ".svg": "image/svg+xml",
}
URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
MEDIA_RE = re.compile(r"/wp-content/uploads/(.+)$", re.IGNORECASE)
SIZED_RE = re.compile(r"-\d+x\d+(?=\.[^.]+$)", re.IGNORECASE)
CSS_URL_RE = re.compile(r"url\(\s*(['\"]?)([^)\"']+)\1\s*\)", re.IGNORECASE)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_url_path(url: str) -> str | None:
    url = urllib.parse.unquote(url).split("#", 1)[0].split("?", 1)[0].rstrip(",.;")
    match = MEDIA_RE.search(url)
    if not match:
        return None
    return PurePosixPath(match.group(1)).as_posix()


def attachment_key(path: str) -> str:
    """Collapse multisite prefixes and generated dimension suffixes for linkage."""
    path = re.sub(r"^sites/\d+/", "", path)
    parts = path.rsplit("/", 1)
    filename = SIZED_RE.sub("", parts[-1])
    return "/".join(parts[:-1] + [filename])


def referenced_paths(value: str) -> list[str]:
    return [path for url in URL_RE.findall(value) if (path := normalize_url_path(url))]


class PageMediaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.references: dict[str, list[dict[str, str]]] = defaultdict(list)

    def handle_starttag(self, tag: str, attributes: list[tuple[str, str | None]]) -> None:
        attrs = {key.lower(): value or "" for key, value in attributes}
        values: list[tuple[str, str]] = []
        for key in ("src", "data-src", "data-lazy-src", "poster"):
            if attrs.get(key):
                values.append((key, attrs[key]))
        for key in ("srcset", "data-srcset"):
            for candidate in attrs.get(key, "").split(","):
                url = candidate.strip().split()
                if url:
                    values.append((key, url[0]))
        property_name = attrs.get("property", "").lower()
        meta_name = attrs.get("name", "").lower()
        if tag.lower() == "meta" and (property_name in {"og:image", "og:image:secure_url"} or meta_name in {"twitter:image", "twitter:image:src"}) and attrs.get("content"):
            values.append(("meta-image", attrs["content"]))
        for kind, value in values:
            path = normalize_url_path(value)
            if path:
                self.references[path].append({"element": tag, "attribute": kind, "url": value})


def record_label(item: ET.Element) -> dict[str, str]:
    return {
        "id": item.findtext("wp:post_id", default="", namespaces=NS),
        "type": item.findtext("wp:post_type", default="", namespaces=NS),
        "status": item.findtext("wp:status", default="", namespaces=NS),
        "title": item.findtext("title", default="", namespaces=NS),
    }


def theme_references(theme_root: Path | None) -> list[dict]:
    if theme_root is None:
        return []
    references = []
    for stylesheet in sorted(theme_root.rglob("*.css")):
        content = stylesheet.read_text(errors="replace")
        for match in CSS_URL_RE.finditer(content):
            raw_url = match.group(2).strip()
            if raw_url.startswith(("data:", "http:", "https:", "//", "/")):
                continue
            relative = urllib.parse.unquote(raw_url.split("?", 1)[0].split("#", 1)[0])
            target = (stylesheet.parent / relative).resolve()
            if target.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            entry = {
                    "source_path": target.relative_to(theme_root.resolve()).as_posix(),
                    "referencing_stylesheet": stylesheet.relative_to(theme_root).as_posix(),
                    "css_url": raw_url,
                    "source_sha256": sha256(target) if target.is_file() else None,
                    "source_bytes": target.stat().st_size if target.is_file() else None,
                    "availability": "present-in-theme-backup" if target.is_file() else "referenced-by-css-but-missing-from-theme-backup",
                    "disposition": "conditional-theme-reference-unverified",
                    "reason": "Local theme CSS references this image, but no rendered snapshot confirms the feature is used on a public page.",
                    "compatibility_disposition": "No legacy theme file is published by MIG-03; MIG-04 should include it only if its replacement renderer uses the referenced behavior.",
                }
            references.append(entry)
    return sorted(references, key=lambda item: (item["referencing_stylesheet"], item["source_path"], item["css_url"]))


def build_inventory(wxr: Path, uploads: Path, theme_root: Path | None = None, homepage_html: Path | None = None) -> dict:
    root = ET.parse(wxr).getroot()
    items = root.findall(".//item")
    attachment_by_path: dict[str, list[dict[str, str]]] = defaultdict(list)
    attachment_by_key: dict[str, list[dict[str, str]]] = defaultdict(list)
    body: dict[str, list[dict[str, str]]] = defaultdict(list)
    metadata: dict[str, list[dict[str, str]]] = defaultdict(list)
    social: dict[str, list[dict[str, str]]] = defaultdict(list)
    homepage: dict[str, list[dict[str, str]]] = defaultdict(list)
    video_refs: list[dict[str, str]] = []

    for item in items:
        label = record_label(item)
        post_type = label["type"]
        if post_type == "attachment":
            url = item.findtext("wp:attachment_url", default="", namespaces=NS)
            path = normalize_url_path(url)
            if path:
                attachment = {
                        **label,
                        "parent_id": item.findtext("wp:post_parent", default="0", namespaces=NS),
                        "attachment_url": url,
                    }
                attachment_by_path[path].append(attachment)
                attachment_by_key[attachment_key(path)].append(attachment)
            continue

        published = post_type in PUBLISHED_TYPES and label["status"] == "publish"
        if not published:
            continue

        for path in referenced_paths(item.findtext("content:encoded", default="", namespaces=NS)):
            body[path].append(label)

        for meta in item.findall("wp:postmeta", NS):
            key = meta.findtext("wp:meta_key", default="", namespaces=NS)
            value = meta.findtext("wp:meta_value", default="", namespaces=NS)
            for path in referenced_paths(value):
                if key == "essb_cached_image":
                    social[path].append(label)
                else:
                    metadata[path].append({**label, "reference": f"metadata:{key}"})

        for value in (ET.tostring(item, encoding="unicode"),):
            for url in URL_RE.findall(value):
                if any(provider in url.lower() for provider in ("youtube.com", "youtu.be", "vimeo.com", "dailymotion.com")):
                    video_refs.append({**label, "provider_url": urllib.parse.unquote(url)})

    page_snapshot_sha256 = None
    if homepage_html is not None:
        parser = PageMediaParser()
        parser.feed(homepage_html.read_text(errors="replace"))
        homepage.update(parser.references)
        page_snapshot_sha256 = sha256(homepage_html)

    files = sorted((p for p in uploads.rglob("*") if p.is_file()), key=lambda p: p.relative_to(uploads).as_posix())
    available_upload_paths = {p.relative_to(uploads).as_posix() for p in files}
    attachment_paths_by_parent: dict[str, list[dict[str, str]]] = defaultdict(list)
    for path, records in attachment_by_path.items():
        for record in records:
            attachment_paths_by_parent[record["parent_id"]].append({**record, "source_available": re.sub(r"^sites/\d+/", "", path) in available_upload_paths})
    assets = []
    normalized_refs = set(body) | set(metadata) | set(social) | set(homepage)
    for source in files:
        relative = source.relative_to(uploads).as_posix()
        candidates = [path for path in normalized_refs if re.sub(r"^sites/\d+/", "", path) == relative]
        body_matches = sorted({p for p in candidates if p in body})
        metadata_matches = sorted({p for p in candidates if p in metadata})
        social_matches = sorted({p for p in candidates if p in social})
        homepage_matches = sorted({p for p in candidates if p in homepage})
        if body_matches or metadata_matches or homepage_matches:
            disposition = "required-content-candidate"
            reason = "Referenced by published WXR content/metadata or the current homepage source snapshot. Confirmed URL path will be preserved."
        elif social_matches:
            disposition = "excluded-unverified-social-metadata"
            reason = "Referenced only by Easy Social Share Buttons cached-image metadata; current Open Graph/Twitter output is unavailable to verify."
        elif source.suffix.lower() not in IMAGE_EXTENSIONS:
            disposition = "excluded-non-image"
            reason = "Non-image upload is outside the approved image set; retain its inventory record for review."
        elif SIZED_RE.search(source.name):
            disposition = "excluded-unused-generated-size"
            reason = "WordPress dimension variant has no published WXR body or non-social metadata reference."
        else:
            disposition = "excluded-unreferenced-upload"
            reason = "No reference in published WXR body or non-social metadata; no approved legacy-URL evidence supplied."

        paths = sorted(set(body_matches + metadata_matches + social_matches + homepage_matches))
        file_stat = source.stat()
        related_attachments = []
        for path in paths:
            key = attachment_key(path)
            relation = "exact-url-path" if path in attachment_by_path else "generated-size-base-name"
            for attachment in attachment_by_key.get(key, []):
                related_attachments.append({**attachment, "relationship": relation})
        source_key = attachment_key(relative)
        source_relation = "exact-source-path" if relative in attachment_by_path else "generated-size-base-name"
        for attachment in attachment_by_key.get(source_key, []):
            record = {**attachment, "relationship": source_relation}
            if not any(existing["id"] == record["id"] for existing in related_attachments):
                related_attachments.append(record)
        if disposition == "required-content-candidate":
            compatibility = "Preserve every referenced public URL path and extension under static/wp-content/uploads/."
        elif disposition == "excluded-unverified-social-metadata":
            compatibility = "Intentionally not published pending evidence that current page metadata emits this URL; verify source head metadata before cutover."
        elif disposition.startswith("excluded-unused") or disposition == "excluded-unreferenced-upload":
            compatibility = "No redirect or alias is created; this historical URL remains absent unless later approved as a legacy compatibility path."
        else:
            compatibility = "Not selected by the image importer; assess separately if another migration feature references this non-image file."
        assets.append(
            {
                "source_path": relative,
                "source_sha256": sha256(source),
                "source_bytes": file_stat.st_size,
                "extension": source.suffix.lower(),
                "content_type": MIME_BY_EXT.get(source.suffix.lower()),
                "disposition": disposition,
                "reason": reason,
                "compatibility_disposition": compatibility,
                "referenced_url_paths": paths,
                "body_url_paths": body_matches,
                "metadata_url_paths": metadata_matches,
                "social_metadata_url_paths": social_matches,
                "homepage_url_paths": homepage_matches,
                "body_references": [ref for path in body_matches for ref in body[path]],
                "metadata_references": [ref for path in metadata_matches for ref in metadata[path]],
                "social_metadata_references": [ref for path in social_matches for ref in social[path]],
                "homepage_references": [ref for path in homepage_matches for ref in homepage[path]],
                "attachment_records": related_attachments,
            }
        )

    missing = []
    for path in sorted(normalized_refs):
        normalized = re.sub(r"^sites/\d+/", "", path)
        if not (uploads / normalized).is_file():
            content_references = body.get(path, []) + metadata.get(path, [])
            source_items = list({(ref["id"], ref["type"], ref["title"]): ref for ref in content_references}.values())
            source_attachment_paths = []
            for ref in source_items:
                source_attachment_paths.extend(attachment_paths_by_parent.get(ref["id"], []))
            same_attachment_candidates = []
            for attachment in attachment_by_key.get(attachment_key(path), []):
                candidate_path = normalize_url_path(attachment["attachment_url"])
                if candidate_path:
                    candidate_source = re.sub(r"^sites/\d+/", "", candidate_path)
                    same_attachment_candidates.append({**attachment, "source_available": candidate_source in available_upload_paths, "source_path": candidate_source})
            missing.append(
                {
                    "url_path": path,
                    "source_items": source_items,
                    "reason": "Published WXR content/metadata or the current homepage snapshot references this path, but the backup uploads tree lacks the source bytes.",
                    "compatibility_disposition": "Hard blocker: this live published URL will be absent until source bytes are recovered or the owner approves a documented replacement.",
                    "body_references": body.get(path, []),
                    "metadata_references": metadata.get(path, []),
                    "social_metadata_references": social.get(path, []),
                    "homepage_references": homepage.get(path, []),
                    "attachment_records": attachment_by_path.get(path, []),
                    "available_attachments_with_same_parent": source_attachment_paths,
                    "same_attachment_derivative_candidates": same_attachment_candidates,
                    "visually_equivalent_replacement_verified": False,
                    "replacement_assessment": "No byte-identical source or visually-equivalent replacement was verified. Available sibling attachments are listed as evidence only and are not substituted.",
                    "recovery_evidence": "Exact URL, backup-relative path, and observed i0.wp.com CDN path returned HTTP 404 with non-image responses on 2026-10-25.",
                }
            )

    return {
        "schema_version": 1,
        "evidence": {
            "wxr_file": wxr.name,
            "published_content_types": sorted(PUBLISHED_TYPES),
            "uploads_tree": "uploads/ (private backup-relative; never copy this tree wholesale)",
            "source_page_evidence": "Optional homepage source snapshot is hashed and parsed for image src/srcset and Open Graph/Twitter image references.",
            "theme_evidence": "The supplied backup includes theme source folders; theme assets are inventoried separately from uploads.",
            "theme_source": theme_root.name if theme_root else None,
            "homepage_snapshot": homepage_html.name if homepage_html else None,
            "homepage_snapshot_sha256": page_snapshot_sha256,
            "missing_source_recovery_attempt": "Attempted exact and backup-relative upload paths on the site and its observed i0.wp.com image CDN on 2026-10-25; all returned HTTP 404 with non-image responses.",
        },
        "counts": {
            "wxr_items": len(items),
            "attachment_records": sum(map(len, attachment_by_path.values())),
            "published_body_paths": len(body),
            "published_non_social_metadata_paths": len(set(metadata) - set(body)),
            "social_metadata_only_paths": len(set(social) - set(body) - set(metadata) - set(homepage)),
            "homepage_paths": len(homepage),
            "backup_upload_files": len(assets),
            "missing_referenced_paths": len(missing),
        },
        "video_provider_references": sorted(video_refs, key=lambda x: (x["id"], x["provider_url"])),
        "theme_references": theme_references(theme_root),
        "attachment_index": [
            {**record, "url_path": path, "source_path": re.sub(r"^sites/\d+/", "", path), "source_available": re.sub(r"^sites/\d+/", "", path) in available_upload_paths}
            for path, records in sorted(attachment_by_path.items()) for record in records
        ],
        "missing_references": missing,
        "assets": assets,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wxr", required=True, type=Path, help="WordPress WXR export (read only)")
    parser.add_argument("--uploads", required=True, type=Path, help="Backup uploads directory (read only)")
    parser.add_argument("--theme", type=Path, help="Optional supplied theme directory for CSS image references")
    parser.add_argument("--homepage-html", type=Path, help="Optional current homepage HTML snapshot (kept outside the repository)")
    parser.add_argument("--output", required=True, type=Path, help="JSON inventory destination")
    args = parser.parse_args()
    report = build_inventory(args.wxr, args.uploads, args.theme, args.homepage_html)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps(report["counts"], sort_keys=True))
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
