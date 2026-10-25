"""Strict, private, hash-bound source-head evidence for Hugo previews."""

import hashlib
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


FIELDS = ('title', 'description', 'canonical', 'ogTitle', 'ogDescription', 'ogImage',
          'twitterTitle', 'twitterDescription', 'twitterImage')
META_KEYS = {'description': 'description', 'og:title': 'ogTitle',
             'og:description': 'ogDescription', 'og:image': 'ogImage',
             'twitter:title': 'twitterTitle', 'twitter:description': 'twitterDescription',
             'twitter:image': 'twitterImage'}


class HeadProbe(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.inside_head = False
        self.inside_title = False
        self.title_chunks = []
        self.values = {key: [] for key in FIELDS}
        self.feed(source)
        self.close()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'head':
            self.inside_head = True
        if not self.inside_head:
            return
        if tag == 'title':
            self.inside_title = True
            self.title_chunks = []
        if tag == 'link' and 'canonical' in (attrs.get('rel') or '').lower().split():
            self.values['canonical'].append(attrs.get('href'))
        if tag == 'meta':
            key = (attrs.get('property') or attrs.get('name') or '').lower()
            if key in META_KEYS:
                self.values[META_KEYS[key]].append(attrs.get('content'))

    handle_startendtag = handle_starttag

    def handle_data(self, data):
        if self.inside_title:
            self.title_chunks.append(data)

    def handle_endtag(self, tag):
        if tag == 'title' and self.inside_title:
            self.values['title'].append(''.join(self.title_chunks).strip())
            self.inside_title = False
        if tag == 'head':
            self.inside_head = False


def extract_source_head(source):
    """Return exact active fields and explicit missing/duplicate/conflict diagnostics."""
    probe = HeadProbe(source)
    duplicates = {key: values for key, values in probe.values.items() if len(values) > 1}
    conflicts = {key: values for key, values in duplicates.items() if len(set(values)) > 1}
    fields = {key: values[0] if values else None for key, values in probe.values.items()}
    missing = [key for key, value in fields.items() if value is None]
    return fields, {'missing': missing, 'duplicates': duplicates, 'conflicts': conflicts}


def validate_head_manifest(document, bundle, source_root):
    """Return source-ID keyed entries after verifying every public page snapshot."""
    if (not isinstance(document, dict) or set(document) != {'schemaVersion', 'items'}
            or document['schemaVersion'] != '1.0.0' or not isinstance(document['items'], list)):
        raise ValueError('source-head manifest must contain version 1.0.0 and items list')
    source_root = Path(source_root).resolve()
    expected = {item['sourceId']: item['canonicalUrl'] for item in bundle['items']}
    if len(expected) != len(bundle['items']):
        raise ValueError('duplicate source ID in content bundle')
    found = {}
    urls = set()
    for entry in document['items']:
        if (not isinstance(entry, dict) or set(entry) != {
                'sourceId', 'canonicalUrl', 'sourcePageSha256', 'sourcePageReference', 'fields'}):
            raise ValueError('invalid source-head item shape')
        source_id, url = entry['sourceId'], entry['canonicalUrl']
        if (not isinstance(source_id, str) or not re.fullmatch(r'wp:[1-9][0-9]*', source_id)
                or not isinstance(url, str) or (source_id in expected and url != expected[source_id])
                or source_id in found or url in urls):
            raise ValueError('duplicate or conflicting source-head ID/URL mapping')
        fields = entry['fields']
        if (not isinstance(fields, dict) or set(fields) != set(FIELDS)
                or any(v is not None and (not isinstance(v, str) or not v) for v in fields.values())):
            raise ValueError(f'{source_id}: source-head fields must preserve explicit values or null absences')
        if fields['canonical'] != url or fields['title'] is None:
            raise ValueError(f'{source_id}: source-head canonical/title conflict')
        for key in ('ogImage', 'twitterImage'):
            image = fields[key]
            if image and (urlsplit(image).scheme not in ('http', 'https') or not urlsplit(image).hostname):
                raise ValueError(f'{source_id}: invalid {key} URL')
        checksum = entry['sourcePageSha256']
        reference = entry['sourcePageReference']
        if (not isinstance(checksum, str) or not re.fullmatch(r'[a-f0-9]{64}', checksum)
                or not isinstance(reference, str) or not re.fullmatch(r'[a-f0-9]{64}\.html', reference)):
            raise ValueError(f'{source_id}: invalid source page checksum/reference')
        page = source_root / reference
        if not page.is_file() or page.is_symlink() or hashlib.sha256(page.read_bytes()).hexdigest() != checksum:
            raise ValueError(f'{source_id}: source page snapshot missing or checksum mismatch')
        observed, diagnostics = extract_source_head(page.read_text(encoding='utf-8'))
        if diagnostics['conflicts'] or diagnostics['duplicates'] or observed != fields:
            raise ValueError(f'{source_id}: source-head values differ from snapshot or duplicate/conflict')
        found[source_id] = entry
        urls.add(url)
    if not set(expected) <= set(found):
        raise ValueError('source-head manifest is incomplete for the selected content bundle')
    return {source_id: found[source_id] for source_id in expected}
