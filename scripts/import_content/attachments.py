"""Freeze public attachment HTML pages separately from uploaded media bytes."""

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from .importer import positive_id, source_date, value
from .routes import Anchors


VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta',
        'param', 'source', 'track', 'wbr'}


class AttachmentPage(HTMLParser):
    def __init__(self, source, source_id):
        super().__init__(convert_charrefs=False)
        self.source = source
        self.lines = source.splitlines(keepends=True)
        self.source_id = source_id
        self.stack = []
        self.bodies = []
        self.titles = []
        self.canonicals = []
        self.image_refs = set()
        self.captions = []
        self.feed(source)
        self.close()

    def position(self):
        line, column = self.getpos()
        return sum(map(len, self.lines[:line - 1])) + column

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = (attributes.get('class') or '').split()
        if tag == 'link' and attributes.get('rel') == 'canonical':
            self.canonicals.append(attributes.get('href'))
        if tag == 'img' and any(row[2] for row in self.stack):
            for field in ('src', 'data-orig-file', 'data-large-file'):
                if attributes.get(field):
                    self.image_refs.add(unescape(attributes[field]))
            if attributes.get('data-image-caption'):
                self.captions.append(unescape(attributes['data-image-caption']))
        if tag in VOID:
            return
        article = tag == 'article' and attributes.get('id') == 'post-' + self.source_id
        in_article = article or any(row[1] for row in self.stack)
        body = tag == 'div' and 'entry-content' in classes and in_article
        title = tag == 'h1' and 'entry-title' in classes and in_article
        self.stack.append((tag, in_article, body, title,
                           self.position() + len(self.get_starttag_text())))

    def handle_endtag(self, tag):
        matches = [index for index, row in enumerate(self.stack) if row[0] == tag]
        if not matches:
            return
        index = matches[-1]
        for row in self.stack[index:]:
            if row[2] and row[0] == tag:
                self.bodies.append(self.source[row[4]:self.position()])
            if row[3] and row[0] == tag:
                self.titles.append(unescape(re.sub(r'<[^>]+>', '', self.source[row[4]:self.position()])))
        self.stack = self.stack[:index]


def freeze_attachment_pages(wxr, capture_index, snapshots):
    """Require exact WXR identities, HTTP HTML captures and self canonicals."""
    source_sha = hashlib.sha256(wxr).hexdigest()
    root = ET.fromstring(wxr)
    channel = root.find('channel')
    if channel is None:
        raise ValueError('WXR channel missing')
    attachments = {}
    for item in channel.findall('item'):
        if value(item, 'wp:post_type') == 'attachment':
            url = value(item, 'link')
            if url in attachments:
                raise ValueError('duplicate WXR attachment URL')
            attachments[url] = item
    if (not isinstance(capture_index, dict) or set(capture_index) != {'capturedAt', 'items'}
            or not isinstance(capture_index['items'], list)):
        raise ValueError('invalid capture index')
    rows = []
    seen = set()
    for capture in capture_index['items']:
        if (not isinstance(capture, dict) or set(capture) != {
                'url', 'status', 'finalUrl', 'contentType', 'sha256', 'bytes', 'privateFile'}):
            raise ValueError('invalid attachment capture record')
        url = capture['url']
        if url not in attachments or url in seen or capture['status'] != 200 or capture['finalUrl'] != url:
            raise ValueError('attachment page identity/status conflict')
        seen.add(url)
        if not capture['contentType'].lower().startswith('text/html'):
            raise ValueError('attachment route is not an HTML page')
        name = capture['privateFile']
        if not re.fullmatch(r'[a-f0-9]{64}\.html', name):
            raise ValueError('unsafe attachment snapshot name')
        raw = (Path(snapshots) / name).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != capture['sha256'] or len(raw) != capture['bytes']:
            raise ValueError('attachment snapshot checksum/length mismatch')
        item = attachments[url]
        source_id = positive_id(value(item, 'wp:post_id'), 'attachment ID')
        page = AttachmentPage(raw.decode('utf-8'), source_id)
        if page.canonicals != [url] or len(page.bodies) != 1 or len(page.titles) != 1:
            raise ValueError(f'wp:{source_id}: attachment HTML title/body/canonical ambiguity')
        body = page.bodies[0]
        anchors = Anchors()
        anchors.feed(body)
        source_anchors = Anchors()
        source_anchors.feed(raw.decode('utf-8'))
        rows.append({'sourceId': 'wp:' + source_id, 'canonicalUrl': url,
                     'path': urlsplit(url).path, 'title': page.titles[0],
                     'publishedAt': source_date(item, 'post_date', 'post_date_gmt'),
                     'modifiedAt': source_date(item, 'post_modified', 'post_modified_gmt'),
                     'sourcePageSha256': digest, 'sourcePageReference': name,
                     'html': body, 'htmlSha256': hashlib.sha256(body.encode()).hexdigest(),
                     'captionHtml': page.captions, 'imageReferences': sorted(page.image_refs),
                     'fragments': anchors.values,
                     'duplicateFragments': sorted(set(anchors.duplicates)),
                     'sourceFragments': source_anchors.values,
                     'duplicateSourceFragments': sorted(set(source_anchors.duplicates))})
    paths = [row['path'] for row in rows]
    if len(paths) != len(set(paths)):
        raise ValueError('duplicate attachment route')
    rows.sort(key=lambda row: int(row['sourceId'][3:]))
    return {'schemaVersion': '1.0.0', 'wxrSha256': source_sha, 'items': rows}


