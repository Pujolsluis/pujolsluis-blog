"""Normalize WXR 1.2 without guessing WordPress rendering or public visibility."""

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

from docs.contracts.validate import ContractError, validate_document

WP = 'http://wordpress.org/export/1.2/'
NS = {'wp': WP, 'content': 'http://purl.org/rss/1.0/modules/content/',
      'excerpt': 'http://wordpress.org/export/1.2/excerpt/',
      'dc': 'http://purl.org/dc/elements/1.1/'}
UNRESOLVED = re.compile(r'<!--\s*/?wp:|\[/?[A-Za-z][\w-]*(?:\s[^\]\n]*)?\]')
BLOCK_HTML = re.compile(r'^\s*<(?:p|h[1-6]|div|section|article|figure|ul|ol|table|pre|blockquote|iframe|hr)\b', re.I)
KNOWN_ITEM_FIELDS = {
    'title', 'link', 'description', 'pubDate', 'guid', 'category',
    '{' + NS['dc'] + '}creator', '{' + NS['content'] + '}encoded',
    '{' + NS['excerpt'] + '}encoded',
} | {'{' + WP + '}' + name for name in (
    'post_id', 'post_date', 'post_date_gmt', 'post_modified', 'post_modified_gmt',
    'comment_status', 'ping_status', 'post_name', 'status', 'post_parent', 'menu_order',
    'post_type', 'post_password', 'is_sticky', 'attachment_url', 'postmeta', 'comment',
)}
SAFE_META = {'_edit_lock', '_edit_last', '_thumbnail_id'}


class ImportFailure(ValueError):
    """Import failed atomically; report is private and may identify source records."""

    def __init__(self, errors, report=None):
        self.errors = errors
        self.report = report or {}
        super().__init__('; '.join(errors))


def sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def value(element, path, required=True, default=''):
    nodes = element.findall(path, NS)
    if len(nodes) > 1:
        raise ValueError(f'duplicate field {path}')
    if not nodes:
        if required:
            raise ValueError(f'missing field {path}')
        return default
    if len(nodes[0]):
        raise ValueError(f'{path} must contain text or CDATA, not child XML')
    result = nodes[0].text or ''
    if required and not result:
        raise ValueError(f'empty required field {path}')
    return result


def positive_id(raw, label):
    if not re.fullmatch(r'[1-9][0-9]*', raw):
        raise ValueError(f'{label} must be a positive WordPress integer ID')
    return raw


def source_date(element, local_field, utc_field):
    """A local/GMT pair establishes an offset, never a timezone name."""
    local_raw = value(element, 'wp:' + local_field)
    utc_raw = value(element, 'wp:' + utc_field)
    try:
        local = datetime.strptime(local_raw, '%Y-%m-%d %H:%M:%S')
        utc = datetime.strptime(utc_raw, '%Y-%m-%d %H:%M:%S')
        offset = local - utc
        if abs(offset.total_seconds()) > 14 * 3600 or offset.total_seconds() % 60:
            raise ValueError('invalid local/GMT offset')
        return local.replace(tzinfo=timezone(offset)).isoformat()
    except ValueError as error:
        raise ValueError(f'invalid {local_field}/{utc_field} pair; provide valid source dates') from error


def canonical(raw):
    parts = urlsplit(raw)
    if parts.scheme not in ('https', 'http') or not parts.hostname or parts.username or parts.password:
        raise ValueError('link must be an absolute HTTP(S) URL without credentials')
    path = parts.path
    decoded = unquote(path)
    if (not path.startswith('/') or path.startswith('//') or parts.query or parts.fragment
            or '\\' in decoded or any(p in ('.', '..') for p in decoded.split('/'))
            or re.search(r'[\x00-\x20\x7f]', decoded)):
        raise ValueError('link path is unsafe or uses a query/fragment canonical; supply reviewed route evidence')
    return path


