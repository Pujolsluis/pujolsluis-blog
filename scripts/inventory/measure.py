"""Resume a bounded set of upload HEAD measurements with a checkpoint per URL.

Run after capture: python -m scripts.inventory.measure migration/inventory/public/observations.json --limit 50
This measures referenced URLs (including resized variants), never an originals archive.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from scripts.inventory.capture import Capture


def update_counts(report):
    uploads = [entry for entry in report['assets'] if entry['wordpressUpload']]
    measured = [entry for entry in uploads if entry.get('bytes') is not None]
    report['counts'].update(measuredUploadUrls=len(measured),
                            unknownUploadBytesUrls=len(uploads) - len(measured),
                            measuredUploadBytes=sum({entry['uploadOriginCandidate']: entry['bytes'] for entry in measured}.values()),
                            uploadOriginCandidates=len({entry['uploadOriginCandidate'] for entry in uploads}),
                            unknownUploadOriginBytes=len({entry['uploadOriginCandidate'] for entry in uploads} - {entry['uploadOriginCandidate'] for entry in measured}))


def measure(path, limit):
    report = json.loads(path.read_text(encoding='utf-8'))
    capture = Capture(report['source'])
    capture.robots.parse(report['robots'].splitlines())
    capture.robots_ready = True
    attempted = 0
    for entry in report['assets']:
        if not entry['wordpressUpload'] or entry.get('headAttempted'):
            continue
        if attempted >= limit:
            break
        origin = entry['uploadOriginCandidate']
        _, headers = capture.fetch(origin, 'HEAD')
        length = headers.get('content-length', '')
        entry.update(headAttempted=True, contentType=headers.get('content-type'),
                     bytes=int(length) if length.isdigit() else None,
                     measuredAt=datetime.now(timezone.utc).isoformat())
        for alias in report['assets']:
            if alias.get('uploadOriginCandidate') == origin:
                alias.update({key: entry[key] for key in ('headAttempted', 'contentType', 'bytes', 'measuredAt')})
        report['responses'].extend(capture.responses)
        report['errors'].extend(capture.errors)
        capture.responses.clear()
        capture.errors.clear()
        attempted += 1
        update_counts(report)
        # Atomic replacement keeps an interrupted acquisition's last complete checkpoint.
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.replace(path)
    return attempted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inventory', type=Path)
    parser.add_argument('--limit', type=int, default=50)
    args = parser.parse_args()
    if args.limit < 1:
        parser.error('limit must be positive')
    print(f'Measured {measure(args.inventory, args.limit)} upload URLs; report checkpointed.')


if __name__ == '__main__':
    main()