def validate_attachment_manifest(document, source_root, wxr_sha256):
    if (not isinstance(document, dict) or set(document) != {'schemaVersion', 'wxrSha256', 'items'}
            or document['schemaVersion'] != '1.0.0' or document['wxrSha256'] != wxr_sha256
            or not isinstance(document['items'], list)):
        raise ValueError('attachment pages sidecar/version/WXR checksum mismatch')
    ids, paths = set(), set()
    for row in document['items']:
        required = {'sourceId', 'canonicalUrl', 'path', 'title', 'publishedAt', 'modifiedAt',
                    'sourcePageSha256', 'sourcePageReference', 'html', 'htmlSha256',
                    'captionHtml', 'imageReferences', 'fragments', 'duplicateFragments',
                    'sourceFragments', 'duplicateSourceFragments'}
        if not isinstance(row, dict) or set(row) != required:
            raise ValueError('invalid attachment page record')
        source_id, url, path = row['sourceId'], row['canonicalUrl'], row['path']
        if (not isinstance(source_id, str) or not re.fullmatch(r'wp:[1-9][0-9]*', source_id)
                or not isinstance(url, str) or urlsplit(url).path != path
                or source_id in ids or path in paths):
            raise ValueError('duplicate/conflicting attachment page identity')
        ids.add(source_id)
        paths.add(path)
        reference = row['sourcePageReference']
        if not isinstance(reference, str) or not re.fullmatch(r'[a-f0-9]{64}\.html', reference):
            raise ValueError('unsafe attachment source reference')
        page_file = Path(source_root) / reference
        if page_file.is_symlink() or not page_file.is_file():
            raise ValueError('attachment source snapshot missing or symlinked')
        raw = page_file.read_bytes()
        if hashlib.sha256(raw).hexdigest() != row['sourcePageSha256']:
            raise ValueError('attachment source snapshot checksum mismatch')
        page = AttachmentPage(raw.decode('utf-8'), source_id.split(':')[1])
        if (page.canonicals != [url] or page.titles != [row['title']]
                or page.bodies != [row['html']] or page.captions != row['captionHtml']
                or sorted(page.image_refs) != row['imageReferences']
                or hashlib.sha256(row['html'].encode()).hexdigest() != row['htmlSha256']):
            raise ValueError('attachment source page content/canonical mismatch')
        anchors = Anchors()
        anchors.feed(row['html'])
        if row['fragments'] != anchors.values or row['duplicateFragments'] != sorted(set(anchors.duplicates)):
            raise ValueError('attachment fragment mapping mismatch')
        source_anchors = Anchors()
        source_anchors.feed(raw.decode('utf-8'))
        if (row['sourceFragments'] != source_anchors.values
                or row['duplicateSourceFragments'] != sorted(set(source_anchors.duplicates))):
            raise ValueError('attachment full-page fragment mapping mismatch')
    return document['items']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wxr', type=Path)
    parser.add_argument('capture_index', type=Path)
    parser.add_argument('snapshots', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args(argv)
    try:
        if any((parent / '.git').exists() for parent in (args.output.parent, *args.output.parent.parents)):
            raise ValueError('attachment evidence output must be outside Git checkouts')
        document = freeze_attachment_pages(args.wxr.read_bytes(),
                                           json.loads(args.capture_index.read_text()), args.snapshots)
        args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    except (OSError, ValueError, ET.ParseError) as error:
        parser.exit(1, f'Attachment route freeze failed: {error}\n')
    print(f'Froze {len(document["items"])} public attachment HTML pages.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
