"""Content route manifest keeps browser-visible fragments and reports duplicate IDs."""

import copy
import json
import unittest
from pathlib import Path

from scripts.import_content.routes import duplicate_anchors_from_content, routes_from_content


FIXTURE = json.loads((Path(__file__).resolve().parents[2] / 'fixtures/v1/content.json').read_text())


class RoutesTests(unittest.TestCase):
    def test_exact_paths_and_rendered_fragments(self):
        document = routes_from_content(FIXTURE)
        self.assertEqual(document['schemaVersion'], '1.0.0')
        self.assertEqual([r['path'] for r in document['routes']],
                         ['/2020/01/02/fixture-post/', '/about/'])
        self.assertEqual(document['routes'][0]['fragments'], ['unicode'])
        self.assertEqual(document['routes'][1]['fragments'], ['biography'])

    def test_duplicate_anchor_reported_and_private_route_fails(self):
        bundle = copy.deepcopy(FIXTURE)
        bundle['items'][0]['content']['html'] += '<a id="unicode"></a>'
        self.assertEqual(routes_from_content(bundle)['routes'][0]['fragments'], ['unicode'])
        self.assertEqual(duplicate_anchors_from_content(bundle),
                         [{'sourceId': 'wp:101', 'duplicateFragments': ['unicode']}])
        bundle = copy.deepcopy(FIXTURE)
        bundle['items'][0]['status'] = 'draft'
        with self.assertRaisesRegex(ValueError, 'nonpublic route'):
            routes_from_content(bundle)


if __name__ == '__main__':
    unittest.main()
