"""Synthetic WXR fidelity, failure, privacy and filesystem regression cases."""

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from docs.contracts.validate import validate_bundle
from scripts.import_content.__main__ import main, private_directory
from scripts.import_content.importer import ImportFailure, NS, WP, import_wxr, serialize, sha

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).parent / 'fixtures' / 'source.xml'


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.data = SOURCE.read_bytes()
        self.source = ET.fromstring(self.data)
        self.fixture = json.loads((ROOT / 'fixtures/v1/content.json').read_text())
        self.manifest = {'schemaVersion': '1.0.0', 'sourceReference': 'synthetic-wxr-v1', 'items': {
            'wp:101': {'originalSha256': sha(self.fixture['items'][0]['content']['original']),
                       'html': self.fixture['items'][0]['content']['html'],
                       'htmlSha256': sha(self.fixture['items'][0]['content']['html']),
                       'reference': 'synthetic-rendered-snapshot-v1#wp:101'},
            'wp:102': {'originalSha256': sha(self.fixture['items'][1]['content']['original']),
                       'directHtmlReference': 'synthetic-direct-html-equality-v1#wp:102'}}}

    def item(self, index=0):
        return self.source.find('channel').findall('item')[index]

    def changed_data(self):
        return ET.tostring(self.source, encoding='utf-8')

    def run_import(self, changed=False, **kwargs):
        return import_wxr(self.changed_data() if changed else self.data,
                          manifest=self.manifest, **kwargs)

    def fails(self, contains, changed=True):
        with self.assertRaises(ImportFailure) as caught:
            self.run_import(changed)
        self.assertIn(contains, str(caught.exception))
        return caught.exception.report

    def test_exact_rich_source_rendered_html_and_contract_references(self):
        bundle, report = self.run_import()
        first = bundle['items'][0]
        self.assertEqual(first['content']['original'], self.fixture['items'][0]['content']['original'])
        self.assertEqual(first['content']['html'], self.fixture['items'][0]['content']['html'])
        self.assertEqual(first['sourceMetadata']['guid'], 'opaque:original-feed-guid:101')
        self.assertEqual(first['sourceMetadata']['excerptHtml'], '<p>Synthetic excerpt.</p>')
        self.assertEqual(first['sourceMetadata']['featuredAssetId'], 'wp:900')
        self.assertEqual(first['author'], {'sourceId': 'wp-author:1', 'name': 'Fixture Author'})
        self.assertEqual(first['categories'], self.fixture['items'][0]['categories'])
        self.assertEqual(first['tags'], self.fixture['items'][0]['tags'])
        self.assertEqual(first['assetIds'], ['wp:900'])
        self.assertEqual(first['embeds'][0]['html'], self.fixture['items'][0]['embeds'][0]['html'])
        self.assertEqual(report['sourceSha256'], hashlib.sha256(self.data).hexdigest())
        assets = json.loads((ROOT / 'fixtures/v1/assets.json').read_text())
        routes = json.loads((ROOT / 'fixtures/v1/routes.json').read_text())
        validate_bundle(bundle, assets, routes)

    def test_timezones_derive_from_source_pairs_and_keep_instant(self):
        bundle, report = self.run_import()
        self.assertEqual(bundle['items'][0]['publishedAt'], '2020-01-02T03:04:05-04:00')
        self.assertEqual(bundle['items'][0]['modifiedAt'], '2020-01-03T03:04:05-04:00')
        self.assertEqual(bundle['items'][0]['comments'][0]['publishedAt'], '2020-01-04T04:00:00-04:00')
        self.assertIsNone(report['sourceMetadata'][0]['timezoneName'])
        self.item().find('wp:post_date_gmt', NS).text = '0000-00-00 00:00:00'
        self.fails('invalid post_date/post_date_gmt pair')

    def test_private_and_password_bodies_and_comment_identifiers_never_public(self):
        bundle, report = self.run_import()
        public = serialize(bundle)
        for marker in ('private-', 'unapproved-private', '192.0.2.55', 'secret-password', 'wp:103', 'wp:104'):
            self.assertNotIn(marker, public)
        self.assertEqual([c['sourceId'] for c in bundle['items'][0]['comments']], ['wp-comment:1'])
        self.assertEqual(report['sourceRecordCount'], 5)
        self.assertEqual(report['publicRecordCount'], 2)
        self.assertEqual(report['excludedByReason'], {'attachment-delegated-to-MIG-03': 1,
                                                     'nonpublic:draft': 1, 'password-protected': 1})
        self.assertEqual(report['sourceCompleteness'], 'unverified')

    def test_all_nonpublic_statuses_excluded_before_body_validation(self):
        draft = self.item(3)
        for status in ('draft', 'pending', 'private', 'future', 'trash', 'auto-draft', 'inherit'):
            draft.find('wp:status', NS).text = status
            self.assertEqual(len(self.run_import(changed=True)[0]['items']), 2)

    def test_repeat_import_is_byte_identical_and_order_independent(self):
        first, report = self.run_import()
        second, repeated = self.run_import()
        self.assertEqual(serialize(first), serialize(second))
        self.assertEqual(serialize(report), serialize(repeated))
        channel = self.source.find('channel')
        records = channel.findall('item')
        for item in records:
            channel.remove(item)
        channel.extend(reversed(records))
        self.assertEqual(serialize(first), serialize(self.run_import(changed=True)[0]))

    def test_final_complete_export_delta_add_change_remove(self):
        before, _ = self.run_import()
        self.item(1).find('wp:status', NS).text = 'draft'
        self.item().find('title').text = 'Updated title'
        bundle, report = self.run_import(changed=True, previous=before)
        self.assertEqual(report['delta'], {'added': [], 'changed': ['wp:101'],
                                           'removed': ['wp:102'], 'unchanged': []})
        fresh, _ = self.run_import(changed=True)
        self.assertEqual(bundle, fresh)
        _, unchanged = self.run_import(previous=before)
        self.assertEqual(unchanged['delta']['unchanged'], ['wp:101', 'wp:102'])

    def test_missing_snapshot_unknown_shortcode_and_block_fail(self):
        self.manifest['items'] = {}
        self.fails('frozen rendered snapshot', changed=False)
        self.item(1).find('content:encoded', NS).text = '<!-- wp:mystery --><p>Something</p><!-- /wp:mystery -->'
        report = self.fails('frozen rendered snapshot')
        self.assertEqual(report['failedRecordCount'], 2)
        self.assertEqual(report['publicRecordCount'], 0)

    def test_hash_bound_snapshot_rejects_raw_or_rendered_changes(self):
        self.item().find('content:encoded', NS).text += ' changed'
        self.fails('stale/tampered snapshot')
        self.manifest['items']['wp:101']['html'] += ' changed'
        self.fails('stale/tampered snapshot', changed=False)

    def test_direct_html_needs_explicit_hash_bound_render_equality_evidence(self):
        del self.manifest['items']['wp:102']
        self.fails('hash-bound directHtmlReference', changed=False)
        self.manifest['items']['wp:102'] = {'originalSha256': '0' * 64,
                                           'directHtmlReference': 'stale-equality-reference'}
        self.fails('hash-bound directHtmlReference', changed=False)

    def test_snapshot_must_be_complete_and_resolved(self):
        entry = self.manifest['items']['wp:101']
        entry['html'] = '[unknown]'
        entry['htmlSha256'] = sha(entry['html'])
        self.fails('still contains an unresolved', changed=False)
        del entry['htmlSha256']
        self.fails('snapshot requires', changed=False)

    def test_conflicting_render_evidence_is_not_silently_ignored(self):
        self.manifest['items']['wp:101']['directHtmlReference'] = 'ambiguous-render-evidence'
        self.fails('choose snapshot or direct HTML equality', changed=False)

    def test_stale_manifest_ids_and_unknown_properties_fail(self):
        self.manifest['items']['wp:99999'] = {}
        self.fails('absent from this complete export', changed=False)
        self.manifest['items']['wp:99999']['silentlyIgnored'] = True
        self.fails('unknown field', changed=False)

    def test_invalid_manifest_types_fail_with_diagnostics(self):
        for manifest in ([], {}, {'schemaVersion': '2.0.0'}):
            with self.assertRaisesRegex(ImportFailure, 'manifest requires'):
                import_wxr(self.data, manifest=manifest)

    def test_unknown_item_structures_and_public_taxonomy_are_actionable(self):
        ET.SubElement(self.item(), '{' + WP + '}mystery').text = 'unknown'
        report = self.fails('unsupported item fields')
        self.assertTrue(report['errors'][0].startswith('wp:101:'))
        self.assertEqual(report['publicRecordCount'], 1)
        self.item().remove(self.item().find('wp:mystery', NS))
        self.item().find('category').set('domain', 'portfolio_category')
        self.fails('unsupported taxonomy portfolio_category')

    def test_public_custom_post_types_and_unknown_status_never_disappear(self):
        self.item(1).find('wp:post_type', NS).text = 'portfolio'
        self.fails('unsupported public post type portfolio')
        self.item(1).find('wp:status', NS).text = 'custom-status'
        self.fails('unsupported publication status custom-status')

    def test_custom_postmeta_requires_explicit_evidence_and_remains_private(self):
        node = ET.SubElement(self.item(), '{' + WP + '}postmeta')
        ET.SubElement(node, '{' + WP + '}meta_key').text = 'custom-template'
        ET.SubElement(node, '{' + WP + '}meta_value').text = 'private-meta-value'
        self.fails('unsupported postmeta')
        self.manifest['items']['wp:101']['reviewedPostMeta'] = {'custom-template': 'reviewed-nonrendered-field-1'}
        bundle, report = self.run_import(changed=True)
        self.assertNotIn('private-meta-value', serialize(bundle))
        self.assertEqual(report['sourceMetadata'][0]['postMeta']['custom-template'], ['private-meta-value'])

    def test_duplicate_ids_paths_singleton_fields_and_term_names_fail(self):
        duplicate = copy.deepcopy(self.item())
        self.source.find('channel').append(duplicate)
        self.fails('duplicate WXR item ID')
        self.source.find('channel').remove(duplicate)
        self.item(1).find('link').text = self.item().find('link').text
        self.fails('duplicate public canonical path')
        self.item(1).find('link').text = 'https://example.invalid/about/'
        ET.SubElement(self.item(), 'title').text = 'Duplicate'
        self.fails('duplicate field title')

    def test_duplicate_canonical_field_diagnostic_does_not_stop_other_records(self):
        ET.SubElement(self.item(), 'link').text = 'https://example.invalid/duplicate/'
        report = self.fails('duplicate field link')
        self.assertEqual(report['failedRecordCount'], 1)
        self.assertEqual(report['publicRecordCount'], 1)
        self.assertEqual(len(report['records']), 5)
        self.assertEqual(report['unresolvedRecords'][0]['sourceId'], 'wp:101')

    def test_encoded_traversal_query_credentials_and_absolute_paths_rejected(self):
        for suffix in ('/%2e%2e/secret/', '/safe?query=1', '//evil/', '/safe%5csecret/', '/bad%00path/'):
            self.item(1).find('link').text = 'https://example.invalid' + suffix
            self.fails('unsafe')
        self.item(1).find('link').text = 'https://secret@example.invalid/about/'
        self.fails('without credentials')

    def test_original_percent_encoded_slug_and_anchor_not_normalized(self):
        self.item(1).find('link').text = 'https://example.invalid/caf%C3%A9/'
        bundle, _ = self.run_import(changed=True)
        self.assertEqual(bundle['items'][1]['path'], '/caf%C3%A9/')
        self.assertIn('/about/#biography', bundle['items'][0]['content']['html'])

    def test_attachments_must_resolve_and_are_delegated_without_fabricated_bytes(self):
        self.source.find('channel').remove(self.item(2))
        self.fails('unresolved attachment IDs: wp:900')
        assets = json.loads((ROOT / 'fixtures/v1/assets.json').read_text())
        bundle, _ = self.run_import(changed=True, assets=assets)
        self.assertEqual(bundle['items'][0]['assetIds'], ['wp:900'])

    def test_safe_comment_html_retained_unsafe_markup_and_cycles_fail(self):
        comment = self.item().find('wp:comment', NS)
        for html in ('<script>alert(1)</script>', '<a href="jav&#x61;script:alert(1)">x</a>',
                     '<a href="java\nscript:alert(1)">x</a>', '<p onclick="x">bad</p>'):
            comment.find('wp:comment_content', NS).text = html
            self.fails('unsafe')
        comment.find('wp:comment_content', NS).text = '<p>Safe <a href="https://example.invalid/">link</a>.</p>'
        self.assertIn('Safe <a', self.run_import(changed=True)[0]['items'][0]['comments'][0]['html'])
        comment.find('wp:comment_parent', NS).text = '1'
        self.fails('comment parent cycle')

    def test_approved_comment_missing_public_parent_fails(self):
        self.item().find('wp:comment/wp:comment_parent', NS).text = '2'
        self.fails('parent is absent or not public')

    def test_xml_entities_unsupported_versions_and_child_xml_fail(self):
        with self.assertRaises(ImportFailure) as caught:
            import_wxr(b'<!DOCTYPE rss [<!ENTITY x "private">]><rss/>')
        self.assertIn('DTD/entity', str(caught.exception))
        self.source.find('channel/wp:wxr_version', NS).text = '1.1'
        self.fails('WXR 1.2')
        self.source.find('channel/wp:wxr_version', NS).text = '1.2'
        ET.SubElement(self.item(1).find('content:encoded', NS), 'div').text = 'invalid raw child XML'
        self.fails('not child XML')

    def test_private_source_metadata_preserves_noncontract_fields_and_flags_behavior(self):
        self.item(1).find('wp:menu_order', NS).text = '2'
        bundle, report = self.run_import(changed=True)
        self.assertEqual(report['sourceMetadata'][1]['slug'], 'about')
        self.assertEqual(report['unresolvedBehavior'], [{'sourceId': 'wp:102', 'field': 'menuOrder', 'value': '2'}])
        self.assertNotIn('menuOrder', serialize(bundle))

    def test_cli_outputs_private_deterministic_files_and_reports_failure_atomically(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wxr = root / 'source.xml'
            wxr.write_bytes(self.data)
            manifest = root / 'manifest.json'
            manifest.write_text(serialize(self.manifest))
            output = root / 'output'
            args = [str(wxr), str(output), '--manifest', str(manifest)]
            self.assertEqual(main(args), 0)
            before = (output / 'content.json').read_bytes()
            self.assertEqual(main(args), 0)
            self.assertEqual(before, (output / 'content.json').read_bytes())
            report = json.loads((output / 'private-report.json').read_text())
            self.assertEqual(report['contentBundleSha256'], hashlib.sha256(before).hexdigest())
            self.assertEqual((output / 'private-report.json').stat().st_mode & 0o777, 0o600)
            self.assertEqual(output.stat().st_mode & 0o777, 0o700)
            self.assertEqual(main([str(wxr), str(output)]), 1)
            self.assertEqual(before, (output / 'content.json').read_bytes())
            self.assertTrue((output / 'failure-report.json').exists())
            self.assertEqual(main(args), 0)
            self.assertFalse((output / 'failure-report.json').exists())

    def test_cli_repository_and_symlink_output_guards(self):
        with self.assertRaisesRegex(ValueError, 'outside every Git checkout'):
            private_directory(ROOT / 'private-export' / 'accidental-import')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'content.json').symlink_to(ROOT / 'README.md')
            with self.assertRaisesRegex(ValueError, 'symlinks'):
                private_directory(root)
            alias = root / 'repo-alias'
            alias.symlink_to(ROOT, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'outside every Git checkout'):
                private_directory(alias / 'hidden')

    def test_module_cli_can_be_called_without_python_path_overrides(self):
        completed = subprocess.run([sys.executable, '-m', 'scripts.import_content', '--help'],
                                   cwd=ROOT, capture_output=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(b'complete WXR', completed.stdout)


if __name__ == '__main__':
    unittest.main()
