"""Hugo handoff preserves reviewed HTML and replaces stale generated records."""

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.import_content.hugo import (HugoExportError, prepare_hugo, sanitize_public_html,
                                         write_hugo)
from scripts.import_content.markdown import html_to_markdown


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads((ROOT / 'fixtures/v1/content.json').read_text(encoding='utf-8'))
BUILD_TIME = '2026-10-24T12:00:00-07:00'


class HugoTests(unittest.TestCase):
    def test_comment_threads_and_submission_forms_are_removed_but_article_html_remains(self):
        source = ('<article><h1>Public article</h1><p>Keep this text.</p>'
                  '<div id="comments" class="comments-area"><article class="comment">'
                  '<strong>Private commenter placeholder</strong><p>Private comment placeholder</p>'
                  '</article></div><div id="respond" class="comment-respond">'
                  '<form id="commentform" action="https://example.invalid/wp-comments-post.php">'
                  '<textarea name="comment"></textarea></form></div>'
                  '<form action="/contact/submit"><input name="email"></form>'
                  '<a href="#comments">3 comments</a>'
                  '<p><script src="https://example.invalid/embed.js"><span data-mce-type="bookmark" '
                  'class="mce_SELRES_start">marker</span></script></p>'
                  '<p>Keep the closing article text.</p></article>')
        cleaned, report = sanitize_public_html(source)
        self.assertIn('Public article', cleaned)
        self.assertIn('Keep this text.', cleaned)
        self.assertIn('Keep the closing article text.', cleaned)
        self.assertNotIn('Private commenter placeholder', cleaned)
        self.assertNotIn('Private comment placeholder', cleaned)
        self.assertNotIn('wp-comments-post.php', cleaned)
        self.assertNotIn('href="#comments"', cleaned)
        self.assertNotIn('mce_SELRES_start', cleaned)
        self.assertIn('<script src="https://example.invalid/embed.js"></script>', cleaned)
        self.assertIn('3 comments', cleaned)
        self.assertNotRegex(cleaned, r'<form\b')
        self.assertEqual(report, {'commentBlockCount': 2, 'formCount': 2,
                                  'commentFormCount': 1, 'otherFormCount': 1,
                                  'commentLinkCount': 1, 'editorMarkerCount': 1})

    def test_markdown_post_path_and_source_metadata(self):
        files, report = prepare_hugo(FIXTURE, BUILD_TIME)
        self.assertEqual(report['inputRecordCount'], 2)
        self.assertEqual(report['outputRecordCount'], 2)
        self.assertEqual(set(files), {'posts/wp-101.md', 'page/wp-102.html'})
        first = files['posts/wp-101.md'].decode('utf-8')
        metadata, end = json.JSONDecoder().raw_decode(first)
        body = first[end + 1:]
        self.assertEqual(body, html_to_markdown(FIXTURE['items'][0]['content']['html']))
        self.assertIn('**', body)
        self.assertEqual(metadata['url'], '/2020/01/02/fixture-post/')
        self.assertEqual(metadata['date'], '2020-01-02T03:04:05-04:00')
        self.assertEqual(metadata['migration']['guid'], 'https://example.invalid/?p=101')
        self.assertEqual(metadata['migration']['author'], FIXTURE['items'][0]['author'])
        self.assertEqual(metadata['migration']['categories'], FIXTURE['items'][0]['categories'])
        self.assertEqual(metadata['migration']['assetIds'], ['wp:900'])
        self.assertTrue(FIXTURE['items'][0]['comments'])
        self.assertNotIn('comments', metadata['migration'])
        self.assertNotIn(FIXTURE['items'][0]['comments'][0]['authorName'], first)
        self.assertEqual(report['deferredComments'], {
            'recordCount': 1, 'commentCount': 1,
            'items': [{'sourceId': 'wp:101', 'count': 1,
                       'disposition': 'owner-publication-decision'}]})
        self.assertEqual(report['items'][0]['fileSha256'], hashlib.sha256(files['posts/wp-101.md']).hexdigest())

    def test_repeat_export_and_final_delta_remove_stale_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / 'content' / 'imported'
            first = write_hugo(FIXTURE, destination, BUILD_TIME)
            before = (destination / 'posts/wp-101.md').read_bytes()
            self.assertEqual(write_hugo(FIXTURE, destination, BUILD_TIME), first)
            self.assertEqual((destination / 'posts/wp-101.md').read_bytes(), before)
            changed = copy.deepcopy(FIXTURE)
            changed['items'].pop()
            second = write_hugo(changed, destination, BUILD_TIME)
            self.assertEqual(second['outputRecordCount'], 1)
            self.assertFalse((destination / 'page/wp-102.html').exists())

    def test_nonpublic_and_tampered_html_fail_before_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / 'generated'
            private = copy.deepcopy(FIXTURE)
            private['items'][0]['status'] = 'draft'
            with self.assertRaisesRegex(HugoExportError, 'nonpublic status'):
                write_hugo(private, destination, BUILD_TIME)
            self.assertFalse(destination.exists())
            broken = copy.deepcopy(FIXTURE)
            broken['items'][0]['content']['html'] += 'tampered'
            with self.assertRaises(ValueError):
                write_hugo(broken, destination, BUILD_TIME)
            self.assertFalse(destination.exists())

    def test_future_publication_has_recorded_exclusion(self):
        files, report = prepare_hugo(FIXTURE, '2019-01-01T00:00:00Z')
        self.assertEqual(files, {})
        self.assertEqual([e['reason'] for e in report['excluded']],
                         ['future-at-build-time', 'future-at-build-time'])
        with self.assertRaisesRegex(HugoExportError, 'explicit offset'):
            prepare_hugo(FIXTURE, '2026-10-24T12:00:00')

    def test_existing_non_generated_destination_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / 'content'
            destination.mkdir()
            (destination / 'owner.html').write_text('keep', encoding='utf-8')
            with self.assertRaisesRegex(HugoExportError, 'not an importer-owned directory'):
                write_hugo(FIXTURE, destination, BUILD_TIME)
            alias = root / 'alias'
            alias.symlink_to(destination, target_is_directory=True)
            with self.assertRaisesRegex(HugoExportError, 'symlink'):
                write_hugo(FIXTURE, alias, BUILD_TIME)
            self.assertEqual((destination / 'owner.html').read_text(encoding='utf-8'), 'keep')

    def test_modified_generated_file_is_never_discarded(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / 'imported'
            write_hugo(FIXTURE, destination, BUILD_TIME)
            target = destination / 'posts/wp-101.md'
            target.write_text('owner edit', encoding='utf-8')
            with self.assertRaisesRegex(HugoExportError, 'generated file changed'):
                write_hugo(FIXTURE, destination, BUILD_TIME)
            self.assertEqual(target.read_text(encoding='utf-8'), 'owner edit')


if __name__ == '__main__':
    unittest.main()