class CommentSafety(HTMLParser):
    """Reject unsafe markup rather than silently removing public comment content."""

    TAGS = {'a', 'abbr', 'acronym', 'b', 'blockquote', 'br', 'cite', 'code', 'del', 'em',
            'i', 'li', 'ol', 'p', 'pre', 'q', 's', 'span', 'strong', 'sub', 'sup', 'u', 'ul'}
    ATTRS = {'a': {'href', 'title', 'rel'}, 'abbr': {'title'}, 'acronym': {'title'},
             'blockquote': {'cite'}, 'q': {'cite'}}

    def handle_starttag(self, tag, attrs):
        if tag not in self.TAGS:
            raise ValueError(f'unsafe/unsupported comment tag {tag}')
        for key, val in attrs:
            if key not in self.ATTRS.get(tag, set()) or val is None:
                raise ValueError(f'unsafe/unsupported comment attribute {key}')
            if key in ('href', 'cite'):
                compact = re.sub(r'[\x00-\x20\x7f]', '', val)
                if urlsplit(compact).scheme.lower() not in ('', 'http', 'https', 'mailto'):
                    raise ValueError('unsafe comment URL scheme')

    handle_startendtag = handle_starttag

    def handle_endtag(self, tag):
        if tag not in self.TAGS:
            raise ValueError(f'unsafe/unsupported comment tag {tag}')

    def handle_decl(self, decl):
        raise ValueError('unsupported comment declaration')


def comments(item):
    result = []
    for comment in item.findall('wp:comment', NS):
        if value(comment, 'wp:comment_approved') != '1':
            continue
        kind = value(comment, 'wp:comment_type', required=False)
        if kind not in ('', 'comment'):
            raise ValueError(f'unsupported approved comment type {kind}; needs a compatibility decision')
        html = value(comment, 'wp:comment_content', required=False)
        CommentSafety().feed(html)
        parent = value(comment, 'wp:comment_parent')
        result.append({
            'sourceId': 'wp-comment:' + positive_id(value(comment, 'wp:comment_id'), 'comment ID'),
            'parentId': None if parent == '0' else 'wp-comment:' + positive_id(parent, 'comment parent'),
            'authorName': value(comment, 'wp:comment_author', required=False),
            'publishedAt': source_date(comment, 'comment_date', 'comment_date_gmt'),
            'html': html, 'status': 'approved',
        })
    ids = [c['sourceId'] for c in result]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate approved comment ID')
    by_id = {c['sourceId']: c for c in result}
    for comment in result:
        seen = {comment['sourceId']}
        parent = comment['parentId']
        while parent is not None:
            if parent not in by_id:
                raise ValueError('approved comment parent is absent or not public; requires reviewed handling')
            if parent in seen:
                raise ValueError('comment parent cycle')
            seen.add(parent)
            parent = by_id[parent]['parentId']
    return sorted(result, key=lambda c: int(c['sourceId'].split(':')[1]))


