"""A real Hugo build must preserve imported HTML and exact public paths."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.import_content.hugo import write_hugo


ROOT = Path(__file__).resolve().parents[2]
BUNDLE = json.loads((ROOT / 'fixtures/v1/content.json').read_text())


@unittest.skipUnless(shutil.which('hugo'), 'Hugo is not installed in this environment')
class HugoBuildTests(unittest.TestCase):
    def test_materialized_fixture_builds_with_exact_routes_and_body(self):
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary)
            (site / 'layouts/_default').mkdir(parents=True)
            (site / 'layouts/_default/single.html').write_text(
                '<!doctype html><title>{{ .Title }}</title><main>{{ .Content }}</main>',
                encoding='utf-8')
            (site / 'hugo.toml').write_text(
                "baseURL = 'https://example.invalid/project/'\n"
                "disableKinds = ['taxonomy', 'term', 'RSS', 'sitemap']\n"
                "[security]\nallowContent = ['text/html']\n", encoding='utf-8')
            report = write_hugo(BUNDLE, site / 'content/imported', '2026-10-24T12:00:00-07:00')
            result = subprocess.run(['hugo', '--source', str(site), '--destination', str(site / 'public')],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            for row in report['items']:
                output = site / 'public' / row['path'].lstrip('/') / 'index.html'
                self.assertTrue(output.is_file(), row['path'])
            post = (site / 'public/2020/01/02/fixture-post/index.html').read_text()
            self.assertIn(BUNDLE['items'][0]['content']['html'], post)
            self.assertIn('id="unicode"', post)


if __name__ == '__main__':
    unittest.main()
