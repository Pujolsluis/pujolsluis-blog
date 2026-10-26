"""Write reviewed v1 content as deterministic Hugo HTML content files.

This is a publication adapter, not a WXR reader. The caller must first review
the normalized public bundle and the private WXR reconciliation report.
"""

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import tempfile
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

from docs.contracts.validate import validate_document
from .attachments import validate_attachment_manifest
from .head import FIELDS, validate_head_manifest
from .media import rewrite_html, rewrite_url, upload_path, validate_media_map


class HugoExportError(ValueError):
    """The public bundle cannot be safely represented as Hugo content."""


def _sha(data):
    return hashlib.sha256(data).hexdigest()


class _CommentMarkup(HTMLParser):
    """Find comment threads, avatars and submission forms without changing other HTML."""

    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta',
            'param', 'source', 'track', 'wbr'}
    COMMENT_IDS = {'comments', 'commentlist', 'comment-list', 'commentform', 'respond'}
    COMMENT_CLASSES = {'comment', 'comments', 'comments-area', 'comment-list', 'commentlist',
                       'comment-respond', 'comment-form'}

    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.source = source
        self.lines = source.splitlines(keepends=True)
        self.stack = []
        self.removals = []
        self.comment_block_count = 0
        self.form_count = 0
        self.comment_form_count = 0
        self.other_form_count = 0
        self.comment_link_count = 0
        self.feed(source)
        self.close()
        for row in self.stack:
            if row['drop']:
                self.removals.append((row['start'], len(source)))

    def position(self):
        line, column = self.getpos()
        return sum(map(len, self.lines[:line - 1])) + column

    def _start(self, tag, attrs, self_closing=False):
        start = self.position()
        attributes = dict(attrs)
        element_id = (attributes.get('id') or '').lower()
        classes = set((attributes.get('class') or '').lower().split())
        action = (attributes.get('action') or '').lower()
        comment_form = tag == 'form' and (
            element_id == 'commentform' or 'comment-form' in classes
            or 'wp-comments-post.php' in action)
        comment_node = (element_id in self.COMMENT_IDS or element_id.startswith('comment-')
                        or bool(classes & self.COMMENT_CLASSES))
        avatar = tag == 'img' and bool(classes & {'avatar', 'gravatar'})
        if tag == 'img':
            source_url = ' '.join((attributes.get(key) or '') for key in ('src', 'srcset')).lower()
            avatar = avatar or 'gravatar.' in source_url or '/avatar/' in source_url
        other_form = tag == 'form' and not comment_form
        href = (attributes.get('href') or '').lower()
        comment_link = tag == 'a' and bool(re.search(
            r'(?:#[^#]*(?:comment|respond)[^#]*$|[?&]replytocom=)', href))
        if comment_link:
            self.comment_link_count += 1
        parent_drop = any(row['drop'] for row in self.stack)
        in_code = any(row['tag'] in {'pre', 'code', 'script', 'style'} for row in self.stack)
        if tag == 'form':
            self.form_count += 1
            if comment_form:
                self.comment_form_count += 1
            else:
                self.other_form_count += 1
        reason = 'comment' if comment_node or comment_form or avatar else 'form' if other_form else None
        drop = not parent_drop and not in_code and reason is not None
        if drop and reason == 'comment':
            self.comment_block_count += 1
        end_start = start + len(self.get_starttag_text() or '')
        if tag in self.VOID or self_closing:
            if drop:
                self.removals.append((start, end_start))
            return
        self.stack.append({'tag': tag, 'start': start, 'drop': drop,
                           'unwrap': comment_link and not drop,
                           'open_end': end_start})

    def handle_starttag(self, tag, attrs):
        self._start(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._start(tag, attrs, self_closing=True)

    def handle_endtag(self, tag):
        indexes = [index for index, row in enumerate(self.stack) if row['tag'] == tag]
        if not indexes:
            return
        index = indexes[-1]
        start = self.position()
        match = re.search(r'</\s*' + re.escape(tag) + r'\s*>', self.source[start:], re.IGNORECASE)
        end = start + match.end() if match else start
        if self.stack[index]['drop']:
            self.removals.append((self.stack[index]['start'], end))
        elif self.stack[index]['unwrap']:
            self.removals.append((self.stack[index]['start'], self.stack[index]['open_end']))
            self.removals.append((start, end))
        self.stack = self.stack[:index]


def sanitize_public_html(source):
    """Remove WordPress comments/forms while preserving the remaining source HTML."""
    source, editor_marker_count = re.subn(
        r'<span\b(?=[^>]*\bclass\s*=\s*["\'][^"\']*\bmce_SELRES_(?:start|end)\b'
        r'[^"\']*["\'])[^>]*>.*?</span\s*>', '', source, flags=re.IGNORECASE | re.DOTALL)
    parsed = _CommentMarkup(source)
    merged = []
    for start, end in sorted(parsed.removals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    output = []
    cursor = 0
    for start, end in merged:
        output.append(source[cursor:start])
        cursor = end
    output.append(source[cursor:])
    return ''.join(output), {
        'commentBlockCount': parsed.comment_block_count,
        'formCount': parsed.form_count,
        'commentFormCount': parsed.comment_form_count,
        'otherFormCount': parsed.other_form_count,
        'commentLinkCount': parsed.comment_link_count,
        'editorMarkerCount': editor_marker_count,
    }


def _is_comment_fragment(fragment):
    value = str(fragment).lower().lstrip('#')
    return 'comment' in value or 'respond' in value


def _public_fragments(fragments):
    return [fragment for fragment in fragments if not _is_comment_fragment(fragment)]


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
            'featuredAssetId': metadata['featuredAssetId'],
            'assetIds': item['assetIds'],
            'embeds': item['embeds'],
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
    deferred_comments = []
    deferred_forms = []
    removed_comment_markup = 0
    form_bridge_count = 0
    authored_sections = {item['kind'] for item in bundle['items'] if item['kind'] != 'page'}
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
        if item['comments']:
            deferred_comments.append({'sourceId': source_id, 'count': len(item['comments']),
                                      'disposition': 'owner-publication-decision'})
        if item['kind'] not in ('post', 'page', 'portfolio'):
            raise HugoExportError(f'{source_id}: unsupported Hugo content kind')
        if not re.fullmatch(r'wp:[1-9][0-9]*', source_id):
            raise HugoExportError(f'{source_id}: expected WordPress source ID')
        body = item['content']['html']
        if _sha(body.encode('utf-8')) != item['content']['provenance']['htmlSha256']:
            raise HugoExportError(f'{source_id}: rendered HTML checksum mismatch')
        body, sanitation = sanitize_public_html(body)
        removed_comment_markup += sanitation['commentBlockCount']
        if sanitation['formCount']:
            deferred_forms.append({'sourceId': source_id, 'count': sanitation['formCount'],
                                   'disposition': 'form-omitted'})
        rendered_body, missing = rewrite_html(body, mapping, base)
        if base != '/' and sanitation['otherFormCount']:
            form_url = html.escape(item['canonicalUrl'], quote=True)
            rendered_body += ('\n<aside class="migration-form-bridge">This preview does not accept '
                              f'submissions. <a href="{form_url}">Use the form on the live site</a>.'
                              '</aside>')
            form_bridge_count += 1
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
        section_root = item['kind'] == 'page' and item['path'].strip('/') in authored_sections \
            and item['path'] == '/' + item['path'].strip('/') + '/'
        content_section = 'posts' if item['kind'] == 'post' else item['kind']
        relative = (item['path'].strip('/') + '/_index.html' if section_root else
                    f'{content_section}/{source_id.replace(":", "-")}.html')
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
        sanitized_body, sanitation = sanitize_public_html(item['html'])
        removed_comment_markup += sanitation['commentBlockCount']
        if sanitation['formCount']:
            deferred_forms.append({'sourceId': source_id, 'count': sanitation['formCount'],
                                   'disposition': 'form-omitted'})
        body, missing = rewrite_html(sanitized_body, mapping, base)
        if base != '/' and sanitation['otherFormCount']:
            form_url = html.escape(item['canonicalUrl'], quote=True)
            body += ('\n<aside class="migration-form-bridge">This preview does not accept '
                     f'submissions. <a href="{form_url}">Use the form on the live site</a>.'
                     '</aside>')
            form_bridge_count += 1
        unresolved_media.extend({'sourceId': source_id, 'sourceUrl': url,
                                 'reason': 'unmapped-upload' if upload_path(url)
                                 else 'owned-non-upload'} for url in missing)
        public_fragments = _public_fragments(item['fragments'])
        front = {'title': item['title'], 'date': item['publishedAt'], 'lastmod': item['modifiedAt'],
                 'url': item['path'], 'type': 'attachment', 'draft': False,
                 'canonical': item['canonicalUrl'],
                 'migration': {'sourceId': source_id, 'sourceType': 'attachment',
                               'canonicalUrl': item['canonicalUrl'],
                               'sourcePageSha256': item['sourcePageSha256'],
                               'sourcePageReference': item['sourcePageReference'],
                               'captionHtml': item['captionHtml'],
                               'imageReferences': item['imageReferences'],
                               'fragments': public_fragments,
                               'duplicateFragments': _public_fragments(item['duplicateFragments']),
                               'sourceFragments': _public_fragments(item['sourceFragments']),
                               'duplicateSourceFragments': _public_fragments(
                                   item['duplicateSourceFragments'])}}
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
              'deferredComments': {'recordCount': len(deferred_comments),
                                   'commentCount': sum(row['count'] for row in deferred_comments),
                                   'items': deferred_comments},
              'removedCommentMarkupCount': removed_comment_markup,
              'formBridgeCount': form_bridge_count,
              'deferredForms': {'recordCount': len(deferred_forms),
                                'formCount': sum(row['count'] for row in deferred_forms),
                                'items': deferred_forms},
              'attachmentRoutes': [{'sourceId': item['sourceId'], 'path': item['path'],
                                    'fragments': _public_fragments(item['fragments']),
                                    'previewFragments': _public_fragments(item['fragments']),
                                    'sourceFragments': _public_fragments(item['sourceFragments']),
                                    'sourceShellFragments': sorted(set(_public_fragments(
                                        item['sourceFragments']))
                                        - set(_public_fragments(item['fragments'])))}
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
