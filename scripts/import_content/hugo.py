"""Write reviewed v1 content as deterministic Hugo HTML content files.

This is a publication adapter, not a WXR reader. The caller must first review
the normalized public bundle and the private WXR reconciliation report.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from docs.contracts.validate import validate_document
from .attachments import validate_attachment_manifest
from .head import FIELDS, validate_head_manifest
from .media import rewrite_html, rewrite_url, upload_path, validate_media_map


class HugoExportError(ValueError):
    """The public bundle cannot be safely represented as Hugo content."""


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _instant(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (AttributeError, ValueError) as error:
        raise HugoExportError('build time must be an ISO 8601 timestamp with an offset') from error
    if result.tzinfo is None or result.utcoffset() is None:
        raise HugoExportError('build time must have an explicit offset')
    return result


def _front_matter(item, source_head=None, mapping=None, base='/', unresolved=None):
    metadata = item['sourceMetadata']
    front = {
        'title': item['title'],
        'date': item['publishedAt'],
        'lastmod': item['modifiedAt'],
        'url': item['path'],
        'type': item['kind'],
        'draft': False,
        'categories': [term['name'] for term in item['categories']],
        'tags': [term['name'] for term in item['tags']],
        'migration': {
            'sourceId': item['sourceId'],
            'sourceType': metadata.get('sourceType', item['kind']),
            'canonicalUrl': item['canonicalUrl'],
            'language': item['language'],
            'author': item['author'],
            'categories': item['categories'],
            'tags': item['tags'],
            'guid': metadata['guid'],
            'excerptHtml': metadata['excerptHtml'],
            'commentStatus': metadata['commentStatus'],
            'pingStatus': metadata['pingStatus'],
            'featuredAssetId': metadata['featuredAssetId'],
            'assetIds': item['assetIds'],
            'embeds': item['embeds'],
            'comments': item['comments'],
            'provenance': item['content']['provenance'],
        },
    }
    if source_head is not None:
        fields = dict(source_head['fields'])
        for key in ('ogImage', 'twitterImage'):
            if fields[key]:
                fields[key] = rewrite_url(fields[key], mapping or {}, base, unresolved)
        front['seoTitle'] = fields['title']
        front['description'] = fields['description']
        front['canonical'] = fields['canonical']
        for key in FIELDS:
            if key not in ('title', 'description', 'canonical'):
                front[key] = fields[key]
        front['migration']['sourceHead'] = {
            'sourcePageSha256': source_head['sourcePageSha256'],
            'sourcePageReference': source_head['sourcePageReference'],
            'fields': source_head['fields'],
        }
    return front


def prepare_hugo(bundle, build_time, head_manifest=None, head_source_root=None, media_map=None,
                 attachment_manifest=None, attachment_source_root=None, wxr_sha256=None):
    """Return {relative file: bytes}, report; fail before producing any files."""
    validate_document('content', bundle)
    if (head_manifest is None) != (head_source_root is None):
        raise HugoExportError('source-head manifest and snapshot root must be supplied together')
    heads = validate_head_manifest(head_manifest, bundle, head_source_root) if head_manifest else {}
    if attachment_manifest is not None and (attachment_source_root is None or wxr_sha256 is None):
        raise HugoExportError('attachment sidecar needs snapshot root and WXR checksum')
    attachments = (validate_attachment_manifest(attachment_manifest, attachment_source_root, wxr_sha256)
                   if attachment_manifest is not None else [])
    mapping, base = validate_media_map(media_map)
    cutoff = _instant(build_time)
    files = {}
    entries = []
    excluded = []
    paths = set()
    ids = set()
    unresolved_media = []
    for item in bundle['items']:
        source_id = item['sourceId']
        if source_id in ids:
            raise HugoExportError(f'{source_id}: duplicate source ID')
        ids.add(source_id)
        if item['status'] != 'publish':
            raise HugoExportError(f'{source_id}: nonpublic status cannot enter Hugo output')
        if item['path'] in paths:
            raise HugoExportError(f'{source_id}: duplicate public path {item["path"]}')
        paths.add(item['path'])
        if _instant(item['publishedAt']) > cutoff:
            excluded.append({'sourceId': source_id, 'reason': 'future-at-build-time'})
            continue
        if item['kind'] not in ('post', 'page', 'portfolio'):
            raise HugoExportError(f'{source_id}: unsupported Hugo content kind')
        if not re.fullmatch(r'wp:[1-9][0-9]*', source_id):
            raise HugoExportError(f'{source_id}: expected WordPress source ID')
        body = item['content']['html']
        if _sha(body.encode('utf-8')) != item['content']['provenance']['htmlSha256']:
            raise HugoExportError(f'{source_id}: rendered HTML checksum mismatch')
        rendered_body, missing = rewrite_html(body, mapping, base)
        missing_set = set(missing)
        front = json.dumps(_front_matter(item, heads.get(source_id), mapping, base, missing_set),
                           ensure_ascii=False, indent=2, sort_keys=True)
        unresolved_media.extend({'sourceId': source_id, 'sourceUrl': url}
                                | {'reason': 'unmapped-upload' if upload_path(url)
                                   else 'owned-non-upload'} for url in sorted(missing_set))
        # JSON front matter uses the outer braces as delimiters in Hugo. The
        # .html extension selects Hugo's HTML content renderer, avoiding any
        # Markdown transformation of code whitespace or element ordering.
        contents = (front + '\n' + rendered_body).encode('utf-8')
        relative = f'{item["kind"]}/{source_id.replace(":", "-")}.html'
        files[relative] = contents
        entries.append({'sourceId': source_id, 'kind': item['kind'], 'path': item['path'],
                        'file': relative, 'fileSha256': _sha(contents),
                        'sourceBodySha256': _sha(body.encode('utf-8')),
                        'bodySha256': _sha(rendered_body.encode('utf-8'))})
    for item in attachments:
        source_id = item['sourceId']
        if source_id in ids or item['path'] in paths:
            raise HugoExportError(f'{source_id}: attachment/content route collision')
        ids.add(source_id)
        paths.add(item['path'])
        if _instant(item['publishedAt']) > cutoff:
            excluded.append({'sourceId': source_id, 'reason': 'future-at-build-time'})
            continue
        body, missing = rewrite_html(item['html'], mapping, base)
        unresolved_media.extend({'sourceId': source_id, 'sourceUrl': url,
                                 'reason': 'unmapped-upload' if upload_path(url)
                                 else 'owned-non-upload'} for url in missing)
        front = {'title': item['title'], 'date': item['publishedAt'], 'lastmod': item['modifiedAt'],
                 'url': item['path'], 'type': 'attachment', 'draft': False,
                 'canonical': item['canonicalUrl'],
                 'migration': {'sourceId': source_id, 'sourceType': 'attachment',
                               'canonicalUrl': item['canonicalUrl'],
                               'sourcePageSha256': item['sourcePageSha256'],
                               'sourcePageReference': item['sourcePageReference'],
                               'captionHtml': item['captionHtml'],
                               'imageReferences': item['imageReferences'],
                               'fragments': item['fragments'],
                               'duplicateFragments': item['duplicateFragments'],
                               'sourceFragments': item['sourceFragments'],
                               'duplicateSourceFragments': item['duplicateSourceFragments']}}
        contents = (json.dumps(front, ensure_ascii=False, indent=2, sort_keys=True) + '\n' + body).encode()
        relative = f'attachment/{source_id.replace(":", "-")}.html'
        files[relative] = contents
        entries.append({'sourceId': source_id, 'kind': 'attachment', 'path': item['path'],
                        'file': relative, 'fileSha256': _sha(contents),
                        'sourceBodySha256': item['htmlSha256'],
                        'bodySha256': _sha(body.encode())})
    entries.sort(key=lambda e: int(e['sourceId'].split(':')[1]))
    excluded.sort(key=lambda e: int(e['sourceId'].split(':')[1]))
    report = {'schemaVersion': '1.0.0', 'sourceCompleteness': 'unverified',
              'buildTime': cutoff.isoformat(), 'inputRecordCount': len(bundle['items']) + len(attachments),
              'outputRecordCount': len(entries), 'excluded': excluded, 'items': entries,
              'sourceHeadCoverage': len(heads), 'attachmentRouteCount': len(attachments),
              'attachmentRoutes': [{'sourceId': item['sourceId'], 'path': item['path'],
                                    'fragments': item['fragments'],
                                    'sourceFragments': item['sourceFragments'],
                                    'sourceShellFragments': sorted(set(item['sourceFragments'])
                                                                   - set(item['fragments']))}
                                   for item in attachments],
              'unresolvedOwnedMedia': unresolved_media}
    report['contentSha256'] = _sha(json.dumps(bundle, ensure_ascii=False, sort_keys=True,
                                               separators=(',', ':')).encode('utf-8'))
    return files, report


def _verify_owned(destination):
    marker = destination / '.hugo-import-report.json'
    if not marker.is_file() or marker.is_symlink():
        raise HugoExportError('existing output is not an importer-owned directory')
    try:
        report = json.loads(marker.read_text(encoding='utf-8'))
        expected = {entry['file']: entry['fileSha256'] for entry in report['items']}
        observed = {p.relative_to(destination).as_posix(): p for p in destination.rglob('*')
                    if p.is_file() or p.is_symlink()}
        if set(observed) != set(expected) | {'.hugo-import-report.json'}:
            raise HugoExportError('existing generated directory has added or missing files')
        for relative, checksum in expected.items():
            path = observed[relative]
            if path.is_symlink() or _sha(path.read_bytes()) != checksum:
                raise HugoExportError(f'existing generated file changed: {relative}')
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise HugoExportError('existing output report is invalid') from error


def write_hugo(bundle, output, build_time, head_manifest=None, head_source_root=None,
               media_map=None, attachment_manifest=None, attachment_source_root=None,
               wxr_sha256=None):
    """Replace a dedicated generated directory after a complete preflight."""
    files, report = prepare_hugo(bundle, build_time, head_manifest, head_source_root, media_map,
                                 attachment_manifest, attachment_source_root, wxr_sha256)
    destination = Path(output).absolute()
    if destination.is_symlink():
        raise HugoExportError('output must not be a symlink')
    if destination.exists():
        _verify_owned(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.hugo-import-', dir=destination.parent))
    backup = None
    try:
        for relative, data in files.items():
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (staging / '.hugo-import-report.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        if destination.exists():
            backup = Path(tempfile.mkdtemp(prefix='.hugo-import-old-', dir=destination.parent))
            backup.rmdir()
            os.replace(destination, backup)
        try:
            os.replace(staging, destination)
        except OSError:
            if backup is not None:
                os.replace(backup, destination)
                backup = None
            raise
        if backup is not None:
            shutil.rmtree(backup)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path, help='reviewed public v1 content.json')
    parser.add_argument('output', type=Path, help='dedicated generated Hugo content directory')
    parser.add_argument('--build-time', required=True, help='fixed ISO 8601 time with explicit offset')
    parser.add_argument('--head-manifest', type=Path, help='private hash-bound live source-head values')
    parser.add_argument('--head-source-root', type=Path, help='private directory of source HTML snapshots')
    parser.add_argument('--media-map', type=Path, help='reviewed selected owned-media URL to local path map')
    parser.add_argument('--attachment-manifest', type=Path, help='private attachment HTML page sidecar')
    parser.add_argument('--attachment-source-root', type=Path, help='private attachment source HTML directory')
    parser.add_argument('--private-report', type=Path, help='successful WXR import report for attachment binding')
    args = parser.parse_args(argv)
    try:
        bundle = json.loads(args.bundle.read_text(encoding='utf-8'))
        head = json.loads(args.head_manifest.read_text(encoding='utf-8')) if args.head_manifest else None
        media = json.loads(args.media_map.read_text(encoding='utf-8')) if args.media_map else None
        attachments = json.loads(args.attachment_manifest.read_text(encoding='utf-8')) if args.attachment_manifest else None
        wxr_report = json.loads(args.private_report.read_text(encoding='utf-8')) if args.private_report else None
        wxr_sha = wxr_report.get('sourceSha256') if isinstance(wxr_report, dict) else None
        report = write_hugo(bundle, args.output, args.build_time, head, args.head_source_root,
                            media, attachments, args.attachment_source_root, wxr_sha)
    except (OSError, ValueError) as error:
        parser.exit(1, f'Hugo export failed: {error}\n')
    print(f'Wrote {report["outputRecordCount"]} Hugo records; source completeness remains unverified.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
