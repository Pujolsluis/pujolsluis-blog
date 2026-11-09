"""Rewrite selected owned media URLs for project previews without changing HTML structure."""

import argparse
import hashlib
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


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


def upload_path(url):
    """Extract an exact upload URL path; never infer a media target from it alone."""
    parts = urlsplit(html.unescape(url))
    if not is_owned(url):
        return None
    path = unquote(parts.path)
    if parts.hostname in ('i0.wp.com', 'i1.wp.com', 'i2.wp.com', 'i3.wp.com'):
        path = re.sub(r'^/(?:www\.)?pujolsluis\.com', '', path, count=1)
    prefix = '/wp-content/uploads/'
    if not path.startswith(prefix):
        return None
    suffix = path[len(prefix):]
    if not suffix or any(segment in ('', '.', '..') for segment in suffix.split('/')):
        return None
    return suffix


def _recovered_outputs(inventory, static_root, evidence):
    """Verify hash-bound case-variant recoveries and return their selected outputs."""
    if evidence is None:
        return {}
    if not isinstance(evidence, dict):
        raise ValueError('recovery evidence must be an object')
    missing_by_path = {row.get('url_path'): row for row in inventory.get('missing_references', [])}
    assets_by_path = {row.get('source_path'): row for row in inventory.get('assets', [])}
    recovered = {}
    for row in evidence.get('recovered_references', []):
        path = row.get('url_path', '')
        source_path = row.get('source_path', '')
        source_sha256 = row.get('source_sha256', '')
        output_path = row.get('output_path', '')
        output_sha256 = row.get('output_sha256', '')
        output_bytes = row.get('output_bytes')
        missing = missing_by_path.get(path)
        if not missing:
            raise ValueError('recovery path is not a manifest missing reference: ' + path)
        if not path or path.casefold() != source_path.casefold() or path == source_path:
            raise ValueError('recovery must be a case-only source path match: ' + path)
        candidate = next((item for item in missing.get('case_variant_candidates', [])
                          if item.get('source_path') == source_path
                          and item.get('source_sha256') == source_sha256), None)
        asset = assets_by_path.get(source_path)
        if not candidate or not asset or asset.get('source_sha256') != source_sha256:
            raise ValueError('recovery source hash does not match MIG-03 evidence: ' + path)
        if (not output_path.startswith('wp-content/uploads/')
                or any(part in ('', '.', '..') for part in Path(output_path).parts)):
            raise ValueError('recovery output must be a safe uploads path: ' + path)
        selected = next((item for item in asset.get('output_paths', [])
                         if item.get('path', '').casefold() == output_path.casefold()), None)
        if (not selected or selected.get('sha256') != output_sha256
                or selected.get('bytes') != output_bytes):
            raise ValueError('recovery output does not match optimized selected asset: ' + path)
        target = Path(static_root) / output_path
        if (not target.is_file() or target.is_symlink()
                or hashlib.sha256(target.read_bytes()).hexdigest() != output_sha256
                or target.stat().st_size != output_bytes):
            raise ValueError('recovery output missing or checksum mismatch: ' + output_path)
        recovered[path] = {'path': output_path, 'sha256': output_sha256,
                           'bytes': output_bytes}
    return recovered


def selected_media_map(inventory, source_urls, preview_base, static_root, recovery_evidence=None):
    """Select only MIG-03 included exact output files, verifying their bytes."""
    if not isinstance(inventory, dict) or inventory.get('schema_version') is None:
        raise ValueError('expected MIG-03 asset inventory')
    selected = {}
    recovered = _recovered_outputs(inventory, static_root, recovery_evidence)
    for field in ('published_body_path_mappings', 'rendered_page_path_mappings',
                  'live_rendered_body_path_mappings', 'attachment_route_path_mappings'):
        for row in inventory.get(field, []):
            if row['status'] != 'included':
                continue
            outputs = [asset['output'] for asset in row['source_assets']]
            if not outputs or len({output['path'] for output in outputs}) != 1:
                raise ValueError('included media path has ambiguous selected output')
            path, output = row['public_url_path'], outputs[0]
            if path in selected and selected[path] != output:
                raise ValueError('conflicting MIG-03 media selection')
            selected[path] = output
    mapping, unresolved = [], []
    checked = set()
    for url in sorted(set(source_urls)):
        if not is_owned(url):
            continue
        path = upload_path(url)
        output = selected.get(path) or recovered.get(path)
        if output is None:
            unresolved.append(url)
            continue
        relative = output['path']
        if not isinstance(relative, str) or not relative.startswith('wp-content/uploads/'):
            raise ValueError('MIG-03 selected path is not under static uploads')
        if relative not in checked:
            file = Path(static_root) / relative
            if (not file.is_file() or file.is_symlink()
                    or hashlib.sha256(file.read_bytes()).hexdigest() != output['sha256']):
                raise ValueError('MIG-03 selected media file missing or checksum mismatch: ' + relative)
            checked.add(relative)
        mapping.append({'sourceUrl': url, 'targetPath': '/' + relative})
    document = {'schemaVersion': '1.0.0', 'previewBase': preview_base, 'mappings': mapping}
    validate_media_map(document)
    return document, unresolved


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


def main(argv=None):
    parser = argparse.ArgumentParser(description='Build a private selected media map from MIG-03 evidence')
    parser.add_argument('inventory', type=Path)
    parser.add_argument('static_root', type=Path)
    parser.add_argument('hugo_report', type=Path, help='first Hugo report listing unresolvedOwnedMedia')
    parser.add_argument('output', type=Path)
    parser.add_argument('--preview-base', required=True)
    parser.add_argument('--recovery-evidence', type=Path,
                        default=Path(__file__).resolve().parents[2]
                        / 'migration/assets/recovery-evidence.json')
    args = parser.parse_args(argv)
    try:
        if any((parent / '.git').exists() for parent in (args.output.parent, *args.output.parent.parents)):
            raise ValueError('media map output must be outside Git checkouts')
        inventory = json.loads(args.inventory.read_text(encoding='utf-8'))
        report = json.loads(args.hugo_report.read_text(encoding='utf-8'))
        urls = [row['sourceUrl'] for row in report['unresolvedOwnedMedia']]
        evidence = (json.loads(args.recovery_evidence.read_text(encoding='utf-8'))
                    if args.recovery_evidence.is_file() else None)
        document, unresolved = selected_media_map(
            inventory, urls, args.preview_base, args.static_root, evidence)
        args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f'Media map selection failed: {error}\n')
    print(f'Selected {len(document["mappings"])} owned URLs; {len(unresolved)} remain unmapped.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
