import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.inventory.measure import measure


class CheckpointTests(unittest.TestCase):
    def test_shared_cdn_origins_are_measured_once_and_resumable(self):
        origin = 'https://example.com/wp-content/uploads/image.jpg'
        asset = {'wordpressUpload': True, 'uploadOriginCandidate': origin}
        report = {'source': 'https://example.com/', 'robots': 'User-agent: *\nAllow: /',
                  'assets': [{**asset, 'url': origin}, {**asset, 'url': 'https://i0.wp.com/example.com/wp-content/uploads/image.jpg?resize=20,20'}],
                  'counts': {}, 'responses': [], 'errors': []}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'observations.json'
            path.write_text(json.dumps(report))
            with patch('scripts.inventory.measure.Capture.fetch', return_value=(b'', {'content-length': '123', 'content-type': 'image/jpeg'})) as fetch:
                self.assertEqual(measure(path, 1), 1)
                self.assertEqual(measure(path, 1), 0)
                fetch.assert_called_once_with(origin, 'HEAD')
            saved = json.loads(path.read_text())
            self.assertEqual(saved['counts']['measuredUploadBytes'], 123)
            self.assertEqual(saved['counts']['unknownUploadOriginBytes'], 0)
            self.assertTrue(all(entry['headAttempted'] for entry in saved['assets']))

    def test_interruption_keeps_previous_url_checkpoint(self):
        assets = [{'url': f'https://example.com/wp-content/uploads/{n}.jpg',
                   'uploadOriginCandidate': f'https://example.com/wp-content/uploads/{n}.jpg',
                   'wordpressUpload': True} for n in (1, 2)]
        report = {'source': 'https://example.com/', 'robots': 'User-agent: *\nAllow: /',
                  'assets': assets, 'counts': {}, 'responses': [], 'errors': []}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'observations.json'
            path.write_text(json.dumps(report))
            with patch('scripts.inventory.measure.Capture.fetch', side_effect=[(b'', {'content-length': '123'}), KeyboardInterrupt]):
                with self.assertRaises(KeyboardInterrupt):
                    measure(path, 2)
            saved = json.loads(path.read_text())
            self.assertTrue(saved['assets'][0]['headAttempted'])
            self.assertNotIn('headAttempted', saved['assets'][1])
            self.assertEqual(saved['counts']['unknownUploadOriginBytes'], 1)


if __name__ == '__main__':
    unittest.main()
