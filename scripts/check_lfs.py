"""Require LFS pointers for binary Git blobs and real bytes in build artifacts."""
import argparse
import hashlib
import re
import subprocess
from pathlib import Path

POINTER_HEADER = b'version https://git-lfs.github.com/spec/v1'
POINTER = re.compile(
    rb'version https://git-lfs.github.com/spec/v1\n'
    rb'oid sha256:([a-f0-9]{64})\nsize (0|[1-9][0-9]*)\n'
)
PAGES_MAX_BYTES = 1_000_000_000
BINARY_SUFFIXES = set('''
.png .jpg .jpeg .gif .webp .avif .ico .bmp .tif .tiff .heic .psd
.woff .woff2 .ttf .otf .eot .mp3 .mp4 .m4a .m4v .mov .webm .ogg .ogv
.opus .wav .flac .aac .avi .pdf .doc .docx .ppt .pptx .xls .xlsx
.zip .gz .tgz .tar .bz2 .xz .7z .rar .bin .exe .dll .so .dylib .wasm
'''.split())


class StorageError(ValueError):
    """Storage policy failed without changing repository or files."""


def binary_content(data):
    """Treat valid UTF-8 without binary controls as text, including textual SVG."""
    try:
        data.decode('utf-8')
    except UnicodeDecodeError:
        return True
    return any(value < 32 and value not in (9, 10, 13) for value in data)


def parse_pointer(data):
    """Accept canonical v1 pointers; fail malformed pointer-like content."""
    if not data.startswith(POINTER_HEADER):
        return None
    match = POINTER.fullmatch(data)
    if match is None:
        raise StorageError('malformed or noncanonical Git LFS pointer')
    return match[1].decode('ascii'), int(match[2])


def git(repository, *args, input_bytes=None):
    result = subprocess.run(
        ['git', '-C', str(repository), *args], input=input_bytes,
        capture_output=True, check=False,
    )
    if result.returncode:
        raise StorageError(f'git {args[0]} failed: {result.stderr.decode().strip()}')
    return result.stdout


def checked_materialized(path, pointer):
    if path.is_symlink() or not path.is_file():
        raise StorageError('LFS content is missing or a symlink; run git lfs pull')
    digest = hashlib.sha256()
    size = 0
    with path.open('rb') as source:
        prefix = source.read(1024)
        if prefix.startswith(POINTER_HEADER):
            raise StorageError('unresolved LFS pointer; install Git LFS and run git lfs pull')
        digest.update(prefix)
        size += len(prefix)
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
            size += len(chunk)
    if (digest.hexdigest(), size) != pointer:
        raise StorageError('materialized LFS bytes differ from pointer SHA-256/size')


def check_repository(repository, history=False, materialized=True):
    repository = Path(git(repository, 'rev-parse', '--show-toplevel').decode().strip())
    records = []
    for record in git(repository, 'ls-files', '--stage', '-z').split(b'\0'):
        if not record:
            continue
        metadata, filename = record.split(b'\t', 1)
        mode, oid, stage = metadata.decode().split()
        if stage != '0':
            raise StorageError('resolve index conflicts before storage validation')
        records.append((filename.decode('utf-8'), oid, mode))
    filenames = b''.join(name.encode('utf-8') + b'\0' for name, _, _ in records)
    attributes = git(repository, 'check-attr', '--cached', '-z', '--stdin',
                     'filter', 'diff', 'merge', 'text', input_bytes=filenames).split(b'\0')
    attrs = {}
    for index in range(0, len(attributes) - 1, 3):
        name, key, value = (item.decode() for item in attributes[index:index + 3])
        attrs.setdefault(name, {})[key] = value
    errors, cache = [], {}
    pointer_count = 0

    def blob(oid):
        if oid not in cache:
            cache[oid] = git(repository, 'cat-file', 'blob', oid)
        return cache[oid]

    for filename, oid, mode in records:
        try:
            data = blob(oid)
            pointer = parse_pointer(data)
            if pointer is None:
                if binary_content(data) or Path(filename).suffix.lower() in BINARY_SUFFIXES:
                    raise StorageError('ordinary binary Git blob; install Git LFS and track this path before adding')
                if attrs[filename]['filter'] == 'lfs':
                    raise StorageError('LFS-tracked path contains a non-pointer Git blob')
            else:
                pointer_count += 1
                expected = {'filter': 'lfs', 'diff': 'lfs', 'merge': 'lfs', 'text': 'unset'}
                if attrs[filename] != expected or mode not in ('100644', '100755'):
                    raise StorageError('LFS pointer needs filter=lfs diff=lfs merge=lfs -text on a regular file')
                if materialized:
                    checked_materialized(repository / filename, pointer)
        except StorageError as error:
            errors.append(f'{filename}: {error}')
    historical_blobs = 0
    if history:
        # Scan HEAD ancestry, including binary blobs deleted later in a PR.
        # CI fetch-depth:0 is necessary; shallow history cannot prove this gate.
        if git(repository, 'rev-parse', '--is-shallow-repository').strip() == b'true':
            errors.append('history validation requires a full fetch (fetch-depth: 0)')
        else:
            for record in git(repository, 'rev-list', '--objects', 'HEAD').decode().splitlines():
                oid, _, filename = record.partition(' ')
                if git(repository, 'cat-file', '-t', oid).strip() != b'blob':
                    continue
                historical_blobs += 1
                try:
                    data = blob(oid)
                    pointer = parse_pointer(data)
                    if pointer is None and (binary_content(data) or Path(filename).suffix.lower() in BINARY_SUFFIXES):
                        raise StorageError('ordinary binary in reachable history; report migration plan before rewriting')
                except StorageError as error:
                    errors.append(f'{filename} ({oid}): {error}')
    if errors:
        raise StorageError('\n'.join(errors))
    return {'trackedFiles': len(records), 'lfsPointers': pointer_count,
            'historicalBlobs': historical_blobs}


def check_artifact(directory, max_bytes=PAGES_MAX_BYTES):
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise StorageError('artifact must be an existing real directory')
    total, count = 0, 0
    for path in directory.rglob('*'):
        if path.is_symlink():
            raise StorageError(f'{path.relative_to(directory)}: artifact symlink is not permitted')
        if path.is_dir():
            continue
        if not path.is_file():
            raise StorageError(f'{path.relative_to(directory)}: artifact contains a nonregular file')
        with path.open('rb') as source:
            if source.read(1024).startswith(POINTER_HEADER):
                raise StorageError(f'{path.relative_to(directory)}: unresolved LFS pointer in artifact')
        count += 1
        total += path.stat().st_size
        if total > max_bytes:
            raise StorageError(f'artifact exceeds {max_bytes} byte output limit; LFS does not increase Pages capacity')
    return {'files': count, 'bytes': total}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, default=Path('.'))
    parser.add_argument('--history', action='store_true')
    parser.add_argument('--no-materialized', action='store_true',
                        help='check stored pointers only; not sufficient for build/deploy')
    parser.add_argument('--artifact', type=Path,
                        help='check output bytes instead of repository storage')
    args = parser.parse_args()
    try:
        result = (check_artifact(args.artifact) if args.artifact else
                  check_repository(args.repository, args.history, not args.no_materialized))
    except (StorageError, OSError) as error:
        parser.exit(1, f'Storage policy failed: {error}\n')
    print(f'Storage policy passed: {result}')


if __name__ == '__main__':
    main()
