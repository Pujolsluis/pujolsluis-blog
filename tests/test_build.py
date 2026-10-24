"""Safety gates for the temporary Pages deployment, not migration validation."""
import tempfile
import unittest
from pathlib import Path

from scripts.build import build


class BuildTests(unittest.TestCase):
    def test_preview_is_non_indexable_and_does_not_claim_domain(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            build(destination)
            html = (destination / 'index.html').read_text()
            self.assertIn('name="robots" content="noindex, nofollow"', html)
            self.assertIn('https://www.pujolsluis.com/', html)
            self.assertIn('Disallow: /', (destination / 'robots.txt').read_text())
            self.assertFalse((destination / 'CNAME').exists())
            self.assertFalse((destination / 'sitemap.xml').exists())
            self.assertEqual(
                {p.name for p in destination.iterdir()},
                {'index.html', 'robots.txt', '.nojekyll'},
            )
