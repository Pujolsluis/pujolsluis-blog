"""Read-only backup size, top-file and exact-duplicate inventory.

Requires Pillow only for image metadata; no source image is encoded or modified.
An existing private backup manifest supplies WordPress original/derivative evidence.
"""

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path

from scripts.inventory.backup import inventory_tree


def image_metadata(path):
    try:
        from PIL import Image
    except ImportError:
        return {'imageProbeAvailable': False, 'reason': 'Pillow unavailable'}
    try:
        with Image.open(path) as image:
            result = {'imageProbeAvailable': True, 'format': image.format, 'width': image.width,
                      'height': image.height, 'mode': image.mode,
                      'frames': getattr(image, 'n_frames', 1), 'animated': getattr(image, 'is_animated', False),
                      'iccProfilePresent': bool(image.info.get('icc_profile')),
                      'exifPresent': bool(image.info.get('exif'))}
            if result['animated']:
                result['loop'] = image.info.get('loop')
                durations = []
                for frame in range(result['frames']):
                    image.seek(frame)
                    durations.append(image.info.get('duration', 0))
                result.update(durationMs=sum(durations), minimumFrameMs=min(durations), maximumFrameMs=max(durations))
            return result
    except Exception as error:
        return {'imageProbeAvailable': False, 'reason': type(error).__name__}


def file_size_report(backup, manifest, limit=30):
    backup = backup.resolve()
    if not backup.is_dir():
        raise ValueError('Backup directory does not exist')
    try:
        import PIL
        pillow_version = PIL.__version__
    except ImportError:
        pillow_version = None
    files, skipped = inventory_tree(backup)
    sets = {key: set(paths) for key, paths in manifest['sets'].items()}
    ranked = sorted(files.items(), key=lambda pair: (-pair[1]['bytes'], pair[0]))
    top = []
    by_type, by_area, by_hash = defaultdict(lambda: {'files': 0, 'bytes': 0}), defaultdict(lambda: {'files': 0, 'bytes': 0}), defaultdict(list)
    for name, information in files.items():
        for group, key in ((by_type, information['extension']), (by_area, name.split('/')[0] if '/' in name else 'top-level')):
            group[key]['files'] += 1
            group[key]['bytes'] += information['bytes']
        by_hash[information['sha256']].append(name)
    for position, (name, information) in enumerate(ranked[:limit], 1):
        upload = name[len('uploads/'):] if name.startswith('uploads/') else None
        labels = [label for key, label in (('originals', 'attachment-main-or-original-image'),
                  ('derivatives', 'metadata-generated-size'), ('backups', 'metadata-image-edit-backup'),
                  ('references', 'observed-public-reference')) if upload in sets[key]]
        row = {'rank': position, 'path': name, **information, 'MiB': round(information['bytes'] / 1024 ** 2, 4),
               'wordpressEvidence': labels or ['not-classified-by-attachment-metadata'],
               'identicalBackupPaths': sorted(by_hash[information['sha256']]),
               'image': image_metadata(backup / name)}
        top.append(row)
    duplicates = []
    for checksum, names in by_hash.items():
        if len(names) > 1:
            size = files[names[0]]['bytes']
            duplicates.append({'sha256': checksum, 'bytesPerFile': size, 'copies': len(names),
                               'repeatedBytes': size * (len(names) - 1), 'paths': sorted(names)})
    duplicates.sort(key=lambda row: (-row['repeatedBytes'], row['sha256']))
    total = sum(row['bytes'] for row in files.values())
    return {'schemaVersion': '1.0.0', 'capturedAt': datetime.now(timezone.utc).isoformat(),
            'scope': 'entire owner backup, including uploads/themes/top-level XML',
            'tool': {'pythonImageLibrary': 'Pillow', 'pillowVersion': pillow_version, 'readOnly': True},
            'totals': {'files': len(files), 'bytes': total, 'MiB': round(total / 1024 ** 2, 4),
                       'symlinksSkipped': len(skipped), 'byArea': dict(by_area),
                       'byExtension': dict(sorted(by_type.items(), key=lambda pair: -pair[1]['bytes'])),
                       'duplicateGroups': len(duplicates), 'repeatedBytes': sum(row['repeatedBytes'] for row in duplicates),
                       'distinctContentBytes': total - sum(row['repeatedBytes'] for row in duplicates),
                       'topFilesBytes': sum(row['bytes'] for row in top)},
            'topFiles': top, 'topDuplicateGroups': duplicates[:15],
            'limitations': ['Only file metadata and hashes are reported; no XML contents, EXIF/GPS values, media bytes or licensed theme implementation are retained.',
                            'Original/derivative labels come from owner WXR metadata; an unclassified image is not assumed disposable.',
                            'Duplicate hashes identify equal bytes, not permission to remove URLs or files.',
                            'Compression savings require measured experiments; file size and dimensions alone do not establish safe savings.',
                            'All source files remain unchanged. Recovered case-sensitive media is in a separate owner directory and is not added to backup totals.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--private-manifest', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--limit', type=int, default=30)
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error('limit must be between 1 and 100')
    backup, output = args.backup.resolve(), args.report.resolve()
    if output == backup or backup in output.parents:
        parser.error('Report must be outside the immutable backup')
    manifest = json.loads(args.private_manifest.read_text(encoding='utf-8'))
    report = file_size_report(backup, manifest, args.limit)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'files': report['totals']['files'], 'bytes': report['totals']['bytes'],
                      'topFilesBytes': report['totals']['topFilesBytes'], 'repeatedBytes': report['totals']['repeatedBytes']}, indent=2))


if __name__ == '__main__':
    main()
