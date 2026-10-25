"""Read owner WXR/uploads/themes without copying private data into public Git.

The private manifest contains paths, hashes and missing-reference details. Only
aggregate counts and public editorial route reconciliation enter the public report.
"""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

from scripts.inventory.capture import asset_record, parse_markup

WP = '{http://wordpress.org/export/1.2/}'
CONTENT = '{http://purl.org/rss/1.0/modules/content/}encoded'
PUBLIC_EDITORIAL = {'post', 'page', 'portfolio'}


class SerializedMetadata:
    """Data-only PHP serialization reader; never instantiates objects or code."""
    def __init__(self, value):
        self.data, self.index = value.encode('utf-8'), 0

    def token(self, delimiter):
        end = self.data.index(delimiter, self.index)
        token = self.data[self.index:end]
        self.index = end + len(delimiter)
        return token

    def read(self, depth=0):
        if depth > 30:
            raise ValueError('PHP metadata nesting exceeds limit')
        kind = self.data[self.index:self.index + 1]
        self.index += 1
        if kind == b'N':
            if self.data[self.index:self.index + 1] != b';':
                raise ValueError('Malformed null')
            self.index += 1
            return None
        if self.data[self.index:self.index + 1] != b':':
            raise ValueError('Malformed PHP value')
        self.index += 1
        if kind in (b'i', b'b', b'd'):
            value = self.token(b';')
            return float(value) if kind == b'd' else int(value)
        if kind == b's':
            length = int(self.token(b':'))
            if length < 0 or self.data[self.index:self.index + 1] != b'"':
                raise ValueError('Malformed PHP string')
            self.index += 1
            value = self.data[self.index:self.index + length]
            self.index += length
            if self.data[self.index:self.index + 2] != b'";':
                raise ValueError('PHP string length mismatch')
            self.index += 2
            return value.decode('utf-8')
        if kind == b'a':
            count = int(self.token(b':'))
            if count < 0 or count > 100000 or self.data[self.index:self.index + 1] != b'{':
                raise ValueError('Malformed PHP array')
            self.index += 1
            result = {}
            for _ in range(count):
                key = self.read(depth + 1)
                value = self.read(depth + 1)
                result[key] = value
            if self.data[self.index:self.index + 1] != b'}':
                raise ValueError('Malformed PHP array terminator')
            self.index += 1
            return result
        raise ValueError('Unsupported PHP metadata value type')

    def parse(self):
        result = self.read()
        if self.index != len(self.data):
            raise ValueError('Trailing PHP metadata data')
        return result


def checked_relative(value):
    value = unquote(value)
    if not value or value.startswith('/') or '\\' in value or '\x00' in value:
        raise ValueError('Unsafe uploads relative path')
    parts = value.split('/')
    if any(part in ('', '.', '..') for part in parts):
        raise ValueError('Unsafe uploads path segment')
    return str(PurePosixPath(value))


def upload_path(url, source):
    origin = asset_record(url, source)['uploadOriginCandidate']
    if origin is None:
        return None
    return checked_relative(urlsplit(origin).path.split('/wp-content/uploads/', 1)[1])


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def inventory_tree(root):
    files, skipped = {}, []
    for directory, names, filenames in os.walk(root, followlinks=False):
        for name in list(names):
            path = Path(directory) / name
            if path.is_symlink():
                skipped.append(str(path.relative_to(root)))
                names.remove(name)
        for name in filenames:
            path = Path(directory) / name
            relative = str(path.relative_to(root))
            if path.is_symlink() or not path.is_file():
                skipped.append(relative)
                continue
            files[relative] = {'bytes': path.stat().st_size, 'sha256': file_hash(path), 'extension': path.suffix.lower() or '(none)'}
    return files, skipped


def summarize(paths, files):
    present = set(paths) & set(files)
    return {'referencedFiles': len(set(paths)), 'presentFiles': len(present),
            'missingFiles': len(set(paths) - set(files)),
            'bytes': sum(files[path]['bytes'] for path in present)}


