"""Hash-bound live head, media rewrites and attachment-page regression cases."""

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.import_content.attachments import freeze_attachment_pages, validate_attachment_manifest
from scripts.import_content.head import FIELDS, extract_source_head, validate_head_manifest
from scripts.import_content.hugo import prepare_hugo
from scripts.import_content.media import rewrite_html, selected_media_map, validate_media_map


ROOT = Path(__file__).resolve().parents[2]
BUNDLE = json.loads((ROOT / 'fixtures/v1/content.json').read_text())
BUILD_TIME = '2026-10-24T12:00:00-07:00'


class LiveEvidenceTests(unittest.TestCase):
    def head_manifest(self, root):
        items = []
        for item in BUNDLE['items']:
            fields = dict.fromkeys(FIELDS)
            fields.update(title='Live ' + item['sourceId'], canonical=item['canonicalUrl'],
                          ogImage='https://i0.wp.com/www.pujolsluis.com/wp-content/uploads/hero.jpg')
            raw = (f'<html><head><title>{fields["title"]}</title>'
                   f'<link rel="canonical" href="{fields["canonical"]}">'
                   f'<meta property="og:image" content="{fields["ogImage"]}">'
                   '</head></html>').encode()
            digest = hashlib.sha256(raw).hexdigest()
            (root / (digest + '.html')).write_bytes(raw)
            items.append({'sourceId': item['sourceId'], 'canonicalUrl': item['canonicalUrl'],
                          'sourcePageSha256': digest, 'sourcePageReference': digest + '.html',
                          'fields': fields})
        return {'schemaVersion': '1.0.0', 'items': items}

    def test_source_head_exact_values_absences_and_hash_binding(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            document = self.head_manifest(root)
            self.assertEqual(len(validate_head_manifest(document, BUNDLE, root)), 2)
            media = {'schemaVersion': '1.0.0', 'previewBase': '/project/', 'mappings': [{
                'sourceUrl': document['items'][0]['fields']['ogImage'],
                'targetPath': '/wp-content/uploads/hero.jpg'}]}
            files, report = prepare_hugo(BUNDLE, BUILD_TIME, document, root, media)
            front = json.loads(files['post/wp-101.html'].rsplit(b'}\n', 1)[0] + b'}')
            self.assertEqual(front['title'], BUNDLE['items'][0]['title'])
            self.assertEqual(front['seoTitle'], 'Live wp:101')
            self.assertIsNone(front['description'])
            self.assertEqual(front['migration']['sourceHead']['fields']['ogImage'],
                             document['items'][0]['fields']['ogImage'])
            self.assertEqual(front['ogImage'], '/project/wp-content/uploads/hero.jpg')
            self.assertEqual(report['sourceHeadCoverage'], 2)
            duplicate = copy.deepcopy(document)
            duplicate['items'].append(copy.deepcopy(duplicate['items'][0]))
            with self.assertRaisesRegex(ValueError, 'duplicate or conflicting'):
                validate_head_manifest(duplicate, BUNDLE, root)
            _, diagnostics = extract_source_head(
                '<head><title>A</title><title>B</title><meta name="description" content="x"></head>')
            self.assertIn('title', diagnostics['duplicates'])
            self.assertIn('title', diagnostics['conflicts'])
            self.assertIn('twitterTitle', diagnostics['missing'])
            (root / document['items'][0]['sourcePageReference']).write_text('tampered')
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                validate_head_manifest(document, BUNDLE, root)

    def test_owned_media_attributes_and_css_rewrite_with_explicit_gaps(self):
        source = 'https://i0.wp.com/www.pujolsluis.com/wp-content/uploads/image.jpg?fit=300%2C200&ssl=1'
        mapping, base = validate_media_map({'schemaVersion': '1.0.0',
                                            'previewBase': '/pujolsluis-blog/',
                                            'mappings': [{'sourceUrl': source,
                                                          'targetPath': '/wp-content/uploads/image.jpg'}]})
        body = (f'<img src="{source.replace("&", "&amp;")}" '
                f'srcset="{source} 300w, https://example.org/external.jpg 600w" '
                f'style="background:url({source})">'
                '<video poster="https://www.pujolsluis.com/wp-content/uploads/missing.jpg"></video>'
                f'<script>const literal = "src=\\"{source}\\"";</script>')
        rendered, missing = rewrite_html(body, mapping, base)
        self.assertIn('/pujolsluis-blog/wp-content/uploads/image.jpg', rendered)
        self.assertIn('https://example.org/external.jpg', rendered)
        self.assertIn(f'const literal = "src=\\"{source}\\"";', rendered)
        self.assertEqual(missing, ['https://www.pujolsluis.com/wp-content/uploads/missing.jpg'])
        with self.assertRaisesRegex(ValueError, 'conflicting'):
            validate_media_map({'schemaVersion': '1.0.0', 'previewBase': '/', 'mappings': [
                {'sourceUrl': source, 'targetPath': '/a.jpg'},
                {'sourceUrl': source, 'targetPath': '/b.jpg'}]})

    def test_inventory_map_requires_selected_file_checksum(self):
        source = 'https://i0.wp.com/www.pujolsluis.com/wp-content/uploads/2020/01/a.jpg?fit=300%2C200'
        rendered_only = 'https://www.pujolsluis.com/wp-content/uploads/2020/01/live-only.jpg'
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / 'wp-content/uploads/2020/01/a.jpg'
            target.parent.mkdir(parents=True)
            target.write_bytes(b'optimized image')
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            live_target = root / 'wp-content/uploads/2020/01/live-only.jpg'
            live_target.write_bytes(b'live rendered image')
            live_digest = hashlib.sha256(live_target.read_bytes()).hexdigest()
            inventory = {'schema_version': '1.0.0', 'published_body_path_mappings': [{
                'public_url_path': '2020/01/a.jpg', 'status': 'included',
                'source_assets': [{'output': {'path': 'wp-content/uploads/2020/01/a.jpg',
                                               'sha256': digest}}]}],
                'rendered_page_path_mappings': [], 'attachment_route_path_mappings': [],
                'live_rendered_body_path_mappings': [{
                    'public_url_path': '2020/01/live-only.jpg', 'status': 'included',
                    'source_assets': [{'output': {
                        'path': 'wp-content/uploads/2020/01/live-only.jpg',
                        'sha256': live_digest}}]}]}
            document, unresolved = selected_media_map(inventory, [source, rendered_only],
                                                      '/project/', root)
            self.assertEqual(document['mappings'], [
                {'sourceUrl': source, 'targetPath': '/wp-content/uploads/2020/01/a.jpg'},
                {'sourceUrl': rendered_only,
                 'targetPath': '/wp-content/uploads/2020/01/live-only.jpg'}])
            self.assertEqual(unresolved, [])
            live_target.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                selected_media_map(inventory, [source, rendered_only], '/project/', root)

    def test_attachment_html_page_is_distinct_from_media_file(self):
        url = 'https://www.pujolsluis.com/example-image/'
        source = ('<rss xmlns:wp="http://wordpress.org/export/1.2/"><channel><item>'
                  f'<link>{url}</link><wp:post_id>900</wp:post_id>'
                  '<wp:post_type>attachment</wp:post_type>'
                  '<wp:post_date>2020-01-02 03:04:05</wp:post_date>'
                  '<wp:post_date_gmt>2020-01-02 07:04:05</wp:post_date_gmt>'
                  '<wp:post_modified>2020-01-03 03:04:05</wp:post_modified>'
                  '<wp:post_modified_gmt>2020-01-03 07:04:05</wp:post_modified_gmt>'
                  '</item></channel></rss>').encode()
        page = ('<html><head><link rel="canonical" href="' + url + '"></head><body>'
                '<article id="post-900"><h1 class="entry-title">Live image</h1>'
                '<div class="entry-content"><p class="attachment"><img id="photo" '
                'src="https://www.pujolsluis.com/wp-content/uploads/photo.jpg" '
                'data-image-caption="&lt;p&gt;Credit&lt;/p&gt;"></p></div>'
                '</article></body></html>').encode()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            digest = hashlib.sha256(page).hexdigest()
            (root / (digest + '.html')).write_bytes(page)
            capture = {'capturedAt': '2026-10-25T00:00:00Z', 'items': [{
                'url': url, 'status': 200, 'finalUrl': url, 'contentType': 'text/html',
                'sha256': digest, 'bytes': len(page), 'privateFile': digest + '.html'}]}
            document = freeze_attachment_pages(source, capture, root)
            row = validate_attachment_manifest(document, root, hashlib.sha256(source).hexdigest())[0]
            self.assertEqual(row['path'], '/example-image/')
            self.assertEqual(row['title'], 'Live image')
            self.assertEqual(row['captionHtml'], ['<p>Credit</p>'])
            self.assertEqual(row['fragments'], ['photo'])
            files, report = prepare_hugo(BUNDLE, BUILD_TIME, attachment_manifest=document,
                                         attachment_source_root=root,
                                         wxr_sha256=hashlib.sha256(source).hexdigest())
            self.assertIn('attachment/wp-900.html', files)
            self.assertEqual(report['attachmentRouteCount'], 1)
            self.assertEqual(report['attachmentRoutes'][0]['path'], '/example-image/')
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                validate_attachment_manifest(document, root, '0' * 64)


if __name__ == '__main__':
    unittest.main()
