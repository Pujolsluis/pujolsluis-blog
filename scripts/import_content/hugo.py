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


def _front_matter(item):
    metadata = item['sourceMetadata']
    return {
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


def prepare_hugo(bundle, build_time):
    """Return {relative file: bytes}, report; fail before producing any files."""
    validate_document('content', bundle)
    cutoff = _instant(build_time)
    files = {}
    entries = []
    excluded = []
    paths = set()
    ids = set()
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
        front = json.dumps(_front_matter(item), ensure_ascii=False, indent=2, sort_keys=True)
        # JSON front matter uses the outer braces as delimiters in Hugo. The
        # .html extension selects Hugo's HTML content renderer, avoiding any
        # Markdown transformation of code whitespace or element ordering.
        contents = (front + '\n' + body).encode('utf-8')
        relative = f'{item["kind"]}/{source_id.replace(":", "-")}.html'
        files[relative] = contents
        entries.append({'sourceId': source_id, 'kind': item['kind'], 'path': item['path'],
                        'file': relative, 'fileSha256': _sha(contents),
                        'bodySha256': _sha(body.encode('utf-8'))})
    entries.sort(key=lambda e: int(e['sourceId'].split(':')[1]))
    excluded.sort(key=lambda e: int(e['sourceId'].split(':')[1]))
    report = {'schemaVersion': '1.0.0', 'sourceCompleteness': 'unverified',
              'buildTime': cutoff.isoformat(), 'inputRecordCount': len(bundle['items']),
              'outputRecordCount': len(entries), 'excluded': excluded, 'items': entries}
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


def write_hugo(bundle, output, build_time):
    """Replace a dedicated generated directory after a complete preflight."""
    files, report = prepare_hugo(bundle, build_time)
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
    args = parser.parse_args(argv)
    try:
        bundle = json.loads(args.bundle.read_text(encoding='utf-8'))
        report = write_hugo(bundle, args.output, args.build_time)
    except (OSError, ValueError) as error:
        parser.exit(1, f'Hugo export failed: {error}\n')
    print(f'Wrote {report["outputRecordCount"]} Hugo records; source completeness remains unverified.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