def analyze_backup(backup, public, private_dir):
    backup, private_dir = backup.resolve(), private_dir.resolve()
    if private_dir == backup or backup in private_dir.parents:
        raise ValueError('Private output must not be inside the immutable backup')
    # Owner controls both paths, but refuse to write private intermediates in Git.
    if any((parent / '.git').exists() for parent in (private_dir, *private_dir.parents)):
        raise ValueError('Private manifest output must be outside a Git checkout')
    if private_dir.exists():
        raise ValueError('Use a new private output directory for every acquisition')
    if not all((backup / name).is_dir() for name in ('uploads', 'themes')):
        raise ValueError('Backup requires uploads and themes directories')
    xml_files = sorted(backup.glob('*.xml'))
    if len(xml_files) != 1:
        raise ValueError('Expected exactly one top-level owner WXR XML file')
    raw = xml_files[0].read_bytes()
    if b'<!DOCTYPE' in raw or b'<!ENTITY' in raw:
        raise ValueError('WXR DTD/entities are not permitted')
    xml = ET.fromstring(raw)
    items = xml.findall('./channel/item')
    if not items:
        raise ValueError('Owner WXR contains no channel items')
    source = public['source']
    counts = Counter((item.findtext(WP + 'post_type'), item.findtext(WP + 'status')) for item in items)
    editorial = [item for item in items if item.findtext(WP + 'post_type') in PUBLIC_EDITORIAL and item.findtext(WP + 'status') == 'publish']
    public_records = [{'sourceId': 'wp:' + item.findtext(WP + 'post_id'), 'type': item.findtext(WP + 'post_type'), 'url': item.findtext('link')} for item in editorial]
    published_ids = {item.findtext(WP + 'post_id') for item in editorial}
    uploads, skipped = inventory_tree(backup / 'uploads')
    originals, derivatives, backups, references = set(), set(), set(), set()
    attachment_ids, unsafe_refs, metadata_errors = {}, [], []
    parent_counts = Counter()
    attachments = [item for item in items if item.findtext(WP + 'post_type') == 'attachment']
    for item in attachments:
        source_id = item.findtext(WP + 'post_id')
        parent = item.findtext(WP + 'post_parent')
        parent_counts['publicEditorialParent' if parent in published_ids else 'unattached' if parent == '0' else 'otherOrPrivateParent'] += 1
        metadata = {meta.findtext(WP + 'meta_key'): meta.findtext(WP + 'meta_value') or '' for meta in item.findall(WP + 'postmeta')}
        try:
            path = checked_relative(metadata.get('_wp_attached_file', ''))
            originals.add(path)
            attachment_ids[source_id] = path
            directory = str(PurePosixPath(path).parent)
            def relative_file(name):
                return checked_relative((directory + '/' if directory != '.' else '') + name)
            for key in ('_wp_attachment_metadata', '_wp_attachment_backup_sizes'):
                if not metadata.get(key):
                    continue
                decoded = SerializedMetadata(metadata[key]).parse()
                if not isinstance(decoded, dict):
                    raise ValueError('Attachment metadata is not an array')
                if key == '_wp_attachment_metadata':
                    if decoded.get('original_image'):
                        originals.add(relative_file(decoded['original_image']))
                    for size in decoded.get('sizes', {}).values():
                        if isinstance(size, dict) and size.get('file'):
                            derivatives.add(relative_file(size['file']))
                else:
                    for size in decoded.values():
                        if isinstance(size, dict) and size.get('file'):
                            backups.add(relative_file(size['file']))
        except (ValueError, IndexError, UnicodeError, TypeError) as error:
            metadata_errors.append({'attachmentId': source_id, 'error': str(error)})
    for asset in public['assets']:
        try:
            path = upload_path(asset['url'], source)
            if path:
                references.add(path)
        except ValueError:
            unsafe_refs.append({'source': 'public-inventory', 'url': asset['url']})
    for item in editorial:
        body = item.findtext(CONTENT) or ''
        parsed = parse_markup(body, item.findtext('link'))
        urls = parsed.assets | set(re.findall(r'https?://[^\s<>"\]\)]+', body))
        for url in urls:
            try:
                path = upload_path(url.replace('&amp;', '&'), source)
                if path:
                    references.add(path)
            except ValueError:
                unsafe_refs.append({'sourceId': item.findtext(WP + 'post_id'), 'url': url})
        metadata = {meta.findtext(WP + 'meta_key'): meta.findtext(WP + 'meta_value') for meta in item.findall(WP + 'postmeta')}
        ids = [metadata.get('_thumbnail_id')]
        for gallery in re.findall(r'\[gallery\b[^\]]*\bids=["\']([^"\']+)["\']', body):
            ids.extend(gallery.split(','))
        for attachment_id in ids:
            if attachment_id and attachment_id.strip() in attachment_ids:
                references.add(attachment_ids[attachment_id.strip()])
    all_files = set(uploads)
    known_preservation = originals | backups | references
    known_metadata = originals | backups | derivatives
    full_preservation = known_metadata | references
    casefold_paths = defaultdict(list)
    for path in full_preservation:
        casefold_paths[path.casefold()].append(path)
    exact_missing = full_preservation - all_files
    missing_with_case_candidate = {path for path in exact_missing if any(candidate.casefold() == path.casefold() for candidate in uploads)}
    unreferenced_derivatives = derivatives - references - originals - backups
    unclassified = all_files - known_metadata - references
    by_extension = defaultdict(lambda: {'files': 0, 'bytes': 0})
    for info in uploads.values():
        by_extension[info['extension']]['files'] += 1
        by_extension[info['extension']]['bytes'] += info['bytes']
    unique = {info['sha256']: info['bytes'] for info in uploads.values()}
    total = sum(info['bytes'] for info in uploads.values())
    # Theme source is licensed owner material; retain only top-level header identity.
    themes = []
    for style in sorted((backup / 'themes').glob('*/style.css')):
        header = style.read_text(encoding='utf-8', errors='replace')[:8192]
        fields = {}
        for label in ('Theme Name', 'Version', 'Template', 'License'):
            match = re.search(r'^\s*' + label + r':\s*(.+)$', header, re.M | re.I)
            if match:
                fields[label] = match.group(1).strip()
        themes.append(fields)
    public_ids = {row['sourceId'] for row in public['records']}
    wxr_post_pages = {row['sourceId'] for row in public_records if row['type'] in ('post', 'page')}
    wxr_urls = {row['url'] for row in public_records}
    attachment_urls = {item.findtext('link') for item in attachments}
    extra_sitemap = set(public['reconciliation']['sitemapNonRestUrls'])
    footprint = summarize(known_preservation, uploads)
    report = {
        'schemaVersion': '1.0.0', 'capturedAt': datetime.now(timezone.utc).isoformat(),
        'completeness': 'unverified', 'source': source,
        'sourceInputs': {'ownerWxrSha256': hashlib.sha256(raw).hexdigest(), 'ownerWxrBytes': len(raw), 'backupModified': False},
        'wxr': {'totalItems': len(items), 'byTypeAndStatus': [{'type': kind, 'status': status, 'count': count} for (kind, status), count in sorted(counts.items())],
                'publicEditorialRecords': public_records, 'attachmentParentCounts': dict(parent_counts),
                'metadataParseErrors': len(metadata_errors)},
        'reconciliation': {'publicRestIdsAbsentFromOwnerWxr': sorted(public_ids - wxr_post_pages),
                           'ownerWxrPublishedPostPageIdsAbsentFromRest': sorted(wxr_post_pages - public_ids),
                           'sitemapExtrasMatchedPublishedEditorial': len(extra_sitemap & wxr_urls),
                           'sitemapExtrasMatchedAttachmentRoutes': len(extra_sitemap & attachment_urls),
                           'sitemapExtrasUnclassified': sorted(extra_sitemap - wxr_urls - attachment_urls - {source})},
        'uploads': {'totalFiles': len(uploads), 'totalBytes': total, 'byExtension': dict(by_extension),
                    'symlinksSkipped': len(skipped), 'distinctSha256': len(unique), 'distinctContentBytes': sum(unique.values()),
                    'duplicateContentBytes': total - sum(unique.values()),
                    'attachmentOriginalCandidates': summarize(originals, uploads), 'attachmentBackupVariants': summarize(backups, uploads),
                    'metadataDerivativeCandidates': summarize(derivatives, uploads), 'observedPublicReferences': summarize(references, uploads),
                    'knownPreservationCandidateUnion': footprint, 'allAttachmentMetadataUnion': summarize(known_metadata, uploads),
                    'fullMetadataAndObservedReferenceUnion': summarize(full_preservation, uploads),
                    'expectedCaseDistinctGroups': sum(len(group) > 1 for group in casefold_paths.values()),
                    'exactCaseMissingWithCaseOnlyCandidate': len(missing_with_case_candidate),
                    'missingWithoutCaseOnlyCandidate': len(exact_missing - missing_with_case_candidate),
                    'metadataDerivativesNotObserved': summarize(unreferenced_derivatives, uploads),
                    'unclassifiedOrUnreferencedFiles': summarize(unclassified, uploads),
                    'unsafeReferences': len(unsafe_refs), 'filesAtOrAbove100MiB': sum(info['bytes'] >= 100 * 1024 ** 2 for info in uploads.values()),
                    'filesAtOrAbove50MiB': sum(info['bytes'] >= 50 * 1024 ** 2 for info in uploads.values()),
                    'largestFiles': [{'bytes': info['bytes'], 'extension': info['extension'],
                                      'attachmentOriginalCandidate': path in originals, 'observedPublicReference': path in references}
                                     for path, info in sorted(uploads.items(), key=lambda item: -item[1]['bytes'])[:10]]},
        'themeHeaders': themes,
        'feasibility': {'fullUploadsExceeds1000000000Bytes': total > 1_000_000_000,
                        'fullUploadsExceeds1GiB': total > 1024 ** 3,
                        'knownPreservationCandidateBytes': footprint['bytes'],
                        'remainingBytesTo1000000000BeforeSiteFiles': 1_000_000_000 - footprint['bytes'],
                        'fullMetadataAndObservedReferenceBytes': summarize(full_preservation, uploads)['bytes'],
                        'fullMetadataAndObservedExceeds1000000000Bytes': summarize(full_preservation, uploads)['bytes'] > 1_000_000_000,
                        'fullMetadataAndObservedExceeds1GiB': summarize(full_preservation, uploads)['bytes'] > 1024 ** 3,
                        'requiredDeploymentFootprintVerified': False},
        'limitations': [
            'Owner WXR and media backup are observed acquisition inputs, not a documented production editing freeze or final delta.',
            'Published post/page ID equality does not resolve all plugin/custom-type semantics or prove full feature fidelity.',
            'Original candidates include every attachment main file plus explicit original_image entries. WordPress image-edit backups and observed public resources are preserved separately in the union.',
            'Exact-case missing paths and same-case bytes require case-sensitive source verification; case-insensitive backup files may contain the opposite-case variant. See separately captured public source URL/hash evidence.',
            'Identical hashes do not authorize removing any original URL. Plain Pages requires a file at every preserved URL; remapping references alone does not preserve historical direct URLs.',
            'All upload files are hashed privately. Hash equality is evidence only; no deduplication, optimization, removal or source modification occurred.',
            'Known preservation union is a planning footprint, not a publication allowlist: attachments with private/unknown parents still require privacy review.',
            'CSS/JS dynamic requests, shortcode/theme/plugin expansion, final renderer assets and every route screenshot remain unresolved; exact required deployment footprint is not proven.',
            'Raw XML, comment/email/IP/password metadata, per-file paths/hashes, missing-reference details and theme source remain outside Git.',
        ],
    }
    private_dir.mkdir(mode=0o700, parents=True)
    manifest = {'files': uploads, 'skipped': skipped, 'attachmentPaths': attachment_ids,
                'sets': {key: sorted(value) for key, value in {'originals': originals, 'derivatives': derivatives, 'backups': backups, 'references': references}.items()},
                'missingKnownPreservationPaths': sorted(known_preservation - all_files),
                'metadataErrors': metadata_errors, 'unsafeReferences': unsafe_refs}
    target = private_dir / 'private-manifest.json'
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    target.chmod(0o600)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--public-inventory', type=Path, required=True)
    parser.add_argument('--private-output', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    report_path = args.report.resolve()
    source = args.backup.resolve()
    if report_path == source or source in report_path.parents:
        parser.error('Public report must not be written inside the immutable backup')
    report = analyze_backup(source, json.loads(args.public_inventory.read_text(encoding='utf-8')), args.private_output)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'wxrItems': report['wxr']['totalItems'], 'uploads': report['uploads']['totalFiles'],
                      'uploadsBytes': report['uploads']['totalBytes'], 'knownPreservation': report['uploads']['knownPreservationCandidateUnion'],
                      'reconciliation': report['reconciliation']}, indent=2))


if __name__ == '__main__':
    main()