class References(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.html = html
        self.asset_classes = set()
        self.urls = set()
        self.embeds = []
        self.iframe_start = None
        self.iframe_url = None
        self.lines = html.splitlines(keepends=True)
        self.feed(html)

    def position(self):
        line, column = self.getpos()
        return sum(len(x) for x in self.lines[:line - 1]) + column

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.asset_classes.update('wp:' + i for i in re.findall(r'\bwp-image-([1-9][0-9]*)\b', attrs.get('class') or ''))
        self.urls.update(v for k, v in attrs.items() if k in ('src', 'href', 'poster') and v)
        if tag == 'iframe':
            if self.iframe_start is not None:
                raise ValueError('nested iframe is unsupported')
            self.iframe_start = self.position()
            self.iframe_url = attrs.get('src')

    def handle_endtag(self, tag):
        if tag == 'iframe' and self.iframe_start is not None:
            url = self.iframe_url
            if not url or urlsplit(url).scheme not in ('https', 'http') or not urlsplit(url).hostname:
                raise ValueError('iframe requires an absolute HTTP(S) source')
            end = self.html.find('>', self.position()) + 1
            self.embeds.append({'provider': urlsplit(url).hostname, 'url': url,
                                'html': self.html[self.iframe_start:end]})
            self.iframe_start = None

    def close(self):
        super().close()
        if self.iframe_start is not None:
            raise ValueError('unclosed iframe')


def validate_manifest(manifest):
    if (not isinstance(manifest, dict) or set(manifest) != {'schemaVersion', 'sourceReference', 'items'}
            or manifest['schemaVersion'] != '1.0.0' or not isinstance(manifest['sourceReference'], str)
            or not manifest['sourceReference'] or not isinstance(manifest['items'], dict)):
        raise ValueError('manifest requires schemaVersion 1.0.0, opaque sourceReference and items object')
    allowed = {'originalSha256', 'html', 'htmlSha256', 'reference', 'directHtmlReference',
               'excerptHtml', 'originalExcerptSha256', 'reviewedPostMeta'}
    for source_id, entry in manifest['items'].items():
        if not re.fullmatch(r'wp:[1-9][0-9]*', source_id) or not isinstance(entry, dict) or set(entry) - allowed:
            raise ValueError('manifest contains an invalid item or unknown field')
        if not all(isinstance(v, str) for k, v in entry.items() if k != 'reviewedPostMeta'):
            raise ValueError(f'{source_id}: snapshot fields must be strings')
        if 'directHtmlReference' in entry and {'html', 'htmlSha256', 'reference'} & set(entry):
            raise ValueError(f'{source_id}: choose snapshot or direct HTML equality evidence, not both')
        reviewed = entry.get('reviewedPostMeta', {})
        if not isinstance(reviewed, dict) or any(not isinstance(k, str) or not isinstance(v, str) or not v
                                                 for k, v in reviewed.items()):
            raise ValueError(f'{source_id}: reviewedPostMeta maps keys to opaque disposition evidence')


def rendered(original, entry, reference):
    snapshot_fields = {'originalSha256', 'html', 'htmlSha256', 'reference'}
    if {'html', 'htmlSha256', 'reference'} & set(entry):
        if not snapshot_fields <= set(entry):
            raise ValueError('snapshot requires originalSha256, html, htmlSha256 and reference')
        if entry['originalSha256'] != sha(original) or entry['htmlSha256'] != sha(entry['html']):
            raise ValueError('stale/tampered snapshot: exact original or rendered HTML hash differs')
        if not entry['reference']:
            raise ValueError('snapshot reference is empty')
        html, kind, reference = entry['html'], 'rendered-snapshot', entry['reference']
    else:
        if original and (UNRESOLVED.search(original) or not BLOCK_HTML.match(original)):
            raise ValueError('shortcode, block or wpautop rendering needs a frozen rendered snapshot bound to originalSha256')
        if original and (not entry.get('directHtmlReference') or entry.get('originalSha256') != sha(original)):
            raise ValueError('HTML rendering needs a frozen rendered snapshot or hash-bound directHtmlReference attesting exact rendered equality')
        reference = entry.get('directHtmlReference', reference)
        html, kind = original, 'direct-html'
    if UNRESOLVED.search(html):
        raise ValueError('rendered HTML still contains an unresolved shortcode/block')
    return {'format': 'wordpress-html', 'original': original, 'html': html,
            'provenance': {'kind': kind, 'reference': reference,
                           'originalSha256': sha(original), 'htmlSha256': sha(html)}}


def _normalize(item, source_id, authors, taxonomies, language, manifest, asset_urls, known_assets):
    unknown = {e.tag for e in item} - KNOWN_ITEM_FIELDS
    if unknown:
        raise ValueError('unsupported item fields: ' + ', '.join(sorted(unknown)))
    entry = manifest['items'].get(source_id, {})
    original = value(item, 'content:encoded', required=False)
    body = rendered(original, entry, manifest['sourceReference'] + '#' + source_id)
    excerpt = value(item, 'excerpt:encoded', required=False)
    if 'excerptHtml' in entry or 'originalExcerptSha256' in entry:
        if entry.get('originalExcerptSha256') != sha(excerpt) or 'excerptHtml' not in entry:
            raise ValueError('stale/incomplete excerpt snapshot')
        excerpt = entry['excerptHtml']
    if UNRESOLVED.search(excerpt):
        raise ValueError('excerpt contains unresolved shortcode/block; needs an excerpt snapshot')
    creator = value(item, 'dc:creator')
    if creator not in authors:
        raise ValueError('creator has no WXR author record')
    url = value(item, 'link')
    path = canonical(url)
    groups = {'category': [], 'post_tag': []}
    for term in item.findall('category'):
        domain, slug = term.get('domain'), term.get('nicename')
        if domain not in groups:
            raise ValueError(f'unsupported taxonomy {domain}; needs a contract/rendering decision')
        key = (domain, slug)
        if key not in taxonomies:
            raise ValueError(f'taxonomy term {domain}/{slug} missing from WXR definitions')
        mapped = taxonomies[key]
        if (term.text or '') != mapped['name']:
            raise ValueError(f'taxonomy term name differs for {domain}/{slug}')
        if mapped in groups[domain]:
            raise ValueError('duplicate taxonomy assignment')
        groups[domain].append(mapped)
    meta = {}
    for node in item.findall('wp:postmeta', NS):
        key = value(node, 'wp:meta_key')
        meta.setdefault(key, []).append(value(node, 'wp:meta_value', required=False))
    unreviewed = set(meta) - SAFE_META - set(entry.get('reviewedPostMeta', {}))
    if unreviewed:
        raise ValueError('unsupported postmeta needs recorded disposition evidence: ' + ', '.join(sorted(unreviewed)))
    featured = None
    if '_thumbnail_id' in meta:
        if len(meta['_thumbnail_id']) != 1:
            raise ValueError('duplicate featured attachment metadata')
        if meta['_thumbnail_id'][0] not in ('', '0'):
            featured = 'wp:' + positive_id(meta['_thumbnail_id'][0], 'featured attachment')
    refs = References(body['html'])
    refs.close()
    asset_ids = refs.asset_classes | {asset_urls[u] for u in refs.urls if u in asset_urls}
    if featured:
        asset_ids.add(featured)
    unknown_assets = asset_ids - known_assets
    if unknown_assets:
        raise ValueError('unresolved attachment IDs: ' + ', '.join(sorted(unknown_assets)))
    normalized = {
        'sourceId': source_id, 'kind': value(item, 'wp:post_type'), 'status': 'publish',
        'path': path, 'canonicalUrl': url, 'title': value(item, 'title'), 'language': language,
        'publishedAt': source_date(item, 'post_date', 'post_date_gmt'),
        'modifiedAt': source_date(item, 'post_modified', 'post_modified_gmt'),
        'author': authors[creator], 'categories': groups['category'], 'tags': groups['post_tag'],
        'content': body, 'assetIds': sorted(asset_ids),
        'embeds': refs.embeds,
        'sourceMetadata': {'guid': value(item, 'guid'), 'excerptHtml': excerpt,
                           'commentStatus': value(item, 'wp:comment_status'),
                           'pingStatus': value(item, 'wp:ping_status'), 'featuredAssetId': featured},
        'comments': comments(item),
    }
    validate_document('content', {'schemaVersion': '1.0.0', 'items': [normalized]})
    source_metadata = {'sourceId': source_id, 'slug': value(item, 'wp:post_name', required=False),
                       'parentId': value(item, 'wp:post_parent', required=False),
                       'menuOrder': value(item, 'wp:menu_order', required=False),
                       'isSticky': value(item, 'wp:is_sticky', required=False),
                       'postMeta': meta, 'reviewedPostMeta': entry.get('reviewedPostMeta', {}),
                       'timezoneName': None}
    return normalized, source_metadata


def import_wxr(data, manifest=None, assets=None, previous=None):
    """Return (public bundle, private report); failures never return partial content.

    The input must be a COMPLETE export. --previous compares a final full export
    against an earlier import; omission is treated as removal, never as an upsert.
    """
    if manifest is None:
        manifest = {'schemaVersion': '1.0.0', 'sourceReference': 'owner-wxr', 'items': {}}
    report = {'schemaVersion': '1.0.0', 'sourceSha256': hashlib.sha256(data).hexdigest(),
              'sourceReference': manifest.get('sourceReference') if isinstance(manifest, dict) else None,
              'scope': 'complete-export',
              'sourceCompleteness': 'unverified', 'errors': [], 'excludedByReason': {},
              'sourceMetadata': [], 'attachments': [], 'unresolvedBehavior': [], 'unresolvedRecords': [],
              'records': []}
    errors = report['errors']
    try:
        validate_manifest(manifest)
        # ElementTree expands internal entities; disallow declarations before parsing.
        if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper() or b'\x00' in data:
            raise ValueError('DTD/entity declarations and non-UTF-8 XML are unsupported')
        root = ET.fromstring(data)
        channel = root.find('channel')
        if root.tag != 'rss' or channel is None or value(channel, 'wp:wxr_version') != '1.2':
            raise ValueError('expected one RSS channel containing WordPress WXR 1.2')
        if len(root.findall('channel')) != 1:
            raise ValueError('expected exactly one WXR channel')
        language = value(channel, 'language')
        authors, taxonomies, author_ids, term_ids = {}, {}, set(), set()
        for node in channel.findall('wp:author', NS):
            login = value(node, 'wp:author_login')
            if login in authors:
                raise ValueError('duplicate WXR author login')
            author_id = 'wp-author:' + positive_id(value(node, 'wp:author_id'), 'author ID')
            if author_id in author_ids:
                raise ValueError('duplicate WXR author ID')
            author_ids.add(author_id)
            authors[login] = {'sourceId': author_id,
                              'name': value(node, 'wp:author_display_name')}
        for domain, tag, slug_field, name_field, prefix in (
                ('category', 'category', 'category_nicename', 'cat_name', 'wp-category:'),
                ('post_tag', 'tag', 'tag_slug', 'tag_name', 'wp-tag:')):
            for node in channel.findall('wp:' + tag, NS):
                slug = value(node, 'wp:' + slug_field)
                key = (domain, slug)
                if key in taxonomies:
                    raise ValueError('duplicate WXR taxonomy definition')
                term_id = prefix + positive_id(value(node, 'wp:term_id'), 'term ID')
                if term_id in term_ids:
                    raise ValueError('duplicate WXR taxonomy term ID')
                term_ids.add(term_id)
                taxonomies[key] = {'sourceId': term_id,
                                   'slug': slug, 'name': value(node, 'wp:' + name_field)}
        asset_urls, known_assets = {}, set()
        if assets is not None:
            validate_document('assets', assets)
            for asset in assets['assets']:
                if asset['assetId'] in known_assets or asset['sourceUrl'] in asset_urls:
                    raise ValueError('duplicate asset identity/source URL')
                known_assets.add(asset['assetId'])
                asset_urls[asset['sourceUrl']] = asset['assetId']
        records = channel.findall('item')
        ids = set()
        for item in records:
            source_id = 'wp:' + positive_id(value(item, 'wp:post_id'), 'post ID')
            if source_id in ids:
                raise ValueError('duplicate WXR item ID ' + source_id)
            ids.add(source_id)
            if value(item, 'wp:post_type') == 'attachment':
                known_assets.add(source_id)
                url = value(item, 'wp:attachment_url')
                if url in asset_urls and asset_urls[url] != source_id:
                    raise ValueError('attachment source URL identity conflict')
                asset_urls[url] = source_id
                report['attachments'].append({'sourceId': source_id, 'sourceUrl': url})
        report['sourceRecordCount'] = len(records)
        counts = Counter()
        items = []
        for item in records:
            source_id = 'wp:' + value(item, 'wp:post_id')
            kind, status = value(item, 'wp:post_type'), value(item, 'wp:status')
            observed_url = item.findtext('link', default='')
            evidence = {'sourceId': source_id, 'kind': kind, 'status': status, 'disposition': 'failed'}
            report['records'].append(evidence)
            if kind == 'attachment':
                counts['attachment-delegated-to-MIG-03'] += 1
                evidence['disposition'] = 'attachment-delegated-to-MIG-03'
                continue
            if status in ('draft', 'pending', 'private', 'future', 'trash', 'auto-draft', 'inherit'):
                counts['nonpublic:' + status] += 1
                evidence['disposition'] = 'excluded-nonpublic'
                continue
            if status != 'publish':
                errors.append(f'{source_id}: unsupported publication status {status}')
                continue
            if value(item, 'wp:post_password', required=False):
                counts['password-protected'] += 1
                evidence['disposition'] = 'excluded-password-protected'
                continue
            if kind not in ('post', 'page'):
                errors.append(f'{source_id}: unsupported public post type {kind}; requires explicit migration disposition')
                report['unresolvedRecords'].append({'sourceId': source_id, 'kind': kind,
                                                     'canonicalUrl': observed_url})
                continue
            try:
                normalized, source_metadata = _normalize(item, source_id, authors, taxonomies, language,
                                                          manifest, asset_urls, known_assets)
                items.append(normalized)
                evidence['disposition'] = 'public-content'
                report['sourceMetadata'].append(source_metadata)
                for field in ('parentId', 'menuOrder', 'isSticky'):
                    if source_metadata[field] not in ('', '0'):
                        report['unresolvedBehavior'].append({'sourceId': source_id, 'field': field,
                                                             'value': source_metadata[field]})
            except (ValueError, ContractError) as error:
                errors.append(f'{source_id}: {error}')
                report['unresolvedRecords'].append({'sourceId': source_id, 'kind': kind,
                                                     'canonicalUrl': observed_url})
        report['excludedByReason'] = dict(sorted(counts.items()))
        report['publicRecordCount'] = len(items)
        report['failedRecordCount'] = sum(r['disposition'] == 'failed' for r in report['records'])
        if set(manifest['items']) - ids:
            errors.append('snapshot manifest references IDs absent from this complete export')
        paths = [item['path'] for item in items]
        if len(paths) != len(set(paths)):
            errors.append('duplicate public canonical path')
        bundle = {'schemaVersion': '1.0.0', 'items': sorted(items, key=lambda i: int(i['sourceId'].split(':')[1]))}
        if previous is not None:
            validate_document('content', previous)
            before = {i['sourceId']: i for i in previous['items']}
            if len(before) != len(previous['items']):
                raise ValueError('previous content bundle has duplicate source IDs')
            after = {i['sourceId']: i for i in items}
            report['delta'] = {key: sorted(values) for key, values in {
                'added': after.keys() - before.keys(), 'removed': before.keys() - after.keys(),
                'changed': {i for i in after.keys() & before.keys() if after[i] != before[i]},
                'unchanged': {i for i in after.keys() & before.keys() if after[i] == before[i]},
            }.items()}
        if errors:
            raise ImportFailure(errors, report)
        validate_document('content', bundle)
        return bundle, report
    except ImportFailure:
        raise
    except (ValueError, ET.ParseError, ContractError) as error:
        errors.append(str(error))
        raise ImportFailure(errors, report) from error


def serialize(document):
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + '\n'
