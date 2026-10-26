"""A real Hugo build must render Markdown posts and exact public paths."""

import copy
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
            (site / 'layouts/shortcodes').mkdir(parents=True)
            (site / 'layouts/_default/single.html').write_text(
                '<!doctype html><title>{{ .Title }}</title><main>{{ .Content }}</main>',
                encoding='utf-8')
            (site / 'layouts/_default/list.html').write_text(
                '<!doctype html><title>{{ .Title }}</title><main>{{ .Content }}</main>',
                encoding='utf-8')
            (site / 'hugo.toml').write_text(
                "baseURL = 'https://example.invalid/project/'\n"
                "disableKinds = ['taxonomy', 'term', 'RSS', 'sitemap']\n"
                "[security]\nallowContent = ['text/html', 'text/markdown']\n"
                "[markup.goldmark.renderer]\nunsafe = true\n", encoding='utf-8')
            (site / 'layouts/shortcodes/figure.html').write_text(
                '<figure><img src="{{ .Get "src" }}" alt="{{ .Get "alt" }}">'
                '{{ with .Inner }}<figcaption>{{ . | markdownify }}</figcaption>{{ end }}</figure>',
                encoding='utf-8')
            (site / 'layouts/shortcodes/youtube.html').write_text(
                '<iframe src="https://www.youtube-nocookie.com/embed/{{ .Get "id" }}" '
                'title="{{ .Get "title" }}"></iframe>', encoding='utf-8')
            report = write_hugo(BUNDLE, site / 'content/imported', '2026-10-24T12:00:00-07:00')
            result = subprocess.run(['hugo', '--source', str(site), '--destination', str(site / 'public')],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            for row in report['items']:
                output = site / 'public' / row['path'].lstrip('/') / 'index.html'
                self.assertTrue(output.is_file(), row['path'])
            post = (site / 'public/2020/01/02/fixture-post/index.html').read_text()
            self.assertIn('<strong>formatting</strong>', post)
            self.assertIn('if x &lt; 2:', post)
            self.assertIn('/about/#biography', post)
            self.assertIn('/media/example.svg', post)
            self.assertIn('youtube-nocookie.com/embed/fixture-video', post)
            self.assertIn('id="unicode"', post)

    def test_authored_section_root_overrides_generated_list_page(self):
        bundle = copy.deepcopy(BUNDLE)
        page = bundle['items'][1]
        page['path'] = '/post/'
        page['canonicalUrl'] = 'https://example.invalid/post/'
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary)
            (site / 'layouts/_default').mkdir(parents=True)
            (site / 'layouts/shortcodes').mkdir(parents=True)
            (site / 'layouts/_default/single.html').write_text('{{ .Content }}')
            (site / 'layouts/_default/list.html').write_text(
                '<title>{{ .Title }}</title><main>{{ .Content }}</main>')
            for shortcode in ('figure.html', 'youtube.html', 'gallery.html', 'gist.html'):
                (site / 'layouts/shortcodes' / shortcode).write_text(
                    (ROOT / 'layouts/shortcodes' / shortcode).read_text(encoding='utf-8'),
                    encoding='utf-8')
            (site / 'hugo.toml').write_text(
                "baseURL = 'https://example.invalid/project/'\n"
                "[security]\nallowContent = ['text/html', 'text/markdown']\n"
                "[markup.goldmark.renderer]\nunsafe = true\n", encoding='utf-8')
            report = write_hugo(bundle, site / 'content/imported', '2026-10-24T12:00:00-07:00')
            self.assertIn('post/_index.html', {row['file'] for row in report['items']})
            result = subprocess.run(['hugo', '--source', str(site), '--destination', str(site / 'public')],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = (site / 'public/post/index.html').read_text()
            self.assertIn('<title>' + page['title'] + '</title>', output)
            self.assertIn(page['content']['html'], output)


if __name__ == '__main__':
    unittest.main()
