import unittest
import xml.etree.ElementTree as ET

from scripts.inventory.capture import Capture, asset_record, parse_markup, public_record, sitemap_images, sitemap_urls


class InventoryParsingTests(unittest.TestCase):
    def test_relative_resources_srcset_embeds_and_css_are_preserved(self):
        page = parse_markup('''<title>Unicode — café</title><link rel="canonical" href="/article/">
        <img src="image.jpg" srcset="small.jpg 400w, /large.jpg 800w" alt="">
        <div style="background-image: url('/background.png')"></div>
        <iframe src="https://www.youtube.com/embed/example?start=12"></iframe>
        <a href="/guide.pdf#page=2">download</a><pre>code</pre>''', 'https://example.com/article/')
        self.assertIn('https://example.com/large.jpg', page.assets)
        self.assertIn('https://example.com/background.png', page.assets)
        self.assertIn('https://example.com/guide.pdf', page.assets)
        self.assertEqual(page.embeds, {'https://www.youtube.com/embed/example?start=12'})
        self.assertEqual(page.canonical, 'https://example.com/article/')
        self.assertEqual(page.title, 'Unicode — café')
        self.assertIn('code', page.signals)

    def test_non_http_anchor_and_image_data_are_not_discovery_targets(self):
        page = parse_markup('<a href="mailto:test@example.com">mail</a><img src="data:image/png;base64,x">', 'https://example.com/')
        self.assertFalse(page.links)
        self.assertFalse(page.assets)

    def test_namespaced_sitemaps_and_xml_errors(self):
        kind, urls = sitemap_urls(b'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>https://example.com/posts.xml</loc></sitemap></sitemapindex>')
        self.assertEqual(kind, 'sitemapindex')
        self.assertEqual(urls, ['https://example.com/posts.xml'])
        with self.assertRaises(ET.ParseError):
            sitemap_urls(b'not XML')

    def test_public_metadata_excludes_source_body_and_unrequested_private_fields(self):
        record = public_record({'id': 3, 'link': 'https://example.com/cafe/', 'title': {'rendered': 'Caf&eacute;'},
                                'content': {'rendered': '<p>Published prose</p>', 'protected': False},
                                'private_key': 'should never appear', 'password': 'private'}, 'post')
        self.assertEqual(record['sourceId'], 'wp:3')
        self.assertEqual(record['title'], 'Café')
        self.assertNotIn('private_key', record)
        self.assertNotIn('password', record)
        self.assertNotIn('content', record)
        self.assertEqual(len(record['contentSha256']), 64)

    def test_collection_follows_pagination_and_records_authoritative_totals(self):
        capture = Capture('https://example.com/', delay=0)
        capture.api = 'https://example.com/wp-json/'
        replies = iter([(b'[{"id":1}]', {'x-wp-total': '2', 'x-wp-totalpages': '2'}),
                        (b'[{"id":2}]', {'x-wp-total': '2', 'x-wp-totalpages': '2'})])
        capture.fetch = lambda url: next(replies)
        self.assertEqual(capture.collection('posts', 'id'), [{'id': 1}, {'id': 2}])
        self.assertEqual(capture.api_totals['posts']['captured'], 2)

    def test_image_sitemap_keeps_page_and_image_namespaces_separate(self):
        body = b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"><url><loc>https://example.com/post/</loc><image:image><image:loc>https://example.com/image.jpg</image:loc></image:image></url></urlset>'
        self.assertEqual(sitemap_urls(body)[1], ['https://example.com/post/'])
        self.assertEqual(sitemap_images(body), ['https://example.com/image.jpg'])

    def test_jetpack_origin_mapping_preserves_original_reference(self):
        url = 'https://i0.wp.com/example.com/wp-content/uploads/image.jpg?resize=200%2C300'
        mapped = asset_record(url, 'https://example.com/')
        self.assertEqual(mapped['url'], url)
        self.assertEqual(mapped['uploadOriginCandidate'], 'https://example.com/wp-content/uploads/image.jpg')
        self.assertTrue(mapped['wordpressUpload'])
        self.assertIsNone(asset_record('https://i0.wp.com/other.example/photo.jpg', 'https://example.com/')['uploadOriginCandidate'])

    def test_external_fetch_is_rejected(self):
        with self.assertRaises(ValueError):
            Capture('https://example.com/', delay=0).fetch('https://external.example/')


if __name__ == '__main__':
    unittest.main()
