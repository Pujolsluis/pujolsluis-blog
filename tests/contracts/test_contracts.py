"""Check fixtures and ensure malformed migration data fails closed."""
import copy
import hashlib
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from docs.contracts.validate import ContractError, SCHEMAS, load_bundle, validate_bundle

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'fixtures' / 'v1'


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.documents = copy.deepcopy(load_bundle(FIXTURES))

    def invalid(self):
        with self.assertRaises(ContractError):
            validate_bundle(*self.documents)

    def test_schemas_are_valid_and_fixture_media_matches_manifest(self):
        for path in SCHEMAS.glob('*.schema.json'):
            Draft202012Validator.check_schema(json.loads(path.read_text()))
        for asset in self.documents[1]['assets']:
            data = (FIXTURES / asset['localPath']).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), asset['sha256'])
            self.assertEqual(len(data), asset['bytes'])

    def test_unknown_fields_and_versions_are_rejected(self):
        self.documents[0]['privateEmail'] = 'must-never-be-public@example.invalid'
        self.invalid()
        del self.documents[0]['privateEmail']
        self.documents[0]['schemaVersion'] = '2.0.0'
        self.invalid()

    def test_unknown_status_and_dates_without_timezone_are_rejected(self):
        item = self.documents[0]['items'][0]
        item['status'] = 'deleted'
        self.invalid()
        item['status'] = 'publish'
        item['publishedAt'] = '2020-01-02T03:04:05'
        self.invalid()

    def test_unsafe_paths_are_rejected(self):
        for path in ('../secret', '/../../secret', '/safe?query=1', '//external/path'):
            self.documents[0]['items'][0]['path'] = path
            self.invalid()
        self.documents = copy.deepcopy(load_bundle(FIXTURES))
        self.documents[1]['assets'][0]['localPath'] = '../secret'
        self.invalid()

    def test_duplicate_ids_and_paths_are_rejected(self):
        self.documents[0]['items'].append(copy.deepcopy(self.documents[0]['items'][0]))
        self.invalid()
        self.documents = copy.deepcopy(load_bundle(FIXTURES))
        self.documents[2]['routes'].append(copy.deepcopy(self.documents[2]['routes'][0]))
        self.invalid()

    def test_missing_asset_content_and_route_targets_are_rejected(self):
        self.documents[0]['items'][0]['assetIds'] = ['wp:missing']
        self.invalid()
        self.documents = copy.deepcopy(load_bundle(FIXTURES))
        self.documents[2]['routes'][0]['contentId'] = 'wp:missing'
        self.invalid()
        self.documents = copy.deepcopy(load_bundle(FIXTURES))
        self.documents[2]['routes'][-1]['target'] = '/missing/'
        self.invalid()

    def test_every_item_requires_a_route_and_matching_canonical(self):
        self.documents[2]['routes'] = self.documents[2]['routes'][1:]
        self.invalid()
        self.documents = copy.deepcopy(load_bundle(FIXTURES))
        self.documents[0]['items'][0]['canonicalUrl'] = 'https://example.invalid/different/'
        self.invalid()

    def test_synthetic_fixture_preserves_rich_content_cases(self):
        content = self.documents[0]['items'][0]['content']
        for value in ('日本語', 'Café', '👋', '<pre><code>', '    print(', '<iframe', 'gallery'):
            self.assertIn(value, content['html'])
        self.assertIn('[notice]', content['original'])
        self.assertIn('[gallery ids="900"]', content['original'])
        self.assertNotIn('[notice]', content['html'])

    def test_provenance_hashes_are_verified_against_exact_utf8(self):
        for field in ('html', 'original'):
            self.documents = copy.deepcopy(load_bundle(FIXTURES))
            self.documents[0]['items'][0]['content'][field] += ' modified'
            self.invalid()

    def test_public_metadata_references_and_comment_privacy(self):
        self.documents[0]['items'][0]['sourceMetadata']['featuredAssetId'] = 'wp:missing'
        self.invalid()
        self.documents = copy.deepcopy(load_bundle(FIXTURES))
        self.documents[0]['items'][0]['comments'][0]['authorEmail'] = 'private@example.invalid'
        self.invalid()
        self.documents = copy.deepcopy(load_bundle(FIXTURES))
        self.documents[0]['items'][0]['comments'][0]['parentId'] = 'wp-comment:missing'
        self.invalid()
