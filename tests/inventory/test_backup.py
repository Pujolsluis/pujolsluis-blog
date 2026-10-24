import json
from pathlib import Path
import tempfile
import unittest

from scripts.inventory.backup import SerializedMetadata, analyze_backup, checked_relative, inventory_tree


class BackupInventoryTests(unittest.TestCase):
    def test_php_metadata_reader_handles_utf8_lengths_and_rejects_objects(self):
        self.assertEqual(SerializedMetadata('a:1:{s:4:"file";s:9:"café.png";}').parse(), {'file': 'café.png'})
        for value in ('O:8:"stdClass":0:{}', 'C:1:"X":0:{}', 's:8:"café.png";', 'N;garbage'):
            with self.assertRaises(ValueError):
                SerializedMetadata(value).parse()

    def test_upload_paths_reject_encoded_traversal_and_absolute_paths(self):
        for value in ('../private', '2020/%2e%2e/private', '/absolute', '2020//image.png', '2020\\private'):
            with self.assertRaises(ValueError):
                checked_relative(value)
        self.assertEqual(checked_relative('2020/caf%C3%A9.png'), '2020/café.png')

    def test_tree_does_not_follow_symlink_files_or_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'uploads'
            root.mkdir()
            (root / 'original.png').write_bytes(b'original')
            (root / 'outside').symlink_to('/etc')
            (root / 'linked-file').symlink_to('/etc/hosts')
            files, skipped = inventory_tree(root)
            self.assertEqual(set(files), {'original.png'})
            self.assertEqual(len(skipped), 2)

    def test_report_contains_aggregates_and_public_ids_without_private_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'backup'
            (root / 'uploads' / '2020').mkdir(parents=True)
            (root / 'themes').mkdir()
            (root / 'uploads' / '2020' / 'PRIVATE_FILE_SENTINEL.png').write_bytes(b'owned original')
            xml = '''<rss xmlns:wp="http://wordpress.org/export/1.2/"><channel>
            <item><link>https://example.com/post/</link><wp:post_id>1</wp:post_id><wp:post_type>post</wp:post_type><wp:status>publish</wp:status></item>
            <item><title>DRAFT_PRIVATE_SENTINEL</title><wp:post_id>2</wp:post_id><wp:post_type>post</wp:post_type><wp:status>draft</wp:status><wp:comment><wp:comment_author_email>PRIVATE_EMAIL_SENTINEL</wp:comment_author_email></wp:comment></item>
            <item><link>https://example.com/attachment/</link><wp:post_id>3</wp:post_id><wp:post_parent>2</wp:post_parent><wp:post_type>attachment</wp:post_type><wp:status>inherit</wp:status><wp:postmeta><wp:meta_key>_wp_attached_file</wp:meta_key><wp:meta_value>2020/PRIVATE_FILE_SENTINEL.png</wp:meta_value></wp:postmeta></item>
            </channel></rss>'''
            source = root / 'owner.xml'
            source.write_text(xml)
            private = Path(directory) / 'private'
            public = {'source': 'https://example.com/', 'records': [{'sourceId': 'wp:1'}], 'assets': [],
                      'reconciliation': {'sitemapNonRestUrls': ['https://example.com/attachment/']}}
            report = analyze_backup(root, public, private)
            serialized = json.dumps(report)
            for sentinel in ('DRAFT_PRIVATE_SENTINEL', 'PRIVATE_EMAIL_SENTINEL', 'PRIVATE_FILE_SENTINEL'):
                self.assertNotIn(sentinel, serialized)
            self.assertEqual(report['wxr']['totalItems'], 3)
            self.assertEqual(report['wxr']['publicEditorialRecords'], [{'sourceId': 'wp:1', 'type': 'post', 'url': 'https://example.com/post/'}])
            self.assertEqual(report['uploads']['totalBytes'], len(b'owned original'))
            self.assertEqual(report['wxr']['attachmentParentCounts'], {'otherOrPrivateParent': 1})
            self.assertFalse(report['feasibility']['requiredDeploymentFootprintVerified'])
            self.assertEqual(source.read_text(), xml)
            manifest = private / 'private-manifest.json'
            self.assertIn('PRIVATE_FILE_SENTINEL', manifest.read_text())
            self.assertEqual(manifest.stat().st_mode & 0o777, 0o600)
            self.assertEqual(private.stat().st_mode & 0o777, 0o700)
            with self.assertRaises(ValueError):
                analyze_backup(root, public, root / 'private')


if __name__ == '__main__':
    unittest.main()
