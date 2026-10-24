"""Use disposable repositories; never commit binary fixture files here."""
import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.check_lfs import (
    StorageError, binary_content, check_artifact, check_repository, parse_pointer,
)

ATTRIBUTES = Path(__file__).resolve().parents[2] / '.gitattributes'
BINARY = b'\x89PNG\r\n\x1a\n\0synthetic-test-bytes'


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Storage test')
        self.git('config', 'user.email', 'storage@example.invalid')
        # Identity filters simulate a Git pointer index independently of the
        # optional installed LFS CLI; production CI uses actual Git LFS checkout.
        self.git('config', 'filter.lfs.clean', 'cat')
        self.git('config', 'filter.lfs.smudge', 'cat')
        self.git('config', 'filter.lfs.process', '')
        self.git('config', 'filter.lfs.required', 'false')
        (self.root / '.gitattributes').write_bytes(ATTRIBUTES.read_bytes())
        self.git('add', '.gitattributes')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args],
                              check=True, capture_output=True)

    def pointer(self, data=BINARY):
        return (f'version https://git-lfs.github.com/spec/v1\n'
                f'oid sha256:{hashlib.sha256(data).hexdigest()}\n'
                f'size {len(data)}\n').encode()

    def stage(self, name, data):
        path = self.root / name
        path.write_bytes(data)
        self.git('add', '--', name)
        return path

    def test_unicode_svg_remains_text_but_unknown_binary_is_detected(self):
        self.assertFalse(binary_content('<svg>café 日本語</svg>'.encode()))
        self.assertTrue(binary_content(BINARY))
        self.stage('fixture.svg', '<svg>café</svg>'.encode())
        check_repository(self.root)
        self.stage('unrecognized.dat', BINARY)
        with self.assertRaisesRegex(StorageError, 'ordinary binary Git blob'):
            check_repository(self.root)

    def test_uppercase_binary_extensions_require_pointers_even_for_ascii(self):
        self.stage('IMAGE.PNG', b'not a pointer')
        with self.assertRaisesRegex(StorageError, 'ordinary binary Git blob'):
            check_repository(self.root)

    def test_pointer_requires_attributes_and_materialized_matching_bytes(self):
        path = self.stage('image.png', self.pointer())
        with self.assertRaisesRegex(StorageError, 'unresolved LFS pointer'):
            check_repository(self.root)
        path.write_bytes(BINARY)
        result = check_repository(self.root)
        self.assertEqual(result['lfsPointers'], 1)
        path.write_bytes(BINARY + b'corrupt')
        with self.assertRaisesRegex(StorageError, 'differ from pointer'):
            check_repository(self.root)
        self.stage('undeclared.dat', self.pointer())
        with self.assertRaisesRegex(StorageError, 'needs filter=lfs'):
            check_repository(self.root)

    def test_pointer_like_payloads_and_lfs_tracked_text_fail(self):
        with self.assertRaisesRegex(StorageError, 'malformed'):
            parse_pointer(b'version https://git-lfs.github.com/spec/v1\ninvalid\n')
        self.stage('misconfigured.svg', b'<svg/>')
        (self.root / '.gitattributes').write_text(
            'misconfigured.svg filter=lfs diff=lfs merge=lfs -text\n')
        self.git('add', '.gitattributes')
        with self.assertRaisesRegex(StorageError, 'non-pointer Git blob'):
            check_repository(self.root)

    def test_deleted_binary_still_fails_reachable_history_gate(self):
        self.stage('historical.dat', BINARY)
        self.git('commit', '-qm', 'Synthetic binary used only in temporary test')
        self.git('rm', 'historical.dat')
        self.git('commit', '-qm', 'Remove temporary binary')
        check_repository(self.root)
        with self.assertRaisesRegex(StorageError, 'ordinary binary in reachable history'):
            check_repository(self.root, history=True)

    def test_build_artifact_requires_bytes_and_enforces_output_limit(self):
        output = self.root / 'dist'
        output.mkdir()
        (output / 'image.png').write_bytes(BINARY)
        self.assertEqual(check_artifact(output)['bytes'], len(BINARY))
        with self.assertRaisesRegex(StorageError, 'output limit'):
            check_artifact(output, max_bytes=len(BINARY) - 1)
        (output / 'image.png').write_bytes(self.pointer())
        with self.assertRaisesRegex(StorageError, 'unresolved LFS pointer'):
            check_artifact(output)
        (output / 'image.png').unlink()
        (output / 'outside').symlink_to(self.root / '.gitattributes')
        with self.assertRaisesRegex(StorageError, 'symlink'):
            check_artifact(output)


if __name__ == '__main__':
    unittest.main()
