"""Build the temporary, non-indexable project landing page."""
from pathlib import Path

HTML = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>pujolsluis.com migration preview</title></head>
<body><main><h1>pujolsluis.com migration preview</h1>
<p>The migration is being prepared. This is not the migrated blog.</p>
<p><a href="https://www.pujolsluis.com/">Read the current blog</a></p>
</main></body></html>
'''


def build(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'index.html').write_text(HTML, encoding='utf-8')
    (destination / '.nojekyll').touch()
    (destination / 'robots.txt').write_text('User-agent: *\nDisallow: /\n')


if __name__ == '__main__':
    build(Path('dist'))
