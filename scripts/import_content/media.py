"""Rewrite selected owned media URLs for project previews without changing HTML structure."""

import html
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit


ATTR = re.compile(r'(?P<name>\b(?:src|srcset|poster|style|href|data-orig-file|data-large-file|data-src))\s*=\s*(?P<quote>["\'])(?P<value>.*?)(?P=quote)', re.I | re.S)
CSS_URL = re.compile(r'url\(\s*(["\']?)(.*?)\1\s*\)', re.I | re.S)
SRCSET_PART = re.compile(r',(?=\s+https?://|\s+/)', re.I)


def validate_media_map(document):
    if document is None:
        return {}, '/'
    if (not isinstance(document, dict) or set(document) != {'schemaVersion', 'previewBase', 'mappings'}
            or document['schemaVersion'] != '1.0.0' or not isinstance(document['mappings'], list)):
        raise ValueError('media map must contain version 1.0.0, previewBase and mappings')
    base = document['previewBase']
    if (not isinstance(base, str) or not base.startswith('/') or not base.endswith('/')
            or '//' in base or '..' in base):
        raise ValueError('previewBase must be a safe rooted path ending in /')
    mapping = {}
    for row in document['mappings']:
        if not isinstance(row, dict) or set(row) != {'sourceUrl', 'targetPath'}:
            raise ValueError('invalid media mapping row')
        source, target = row['sourceUrl'], row['targetPath']
        if (not isinstance(source, str) or urlsplit(source).scheme not in ('http', 'https')
                or not urlsplit(source).hostname or not isinstance(target, str)
                or not target.startswith('/') or target.startswith('//') or '?' in target or '#' in target
                or any(segment in ('.', '..') for segment in target.split('/'))):
            raise ValueError('invalid media source or local exact target path')
        if source in mapping and mapping[source] != target:
            raise ValueError('conflicting selected media target')
        mapping[source] = target
    return mapping, base


def is_owned(url):
    parts = urlsplit(html.unescape(url))
    host = (parts.hostname or '').lower()
    if host in ('pujolsluis.com', 'www.pujolsluis.com'):
        return True
    return host in ('i0.wp.com', 'i1.wp.com', 'i2.wp.com', 'i3.wp.com') and (
        parts.path.startswith('/www.pujolsluis.com/') or parts.path.startswith('/pujolsluis.com/'))


def rewrite_url(url, mapping, base, unresolved):
    decoded = html.unescape(url.strip())
    if not is_owned(decoded):
        return url
    target = mapping.get(decoded)
    if target is None:
        unresolved.add(decoded)
        return url
    return base.rstrip('/') + target


def _css(value, mapping, base, unresolved):
    def replace(match):
        quote, url = match.groups()
        return f'url({quote}{rewrite_url(url, mapping, base, unresolved)}{quote})'
    return CSS_URL.sub(replace, value)


def rewrite_html(body, mapping, base):
    unresolved = set()
    changes = []

    def replace_attribute(match):
        name, quote, value = match.group('name', 'quote', 'value')
        if name.lower() == 'srcset':
            parts = SRCSET_PART.split(value)
            updated = []
            for part in parts:
                candidate = re.match(r'(\s*)(\S+)(.*)', part, re.S)
                if candidate:
                    lead, url, tail = candidate.groups()
                    part = lead + rewrite_url(url, mapping, base, unresolved) + tail
                updated.append(part)
            value = ','.join(updated)
        elif name.lower() == 'style':
            value = _css(value, mapping, base, unresolved)
        elif name.lower() == 'href' and '/wp-content/uploads/' not in html.unescape(value):
            pass
        else:
            value = rewrite_url(value, mapping, base, unresolved)
        return f'{name}={quote}{value}{quote}'

    class Rewriter(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.lines = body.splitlines(keepends=True)
            self.inside_style = False

        def position(self):
            line, column = self.getpos()
            return sum(map(len, self.lines[:line - 1])) + column

        def handle_starttag(self, tag, attrs):
            start = self.position()
            original = self.get_starttag_text()
            rewritten = ATTR.sub(replace_attribute, original)
            if rewritten != original:
                changes.append((start, start + len(original), rewritten))
            if tag == 'style':
                self.inside_style = True

        handle_startendtag = handle_starttag

        def handle_endtag(self, tag):
            if tag == 'style':
                self.inside_style = False

        def handle_data(self, data):
            if self.inside_style:
                rewritten = _css(data, mapping, base, unresolved)
                if rewritten != data:
                    start = self.position()
                    changes.append((start, start + len(data), rewritten))

    parser = Rewriter()
    parser.feed(body)
    parser.close()
    result = body
    for start, end, rewritten in reversed(changes):
        result = result[:start] + rewritten + result[end:]
    return result, sorted(unresolved)
