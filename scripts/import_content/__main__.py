"""Import a complete owner WXR export into a private working directory."""

import argparse
import json
import os
import tempfile
from pathlib import Path

from .importer import ImportFailure, import_wxr, serialize
from .routes import routes_from_content


def private_directory(raw):
    path = raw.resolve()
    for ancestor in (path, *path.parents):
        if (ancestor / '.git').exists():
            raise ValueError('output must be outside every Git checkout; report includes private source metadata')
    if path.exists():
        if not path.is_dir() or path.stat().st_mode & 0o077:
            raise ValueError('existing output must be a dedicated private directory (chmod 700)')
    else:
        path.mkdir(mode=0o700, parents=True)
    for name in ('content.json', 'routes.json', 'private-report.json', 'failure-report.json'):
        if (path / name).is_symlink():
            raise ValueError('output files must not be symlinks')
    return path


def atomic_write(path, document):
    descriptor, temporary = tempfile.mkstemp(prefix='.import-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(serialize(document))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wxr', type=Path, help='complete WXR 1.2 export (not a partial incremental export)')
    parser.add_argument('output', type=Path, help='private directory outside Git checkouts')
    parser.add_argument('--manifest', type=Path, help='reviewed snapshot/metadata evidence manifest')
    parser.add_argument('--assets', type=Path, help='v1 assets.json for attachment reference resolution')
    parser.add_argument('--previous', type=Path, help='earlier content.json, for final full-export delta report')
    args = parser.parse_args(argv)
    try:
        output = private_directory(args.output)
        options = {name: json.loads(getattr(args, name).read_text(encoding='utf-8'))
                   for name in ('manifest', 'assets', 'previous') if getattr(args, name)}
        bundle, report = import_wxr(args.wxr.read_bytes(), **options)
        try:
            routes = routes_from_content(bundle)
        except ValueError as error:
            report['errors'].append(f'content route reconciliation: {error}')
            raise ImportFailure(report['errors'], report) from error
        # Individual files are atomic. The report hashes the completed bundle so
        # consumers can detect interrupted writes instead of using a mixed pair.
        import hashlib
        report['contentBundleSha256'] = hashlib.sha256(serialize(bundle).encode('utf-8')).hexdigest()
        report['routesBundleSha256'] = hashlib.sha256(serialize(routes).encode('utf-8')).hexdigest()
        atomic_write(output / 'content.json', bundle)
        atomic_write(output / 'routes.json', routes)
        atomic_write(output / 'private-report.json', report)
        (output / 'failure-report.json').unlink(missing_ok=True)
        print(f'Imported {len(bundle["items"])} published records. Source completeness remains unverified.')
        return 0
    except ImportFailure as error:
        atomic_write(output / 'failure-report.json', error.report)
        print(f'Import failed: {len(error.errors)} diagnostic(s); inspect the private failure-report.json. Previous content was not updated.')
        return 1
    except (ValueError, OSError) as error:
        parser.exit(2, f'Import could not run: {error}\n')


if __name__ == '__main__':
    raise SystemExit(main())
