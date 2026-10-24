"""Ensure incomplete source evidence cannot look like a complete migration."""
import json
import unittest
from pathlib import Path

from docs.contracts.reconcile import difference, reconcile
from docs.contracts.validate import ContractError, load_bundle

FIXTURES = Path(__file__).resolve().parents[2] / 'fixtures' / 'v1'


class ReconciliationTests(unittest.TestCase):
    def test_absent_baseline_is_unknown_not_zero(self):
        baseline = json.loads((FIXTURES / 'inventory-baseline.json').read_text())
        report = reconcile(baseline, load_bundle(FIXTURES))
        self.assertEqual(report['comparisons']['contentIds']['status'], 'unknown')
        self.assertIsNone(report['media']['expectedBytes'])
        self.assertFalse(report['readyForSourceAudit'])
        self.assertEqual(report['sourceCompleteness'], 'unverified')
        self.assertIn('wxr', report['missingInputs'])

    def test_difference_reports_missing_unexpected_duplicates_and_denominators(self):
        report = difference(['wp:1', 'wp:2', 'wp:2'], ['wp:1', 'wp:3', 'wp:3'])
        self.assertEqual(report, {
            'expectedCount': 3, 'actualCount': 3, 'missing': ['wp:2'],
            'unexpected': ['wp:3'], 'duplicateExpected': ['wp:2'],
            'duplicateActual': ['wp:3'],
        })

    def test_matching_sets_without_frozen_inputs_do_not_pass_gate(self):
        docs = load_bundle(FIXTURES)
        baseline = {
            'schemaVersion': '1.0.0', 'contentIds': [i['sourceId'] for i in docs[0]['items']],
            'assetIds': [i['assetId'] for i in docs[1]['assets']],
            'routeKeys': [i['path'] + ('?' + i['query'] if i['query'] else '')
                          for i in docs[2]['routes']],
            'totalMediaBytes': sum(i['bytes'] for i in docs[1]['assets']),
        }
        report = reconcile(baseline, docs)
        self.assertFalse(report['readyForSourceAudit'])
        self.assertTrue(report['media']['matches'])
        baseline['sourceFrozenAt'] = '2020-01-01T00:00:00Z'
        baseline['inputs'] = dict.fromkeys(
            ('wxr', 'uploads', 'renderedSnapshots', 'themeSettings'), 'synthetic-test-reference'
        )
        report = reconcile(baseline, docs)
        self.assertTrue(report['readyForSourceAudit'])
        self.assertEqual(report['sourceCompleteness'], 'unverified')
        baseline['totalMediaBytes'] += 1
        self.assertFalse(reconcile(baseline, docs)['readyForSourceAudit'])

    def test_invalid_baseline_data_is_rejected(self):
        for baseline in ({'schemaVersion': '2'},
                         {'schemaVersion': '1.0.0', 'contentIds': 'not-a-list'},
                         {'schemaVersion': '1.0.0', 'totalMediaBytes': -1}):
            with self.subTest(baseline=baseline), self.assertRaises(ContractError):
                reconcile(baseline, load_bundle(FIXTURES))
